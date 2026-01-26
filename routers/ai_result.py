from fastapi import APIRouter, Body
from services.chat_session_service import chat_session_service
import json
from datetime import datetime

router = APIRouter(prefix="/ai", tags=["AI分析"])

@router.post("/result")
async def register_ai_result(
    tenantId: str = Body(...),
    json_text: str = Body(...)
):
    """
    AI分析結果をAiResultに登録し、ChatFileのextractedAmount, extractedDate, statusを更新する。
    json_text: AI分析結果の配列JSON文字列（各要素にchatFileId, tenantIdを含むこと）
    """
    try:
        # tenantId必須チェック
        if not tenantId:
            return {"success": False, "error": "tenantId is required"}
        ai_results = json.loads(json_text)
        if not isinstance(ai_results, list):
            ai_results = [ai_results]
        for result in ai_results:
            chat_file_id = result.get("chatFileId")
            if not chat_file_id:
                # OCR失敗等でchat_file_idがNoneの場合はスキップ
                continue
            extracted_amount = result.get("totalAmount")
            date_str = result.get("invoiceDate")
            extracted_date = None
            if date_str:
                try:
                    extracted_date = datetime.fromisoformat(date_str)
                except Exception:
                    extracted_date = None
            # AiResult登録
            await chat_session_service.register_ai_result(
                chat_file_id=chat_file_id,
                result=json.dumps(result, ensure_ascii=False),
                status="completed"
            )
            # ChatFile更新
            await chat_session_service.update_chat_file(
                chat_file_id=chat_file_id,
                tenant_id=tenantId,
                extracted_amount=extracted_amount,
                extracted_date=extracted_date,
                status="ai_completed"
            )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
