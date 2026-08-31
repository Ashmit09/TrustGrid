"""
Authentication routes:
  POST /auth/register
  POST /auth/login
  GET  /auth/me
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError

from app.db.session import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse
from app.services.user_service import create_user, get_user_by_id
from app.services.auth_service import authenticate_user, build_auth_response
from app.core.dependencies import get_current_user_payload

router = APIRouter()


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new buyer or seller",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Creates a new user account.
    Automatically generates a unique user_id (BUY-xxxxx or SEL-xxxxx).
    Initialises TrustScore at 700 / LOW / TRUSTED.
    Returns a JWT token so the user is immediately logged in.
    """
    user = create_user(
        db=db,
        name=payload.name,
        email=payload.email,
        password=payload.password,
        role=payload.role,
    )
    return build_auth_response(user)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in with email and password",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates the user and returns a JWT token.
    The trust summary (score, confidence, tier) is included in the response.
    """
    user = authenticate_user(db, payload.email, payload.password)
    # Eager-load trust_score relationship
    db.refresh(user)
    return build_auth_response(user)


@router.get(
    "/me",
    summary="Get the currently authenticated user's profile",
)
def me(
    payload: dict = Depends(get_current_user_payload),
    db: Session   = Depends(get_db),
):
    """
    Returns the full profile for the JWT-authenticated user.
    """
    user = get_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return build_auth_response(user)
