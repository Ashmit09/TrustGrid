"""
Pydantic schemas for authentication and user data.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Registration ──────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name:     str       = Field(..., min_length=2, max_length=120)
    email:    EmailStr
    password: str       = Field(..., min_length=8, max_length=128)
    role:     str       = Field(..., pattern="^(buyer|seller)$")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be blank.")
        return v.strip()


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str = Field(..., min_length=1)


# ── User profile in responses ─────────────────────────────────────────────────

class UserOut(BaseModel):
    user_id:    str
    name:       str
    email:      str
    role:       str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Auth response — returned on register and login ───────────────────────────

class TrustSummary(BaseModel):
    """Minimal trust state embedded in the auth response."""
    trust_score: int
    confidence:  str
    tier:        str


class AuthResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserOut
    trust:        Optional[TrustSummary] = None
