from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from jose import jwt
from passlib.context import CryptContext
from config import SECRET_KEY, ALGORITHM
from prisma import Prisma

router = APIRouter(prefix="/auth", tags=["Auth"])


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class TokenRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

async def authenticate_super_admin(email: str, password: str):
    prisma = Prisma()
    await prisma.connect()
    user = await prisma.user.find_unique(where={"email": email})
    await prisma.disconnect()
    if not user or user.role != "super_admin":
        return None
    print(f"[DEBUG] password: {password}")
    print(f"[DEBUG] user.password: {user.password}")
    if not pwd_context.verify(password, user.password):
        print("[DEBUG] password verify failed")
        return None
    print("[DEBUG] password verify success")
    return user

@router.post("/token", response_model=TokenResponse)
async def issue_token(data: TokenRequest):
    user = await authenticate_super_admin(data.email, data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="認証失敗または権限不足")
    payload = {
        "sub": user.email,
        "role": user.role,
        "user_id": user.id,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}
