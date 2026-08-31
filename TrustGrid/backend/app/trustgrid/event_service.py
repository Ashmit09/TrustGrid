"""
TrustGrid Event Service.

Responsibilities:
  1. Record every marketplace event that affects trust.
  2. Associate the event with the correct user_id (buyer OR seller).
  3. Return the set of affected user_ids so callers can trigger
     feature recalculation after the transaction closes.

Design decisions:
  - Each marketplace action that affects two users (e.g. an order completion
    affects both the buyer's Order Reliability and the seller's Order Fulfillment)
    fires TWO separate TrustEvent rows — one per user.
  - The event_id is a UUID so events are idempotent-safe.
  - Feature recalculation is intentionally NOT triggered inside this module.
    It must be called AFTER the current transaction commits so that SQLite
    and PostgreSQL both see the new events in subsequent queries.
    Callers (order_service etc.) invoke `update_features_for_users()` themselves.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from app.models.trust import TrustEvent
from app.trustgrid.event_types import EventType


def _new_event_id() -> str:
    return f"EVT-{uuid.uuid4().hex[:16].upper()}"


def record_event(
    db: Session,
    user_id: str,
    event_type: EventType,
    reference_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    impact_summary: Optional[str] = None,
    commit: bool = True,
) -> TrustEvent:
    """
    Persist a single TrustGrid event for one user.

    Args:
        db:             SQLAlchemy session.
        user_id:        The user this event belongs to (buyer or seller).
        event_type:     One of the EventType enum values.
        reference_id:   Optional order_id / product_id / etc. for traceability.
        metadata:       Optional extra JSON payload.
        impact_summary: Human-readable summary of the impact (e.g. "Order completed").
        commit:         If False, caller manages the transaction (useful for batching).
    """
    event = TrustEvent(
        event_id=_new_event_id(),
        user_id=user_id,
        event_type=event_type.value,
        reference_id=reference_id,
        metadata_=metadata or {},
        impact_summary=impact_summary,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    return event


def record_events_batch(
    db: Session,
    events: List[dict],
) -> List[TrustEvent]:
    """
    Record multiple events in a single transaction.

    Each dict in `events` must contain:
        user_id, event_type, and optionally reference_id / metadata / impact_summary.
    """
    created = []
    for ev in events:
        created.append(record_event(
            db=db,
            user_id=ev["user_id"],
            event_type=ev["event_type"],
            reference_id=ev.get("reference_id"),
            metadata=ev.get("metadata"),
            impact_summary=ev.get("impact_summary"),
            commit=False,
        ))
    db.commit()
    for e in created:
        db.refresh(e)
    return created


def update_features_for_users(db: Session, user_ids: List[str]) -> None:
    """
    Trigger Feature Engine recalculation for each unique user_id.
    Must be called AFTER the event-recording transaction has committed
    so that the new TrustEvent rows are visible in a fresh query.
    """
    from app.trustgrid.feature_engine import update_features
    seen: Set[str] = set()
    for uid in user_ids:
        if uid not in seen:
            update_features(db, uid)
            seen.add(uid)


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_events_for_user(
    db: Session,
    user_id: str,
    limit: int = 200,
    event_type: Optional[EventType] = None,
) -> List[TrustEvent]:
    """Return events for one user, newest first."""
    q = db.query(TrustEvent).filter(TrustEvent.user_id == user_id)
    if event_type:
        q = q.filter(TrustEvent.event_type == event_type.value)
    return q.order_by(TrustEvent.created_at.desc()).limit(limit).all()


def get_events_since(
    db: Session,
    user_id: str,
    since: datetime,
) -> List[TrustEvent]:
    """Return all events for a user after a given timestamp (for time-decay engine)."""
    return (
        db.query(TrustEvent)
        .filter(
            TrustEvent.user_id == user_id,
            TrustEvent.created_at >= since,
        )
        .order_by(TrustEvent.created_at.asc())
        .all()
    )


def count_meaningful_events(db: Session, user_id: str) -> int:
    """
    Count events that constitute meaningful behavioral evidence.
    Used by ConfidenceService to determine LOW / MEDIUM / HIGH.
    """
    from app.trustgrid.event_types import MEANINGFUL_EVENTS
    meaningful_types = [e.value for e in MEANINGFUL_EVENTS]
    return (
        db.query(TrustEvent)
        .filter(
            TrustEvent.user_id == user_id,
            TrustEvent.event_type.in_(meaningful_types),
        )
        .count()
    )
