"""
Referral service — record a successful referral and fire TrustGrid event.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.marketplace import Referral
from app.services.user_service import get_user_by_email
from app.trustgrid.event_service import record_events_batch, update_features_for_users
from app.trustgrid.event_types import EventType
from app.services import trust_service as _trust_svc


def complete_referral(db: Session, referrer_id: str, referred_email: str) -> Referral:
    """
    Mark a referral as completed when the referred user has registered.
    The referred user must already have an account.
    """
    referred = get_user_by_email(db, referred_email)
    if not referred:
        raise HTTPException(status_code=404, detail="Referred user not found. They must register first.")

    if referred.user_id == referrer_id:
        raise HTTPException(status_code=400, detail="Cannot refer yourself.")

    # Check for duplicate
    existing = db.query(Referral).filter(
        Referral.referrer_id == referrer_id,
        Referral.referred_id == referred.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="This referral already exists.")

    referral = Referral(
        referrer_id=referrer_id,
        referred_id=referred.user_id,
        status="completed",
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)

    # ── Fire TrustGrid events ─────────────────────────────────────────────────
    record_events_batch(db, [
        {
            "user_id":        referrer_id,
            "event_type":     EventType.REFERRAL_COMPLETED,
            "reference_id":   referred.user_id,
            "impact_summary": "Successful referral completed",
        },
        {
            "user_id":        referred.user_id,
            "event_type":     EventType.REFERRAL_MADE,
            "reference_id":   referrer_id,
            "impact_summary": "Joined via referral",
        },
    ])

    update_features_for_users(db, [referrer_id])
    _trust_svc.refresh_trust(db, referrer_id,
                              event_type=EventType.REFERRAL_COMPLETED.value,
                              reason="Successful referral completed.")
    return referral
