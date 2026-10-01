"""
TrustGrid — Trust API Router

GET  /trust/me                  → current user's trust state
GET  /trust/{user_id}           → trust state (admin or self)
GET  /trust/{user_id}/history   → score history
GET  /trust/{user_id}/breakdown → dimension breakdown
GET  /trust/{user_id}/benefits  → active privileges
POST /trust/events              → emit a trust event (internal/admin)
POST /trust/recalculate         → trigger immediate recalculation for current user
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.trust_score import TrustScore
from app.models.score_history import ScoreHistory
from app.models.trust_event import TrustEvent
from app.schemas.trust import TrustStateResponse, ScoreHistoryEntry, TrustEventEmit
from app.services.auth_service import get_current_user, require_role
from app.services.event_service import emit_event, get_events_for_user
from app.services.trust_engine import run_trust_engine

router = APIRouter()


def _orm_event_to_dict(e: TrustEvent) -> dict:
    return {
        "event_type": e.event_type,
        "created_at": e.created_at,
        "metadata_": e.metadata_ or {},
        "transaction_id": e.transaction_id,
    }


def _run_for_user(db: Session, user_id: str, role: str) -> dict:
    """Load events and run the trust engine for a user."""
    raw_events = get_events_for_user(db, user_id)
    events = [_orm_event_to_dict(e) for e in raw_events]
    return run_trust_engine(db, user_id, role, events)


# ── GET /trust/me ─────────────────────────────────────────────────────────────

@router.get("/me", response_model=TrustStateResponse)
def get_my_trust(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _run_for_user(db, current_user.user_id, current_user.role)


# ── GET /trust/{user_id} ──────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=TrustStateResponse)
def get_trust_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only self or admin
    if current_user.user_id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied.")
    target = db.query(User).filter(User.user_id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    return _run_for_user(db, user_id, target.role)


# ── GET /trust/{user_id}/history ──────────────────────────────────────────────

@router.get("/{user_id}/history", response_model=List[ScoreHistoryEntry])
def get_score_history(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied.")
    rows = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.user_id == user_id)
        .order_by(ScoreHistory.created_at.desc())
        .limit(50)
        .all()
    )
    return rows


# ── GET /trust/{user_id}/breakdown ────────────────────────────────────────────

@router.get("/{user_id}/breakdown")
def get_breakdown(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied.")
    target = db.query(User).filter(User.user_id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    result = _run_for_user(db, user_id, target.role)
    return {"user_id": user_id, "breakdown": result["breakdown"]}


# ── GET /trust/{user_id}/benefits ─────────────────────────────────────────────

@router.get("/{user_id}/benefits")
def get_benefits(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied.")
    target = db.query(User).filter(User.user_id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    result = _run_for_user(db, user_id, target.role)
    return {"user_id": user_id, "benefits": result["benefits"], "tier": result["tier"]}


# ── POST /trust/events (admin/internal) ───────────────────────────────────────

@router.post("/events", status_code=201)
def emit_trust_event(
    data: TrustEventEmit,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """Admin-only: manually emit a trust event."""
    event = emit_event(
        db,
        user_id=data.user_id,
        role=data.role,
        event_type=data.event_type,
        transaction_id=data.transaction_id,
        metadata=data.metadata,
        impact_summary=data.impact_summary,
    )
    return {"event_id": event.event_id, "status": "emitted"}


# ── POST /trust/recalculate ───────────────────────────────────────────────────

@router.post("/recalculate", response_model=TrustStateResponse)
def recalculate_trust(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a fresh trust calculation for the current user."""
    return _run_for_user(db, current_user.user_id, current_user.role)
