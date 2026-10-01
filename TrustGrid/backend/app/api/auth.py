"""
TrustGrid — Auth API Router
POST /auth/register
POST /auth/login
GET  /auth/me
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserRead
from app.services.auth_service import register_user, login_user, get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    from app.core.security import create_access_token
    user = register_user(db, data)
    token = create_access_token({"sub": user.user_id, "role": user.role})
    return TokenResponse(access_token=token, user_id=user.user_id, role=user.role)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    result = login_user(db, data.email, data.password)
    return TokenResponse(**result)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user
