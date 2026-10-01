"""
TrustGrid — Unit Tests: Confidence, Tier, Privileges, Blending, Smoothing
(spec §24-D, §24-E, §24-F, §24-G)

Run with:
    PYTHONPATH=backend pytest backend/tests/test_trust_core.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.confidence import get_confidence
from app.services.tier_service import get_tier
from app.services.privilege_engine import get_privileges
from app.core.constants import ML_BETA, SMOOTHING_ALPHA, INITIAL_TRUST_SCORE


# ── Confidence Boundary Tests (spec §24-D) ────────────────────────────────────

class TestConfidence:
    @pytest.mark.parametrize("n,expected", [
        (0,  "LOW"),
        (1,  "LOW"),
        (5,  "LOW"),
        (6,  "MEDIUM"),
        (15, "MEDIUM"),
        (30, "MEDIUM"),
        (31, "HIGH"),
        (100,"HIGH"),
        (999,"HIGH"),
    ])
    def test_boundaries(self, n, expected):
        assert get_confidence(n) == expected, f"confidence({n}) should be {expected}"


# ── Tier Boundary Tests (spec §24-E) ──────────────────────────────────────────

class TestTier:
    @pytest.mark.parametrize("score,expected", [
        (0,    "RESTRICTED"),
        (399,  "RESTRICTED"),
        (400,  "STANDARD"),
        (500,  "STANDARD"),
        (599,  "STANDARD"),
        (600,  "TRUSTED"),
        (700,  "TRUSTED"),
        (799,  "TRUSTED"),
        (800,  "ELITE"),
        (900,  "ELITE"),
        (1000, "ELITE"),
    ])
    def test_boundaries(self, score, expected):
        assert get_tier(score) == expected, f"tier({score}) should be {expected}"


# ── Blending Tests (spec §24-F) ───────────────────────────────────────────────

class TestBlending:
    """
    Formulas (spec §10):
        CombinedScore = (1−β)·RuleScore + β·MLScore
        LOW:    β=0.0  → CombinedScore = RuleScore
        MEDIUM: β=0.3  → CombinedScore = 0.7·RS + 0.3·ML
        HIGH:   β=0.5  → CombinedScore = 0.5·RS + 0.5·ML
    """
    def _blend(self, rule, ml, confidence):
        beta = ML_BETA[confidence]
        return (1.0 - beta) * rule + beta * ml

    def test_low_combined_equals_rule(self):
        """LOW: CombinedScore = RuleScore (ML has no influence)"""
        assert self._blend(84.0, 92.0, "LOW") == pytest.approx(84.0, abs=1e-6)

    def test_medium_blending(self):
        """MEDIUM: 0.7×RS + 0.3×ML"""
        result = self._blend(84.0, 92.0, "MEDIUM")
        assert result == pytest.approx(0.7 * 84.0 + 0.3 * 92.0, abs=1e-6)

    def test_high_blending(self):
        """HIGH: 0.5×RS + 0.5×ML (spec §10 example: RS=84, ML=92 → 88)"""
        result = self._blend(84.0, 92.0, "HIGH")
        assert result == pytest.approx(88.0, abs=1e-6)

    def test_beta_values_frozen(self):
        assert ML_BETA["LOW"]    == 0.0
        assert ML_BETA["MEDIUM"] == 0.3
        assert ML_BETA["HIGH"]   == 0.5


# ── Smoothing Tests (spec §24-G) ──────────────────────────────────────────────

class TestSmoothing:
    """
    Formula (spec §12):
        NewScore = (1−α)·PreviousScore + α·ModelScore
        LOW:    α=0.2
        MEDIUM: α=0.5
        HIGH:   α=0.8

    Spec smoothing test values (converted to 0–100 internal scale):
        Previous=700→70, Model=900→90, LOW    → 0.8×70 + 0.2×90 = 74.0  (740 / 1000)
        Previous=740→74, Model=880→88, MEDIUM → 0.5×74 + 0.5×88 = 81.0  (810 / 1000)
        Previous=810→81, Model=900→90, HIGH   → 0.2×81 + 0.8×90 = 88.2  (882 / 1000)
    """
    def _smooth(self, prev_100, model_100, confidence):
        alpha = SMOOTHING_ALPHA[confidence]
        return (1.0 - alpha) * prev_100 + alpha * model_100

    def test_spec_example_low(self):
        result = self._smooth(70.0, 90.0, "LOW")
        assert result == pytest.approx(74.0, abs=0.01)

    def test_spec_example_medium(self):
        result = self._smooth(74.0, 88.0, "MEDIUM")
        assert result == pytest.approx(81.0, abs=0.01)

    def test_spec_example_high(self):
        result = self._smooth(81.0, 90.0, "HIGH")
        assert result == pytest.approx(88.2, abs=0.01)

    def test_alpha_values_frozen(self):
        assert SMOOTHING_ALPHA["LOW"]    == 0.2
        assert SMOOTHING_ALPHA["MEDIUM"] == 0.5
        assert SMOOTHING_ALPHA["HIGH"]   == 0.8

    def test_no_score_jump_single_event_low(self):
        """A single event with LOW confidence must not produce a large jump."""
        prev = 70.0    # 700/1000
        model = 100.0  # best possible
        new = self._smooth(prev, model, "LOW")
        change = (new - prev) * 10  # in 0-1000 scale
        assert change <= 60, f"Score change {change} too large for LOW confidence single event"

    def test_initial_score_700(self):
        assert INITIAL_TRUST_SCORE == 700


# ── Privilege Tests ────────────────────────────────────────────────────────────

class TestPrivileges:
    def test_buyer_restricted(self):
        p = get_privileges(200, "LOW", "RESTRICTED", "buyer")
        assert "STANDARD_DELIVERY" in p
        assert "COD" not in p

    def test_buyer_standard(self):
        p = get_privileges(500, "MEDIUM", "STANDARD", "buyer")
        assert "COD" in p

    def test_buyer_trusted(self):
        p = get_privileges(700, "HIGH", "TRUSTED", "buyer")
        assert "COD" in p
        assert "VOUCHER_100" in p
        assert "FREE_DELIVERY" in p
        assert "PRIORITY_SUPPORT" in p

    def test_buyer_elite_high(self):
        p = get_privileges(900, "HIGH", "ELITE", "buyer")
        assert "VOUCHER_150" in p
        assert "FREE_DELIVERY" in p

    def test_buyer_elite_low_gates_voucher(self):
        """ELITE + LOW should not include VOUCHER_150."""
        p = get_privileges(850, "LOW", "ELITE", "buyer")
        assert "VOUCHER_150" not in p
        assert "FREE_DELIVERY" in p    # still gets other Elite benefits

    def test_seller_elite_low_gates_credit(self):
        """Seller ELITE + LOW should lose PROMO_CREDIT_500 and LOWER_PLATFORM_FEE."""
        p = get_privileges(900, "LOW", "ELITE", "seller")
        assert "PROMO_CREDIT_500" not in p
        assert "LOWER_PLATFORM_FEE" not in p
        assert "TRUSTED_SELLER_BADGE" in p   # still gets badge

    def test_seller_trusted(self):
        p = get_privileges(750, "HIGH", "TRUSTED", "seller")
        assert "TRUSTED_SELLER_BADGE" in p
        assert "SEARCH_VISIBILITY_BOOST" in p

    def test_privileges_are_deterministic(self):
        """Same inputs must always produce the same result."""
        p1 = get_privileges(700, "MEDIUM", "TRUSTED", "buyer")
        p2 = get_privileges(700, "MEDIUM", "TRUSTED", "buyer")
        assert p1 == p2
