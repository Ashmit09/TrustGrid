"""
Trust events API route — query and manual-fire events.

  GET  /trust/events          — list events for authenticated user
  POST /trust/events          — manually fire an event (admin / demo use)
  POST /trust/referral        — buyer submits a referral
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.trustgrid.event_service import get_events_for_user, record_event, count_meaningful_events
from app.trustgrid.event_types import EventType
from app.services.referral_service import complete_referral
from app.schemas.order import ReferralCreate, ReferralOut
from app.core.dependencies import get_current_user_payload, require_role

router = APIRouter()


# ── Output schema ─────────────────────────────────────────────────────────────

class TrustEventOut(BaseModel):
    event_id:       str
    user_id:        str
    event_type:     str
    reference_id:   Optional[str] = None
    impact_summary: Optional[str] = None
    created_at:     str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_custom(cls, ev):
        return cls(
            event_id=ev.event_id,
            user_id=ev.user_id,
            event_type=ev.event_type,
            reference_id=ev.reference_id,
            impact_summary=ev.impact_summary,
            created_at=ev.created_at.isoformat(),
        )


class ManualEventRequest(BaseModel):
    user_id:    str
    event_type: str
    reference_id: Optional[str] = None
    metadata:     Optional[dict] = None
    impact_summary: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/events", summary="List TrustGrid events for authenticated user")
def list_my_events(
    limit: int = Query(50, ge=1, le=200),
    payload: dict    = Depends(get_current_user_payload),
    db:      Session = Depends(get_db),
):
    events = get_events_for_user(db, user_id=payload["sub"], limit=limit)
    return [TrustEventOut.from_orm_custom(e) for e in events]


@router.get("/events/count-meaningful", summary="Count meaningful evidence events")
def meaningful_count(
    payload: dict    = Depends(get_current_user_payload),
    db:      Session = Depends(get_db),
):
    count = count_meaningful_events(db, payload["sub"])
    return {"user_id": payload["sub"], "meaningful_event_count": count}


@router.post("/events", status_code=201, summary="Manually fire a trust event (admin/demo)")
def fire_event(
    data:    ManualEventRequest,
    payload: dict    = Depends(require_role("admin")),
    db:      Session = Depends(get_db),
):
    try:
        etype = EventType(data.event_type)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown event type: {data.event_type}")

    event = record_event(
        db,
        user_id=data.user_id,
        event_type=etype,
        reference_id=data.reference_id,
        metadata=data.metadata,
        impact_summary=data.impact_summary,
    )
    return TrustEventOut.from_orm_custom(event)


@router.post("/referral", status_code=201, summary="Submit a successful referral (buyer)")
def referral(
    data:    ReferralCreate,
    payload: dict    = Depends(require_role("buyer")),
    db:      Session = Depends(get_db),
):
    return complete_referral(db, referrer_id=payload["sub"], referred_email=data.referred_email)
