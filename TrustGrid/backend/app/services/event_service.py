"""
TrustGrid — Event Service
Records trust events. Enforces idempotency (same event_id → no duplicate).
Does NOT recalculate trust; the Trust Engine reads events when it runs.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.trust_event import TrustEvent
from app.core.constants import BUYER_EVENT_TYPES, SELLER_EVENT_TYPES


def emit_event(
    db: Session,
    *,
    user_id: str,
    role: str,
    event_type: str,
    transaction_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    impact_summary: Optional[str] = None,
    event_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> TrustEvent:
    """
    Persist a trust event.

    - event_id is used for idempotency: if a row with the same event_id already
      exists, return it unchanged without inserting a duplicate.
    - created_at can be supplied for synthetic/backfilled data; defaults to now.
    - Future-dated events are rejected.
    """
    valid_types = BUYER_EVENT_TYPES if role == "buyer" else SELLER_EVENT_TYPES
    if event_type not in valid_types:
        raise ValueError(f"Invalid event_type '{event_type}' for role '{role}'.")

    if created_at is None:
        created_at = datetime.now(timezone.utc)

    # Reject future-dated events
    now = datetime.now(timezone.utc)
    # Make created_at timezone-aware if naive
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if created_at > now:
        raise ValueError("Future-dated events are not accepted as historical evidence.")

    # Idempotency check
    if event_id:
        existing = db.query(TrustEvent).filter(TrustEvent.event_id == event_id).first()
        if existing:
            return existing
    else:
        event_id = str(uuid.uuid4())

    event = TrustEvent(
        event_id=event_id,
        user_id=user_id,
        role=role,
        event_type=event_type,
        transaction_id=transaction_id,
        metadata_=metadata or {},
        impact_summary=impact_summary,
        created_at=created_at,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_events_for_user(db: Session, user_id: str) -> list:
    """Return all trust events for a user, ordered oldest-first."""
    return (
        db.query(TrustEvent)
        .filter(TrustEvent.user_id == user_id)
        .order_by(TrustEvent.created_at.asc())
        .all()
    )
