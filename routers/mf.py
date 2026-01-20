from fastapi import APIRouter, Request, HTTPException, Depends
import json
import time
from auth import verify_token

router = APIRouter(prefix="/mf", tags=["MF"])

def call_money_forward_api(item: dict):
    if item.get("totalAmount", 0) <= 0:
        raise Exception("金額不正：金額必須大於 0")
    return True

@router.post("/register")
async def register_to_mf(request: Request, token_payload: dict = Depends(verify_token)):
    body = await request.json()
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
        try:
            call_money_forward_api(item)
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
