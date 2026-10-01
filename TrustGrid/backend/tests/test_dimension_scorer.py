"""
TrustGrid — Unit Tests: Dimension Scorer (spec §24-B, §24-C)

Run with:
    PYTHONPATH=backend pytest backend/tests/test_dimension_scorer.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.dimension_scorer import (
    buyer_dimensions, seller_dimensions, compute_rule_score, calculate_dimensions
)


# ── Buyer Dimensions ──────────────────────────────────────────────────────────

class TestBuyerDimensions:

    def _features_all_positive(self):
        return {
            "decayed_completion_rate": 1.0,
            "decayed_problematic_return_rate": 0.0,
            "decayed_payment_success_rate": 1.0,
            "decayed_cancellation_rate": 0.0,
            "engagement_quality": 1.0,
        }

    def _features_all_negative(self):
        return {
            "decayed_completion_rate": 0.0,
            "decayed_problematic_return_rate": 1.0,
            "decayed_payment_success_rate": 0.0,
            "decayed_cancellation_rate": 1.0,
            "engagement_quality": 0.0,
        }

    def test_all_positive_gives_100(self):
        dims = buyer_dimensions(self._features_all_positive())
        for k, v in dims.items():
            assert v == pytest.approx(100.0, abs=1e-4), f"{k} should be 100, got {v}"

    def test_all_negative_gives_0(self):
        dims = buyer_dimensions(self._features_all_negative())
        for k, v in dims.items():
            assert v == pytest.approx(0.0, abs=1e-4), f"{k} should be 0, got {v}"

    def test_mixed_between_0_and_100(self):
        features = {
            "decayed_completion_rate": 0.7,
            "decayed_problematic_return_rate": 0.1,
            "decayed_payment_success_rate": 0.9,
            "decayed_cancellation_rate": 0.2,
            "engagement_quality": 0.3,
        }
        dims = buyer_dimensions(features)
        for k, v in dims.items():
            assert 0.0 <= v <= 100.0, f"{k} = {v} out of range"

    def test_dimensions_never_negative(self):
        # Extreme negative input should still clamp to 0
        features = {
            "decayed_completion_rate": -0.5,
            "decayed_problematic_return_rate": 2.0,
            "decayed_payment_success_rate": -1.0,
            "decayed_cancellation_rate": 1.5,
            "engagement_quality": -0.1,
        }
        dims = buyer_dimensions(features)
        for k, v in dims.items():
            assert v >= 0.0, f"{k} should not be negative"

    def test_dimensions_never_exceed_100(self):
        features = {
            "decayed_completion_rate": 1.5,
            "decayed_problematic_return_rate": -0.5,
            "decayed_payment_success_rate": 2.0,
            "decayed_cancellation_rate": -1.0,
            "engagement_quality": 5.0,
        }
        dims = buyer_dimensions(features)
        for k, v in dims.items():
            assert v <= 100.0, f"{k} should not exceed 100"

    def test_no_eligible_evidence_cold_start(self):
        """With no evidence (all defaults 0.5), dimensions stay around 50."""
        features = {
            "decayed_completion_rate": 0.5,
            "decayed_problematic_return_rate": 0.0,
            "decayed_payment_success_rate": 0.5,
            "decayed_cancellation_rate": 0.5,
            "engagement_quality": 0.0,
        }
        dims = buyer_dimensions(features)
        # All should be deterministic, not None or NaN
        for k, v in dims.items():
            assert isinstance(v, float), f"{k} should be float"
            assert not (v != v), f"{k} should not be NaN"


# ── Seller Dimensions ──────────────────────────────────────────────────────────

class TestSellerDimensions:

    def _features_all_positive(self):
        return {
            "decayed_fulfillment_rate": 1.0,
            "decayed_late_delivery_rate": 0.0,
            "avg_rating_decayed": 5.0,
            "decayed_resolution_rate": 1.0,
            "platform_reliability": 1.0,
        }

    def _features_all_negative(self):
        return {
            "decayed_fulfillment_rate": 0.0,
            "decayed_late_delivery_rate": 1.0,
            "avg_rating_decayed": 1.0,    # 1 star → 0
            "decayed_resolution_rate": 0.0,
            "platform_reliability": 0.0,
        }

    def test_all_positive_gives_100(self):
        dims = seller_dimensions(self._features_all_positive())
        for k, v in dims.items():
            assert v == pytest.approx(100.0, abs=1e-4), f"{k} = {v}"

    def test_all_negative_gives_0(self):
        dims = seller_dimensions(self._features_all_negative())
        for k, v in dims.items():
            assert v == pytest.approx(0.0, abs=1e-4), f"{k} = {v}"

    def test_rating_scale(self):
        """1 star=0, 3 stars=50, 5 stars=100"""
        for rating, expected in [(1.0, 0.0), (3.0, 50.0), (5.0, 100.0)]:
            f = {"decayed_fulfillment_rate": 0.5, "decayed_late_delivery_rate": 0.5,
                 "avg_rating_decayed": rating, "decayed_resolution_rate": 0.5,
                 "platform_reliability": 0.5}
            d = seller_dimensions(f)
            assert d["customer_satisfaction"] == pytest.approx(expected, abs=0.01), \
                f"rating {rating} → expected {expected}, got {d['customer_satisfaction']}"

    def test_no_negative_no_exceed_100(self):
        dims = seller_dimensions(self._features_all_negative())
        for k, v in dims.items():
            assert 0.0 <= v <= 100.0


# ── Rule Score ────────────────────────────────────────────────────────────────

class TestRuleScore:

    def test_all_100_gives_100(self):
        dims = {k: 100.0 for k in ["order_reliability", "return_behaviour",
                                    "payment_reliability", "cancellation_behaviour",
                                    "platform_engagement"]}
        assert compute_rule_score(dims, "buyer") == pytest.approx(100.0, abs=1e-4)

    def test_all_0_gives_0(self):
        dims = {k: 0.0 for k in ["order_reliability", "return_behaviour",
                                   "payment_reliability", "cancellation_behaviour",
                                   "platform_engagement"]}
        assert compute_rule_score(dims, "buyer") == pytest.approx(0.0, abs=1e-4)

    def test_spec_numerical_check(self):
        """
        Spec §8 example:
            D1=92, D2=84, D3=96, D4=88, D5=80
            RuleScore = 0.25(92)+0.25(84)+0.20(96)+0.15(88)+0.15(80) = 88.4
        """
        dims = {
            "order_reliability":      92.0,
            "return_behaviour":       84.0,
            "payment_reliability":    96.0,
            "cancellation_behaviour": 88.0,
            "platform_engagement":    80.0,
        }
        score = compute_rule_score(dims, "buyer")
        assert score == pytest.approx(88.4, abs=0.01)

    def test_seller_all_100(self):
        dims = {k: 100.0 for k in ["order_fulfillment", "delivery_performance",
                                    "customer_satisfaction", "return_dispute_handling",
                                    "platform_reliability"]}
        assert compute_rule_score(dims, "seller") == pytest.approx(100.0, abs=1e-4)

    def test_trust_score_1000_from_rule_100(self):
        """All dims=100 → RuleScore=100 → TrustScore=1000 (before smoothing)."""
        dims = {k: 100.0 for k in ["order_reliability", "return_behaviour",
                                    "payment_reliability", "cancellation_behaviour",
                                    "platform_engagement"]}
        rule = compute_rule_score(dims, "buyer")
        assert rule == pytest.approx(100.0, abs=1e-4)
        trust_score = round(rule * 10)
        assert trust_score == 1000

    def test_dispatcher_buyer(self):
        features = {
            "decayed_completion_rate": 1.0,
            "decayed_problematic_return_rate": 0.0,
            "decayed_payment_success_rate": 1.0,
            "decayed_cancellation_rate": 0.0,
            "engagement_quality": 1.0,
        }
        dims = calculate_dimensions(features, "buyer")
        assert "order_reliability" in dims
        assert "platform_engagement" in dims

    def test_dispatcher_seller(self):
        features = {
            "decayed_fulfillment_rate": 0.9,
            "decayed_late_delivery_rate": 0.1,
            "avg_rating_decayed": 4.5,
            "decayed_resolution_rate": 0.8,
            "platform_reliability": 0.5,
        }
        dims = calculate_dimensions(features, "seller")
        assert "order_fulfillment" in dims
        assert "customer_satisfaction" in dims
