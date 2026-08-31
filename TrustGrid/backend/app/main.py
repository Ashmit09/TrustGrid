"""
TrustGrid FastAPI Application — Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import engine
from app.db.base import Base

# ── Create all tables on startup (skipped during unit tests) ─────────────────
if not settings.TESTING:
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrustGrid API",
    description="Dynamic Trust Engine for E-Commerce Marketplaces",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import auth, users, products, orders, trust_events, trust, admin  # noqa: E402

app.include_router(auth.router,         prefix="/auth",     tags=["auth"])
app.include_router(users.router,        prefix="/users",    tags=["users"])
app.include_router(products.router,     prefix="/products", tags=["products"])
app.include_router(orders.router,       prefix="/orders",   tags=["orders"])
app.include_router(trust_events.router, prefix="/trust",    tags=["trust-events"])
app.include_router(trust.router,        prefix="/trust",    tags=["trust"])
app.include_router(admin.router,        prefix="/admin",    tags=["admin"])


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "TrustGrid API", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "healthy"}
