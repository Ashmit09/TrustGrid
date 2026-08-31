"""
TrustGrid Seed Data Script.

Creates demo users, products, orders, and TrustGrid events so the
application looks populated and demonstrates the full scoring pipeline
immediately after setup.

Demo users created
------------------
BUYERS
  alice@demo.com       → Reliable buyer  (high score, HIGH confidence)
  bob@demo.com         → Occasional buyer (good score, MEDIUM confidence)
  charlie@demo.com     → Frequent canceller (lower score)
  diana@demo.com       → New buyer (starting 700 / LOW)

SELLERS
  seller1@demo.com     → Excellent seller (high score, HIGH confidence)
  seller2@demo.com     → Average seller (mid score, MEDIUM confidence)

Admin
  admin@demo.com       → Admin account

All passwords: Demo1234!

Run
---
  cd TrustGrid/backend
  PYTHONPATH=. python database/seed/seed.py
  
  OR with the venv:
  .venv/bin/python database/seed/seed.py
"""
import os
import sys
import random
import datetime
from pathlib import Path
from decimal import Decimal

# Ensure backend app is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Use SQLite for seeding if no .env DATABASE_URL is set (dev convenience)
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql://trustgrid_user:password@localhost:5432/trustgrid_db"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models.user import UserRole
from app.models.trust import ConfidenceLevel, TrustTier
from app.services.user_service import create_user, get_user_by_email
from app.services.product_service import create_product
from app.services.order_service import (
    place_order, ship_order, complete_order, cancel_order,
    request_return, submit_review,
)
from app.trustgrid.event_service import record_event, update_features_for_users
from app.trustgrid.event_types import EventType
from app.services.trust_service import refresh_trust
from app.schemas.product import ProductCreate
from app.schemas.order import OrderCreate, ReturnCreate, ReviewCreate

DEMO_PASSWORD = "Demo1234!"

# ── DB Setup ──────────────────────────────────────────────────────────────────

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
if is_sqlite:
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _back_date(db, user_id: str, days: float):
    """Back-date all existing events for a user to simulate history."""
    from app.models.trust import TrustEvent
    from sqlalchemy import text as sa_text
    from datetime import timezone
    past = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=days)
    evs = db.query(TrustEvent).filter(TrustEvent.user_id == user_id).all()
    for ev in evs:
        ev.created_at = past
    db.commit()


def _or_create_user(db, name, email, role):
    existing = get_user_by_email(db, email)
    if existing:
        print(f"  [skip] {email} already exists")
        return existing
    return create_user(db, name, email, DEMO_PASSWORD, role)


def _safe_order(db, buyer_id, product):
    """Place an order and force payment to succeed."""
    random.seed(42)
    product.stock = 100
    db.commit()
    from app.models.marketplace import OrderStatus
    order = place_order(db, buyer_id, OrderCreate(product_id=product.id, quantity=1))
    if order.status != OrderStatus.paid:
        order.status = OrderStatus.paid
        db.commit()
        db.refresh(order)
    return order


# ── Products ──────────────────────────────────────────────────────────────────

DEMO_PRODUCTS = [
    ProductCreate(title="Wireless Headphones", description="Premium audio experience", price=Decimal("1499"), stock=50, category="Electronics"),
    ProductCreate(title="Running Shoes", description="Lightweight and comfortable", price=Decimal("2499"), stock=30, category="Sports"),
    ProductCreate(title="Python Programming Book", description="Learn Python from scratch", price=Decimal("599"), stock=100, category="Books"),
    ProductCreate(title="Coffee Maker", description="Brew perfect coffee every time", price=Decimal("3299"), stock=20, category="Home"),
    ProductCreate(title="Yoga Mat", description="Non-slip premium mat", price=Decimal("899"), stock=40, category="Sports"),
    ProductCreate(title="Mechanical Keyboard", description="Tactile typing experience", price=Decimal("4999"), stock=15, category="Electronics"),
    ProductCreate(title="Water Bottle", description="BPA-free, 1L capacity", price=Decimal("399"), stock=80, category="Sports"),
    ProductCreate(title="LED Desk Lamp", description="Adjustable brightness, USB charging", price=Decimal("1299"), stock=25, category="Home"),
]


# ── Main seed ─────────────────────────────────────────────────────────────────

def seed():
    db = Session()
    print("\n" + "=" * 60)
    print("  TrustGrid Seed Data")
    print("=" * 60)

    try:
        # ── Admin ──────────────────────────────────────────────────
        print("\n[1] Creating admin account…")
        admin = _or_create_user(db, "Admin", "admin@demo.com", "admin")
        print(f"  admin@demo.com  → {admin.user_id}")

        # ── Sellers ────────────────────────────────────────────────
        print("\n[2] Creating sellers…")
        sel1 = _or_create_user(db, "Priya Sharma", "seller1@demo.com", "seller")
        sel2 = _or_create_user(db, "Raj Mehta",    "seller2@demo.com", "seller")
        print(f"  seller1@demo.com → {sel1.user_id}")
        print(f"  seller2@demo.com → {sel2.user_id}")

        # ── Products ───────────────────────────────────────────────
        print("\n[3] Creating products…")
        products = []
        for pd_data in DEMO_PRODUCTS[:6]:
            try:
                p = create_product(db, sel1.user_id, pd_data)
                products.append(p)
                print(f"  {p.title}  → id={p.id}")
            except Exception as e:
                print(f"  [skip] {pd_data.title}: {e}")

        for pd_data in DEMO_PRODUCTS[6:]:
            try:
                p = create_product(db, sel2.user_id, pd_data)
                products.append(p)
                print(f"  {p.title}  → id={p.id}")
            except Exception as e:
                print(f"  [skip] {pd_data.title}: {e}")

        if not products:
            print("  No products available — skipping order simulation.")
            return

        p1, p2 = products[0], products[1]

        # ── Buyers ─────────────────────────────────────────────────
        print("\n[4] Creating buyers…")
        alice   = _or_create_user(db, "Alice Chen",    "alice@demo.com",   "buyer")
        bob     = _or_create_user(db, "Bob Kumar",     "bob@demo.com",     "buyer")
        charlie = _or_create_user(db, "Charlie Singh", "charlie@demo.com", "buyer")
        diana   = _or_create_user(db, "Diana Verma",   "diana@demo.com",   "buyer")
        print(f"  alice@demo.com   → {alice.user_id}")
        print(f"  bob@demo.com     → {bob.user_id}")
        print(f"  charlie@demo.com → {charlie.user_id}")
        print(f"  diana@demo.com   → {diana.user_id}")

        # ── Simulate Alice — reliable buyer (35 completed orders) ──
        print("\n[5] Simulating Alice (reliable buyer)…")
        for i in range(35):
            p = products[i % len(products)]
            order = _safe_order(db, alice.user_id, p)
            ship_order(db, order.order_id, p.seller_id)
            complete_order(db, order.order_id, alice.user_id)
            if i % 5 == 0:
                try:
                    submit_review(db, order.order_id, alice.user_id, ReviewCreate(rating=5, comment="Excellent!"))
                except Exception:
                    pass
        # Add a referral event for Alice
        record_event(db, alice.user_id, EventType.REFERRAL_COMPLETED, impact_summary="Referred Bob")
        update_features_for_users(db, [alice.user_id])
        refresh_trust(db, alice.user_id, reason="Simulated reliable buyer history")
        print(f"  Done — {alice.user_id}")

        # ── Simulate Bob — occasional but reliable buyer (10 orders) ──
        print("\n[6] Simulating Bob (occasional reliable buyer)…")
        for i in range(10):
            p = products[i % len(products)]
            order = _safe_order(db, bob.user_id, p)
            ship_order(db, order.order_id, p.seller_id)
            complete_order(db, order.order_id, bob.user_id)
        # Back-date Bob's events to simulate spread over time
        _back_date(db, bob.user_id, days=120)
        update_features_for_users(db, [bob.user_id])
        refresh_trust(db, bob.user_id, reason="Simulated occasional buyer history")
        print(f"  Done — {bob.user_id}")

        # ── Simulate Charlie — frequent canceller (mixed behaviour) ──
        print("\n[7] Simulating Charlie (frequent canceller)…")
        for i in range(8):
            p = products[i % len(products)]
            order = _safe_order(db, charlie.user_id, p)
            cancel_order(db, order.order_id, charlie.user_id, "buyer")
        for i in range(4):
            p = products[i % len(products)]
            order = _safe_order(db, charlie.user_id, p)
            ship_order(db, order.order_id, p.seller_id)
            complete_order(db, order.order_id, charlie.user_id)
        update_features_for_users(db, [charlie.user_id])
        refresh_trust(db, charlie.user_id, reason="Simulated frequent canceller history")
        print(f"  Done — {charlie.user_id}")

        # ── Diana stays as new user (700 / LOW) ───────────────────
        print(f"\n[8] Diana stays as new user — {diana.user_id} (700/LOW)")

        # ── Simulate Seller 1 — excellent seller ──────────────────
        print("\n[9] Simulating Seller 1 (excellent)…")
        for i in range(40):
            p = products[i % min(3, len(products))]
            order = _safe_order(db, alice.user_id, p)
            try:
                ship_order(db, order.order_id, sel1.user_id)
                complete_order(db, order.order_id, alice.user_id)
            except Exception:
                pass
        update_features_for_users(db, [sel1.user_id])
        refresh_trust(db, sel1.user_id, reason="Simulated excellent seller history")
        print(f"  Done — {sel1.user_id}")

        # ── Simulate Seller 2 — average seller with some cancellations ──
        print("\n[10] Simulating Seller 2 (average)…")
        for i in range(6):
            p = products[min(i, len(products)-1)]
            order = _safe_order(db, bob.user_id, p)
            try:
                cancel_order(db, order.order_id, sel2.user_id, "seller")
            except Exception:
                pass
        for i in range(12):
            p = products[min(i % 3, len(products)-1)]
            order = _safe_order(db, bob.user_id, p)
            try:
                ship_order(db, order.order_id, sel2.user_id)
                complete_order(db, order.order_id, bob.user_id)
            except Exception:
                pass
        update_features_for_users(db, [sel2.user_id])
        refresh_trust(db, sel2.user_id, reason="Simulated average seller history")
        print(f"  Done — {sel2.user_id}")

        # ── Final summary ──────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  Seed complete. Final Trust Scores:")
        print("=" * 60)
        for uid_str, label in [
            (alice.user_id, "Alice (reliable buyer)"),
            (bob.user_id,   "Bob (occasional buyer)"),
            (charlie.user_id, "Charlie (canceller)"),
            (diana.user_id, "Diana (new buyer)"),
            (sel1.user_id,  "Seller 1 (excellent)"),
            (sel2.user_id,  "Seller 2 (average)"),
        ]:
            from app.models.trust import TrustScore as TS
            ts = db.query(TS).filter(TS.user_id == uid_str).first()
            score = ts.trust_score if ts else "?"
            conf  = ts.confidence.value if ts else "?"
            tier  = ts.tier.value if ts else "?"
            print(f"  {label:<35} {uid_str}  →  {score}/1000  {tier}  [{conf}]")

        print("\n  Login credentials: <email> / Demo1234!")
        print("=" * 60 + "\n")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Seed failed: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
