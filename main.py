import os
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

            result = poller.result()

            results.append({
                "filename": file.filename,
                "model": "prebuilt-invoice",
                "result": result
            })

        except Exception as e:
            # 1ファイル失敗しても全体を落とさない
            results.append({
                "filename": file.filename,
                "error": str(e)
            })

    return {
        "count": len(files),
        "results": results
    }
