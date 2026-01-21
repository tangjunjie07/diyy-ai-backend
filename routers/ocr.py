from fastapi import APIRouter, UploadFile, File, Depends
from typing import List
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
import json
import logging

from auth import verify_token
from services.chat_session_service import chat_session_service
from config import AZURE_ENDPOINT, AZURE_KEY

logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analyze", tags=["OCR"])

client = DocumentIntelligenceClient(
    endpoint=AZURE_ENDPOINT,
    credential=AzureKeyCredential(AZURE_KEY)
)

def extract_ocr_content(result) -> str:
    content = getattr(result, "content", "") or ""
    return content[:3000]

def extract_items(result) -> list:
    items = []
    for table in getattr(result, "tables", []) or []:
        for cell in table.cells:
            items.append({
                "row": cell.row_index,
                "col": cell.column_index,
                "text": cell.content
            })
    return items

def extract_structured_data(result) -> dict:
    documents = getattr(result, "documents", []) or []
    if not documents:
        return {}
    doc = documents[0]
    data = {}
    for key, field in doc.fields.items():
        data[key] = {
            "value": field.content,
            "confidence": field.confidence
        }
    return data

def extract_confidence(analyze_result) -> float:
    """
    OCR結果から信頼度(confidence)を抽出。失敗時はNone。
    """
    try:
        if hasattr(analyze_result, "confidence"):
            return analyze_result.confidence
        elif hasattr(analyze_result, "documents") and analyze_result.documents:
            doc = analyze_result.documents[0]
            return getattr(doc, "confidence", None)
    except Exception as ce:
        logging.warning(f"OCR confidence抽出失敗: {ce}")
    return None

def build_ocr_result_dict(file, ocr_result_obj, chat_file_id=None):
    try:
        ocr_json = json.loads(ocr_result_obj.ocrResult)
        result_dict = normalize_invoice_result(file.filename, ocr_json)
    except Exception:
        result_dict = {
            "filename": file.filename,
            "ocr_content": "",
            "ocr_items": "[]",
            "ocr_data": "{}"
        }
    if chat_file_id:
        result_dict["chat_file_id"] = chat_file_id
    return result_dict

def to_json_safe(obj):
    import dataclasses
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_json_safe(i) for i in obj]
    if hasattr(obj, "__dict__"):
        return {k: to_json_safe(v) for k, v in obj.__dict__.items()}
    return str(obj)

def normalize_invoice_result(filename: str, analyze_result: object) -> dict:

    # chat_file_idはnormalize_invoice_resultでは受け取らないので、呼び出し側で付与する
    return {
        "filename": filename,
        "ocr_content": extract_ocr_content(analyze_result),
        "ocr_items": json.dumps(extract_items(analyze_result), ensure_ascii=False),
        "ocr_data": json.dumps(extract_structured_data(analyze_result), ensure_ascii=False)
    }


@router.post("/invoice")
async def analyze_invoice(
    userId: str = File(...),
    difyId: str = File(...),
    tenantId: str = File(...),
    files: List[UploadFile] = File(...),
    token_payload: dict = Depends(verify_token)
):
    # 必須パラメータチェック
    if not tenantId:
        return {"success": False, "error": "tenantId is required"}
    if not userId:
        return {"success": False, "error": "userId is required"}
    if not difyId:
        return {"success": False, "error": "difyId is required"}
    # ChatSessionの存在チェック・登録（サービス層呼び出し）
    await chat_session_service.ensure_session_exists(userId, difyId)
    # token_payloadはAPI認証用（schema.prismaのUserモデルと連携）
    results = []
    for file in files:
        file_size = file.size if hasattr(file, "size") else None
        try:
            # サービス経由で既存OCR取得
            chat_file, ocr_result = await chat_session_service.get_existing_ocr_result(
                tenant_id=tenantId,
                file_name=file.filename,
                file_size=file_size
            )
            if ocr_result:
                # 既存ヒット時、同一Dify IDなら登録不要
                if chat_file and hasattr(chat_file, "difyId") and chat_file.difyId == difyId:
                    result_dict = build_ocr_result_dict(file, ocr_result, chat_file.id if chat_file and hasattr(chat_file, "id") else None)
                    results.append(result_dict)
                    continue
                # Dify IDが異なる場合のみ新規登録
                chat_file_new = await chat_session_service.register_chat_file_with_ocr_result(
                    dify_id=difyId,
                    tenant_id=tenantId,
                    file_name=file.filename,
                    file_size=file_size,
                    mime_type=file.content_type if hasattr(file, "content_type") else None,
                    ocr_result_str=ocr_result.ocrResult,
                    confidence=ocr_result.confidence,
                    status="completed"
                )
                result_dict = build_ocr_result_dict(file, ocr_result, chat_file_new.id if chat_file_new and hasattr(chat_file_new, "id") else None)
                results.append(result_dict)
                continue
            # 既存がなければOCR実行
            import logging
            logging.info(f"[OCR] Azure実行: file={file.filename}")
            content = await file.read()
            poller = client.begin_analyze_document(
                model_id="prebuilt-invoice",
                body=content
            )
            analyze_result = poller.result()
            confidence = extract_confidence(analyze_result)
            ocr_result_str = json.dumps(
                to_json_safe(analyze_result),
                ensure_ascii=False
            )
            chat_file_new = await chat_session_service.register_chat_file_with_ocr_result(
                dify_id=difyId,
                tenant_id=tenantId,
                file_name=file.filename,
                file_size=file_size,
                mime_type=file.content_type if hasattr(file, "content_type") else None,
                ocr_result_str=ocr_result_str,
                confidence=confidence,
                status="completed"
            )
            result_dict = normalize_invoice_result(
                filename=file.filename,
                analyze_result=analyze_result
            )
            if chat_file_new and hasattr(chat_file_new, "id"):
                result_dict["chat_file_id"] = chat_file_new.id
            results.append(result_dict)
        except Exception as e:
            await chat_session_service.register_chat_file(
                dify_id=difyId,
                tenant_id=tenantId,
                file_name=file.filename,
                file_size=file_size,
                mime_type=file.content_type if hasattr(file, "content_type") else None,
                error_message=str(e),
                status="failed"
            )
            results.append({
                "filename": file.filename,
                "error": str(e),
                "ocr_content": "",
                "ocr_items": "[]",
                "ocr_data": "{}",
                "chat_file_id": None
            })
    return {
        "count": len(files),
        "results": results
    }
