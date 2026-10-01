"""
TrustGrid — Auth Service
Handles user registration (with logical ID assignment), login, and JWT dependency.
"""
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db.database import get_db
from app.models.user import User
from app.models.trust_score import TrustScore
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.core.constants import (
    INITIAL_TRUST_SCORE,
    BUYER_ID_PREFIX, SELLER_ID_PREFIX, ADMIN_ID_PREFIX,
    BUYER_ID_START, SELLER_ID_START, ADMIN_ID_START,
)
from app.schemas.auth import RegisterRequest

bearer_scheme = HTTPBearer()


# ── Logical ID Generation ─────────────────────────────────────────────────────

def _next_logical_id(db: Session, role: str) -> str:
    """
    Generate the next logical user_id for the given role.
    BUY-10001, BUY-10002 ... | SEL-20001 ... | ADM-30001 ...
    """
    prefix_map = {
        "buyer":  (BUYER_ID_PREFIX,  BUYER_ID_START),
        "seller": (SELLER_ID_PREFIX, SELLER_ID_START),
        "admin":  (ADMIN_ID_PREFIX,  ADMIN_ID_START),
    }
    prefix, start = prefix_map[role]
    like_pattern = f"{prefix}-%"
    count = db.query(User).filter(User.user_id.like(like_pattern)).count()
    return f"{prefix}-{start + count}"


# ── Register ──────────────────────────────────────────────────────────────────

def register_user(db: Session, data: RegisterRequest) -> User:
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )
    logical_id = _next_logical_id(db, data.role)
    user = User(
        user_id=logical_id,
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.flush()  # get the row without committing

    # Cold-start trust state
    trust = TrustScore(
        user_id=logical_id,
        trust_score=INITIAL_TRUST_SCORE,
        confidence="LOW",
        tier="TRUSTED",
    )
    db.add(trust)
    db.commit()
    db.refresh(user)
    return user


# ── Login ─────────────────────────────────────────────────────────────────────

def login_user(db: Session, email: str, password: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    token = create_access_token({"sub": user.user_id, "role": user.role})
    return {"access_token": token, "user_id": user.user_id, "role": user.role}


# ── JWT Dependency ─────────────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
    user = db.query(User).filter(User.user_id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


def require_role(*roles: str):
    """FastAPI dependency factory: ensures current user has one of the specified roles."""
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access requires role: {roles}",
            )
        return current_user
    return _check
