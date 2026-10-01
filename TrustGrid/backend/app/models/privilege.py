"""
TrustGrid — Privilege ORM Model
Active privileges derived from score + confidence + tier.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from app.db.database import Base


class Privilege(Base):
    __tablename__ = "privileges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(20), nullable=False, index=True)
    privilege_name = Column(String(60), nullable=False)      # e.g. FREE_DELIVERY
    status = Column(String(20), nullable=False)              # ACTIVE | INACTIVE
    reason = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
