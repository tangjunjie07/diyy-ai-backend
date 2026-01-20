from fastapi import APIRouter, UploadFile, File, Depends
from typing import List
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
import json


from auth import verify_token
from services.chat_session_service import chat_session_service

router = APIRouter(prefix="/analyze", tags=["OCR"])


from config import AZURE_ENDPOINT, AZURE_KEY

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
        import logging
        logging.warning(f"OCR confidence抽出失敗: {ce}")
    return None

def normalize_invoice_result(filename: str, analyze_result: object) -> dict:
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
    # ChatSessionの存在チェック・登録（サービス層呼び出し）
    await chat_session_service.ensure_session_exists(userId, difyId)
    # token_payloadはAPI認証用（schema.prismaのUserモデルと連携）
    results = []
    for file in files:
        try:
            content = await file.read()
            poller = client.begin_analyze_document(
                model_id="prebuilt-invoice",
                body=content
            )
            analyze_result = poller.result()
            # OCR成功時のChatFile登録
            chat_file = await chat_session_service.register_chat_file(
                dify_id=difyId,
                tenant_id=tenantId,
                file_name=file.filename,
                file_size=file.size if hasattr(file, "size") else None,
                mime_type=file.content_type if hasattr(file, "content_type") else None,
                status="completed"
            )
            # OcrResultテーブルにも登録（confidence抽出は専用メソッドで）
            confidence = extract_confidence(analyze_result)
            await chat_session_service.register_ocr_result(
                tenant_id=tenantId,
                chat_file_id=chat_file.id if chat_file else None,
                file_name=file.filename,
                ocr_result=json.dumps(analyze_result, ensure_ascii=False),
                confidence=confidence,
                status="completed"
            )
            results.append(
                normalize_invoice_result(
                    filename=file.filename,
                    analyze_result=analyze_result
                )
            )
        except Exception as e:
            # OCR失敗時のChatFile登録のみ
            await chat_session_service.register_chat_file(
                dify_id=difyId,
                tenant_id=tenantId,
                file_name=file.filename,
                file_size=file.size if hasattr(file, "size") else None,
                mime_type=file.content_type if hasattr(file, "content_type") else None,
                error_message=str(e),
                status="failed"
            )
            results.append({
                "filename": file.filename,
                "error": str(e),
                "ocr_content": "",
                "ocr_items": "[]",
                "ocr_data": "{}"
            })
    return {
        "count": len(files),
        "results": results
    }
