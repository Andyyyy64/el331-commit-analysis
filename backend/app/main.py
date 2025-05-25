from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

from .routers import analysis

app = FastAPI(
    title="Git Commit Fingerprint Analyzer API",
    description="API for analyzing Git commit messages.",
    version="0.1.0",
)

# CORS設定
origins = [
    "http://localhost:3000",  # Next.jsのデフォルトポート
    # 必要に応じて他のオリジンも追加
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Git Commit Fingerprint Analyzer API"}

# 分析ルーターを追加
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])

# Uvicornサーバーを起動するための設定 (ファイルが直接実行された場合)
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000")) # 環境変数PORTがあればそれを使用、なければ8000
    uvicorn.run(app, host="0.0.0.0", port=port) 