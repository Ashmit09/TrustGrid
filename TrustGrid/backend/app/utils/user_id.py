"""
User ID generation.
Buyers:  BUY-10001, BUY-10002, …
Sellers: SEL-20001, SEL-20002, …
Admins:  ADM-30001, …

The numeric suffix is derived from: prefix_start + count_of_existing_users_of_that_role + 1
This keeps IDs stable and sequential without a separate counter table.
"""
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


_PREFIX_MAP = {
    UserRole.buyer:  ("BUY", 10000),
    UserRole.seller: ("SEL", 20000),
    UserRole.admin:  ("ADM", 30000),
}


def generate_user_id(db: Session, role: UserRole) -> str:
    """
    Generate the next sequential user ID for the given role.
    Thread-safety note: for this prototype a simple count query is sufficient.
    Production would use a database sequence or advisory lock.
    """
    prefix, base = _PREFIX_MAP[role]
    count = db.query(User).filter(User.role == role).count()
    numeric = base + count + 1
    return f"{prefix}-{numeric}"
