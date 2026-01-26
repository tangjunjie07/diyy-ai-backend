from fastapi import APIRouter, Body
from services.chat_session_service import chat_session_service
import json
from datetime import datetime
from typing import Any  # 导入 Any

router = APIRouter(prefix="/ai", tags=["AI分析"])

@router.post("/result")
async def register_ai_result(
    tenantId: str = Body(...),
    json_text: Any = Body(...)  # 1. 改为 Any，不再强制要求 str
):
    try:
        if not tenantId:
            return {"success": False, "error": "tenantId is required"}

        # 2. 兼容性处理：如果是字符串则解析，如果是对象/数组则直接使用
        if isinstance(json_text, str):
            ai_results = json.loads(json_text)
        else:
            ai_results = json_text

        # 确保 ai_results 是列表格式
        if not isinstance(ai_results, list):
            ai_results = [ai_results]

        for result in ai_results:
            chat_file_id = result.get("chatFileId")
            if not chat_file_id:
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
        # 这里建议打印一下 e，方便调试
        print(f"Error in register_ai_result: {str(e)}")
        return {"success": False, "error": str(e)}