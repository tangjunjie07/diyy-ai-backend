
from dotenv import load_dotenv

load_dotenv()
import os
import json
import requests
import time
import subprocess
import stat
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
    
    print("Starting runtime prisma fetch...")
    # 1. 运行下载
    subprocess.run(["python", "-m", "prisma", "py", "fetch"], check=True)
    
    # 2. 暴力寻找下载的文件并赋予执行权限
    # 我们直接遍历那个缓存目录
    base_path = "/opt/render/.cache/prisma-python/binaries"
    if os.path.exists(base_path):
        for root, dirs, files in os.walk(base_path):
            for f in files:
                if "query-engine" in f:
                    file_path = os.path.join(root, f)
                    print(f"Setting executable permission on: {file_path}")
                    st = os.stat(file_path)
                    os.chmod(file_path, st.st_mode | stat.S_IEXEC)
    
    # 3. 连接
    try:
        await prisma.connect()
        print("Connected to Prisma engine successfully!")
    except Exception as e:
        print(f"Connection failed again: {e}")

@app.on_event("shutdown")
async def shutdown():
    await prisma.disconnect()

# ルーター登録
app.include_router(ocr)
app.include_router(ai_result_router)
app.include_router(mf)
app.include_router(auth.router)
app.include_router(status.router)
