from fastapi import APIRouter, Body
from services.chat_session_service import chat_session_service
import json
from datetime import datetime
from typing import Any
# import logging

# 配置日志（如果你的项目已经配置过可以跳过此行）
# logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/ai", tags=["AI分析"])

@router.post("/result")
async def register_ai_result(
    tenantId: str = Body(...),
    json_text: Any = Body(...)
):
    # --- 日志输出开始 ---
    # print("\n" + "="*50)
    # print(f"🕒 收到 AI 结果请求 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    # print(f"🏢 Tenant ID: {tenantId}")
    # print(f"数据类型: {type(json_text)}")
    # try:
    #     # 将收到的原始数据格式化打印出来，方便 F12 对比
    #     debug_output = json_text if not isinstance(json_text, str) else json.loads(json_text)
    #     print("📦 JSON_TEXT 内容:")
    #     print(json.dumps(debug_output, indent=2, ensure_ascii=False))
    # except Exception:
    #     print(f"📦 JSON_TEXT 原始字符串 (解析失败): {json_text}")
    # print("="*50 + "\n")
    # --- 日志输出结束 ---

    try:
        if not tenantId:
            return {"success": False, "error": "tenantId is required"}

        # 兼容处理
        if isinstance(json_text, str):
            ai_results = json.loads(json_text)
        else:
            ai_results = json_text

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

            await chat_session_service.register_ai_result(
                chat_file_id=chat_file_id,
                result=json.dumps(result, ensure_ascii=False),
                status="completed"
            )
            
            await chat_session_service.update_chat_file(
                chat_file_id=chat_file_id,
                tenant_id=tenantId,
                extracted_amount=extracted_amount,
                extracted_date=extracted_date,
                status="ai_completed"
            )
        return {"success": True}
    except Exception as e:
        # 错误时打印堆栈信息
        print(f"❌ 处理出错: {str(e)}")
        return {"success": False, "error": str(e)}