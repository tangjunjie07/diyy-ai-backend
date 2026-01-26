
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
    
    # 尝试连接，如果失败则在运行时强行下载
    try:
        await prisma.connect()
    except Exception as e:
        print(f"Prisma connection error, attempting runtime fetch: {e}")
        # 在运行环境直接下载二进制文件
        subprocess.run(["python", "-m", "prisma", "py", "fetch"])
        # 再次尝试连接
        await prisma.connect()

@app.on_event("shutdown")
async def shutdown():
    await prisma.disconnect()

# ルーター登録
app.include_router(ocr)
app.include_router(ai_result_router)
app.include_router(mf)
app.include_router(auth.router)
app.include_router(status.router)
