"""
User routes (profile lookup).
  GET /users/me        — authenticated user's public profile
  GET /users/{user_id} — admin or self lookup
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import UserOut
from app.services.user_service import get_user_by_id
from app.core.dependencies import get_current_user_payload

router = APIRouter()


@router.get("/me", response_model=UserOut, summary="Get authenticated user profile")
def get_me(
    payload: dict = Depends(get_current_user_payload),
    db: Session   = Depends(get_db),
):
    user = get_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.get("/{user_id}", response_model=UserOut, summary="Get user by user_id (self or admin)")
def get_user(
    user_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: Session   = Depends(get_db),
):
    # Allow only the user themselves or an admin
    if payload["sub"] != user_id and payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user
