"""
TrustGrid — FastAPI Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import auth, users, products, orders, trust, admin

app = FastAPI(
    title="TrustGrid API",
    description="Dynamic ML-assisted trust and privilege engine for a two-sided marketplace.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
app.include_router(users.router,    prefix="/users",    tags=["users"])
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(orders.router,   prefix="/orders",   tags=["orders"])
app.include_router(trust.router,    prefix="/trust",    tags=["trust"])
app.include_router(admin.router,    prefix="/admin",    tags=["admin"])


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "TrustGrid API"}
