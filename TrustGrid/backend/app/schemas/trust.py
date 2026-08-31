"""
Pydantic schemas for TrustGrid state, score history, and privileges.
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel


class DimScores(BaseModel):
    """Per-dimension score breakdown (0–100 each)."""
    # Buyer dimensions
    order_reliability:      Optional[float] = None
    return_behaviour:       Optional[float] = None
    payment_reliability:    Optional[float] = None
    cancellation_behaviour: Optional[float] = None
    platform_engagement:    Optional[float] = None
    # Seller dimensions
    order_fulfillment:      Optional[float] = None
    delivery_performance:   Optional[float] = None
    customer_satisfaction:  Optional[float] = None
    return_dispute_handling: Optional[float] = None
    platform_reliability:   Optional[float] = None


class ScoreChangeOut(BaseModel):
    change:     int
    reason:     Optional[str]
    event_type: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PrivilegeOut(BaseModel):
    privilege_name: str
    status:         str
    reason:         Optional[str]

    model_config = {"from_attributes": True}


class TrustProfileOut(BaseModel):
    """Full TrustGrid profile — returned by GET /trust/me."""
    user_id:        str
    trust_score:    int
    confidence:     str
    tier:           str
    breakdown:      Optional[Dict] = None
    recent_changes: List[ScoreChangeOut] = []
    benefits:       List[str] = []
    last_updated:   Optional[datetime] = None

    model_config = {"from_attributes": True}
