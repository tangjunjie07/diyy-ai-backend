import os
import json
import requests
import time
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

app = FastAPI(title="Azure OCR Backend")

# =========================
# Azure 設定（Render の環境変数）
# =========================
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_KEY")

if not AZURE_ENDPOINT or not AZURE_KEY:
    raise RuntimeError("AZURE_ENDPOINT or AZURE_KEY is missing")

client = DocumentIntelligenceClient(
    endpoint=AZURE_ENDPOINT,
    credential=AzureKeyCredential(AZURE_KEY)
)

# =========================
# Health Check
# =========================
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
    return {
        "filename": filename,
        "ocr_content": extract_ocr_content(analyze_result),
        "ocr_items": json.dumps(extract_items(analyze_result), ensure_ascii=False),
        "ocr_data": json.dumps(extract_structured_data(analyze_result), ensure_ascii=False)
    }

# =========================
# OCR API
# =========================
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
                body=content
            )

            analyze_result = poller.result()

            results.append(
                normalize_invoice_result(
                    filename=file.filename,
                    analyze_result=analyze_result
                )
            )

        except Exception as e:
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

# =========================
# 模擬 Money Forward API
# =========================
def call_money_forward_api(item: dict):
    """
    模擬 Money Forward API 調用
    """
    if item.get("totalAmount", 0) <= 0:
        raise Exception("金額不正：金額必須大於 0")

    # 真實情況可用 requests.post(...)
    return True

# =========================
# MF 登録 API
# =========================
@app.post("/mf/register")
async def register_to_mf(request: Request):
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
