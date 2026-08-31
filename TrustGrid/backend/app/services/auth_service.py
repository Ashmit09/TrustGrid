"""
Authentication service — login verification and token creation.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.services.user_service import get_user_by_email


def authenticate_user(db: Session, email: str, password: str) -> User:
    """
    Verify email + password.
    Returns the User on success; raises 401 on failure.
    Generic error message intentionally avoids revealing whether
    the email exists (security best practice).
    """
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def build_auth_response(user: User) -> dict:
    """
    Build the JWT + trust summary dict returned after register / login.
    """
    token = create_access_token(subject=user.user_id, role=user.role.value)

    trust = user.trust_score
    trust_summary = None
    if trust:
        trust_summary = {
            "trust_score": trust.trust_score,
            "confidence":  trust.confidence.value,
            "tier":        trust.tier.value,
        }

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "user_id":    user.user_id,
            "name":       user.name,
            "email":      user.email,
            "role":       user.role.value,
            "created_at": user.created_at,
        },
        "trust": trust_summary,
    }
