from dotenv import load_dotenv
load_dotenv()

import os
import json
import requests
import time
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import ocr, mf, auth, status
from routers.ai_result import router as ai_result_router

app = FastAPI(title="Azure OCR Backend")

# CORS設定（必要に応じて）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(ocr)
app.include_router(ai_result_router)
app.include_router(mf)
app.include_router(auth.router)
app.include_router(status.router)
