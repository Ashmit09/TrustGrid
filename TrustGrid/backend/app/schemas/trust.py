"""
TrustGrid — Trust API Schemas
"""
from pydantic import BaseModel
from typing import Dict, List, Optional, Any


class DimensionBreakdown(BaseModel):
    model_config = {"extra": "allow"}


class TrustStateResponse(BaseModel):
    user_id: str
    trust_score: int
    confidence: str
    tier: str
    breakdown: Dict[str, float]
    rule_score: Optional[float]
    ml_score: Optional[float]
    combined_score: Optional[float]
    benefits: List[str]
    explanation: Optional[Dict[str, Any]]


class ScoreHistoryEntry(BaseModel):
    old_score: int
    new_score: int
    score_change: int
    reason: Optional[str]
    event_type: Optional[str]
    created_at: Any

    model_config = {"from_attributes": True}


class TrustEventEmit(BaseModel):
    user_id: str
    role: str
    event_type: str
    transaction_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    impact_summary: Optional[str] = None
