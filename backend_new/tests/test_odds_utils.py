"""Unit tests for app/utils/odds_utils.py — pure math, no mocking."""

import pytest

from app.utils.odds_utils import american_from_prob, implied_prob_from_american


class TestImpliedProbFromAmerican:
    def test_positive_odds(self):
        # +250 → 100 / (250 + 100) ≈ 0.2857
        assert implied_prob_from_american(250) == pytest.approx(100 / 350, rel=1e-4)

    def test_negative_odds(self):
        # -150 → 150 / (150 + 100) = 0.6000
        assert implied_prob_from_american(-150) == pytest.approx(150 / 250, rel=1e-4)

    def test_even_money(self):
        # +100 → 100 / 200 = 0.5
        assert implied_prob_from_american(100) == pytest.approx(0.5, rel=1e-4)

    def test_heavy_favorite(self):
        # -300 → 300 / 400 = 0.75
        assert implied_prob_from_american(-300) == pytest.approx(0.75, rel=1e-4)

    def test_heavy_underdog(self):
        # +500 → 100 / 600 ≈ 0.1667
        assert implied_prob_from_american(500) == pytest.approx(1 / 6, rel=1e-4)

    def test_result_bounded(self):
        for odds in [-500, -200, -110, 100, 200, 500]:
            p = implied_prob_from_american(odds)
            assert 0 < p < 1


class TestAmericanFromProb:
    def test_underdog_prob(self):
        # prob ≈ 0.2857 → +250
        assert american_from_prob(100 / 350) == 250

    def test_favorite_prob(self):
        # prob = 0.6 → -150
        assert american_from_prob(0.6) == -150

    def test_even_money(self):
        # prob = 0.5 → +100 (or -100 depending on rounding)
        result = american_from_prob(0.5)
        assert result in (100, -100)

    def test_raises_on_zero(self):
        with pytest.raises(ValueError):
            american_from_prob(0.0)

    def test_raises_on_one(self):
        with pytest.raises(ValueError):
            american_from_prob(1.0)

    def test_raises_on_negative(self):
        with pytest.raises(ValueError):
            american_from_prob(-0.1)

    def test_raises_on_above_one(self):
        with pytest.raises(ValueError):
            american_from_prob(1.5)

    def test_roundtrip_positive_odds(self):
        """prob → american → prob should be close (vig-free)."""
        original_odds = 300
        prob = implied_prob_from_american(original_odds)
        recovered = american_from_prob(prob)
        assert recovered == original_odds

    def test_roundtrip_negative_odds(self):
        original_odds = -200
        prob = implied_prob_from_american(original_odds)
        recovered = american_from_prob(prob)
        assert recovered == original_odds
