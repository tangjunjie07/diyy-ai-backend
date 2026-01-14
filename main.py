import os
import json
from typing import List
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
