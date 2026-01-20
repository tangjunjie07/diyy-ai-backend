from fastapi import APIRouter, Depends, status
from auth import verify_token

router = APIRouter()

@router.get("/status", tags=["status"])
def get_status(current_user=Depends(verify_token)):
    """
    APIトークン認証済みでステータスを返すエンドポイント
    """
    return {"status": "ok", "user": current_user}
