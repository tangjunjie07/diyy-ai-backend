from fastapi import APIRouter, Request, HTTPException, Depends
import json
import time
from auth import verify_token
from services.chat_session_service import chat_session_service

router = APIRouter(prefix="/mf", tags=["MF"])

def call_money_forward_api(item: dict):
    if item.get("totalAmount", 0) <= 0:
        raise Exception("金額不正：金額必須大於 0")
    return True

@router.post("/register")
async def register_to_mf(request: Request, token_payload: dict = Depends(verify_token)):
    body = await request.json()
    tenant_id = body.get("tenantId")
    if not tenant_id:
        return {"success": False, "error": "tenantId is required"}
    json_text = body.get("journal_data", "[]")
    try:
        journal_list = json.loads(json_text) if isinstance(json_text, str) else json_text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON 解析失敗: {e}")
    success_count = 0
    failure_count = 0
    details = []
    failed_items_data = []
    for item in journal_list:
        filename = item.get("filename", "unknown")
        # OCR返却項目名に合わせてchat_file_idを取得
        chat_file_id = item.get("chat_file_id") or item.get("chatFileId")
        # 金額・日付は取れた場合のみ更新
        extracted_amount = item.get("totalAmount") if "totalAmount" in item else None
        extracted_date = item.get("invoiceDate") if "invoiceDate" in item else None
        try:
            call_money_forward_api(item)
            # MF連携成功時にChatFileを更新
            if chat_file_id and tenant_id:
                update_kwargs = {"chat_file_id": chat_file_id, "tenant_id": tenant_id, "status": "mf_completed"}
                if extracted_amount is not None:
                    update_kwargs["extracted_amount"] = extracted_amount
                if extracted_date is not None:
                    update_kwargs["extracted_date"] = extracted_date
                await chat_session_service.update_chat_file(**update_kwargs)
            success_count += 1
            details.append({
                "filename": filename,
                "status": "success"
            })
        except Exception as e:
            failure_count += 1
            details.append({
                "filename": filename,
                "status": "failed",
                "error": str(e)
            })
            failed_items_data.append(item)
        time.sleep(0.1)
    return {
        "total": len(journal_list),
        "success_count": success_count,
        "failure_count": failure_count,
        "details": details,
        "failed_items": json.dumps(failed_items_data, ensure_ascii=False) if failed_items_data else ""
    }
