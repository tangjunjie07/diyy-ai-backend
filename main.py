import os
import json
import requests
import time
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, HTTPException
from azure.ai.documentintelligence import DocumentIntelligenceClient 
from azure.core.credentials import AzureKeyCredential

app = FastAPI(title="Azure OCR Backend")

# Azure 設定（Render の環境変数）
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_KEY")

if not AZURE_ENDPOINT or not AZURE_KEY:
    raise RuntimeError("AZURE_ENDPOINT or AZURE_KEY is missing")

# インスタンス化するクラス名も変更
client = DocumentIntelligenceClient(
    endpoint=AZURE_ENDPOINT,
    credential=AzureKeyCredential(AZURE_KEY)
)

@app.get("/")
def health_check():
    return {"status": "ok"}


# =========================
# OCR加工ロジック
# =========================
def extract_ocr_content(result) -> str:
    """
    OCR全文（最大3000文字）
    """
    content = getattr(result, "content", "") or ""
    return content[:3000]


def extract_items(result) -> list:
    """
    tables から簡易items抽出
    （後で品目・数量・金額に強化可能）
    """
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
    """
    Invoiceモデルの structured data
    """
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


def normalize_invoice_result(filename: str, analyze_result: object) -> dict:
    """
    Dify / LLM / API 共通で安全な最終形
    """
    ocr_content = extract_ocr_content(analyze_result)
    items = extract_items(analyze_result)
    structured_data = extract_structured_data(analyze_result)

    return {
        "filename": filename,
        "ocr_content": ocr_content,
        "ocr_items": json.dumps(items, ensure_ascii=False),
        "ocr_data": json.dumps(structured_data, ensure_ascii=False)
    }


@app.post("/analyze/invoice")
async def analyze_invoice(
    files: List[UploadFile] = File(...)
):
    results = []

    for file in files:
        try:
            content = await file.read()

            poller = client.begin_analyze_document(
                model_id="prebuilt-invoice",
                body=content  # document ではなく body
            )

            analyze_result = poller.result()

            normalized = normalize_invoice_result(
                filename=file.filename,
                analyze_result=analyze_result
            )

            results.append(normalized)

        except Exception as e:
            # 1ファイル失敗しても全体は返す
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

# 模擬 Money Forward API 的調用函數
def call_money_forward_api(item):
    """
    這裡替換成實際的 MF API 調用邏輯
    URL: https://api.moneyforward.com/v1/journal_entries 等
    """
    # 這裡僅作模擬邏輯
    if item.get("totalAmount", 0) <= 0:
        raise Exception("金額不正：金額必須大於 0")
    
    # 模擬網絡請求成功
    # response = requests.post(url, json=item, headers=headers)
    # response.raise_for_status()
    return True

@app.post("/mf/register")
async def register_to_mf(request: Request):
    # 接收來自 Dify 的 Body
    body = await request.json()
    
    # 獲取傳入的 json_text 並轉回 Python 列表
    # Dify 傳過來時可能是 {"journal_data": "[{...}]"}
    json_text = body.get("journal_data", "[]")
    
    try:
        journal_list = json.loads(json_text) if isinstance(json_text, str) else json_text
    except Exception as e:
        return {"error": "JSON 解析失敗", "details": str(e)}

    total = len(journal_list)
    success_count = 0
    failure_count = 0
    details = []
    failed_items_data = [] # 用於重新打包失敗的原始數據

    for item in journal_list:
        filename = item.get("filename", "unknown")
        try:
            # 執行 MF 註冊
            call_money_forward_api(item)
            
            success_count += 1
            details.append({
                "filename": filename,
                "status": "success"
            })
        except Exception as e:
            failure_count += 1
            error_msg = str(e)
            details.append({
                "filename": filename,
                "status": "failed",
                "error": error_msg
            })
            # 將失敗的原始物件打包，方便 Dify 下一輪修正
            failed_items_data.append(item)
        
        # 防止 API 頻率限制，適度延遲
        time.sleep(0.1)

    return {
        "total": total,
        "success_count": success_count,
        "failure_count": failure_count,
        "details": details,
        # 新增：失敗項目的原始 JSON 數據，Dify 可以拿這個再去修復
        "failed_items": json.dumps(failed_items_data, ensure_ascii=False) if failed_items_data else ""
    }