"""
Import every ORM model here so SQLAlchemy/Alembic discovers the full schema
in one import.
"""
from app.models.user import User                     # noqa: F401
from app.models.trust_score import TrustScore        # noqa: F401
from app.models.trust_event import TrustEvent        # noqa: F401
from app.models.score_history import ScoreHistory    # noqa: F401
from app.models.privilege import Privilege           # noqa: F401
from app.models.product import Product               # noqa: F401
from app.models.order import Order                   # noqa: F401
from app.models.payment import Payment               # noqa: F401
from app.models.return_model import Return           # noqa: F401
from app.models.review import Review                 # noqa: F401
from app.models.referral import Referral             # noqa: F401
