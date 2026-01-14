import os
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

app = FastAPI(title="Azure OCR Backend")

# =========================
# Azure 設定（Render 環境変数）
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
# ヘルスチェック
# =========================
@app.get("/")
def health_check():
    return {"status": "ok"}

# =========================
# OCR加工ロジック
# =========================
def extract_ocr_content(result) -> str:
    """OCR全文（最大3000文字）"""
    content = getattr(result, "content", "") or ""
    return content[:3000]


def extract_items(result) -> list:
    """tables から簡易items抽出"""
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
    """Invoiceモデルの structured data"""
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
    """Dify / LLM / API 共通で安全な最終形"""
    return {
        "filename": filename,
        "ocr_content": extract_ocr_content(analyze_result),
        "ocr_items": json.dumps(
            extract_items(analyze_result),
            ensure_ascii=False
        ),
        "ocr_data": json.dumps(
            extract_structured_data(analyze_result),
            ensure_ascii=False
        )
    }

# =========================
# 請求書OCR（単一ファイル）
# =========================
@app.post("/analyze/invoice")
async def analyze_invoice(
    file: UploadFile = File(...)
):
    try:
        content = await file.read()

        poller = client.begin_analyze_document(
            model_id="prebuilt-invoice",
            body=content
        )

        analyze_result = poller.result()

        return normalize_invoice_result(
            filename=file.filename,
            analyze_result=analyze_result
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
