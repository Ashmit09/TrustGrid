"""
TrustGrid — Synthetic Dataset Generator (spec §23)

Generates 50,000 event records for realistic buyer and seller profiles.
The data contains realistic behavioral relationships and label overlap —
NOT perfect separability.

Buyer profiles (spec §23):
    reliable, occasional_reliable, frequent_returner,
    frequent_canceller, poor_payment, mixed

Seller profiles:
    excellent, reliable, slow, high_cancellation,
    poor_return_handling, mixed

Output: TrustGrid/ml/dataset/buyer_events.csv
         TrustGrid/ml/dataset/seller_events.csv
         TrustGrid/ml/dataset/buyer_features.csv    (pre-built feature rows)
         TrustGrid/ml/dataset/seller_features.csv

Usage:
    cd TrustGrid && source .venv/bin/activate
    PYTHONPATH=backend python ml/dataset/generate.py
"""
import sys, os
import math
import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple

import pandas as pd
import numpy as np

# Allow imports from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from app.services.feature_engine import build_buyer_features, build_seller_features
from app.core.constants import DECAY_LAMBDA

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

N_BUYERS  = 3000
N_SELLERS = 1000
REF_DATE  = datetime(2024, 6, 1, tzinfo=timezone.utc)   # fixed reference for reproducibility


# ── Profile definitions ────────────────────────────────────────────────────────

BUYER_PROFILES = {
    "reliable": {
        "n_orders": (20, 60),
        "completion_prob": 0.95,
        "payment_success_prob": 0.98,
        "return_prob": 0.05,
        "problematic_return_prob": 0.02,
        "review_prob": 0.60,
        "referral_prob": 0.20,
        "label": 1,  # reliable future behavior
    },
    "occasional_reliable": {
        "n_orders": (3, 15),
        "completion_prob": 0.88,
        "payment_success_prob": 0.94,
        "return_prob": 0.06,
        "problematic_return_prob": 0.03,
        "review_prob": 0.40,
        "referral_prob": 0.10,
        "label": 1,
    },
    "frequent_returner": {
        "n_orders": (15, 40),
        "completion_prob": 0.90,
        "payment_success_prob": 0.95,
        "return_prob": 0.35,
        "problematic_return_prob": 0.20,
        "review_prob": 0.30,
        "referral_prob": 0.05,
        "label": 0,
    },
    "frequent_canceller": {
        "n_orders": (10, 40),
        "completion_prob": 0.45,
        "payment_success_prob": 0.88,
        "return_prob": 0.05,
        "problematic_return_prob": 0.02,
        "review_prob": 0.10,
        "referral_prob": 0.03,
        "label": 0,
    },
    "poor_payment": {
        "n_orders": (10, 30),
        "completion_prob": 0.82,
        "payment_success_prob": 0.55,
        "return_prob": 0.08,
        "problematic_return_prob": 0.04,
        "review_prob": 0.15,
        "referral_prob": 0.05,
        "label": 0,
    },
    "mixed": {
        "n_orders": (8, 35),
        "completion_prob": 0.70,
        "payment_success_prob": 0.78,
        "return_prob": 0.15,
        "problematic_return_prob": 0.08,
        "review_prob": 0.25,
        "referral_prob": 0.08,
        "label": 0,  # 50% chance, label is randomized below
    },
}

SELLER_PROFILES = {
    "excellent": {
        "n_orders": (40, 120),
        "fulfillment_prob": 0.98,
        "on_time_prob": 0.96,
        "avg_rating": (4.5, 5.0),
        "resolution_prob": 0.95,
        "n_products": (8, 20),
        "label": 1,
    },
    "reliable": {
        "n_orders": (20, 80),
        "fulfillment_prob": 0.90,
        "on_time_prob": 0.85,
        "avg_rating": (3.8, 4.6),
        "resolution_prob": 0.80,
        "n_products": (5, 15),
        "label": 1,
    },
    "slow": {
        "n_orders": (15, 50),
        "fulfillment_prob": 0.88,
        "on_time_prob": 0.50,
        "avg_rating": (3.0, 4.0),
        "resolution_prob": 0.70,
        "n_products": (3, 10),
        "label": 0,
    },
    "high_cancellation": {
        "n_orders": (15, 60),
        "fulfillment_prob": 0.40,
        "on_time_prob": 0.75,
        "avg_rating": (2.5, 3.5),
        "resolution_prob": 0.65,
        "n_products": (2, 8),
        "label": 0,
    },
    "poor_return_handling": {
        "n_orders": (15, 50),
        "fulfillment_prob": 0.85,
        "on_time_prob": 0.80,
        "avg_rating": (2.0, 3.5),
        "resolution_prob": 0.25,
        "n_products": (3, 12),
        "label": 0,
    },
    "mixed": {
        "n_orders": (10, 40),
        "fulfillment_prob": 0.72,
        "on_time_prob": 0.65,
        "avg_rating": (2.8, 4.0),
        "resolution_prob": 0.55,
        "n_products": (2, 10),
        "label": 0,
    },
}


# ── Event generators ───────────────────────────────────────────────────────────

def random_ts(ref: datetime, max_age_days: int = 365) -> datetime:
    """Random timestamp in the past up to max_age_days before ref."""
    days_ago = random.uniform(0, max_age_days)
    return ref - timedelta(days=days_ago)


def generate_buyer_events(user_id: str, profile: str, ref: datetime) -> List[Dict]:
    p = BUYER_PROFILES[profile]
    n = random.randint(*p["n_orders"])
    events = []

    for _ in range(n):
        ts = random_ts(ref)
        # ORDER_PLACED always occurs
        events.append({"user_id": user_id, "event_type": "ORDER_PLACED",
                        "created_at": ts, "metadata_": {}})

        completed = random.random() < p["completion_prob"]
        if completed:
            events.append({"user_id": user_id, "event_type": "ORDER_COMPLETED",
                            "created_at": ts + timedelta(hours=random.uniform(1, 48)),
                            "metadata_": {}})
            # Payment
            pay_success = random.random() < p["payment_success_prob"]
            events.append({"user_id": user_id,
                            "event_type": "PAYMENT_SUCCESS" if pay_success else "PAYMENT_FAILED",
                            "created_at": ts + timedelta(minutes=random.uniform(5, 120)),
                            "metadata_": {}})
            # Possible return
            if random.random() < p["return_prob"]:
                is_prob = random.random() < p["problematic_return_prob"]
                events.append({"user_id": user_id, "event_type": "RETURN_REQUESTED",
                                "created_at": ts + timedelta(days=random.uniform(1, 14)),
                                "metadata_": {"is_problematic": is_prob}})
                if not is_prob:
                    events.append({"user_id": user_id, "event_type": "RETURN_COMPLETED",
                                    "created_at": ts + timedelta(days=random.uniform(5, 21)),
                                    "metadata_": {}})
            # Possible review
            if random.random() < p["review_prob"]:
                events.append({"user_id": user_id, "event_type": "REVIEW_SUBMITTED",
                                "created_at": ts + timedelta(days=random.uniform(2, 10)),
                                "metadata_": {"rating": random.uniform(3.5, 5.0)}})
        else:
            events.append({"user_id": user_id, "event_type": "ORDER_CANCELLED",
                            "created_at": ts + timedelta(hours=random.uniform(0.5, 12)),
                            "metadata_": {}})

    # Referrals
    n_ref = int(np.random.poisson(p["referral_prob"] * 5))
    for _ in range(n_ref):
        events.append({"user_id": user_id, "event_type": "REFERRAL_COMPLETED",
                        "created_at": random_ts(ref),
                        "metadata_": {}})

    return events


def generate_seller_events(user_id: str, profile: str, ref: datetime) -> List[Dict]:
    p = SELLER_PROFILES[profile]
    n = random.randint(*p["n_orders"])
    events = []

    # Products
    n_prod = random.randint(*p["n_products"])
    for _ in range(n_prod):
        events.append({"user_id": user_id, "event_type": "PRODUCT_LISTED",
                        "created_at": random_ts(ref, 400), "metadata_": {}})

    for _ in range(n):
        ts = random_ts(ref)
        events.append({"user_id": user_id, "event_type": "ORDER_ACCEPTED",
                        "created_at": ts, "metadata_": {}})

        fulfilled = random.random() < p["fulfillment_prob"]
        if fulfilled:
            events.append({"user_id": user_id, "event_type": "ORDER_FULFILLED",
                            "created_at": ts + timedelta(hours=random.uniform(1, 6)),
                            "metadata_": {}})
            on_time = random.random() < p["on_time_prob"]
            deliver_type = "ORDER_DELIVERED" if on_time else "ORDER_LATE"
            events.append({"user_id": user_id, "event_type": deliver_type,
                            "created_at": ts + timedelta(days=random.uniform(1, 10)),
                            "metadata_": {}})
            if on_time:
                events.append({"user_id": user_id, "event_type": "ORDER_SHIPPED",
                                "created_at": ts + timedelta(hours=random.uniform(6, 48)),
                                "metadata_": {}})
            # Review received
            if random.random() < 0.4:
                lo, hi = p["avg_rating"]
                rating = random.uniform(lo, hi)
                events.append({"user_id": user_id, "event_type": "REVIEW_RECEIVED",
                                "created_at": ts + timedelta(days=random.uniform(2, 12)),
                                "metadata_": {"rating": rating}})
            # Return received
            if random.random() < 0.12:
                events.append({"user_id": user_id, "event_type": "RETURN_REQUEST_RECEIVED",
                                "created_at": ts + timedelta(days=random.uniform(2, 10)),
                                "metadata_": {}})
                if random.random() < p["resolution_prob"]:
                    events.append({"user_id": user_id, "event_type": "RETURN_RESOLVED",
                                    "created_at": ts + timedelta(days=random.uniform(5, 20)),
                                    "metadata_": {}})
        else:
            events.append({"user_id": user_id, "event_type": "SELLER_CANCELLED",
                            "created_at": ts + timedelta(hours=random.uniform(0.5, 24)),
                            "metadata_": {}})

    return events


# ── Feature row builder ────────────────────────────────────────────────────────

def events_to_feature_row_buyer(user_id: str, events: List[Dict], profile: str, ref: datetime) -> Dict:
    features = build_buyer_features(events, reference_ts=ref)
    p = BUYER_PROFILES[profile]
    # For mixed profile randomize label
    label = p["label"]
    if profile == "mixed":
        label = 1 if random.random() < 0.45 else 0
    features["user_id"] = user_id
    features["profile"] = profile
    features["label"] = label
    return features


def events_to_feature_row_seller(user_id: str, events: List[Dict], profile: str, ref: datetime) -> Dict:
    features = build_seller_features(events, reference_ts=ref)
    p = SELLER_PROFILES[profile]
    label = p["label"]
    if profile == "mixed":
        label = 1 if random.random() < 0.45 else 0
    features["user_id"] = user_id
    features["profile"] = profile
    features["label"] = label
    return features


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    out_dir = os.path.join(os.path.dirname(__file__))
    os.makedirs(out_dir, exist_ok=True)

    # ── Buyers ───────────────────────────────────────────────────────────────
    print(f"Generating {N_BUYERS} buyer feature rows …")
    buyer_rows = []
    buyer_profiles = list(BUYER_PROFILES.keys())
    for i in range(N_BUYERS):
        uid = f"BUY-{10001 + i}"
        profile = buyer_profiles[i % len(buyer_profiles)]
        events = generate_buyer_events(uid, profile, REF_DATE)
        row = events_to_feature_row_buyer(uid, events, profile, REF_DATE)
        buyer_rows.append(row)
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{N_BUYERS} buyers done")

    buyer_df = pd.DataFrame(buyer_rows)
    buyer_df.to_csv(os.path.join(out_dir, "buyer_features.csv"), index=False)
    print(f"  → buyer_features.csv  shape={buyer_df.shape}  label_dist={buyer_df['label'].value_counts().to_dict()}")

    # ── Sellers ───────────────────────────────────────────────────────────────
    print(f"\nGenerating {N_SELLERS} seller feature rows …")
    seller_rows = []
    seller_profiles = list(SELLER_PROFILES.keys())
    for i in range(N_SELLERS):
        uid = f"SEL-{20001 + i}"
        profile = seller_profiles[i % len(seller_profiles)]
        events = generate_seller_events(uid, profile, REF_DATE)
        row = events_to_feature_row_seller(uid, events, profile, REF_DATE)
        seller_rows.append(row)
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{N_SELLERS} sellers done")

    seller_df = pd.DataFrame(seller_rows)
    seller_df.to_csv(os.path.join(out_dir, "seller_features.csv"), index=False)
    print(f"  → seller_features.csv shape={seller_df.shape}  label_dist={seller_df['label'].value_counts().to_dict()}")

    print("\nDataset generation complete.")


if __name__ == "__main__":
    main()
