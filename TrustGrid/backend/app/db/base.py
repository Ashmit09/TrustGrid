"""
Import all ORM models here so that SQLAlchemy's metadata is fully populated
before Base.metadata.create_all() is called in main.py.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# All models must be imported below so their tables are registered
from app.models.user import User                    # noqa: F401, E402
from app.models.product import Product              # noqa: F401, E402
from app.models.marketplace import (                # noqa: F401, E402
    Order, Payment, Return, Review, Referral
)
from app.models.trust import (                      # noqa: F401, E402
    TrustEvent, BehaviorFeatures, TrustScore, ScoreHistory, Privilege, AnomalyFlag
)
