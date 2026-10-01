"""
TrustGrid — Pydantic Schemas: Auth + User
"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Literal


# ── Register ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["buyer", "seller"]

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


# ── User Read ─────────────────────────────────────────────────────────────────

class UserRead(BaseModel):
    user_id: str
    name: str
    email: str
    role: str

    model_config = {"from_attributes": True}
