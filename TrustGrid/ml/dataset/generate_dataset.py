"""
Synthetic Dataset Generator for TrustGrid ML pipeline.

Generates realistic behavioral event sequences for buyers and sellers,
then computes time-decayed feature vectors and binary reliability labels.

Output files (written to ml/dataset/)
--------------------------------------
  buyer_events.csv    — raw event log for buyers
  seller_events.csv   — raw event log for sellers
  buyer_features.csv  — feature vectors + labels (buyer model input)
  seller_features.csv — feature vectors + labels (seller model input)

Design
------
• Each synthetic "user" has a profile that controls their behavioral probabilities.
• Events are spread across a realistic time window (up to 365 days ago).
• Time decay (λ = ln(2)/90) is applied when computing feature vectors,
  so that recent events dominate over old ones.
• The ML target (label) is defined per-profile — it represents
  whether the user would be considered "reliably behaving" based on
  their behavioral pattern.
• No data leakage: features are computed from the event sequence only;
  the label is a profile-level annotation that is NOT derived from the
  feature values (it is an independent ground-truth annotation).

Run
---
  python ml/dataset/generate_dataset.py
"""
import math
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import pandas as pd

# Add project root to path so we can import profiles
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.dataset.profiles import (
    BUYER_PROFILES, SELLER_PROFILES, ACTIVITY_LEVELS,
)

# ── Constants ─────────────────────────────────────────────────────────────────

RANDOM_SEED       = 42
N_BUYERS          = 3_000    # number of synthetic buyer users
N_SELLERS         = 1_500    # number of synthetic seller users
MAX_HISTORY_DAYS  = 365      # events span up to 1 year in the past
HALF_LIFE_DAYS    = 90.0
LAMBDA            = math.log(2) / HALF_LIFE_DAYS   # ≈ 0.00770

OUTPUT_DIR = Path(__file__).resolve().parent


# ── Decay helper ──────────────────────────────────────────────────────────────

def decay_weight(age_days: float) -> float:
    return math.exp(-LAMBDA * age_days)


# ── Buyer event generation ────────────────────────────────────────────────────

def generate_buyer_events(
    user_id: str,
    profile: Dict[str, Any],
    now: datetime,
) -> List[Dict]:
    """Generate a sequence of buyer events for one synthetic user."""
    events = []
    rng = random.Random()   # local RNG so we don't disturb global seed

    low, high = ACTIVITY_LEVELS[profile["activity_level"]]
    n_orders = rng.randint(low // 3, max(1, high // 3))

    for i in range(n_orders):
        # Spread orders over the history window — older orders first
        age_days  = rng.uniform(0, MAX_HISTORY_DAYS)
        event_ts  = now - timedelta(days=age_days)

        # ORDER_PLACED
        events.append({
            "user_id":    user_id,
            "event_type": "ORDER_PLACED",
            "age_days":   age_days,
            "timestamp":  event_ts.isoformat(),
            "metadata":   {},
        })

        # Payment outcome
        if rng.random() < profile["payment_success_prob"]:
            events.append({
                "user_id":    user_id,
                "event_type": "PAYMENT_SUCCESS",
                "age_days":   age_days,
                "timestamp":  event_ts.isoformat(),
                "metadata":   {},
            })
            paid = True
        else:
            events.append({
                "user_id":    user_id,
                "event_type": "PAYMENT_FAILED",
                "age_days":   age_days,
                "timestamp":  event_ts.isoformat(),
                "metadata":   {},
            })
            paid = False

        if not paid:
            continue

        # Buyer cancellation
        if rng.random() < profile["cancellation_rate"]:
            events.append({
                "user_id":    user_id,
                "event_type": "ORDER_CANCELLED",
                "age_days":   age_days + 0.5,
                "timestamp":  (event_ts + timedelta(hours=12)).isoformat(),
                "metadata":   {},
            })
            continue

        # Order completion
        if rng.random() < profile["order_completion_prob"]:
            complete_age = age_days - rng.uniform(3, 10)   # completed some days after placing
            complete_age = max(0, complete_age)
            events.append({
                "user_id":    user_id,
                "event_type": "ORDER_COMPLETED",
                "age_days":   complete_age,
                "timestamp":  (now - timedelta(days=complete_age)).isoformat(),
                "metadata":   {},
            })

            # Return request (after completion)
            if rng.random() < profile["return_rate"]:
                return_age = max(0, complete_age - rng.uniform(1, 5))
                events.append({
                    "user_id":    user_id,
                    "event_type": "RETURN_REQUESTED",
                    "age_days":   return_age,
                    "timestamp":  (now - timedelta(days=return_age)).isoformat(),
                    "metadata":   {},
                })

            # Review
            if rng.random() < profile["review_prob"]:
                review_age = max(0, complete_age - rng.uniform(0.5, 3))
                events.append({
                    "user_id":    user_id,
                    "event_type": "REVIEW_SUBMITTED",
                    "age_days":   review_age,
                    "timestamp":  (now - timedelta(days=review_age)).isoformat(),
                    "metadata":   {},
                })

    # Referral (one-time, profile probability)
    if rng.random() < profile["referral_prob"]:
        ref_age = rng.uniform(0, MAX_HISTORY_DAYS)
        events.append({
            "user_id":    user_id,
            "event_type": "REFERRAL_COMPLETED",
            "age_days":   ref_age,
            "timestamp":  (now - timedelta(days=ref_age)).isoformat(),
            "metadata":   {},
        })

    return events


# ── Seller event generation ───────────────────────────────────────────────────

def generate_seller_events(
    user_id: str,
    profile: Dict[str, Any],
    now: datetime,
) -> List[Dict]:
    """Generate a sequence of seller events for one synthetic user."""
    events = []
    rng = random.Random()

    low, high = ACTIVITY_LEVELS[profile["activity_level"]]
    n_orders = rng.randint(low // 3, max(1, high // 3))

    # Products listed
    n_listed = rng.randint(*profile["products_listed_range"])
    for _ in range(n_listed):
        age_days = rng.uniform(10, MAX_HISTORY_DAYS)
        events.append({
            "user_id":    user_id,
            "event_type": "PRODUCT_LISTED",
            "age_days":   age_days,
            "timestamp":  (now - timedelta(days=age_days)).isoformat(),
            "metadata":   {},
        })

    for i in range(n_orders):
        age_days = rng.uniform(0, MAX_HISTORY_DAYS)
        event_ts = now - timedelta(days=age_days)

        # Seller cancellation
        if rng.random() < profile["seller_cancellation_rate"]:
            events.append({
                "user_id":    user_id,
                "event_type": "SELLER_CANCELLED",
                "age_days":   age_days,
                "timestamp":  event_ts.isoformat(),
                "metadata":   {},
            })
            continue

        # Fulfillment
        if rng.random() < profile["fulfillment_rate"]:
            ship_age = max(0, age_days - rng.uniform(1, 5))
            events.append({
                "user_id":    user_id,
                "event_type": "ORDER_FULFILLED",
                "age_days":   ship_age,
                "timestamp":  (now - timedelta(days=ship_age)).isoformat(),
                "metadata":   {},
            })

            # Delivered / late
            deliver_age = max(0, ship_age - rng.uniform(3, 10))
            if rng.random() < profile["on_time_delivery_prob"]:
                events.append({
                    "user_id":    user_id,
                    "event_type": "ORDER_DELIVERED",
                    "age_days":   deliver_age,
                    "timestamp":  (now - timedelta(days=deliver_age)).isoformat(),
                    "metadata":   {},
                })
            else:
                events.append({
                    "user_id":    user_id,
                    "event_type": "ORDER_LATE",
                    "age_days":   deliver_age,
                    "timestamp":  (now - timedelta(days=deliver_age)).isoformat(),
                    "metadata":   {},
                })
                events.append({
                    "user_id":    user_id,
                    "event_type": "ORDER_DELIVERED",
                    "age_days":   deliver_age,
                    "timestamp":  (now - timedelta(days=deliver_age)).isoformat(),
                    "metadata":   {},
                })

            # Rating received
            rating = max(1, min(5, round(
                rng.gauss(profile["avg_rating"], profile["rating_std"])
            )))
            events.append({
                "user_id":    user_id,
                "event_type": "REVIEW_RECEIVED",
                "age_days":   deliver_age,
                "timestamp":  (now - timedelta(days=deliver_age)).isoformat(),
                "metadata":   {"rating": rating},
            })

            # Return request + response
            if rng.random() < 0.10:  # 10% of orders get a return request
                ret_age = max(0, deliver_age - rng.uniform(1, 7))
                events.append({
                    "user_id":    user_id,
                    "event_type": "RETURN_REQUEST_RECEIVED",
                    "age_days":   ret_age,
                    "timestamp":  (now - timedelta(days=ret_age)).isoformat(),
                    "metadata":   {},
                })
                if rng.random() < profile["return_response_rate"]:
                    events.append({
                        "user_id":    user_id,
                        "event_type": "RETURN_RESOLVED",
                        "age_days":   max(0, ret_age - 1),
                        "timestamp":  (now - timedelta(days=max(0, ret_age - 1))).isoformat(),
                        "metadata":   {},
                    })

    return events


# ── Feature computation from raw events ──────────────────────────────────────

def compute_buyer_features(events: List[Dict]) -> Dict[str, float]:
    """
    Compute time-decayed feature vector for a buyer from their raw events.
    Uses the same decay formula as the production feature_engine.
    """
    w_placed = w_completed = w_cancelled = 0.0
    w_pay_attempts = w_pay_success = w_pay_failed = 0.0
    w_returns = 0.0
    referral_count = review_count = 0
    total_weight = 0.0

    for ev in events:
        w = decay_weight(ev["age_days"])
        total_weight += w
        et = ev["event_type"]

        if et == "ORDER_PLACED":
            w_placed       += w
            w_pay_attempts += w
        elif et == "ORDER_COMPLETED":
            w_completed    += w
        elif et == "ORDER_CANCELLED":
            w_cancelled    += w
        elif et == "PAYMENT_SUCCESS":
            w_pay_success  += w
        elif et == "PAYMENT_FAILED":
            w_pay_failed   += w
            w_pay_attempts += w
        elif et == "RETURN_REQUESTED":
            w_returns      += w
        elif et == "REFERRAL_COMPLETED":
            referral_count += 1
        elif et == "REVIEW_SUBMITTED":
            review_count   += 1

    def safe_rate(n, d):
        return min(1.0, max(0.0, n / d)) if d > 0 else 1.0

    return {
        "order_completion_rate":  safe_rate(w_completed, w_placed),
        "return_rate":            safe_rate(w_returns,   w_completed),
        "payment_success_rate":   safe_rate(w_pay_success, w_pay_attempts),
        "cancellation_rate":      safe_rate(w_cancelled,   w_placed),
        "referral_count":         float(referral_count),
        "review_count":           float(review_count),
        "total_orders":           float(round(w_placed)),
        "completed_orders":       float(round(w_completed)),
        "total_cancellations":    float(round(w_cancelled)),
        "total_returns":          float(round(w_returns)),
        "decayed_event_weight":   round(total_weight, 4),
    }


def compute_seller_features(events: List[Dict]) -> Dict[str, float]:
    """
    Compute time-decayed feature vector for a seller from their raw events.
    """
    w_fulfilled = w_delivered = w_late = w_seller_cancelled = 0.0
    w_return_requests = w_return_resolved = 0.0
    w_ratings_sum = w_ratings_count = 0.0
    products_listed = 0
    total_weight = 0.0

    for ev in events:
        w = decay_weight(ev["age_days"])
        total_weight += w
        et = ev["event_type"]

        if et == "ORDER_FULFILLED":
            w_fulfilled        += w
        elif et == "ORDER_DELIVERED":
            w_delivered        += w
        elif et == "ORDER_LATE":
            w_late             += w
        elif et == "SELLER_CANCELLED":
            w_seller_cancelled += w
        elif et == "RETURN_REQUEST_RECEIVED":
            w_return_requests  += w
        elif et == "RETURN_RESOLVED":
            w_return_resolved  += w
        elif et == "REVIEW_RECEIVED":
            rating = ev.get("metadata", {}).get("rating", 0)
            if rating:
                w_ratings_sum   += w * float(rating)
                w_ratings_count += w
        elif et == "PRODUCT_LISTED":
            products_listed += 1

    def safe_rate(n, d):
        return min(1.0, max(0.0, n / d)) if d > 0 else 1.0

    fulfillment_denom = w_fulfilled + w_seller_cancelled
    avg_rating = (w_ratings_sum / w_ratings_count) if w_ratings_count > 0 else 0.0

    return {
        "fulfillment_rate":          safe_rate(w_fulfilled,       fulfillment_denom),
        "late_delivery_rate":        safe_rate(w_late,            w_delivered),
        "avg_rating_received":       round(avg_rating, 3),
        "return_response_rate":      safe_rate(w_return_resolved, w_return_requests),
        "products_listed":           float(products_listed),
        "fulfilled_orders":          float(round(w_fulfilled)),
        "seller_cancellations":      float(round(w_seller_cancelled)),
        "on_time_deliveries":        float(round(w_delivered - w_late)),
        "late_deliveries":           float(round(w_late)),
        "return_requests_received":  float(round(w_return_requests)),
        "returns_responded":         float(round(w_return_resolved)),
        "decayed_event_weight":      round(total_weight, 4),
    }


# ── Main generation loop ──────────────────────────────────────────────────────

def generate_buyers(n: int, now: datetime) -> tuple:
    """Returns (events_df, features_df)."""
    np.random.seed(RANDOM_SEED)
    random.seed(RANDOM_SEED)

    weights = [p["weight"] for p in BUYER_PROFILES]
    # Normalise weights
    total_w = sum(weights)
    weights = [w / total_w for w in weights]

    all_events   = []
    all_features = []

    for i in range(n):
        profile_idx = np.random.choice(len(BUYER_PROFILES), p=weights)
        profile     = BUYER_PROFILES[profile_idx]
        user_id     = f"BUY-SYN-{i+1:05d}"

        events = generate_buyer_events(user_id, profile, now)
        for ev in events:
            ev["profile"] = profile["name"]
            ev["label"]   = profile["label"]
        all_events.extend(events)

        features = compute_buyer_features(events)
        features["user_id"]  = user_id
        features["profile"]  = profile["name"]
        features["label"]    = profile["label"]
        all_features.append(features)

    events_df   = pd.DataFrame(all_events)
    features_df = pd.DataFrame(all_features)
    return events_df, features_df


def generate_sellers(n: int, now: datetime) -> tuple:
    """Returns (events_df, features_df)."""
    np.random.seed(RANDOM_SEED + 1)
    random.seed(RANDOM_SEED + 1)

    weights = [p["weight"] for p in SELLER_PROFILES]
    total_w = sum(weights)
    weights = [w / total_w for w in weights]

    all_events   = []
    all_features = []

    for i in range(n):
        profile_idx = np.random.choice(len(SELLER_PROFILES), p=weights)
        profile     = SELLER_PROFILES[profile_idx]
        user_id     = f"SEL-SYN-{i+1:05d}"

        events = generate_seller_events(user_id, profile, now)
        for ev in events:
            ev["profile"] = profile["name"]
            ev["label"]   = profile["label"]
        all_events.extend(events)

        features = compute_seller_features(events)
        features["user_id"]  = user_id
        features["profile"]  = profile["name"]
        features["label"]    = profile["label"]
        all_features.append(features)

    events_df   = pd.DataFrame(all_events)
    features_df = pd.DataFrame(all_features)
    return events_df, features_df


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    now = datetime.now(timezone.utc)
    print("=" * 60)
    print("TrustGrid Synthetic Dataset Generator")
    print("=" * 60)

    print(f"\n[1/4] Generating {N_BUYERS} synthetic buyers ...")
    buyer_events, buyer_features = generate_buyers(N_BUYERS, now)
    print(f"      → {len(buyer_events):,} buyer events generated")
    print(f"      → {len(buyer_features):,} buyer feature vectors")
    print(f"      → Label distribution: {dict(buyer_features['label'].value_counts().sort_index())}")

    print(f"\n[2/4] Generating {N_SELLERS} synthetic sellers ...")
    seller_events, seller_features = generate_sellers(N_SELLERS, now)
    print(f"      → {len(seller_events):,} seller events generated")
    print(f"      → {len(seller_features):,} seller feature vectors")
    print(f"      → Label distribution: {dict(seller_features['label'].value_counts().sort_index())}")

    print(f"\n[3/4] Saving event logs ...")
    buyer_events.to_csv(OUTPUT_DIR / "buyer_events.csv",   index=False)
    seller_events.to_csv(OUTPUT_DIR / "seller_events.csv", index=False)
    print(f"      → buyer_events.csv  ({len(buyer_events):,} rows)")
    print(f"      → seller_events.csv ({len(seller_events):,} rows)")

    print(f"\n[4/4] Saving feature datasets ...")
    buyer_features.to_csv(OUTPUT_DIR / "buyer_features.csv",   index=False)
    seller_features.to_csv(OUTPUT_DIR / "seller_features.csv", index=False)
    print(f"      → buyer_features.csv  ({len(buyer_features):,} rows)")
    print(f"      → seller_features.csv ({len(seller_features):,} rows)")

    print("\n" + "=" * 60)
    print("Dataset generation complete.")
    print("=" * 60)
    print("\nBuyer feature summary:")
    print(buyer_features.drop(columns=["user_id", "profile", "label"]).describe().round(3).to_string())
    print("\nSeller feature summary:")
    print(seller_features.drop(columns=["user_id", "profile", "label"]).describe().round(3).to_string())


if __name__ == "__main__":
    main()
