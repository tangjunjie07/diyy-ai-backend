
from dotenv import load_dotenv

load_dotenv()
import os
import json
import requests
import time
import subprocess
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import ocr, mf, auth, status
from routers.ai_result import router as ai_result_router
from database import prisma

app = FastAPI(title="Azure OCR Backend")

# CORS設定（必要に応じて）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prisma 接続管理
@app.on_event("startup")
async def startup():
    
    # 强制在启动时下载，这是在 Render 运行环境中最稳妥的办法
    try:
        print("Starting runtime prisma fetch...")
        # 即使已经有了，执行一次 fetch 也就几秒钟，确保万无一失
        subprocess.run(["python", "-m", "prisma", "py", "fetch"], check=True)
        print("Fetch successful, connecting...")
        await prisma.connect()
    except Exception as e:
        print(f"Prisma connection failed: {e}")
        # 如果还是不行，打印一下环境信息帮我们排查
        print(f"Current Directory: {os.getcwd()}")

@app.on_event("shutdown")
async def shutdown():
    await prisma.disconnect()

# ルーター登録
app.include_router(ocr)
app.include_router(ai_result_router)
app.include_router(mf)
app.include_router(auth.router)
app.include_router(status.router)
