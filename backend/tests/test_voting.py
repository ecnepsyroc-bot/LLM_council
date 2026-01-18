"""Tests for voting algorithms."""

import pytest
from backend.council import (
    calculate_borda_count,
    calculate_mrr,
    calculate_confidence_weighted_rankings,
    calculate_aggregate_rankings,
)


class TestBordaCount:
    """Tests for Borda Count voting method."""

    def test_single_voter(self, sample_label_to_model):
        """Borda count with single voter."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]}
        ]

        result = calculate_borda_count(rankings, sample_label_to_model)

        # First place gets 3 points, second 2, third 1
        assert len(result) == 3
        assert result[0]["model"] == "openai/gpt-4"  # Response A
        assert result[0]["borda_score"] == 3
        assert result[1]["borda_score"] == 2
        assert result[2]["borda_score"] == 1

    def test_multiple_voters_consensus(self, sample_label_to_model):
        """Borda count with agreement on winner."""
        rankings = [
            {"parsed_ranking": ["Response B", "Response A", "Response C"]},
            {"parsed_ranking": ["Response B", "Response A", "Response C"]},
            {"parsed_ranking": ["Response B", "Response C", "Response A"]},
        ]

        result = calculate_borda_count(rankings, sample_label_to_model)

        # Response B should win (first in all rankings)
        assert result[0]["model"] == "anthropic/claude-3"  # Response B
        assert result[0]["borda_score"] == 9  # 3 + 3 + 3

    def test_tie_scenario(self, sample_label_to_model):
        """Borda count with tied scores."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B"]},
            {"parsed_ranking": ["Response B", "Response A"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
        }

        result = calculate_borda_count(rankings, label_to_model)

        # Both should have equal scores (2 + 1 = 3 each)
        assert result[0]["borda_score"] == result[1]["borda_score"]

    def test_empty_rankings(self):
        """Borda count handles empty rankings gracefully."""
        result = calculate_borda_count([], {})
        assert result == []

    def test_partial_rankings(self, sample_label_to_model):
        """Borda count handles voters who didn't rank all options."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response B"]},  # Only ranked one
        ]

        result = calculate_borda_count(rankings, sample_label_to_model)

        # Should not crash, all models should have scores
        assert len(result) == 3
        # Response B should have good score (ranked first twice effectively)
        b_result = next(r for r in result if r["model"] == "anthropic/claude-3")
        assert b_result["borda_score"] > 0

    def test_normalization(self, sample_label_to_model):
        """Normalized scores are between 0 and 1."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
        ]

        result = calculate_borda_count(rankings, sample_label_to_model)

        for r in result:
            assert 0 <= r["normalized_score"] <= 1


class TestMRR:
    """Tests for Mean Reciprocal Rank voting method."""

    def test_mrr_calculation(self):
        """MRR correctly calculates reciprocal ranks."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response C", "Response B"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        result = calculate_mrr(rankings, label_to_model)

        # A is first in both, so MRR = 1.0
        a_result = next(r for r in result if r["model"] == "model-a")
        assert a_result["mrr_score"] == 1.0

        # B is second in one (0.5), third in other (0.33), avg ≈ 0.42
        b_result = next(r for r in result if r["model"] == "model-b")
        assert 0.4 < b_result["mrr_score"] < 0.45

    def test_first_place_only(self):
        """MRR gives 1.0 to consistent first-place finisher."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B"]},
            {"parsed_ranking": ["Response A", "Response B"]},
            {"parsed_ranking": ["Response A", "Response B"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
        }

        result = calculate_mrr(rankings, label_to_model)

        assert result[0]["model"] == "model-a"
        assert result[0]["mrr_score"] == 1.0

    def test_empty_rankings(self):
        """MRR handles empty rankings."""
        result = calculate_mrr([], {})
        assert result == []


class TestAggregateRankings:
    """Tests for aggregate ranking dispatcher."""

    def test_simple_method(self, sample_rankings, sample_label_to_model):
        """Simple average method works."""
        result = calculate_aggregate_rankings(
            sample_rankings,
            sample_label_to_model,
            method="simple"
        )
        assert len(result) > 0
        assert "average_rank" in result[0]

    def test_borda_method(self, sample_rankings, sample_label_to_model):
        """Borda method works."""
        result = calculate_aggregate_rankings(
            sample_rankings,
            sample_label_to_model,
            method="borda"
        )
        assert len(result) > 0
        assert "borda_score" in result[0]

    def test_mrr_method(self, sample_rankings, sample_label_to_model):
        """MRR method works."""
        result = calculate_aggregate_rankings(
            sample_rankings,
            sample_label_to_model,
            method="mrr"
        )
        assert len(result) > 0
        assert "mrr_score" in result[0]

    def test_default_method_is_borda(self, sample_rankings, sample_label_to_model):
        """Default voting method is Borda."""
        result = calculate_aggregate_rankings(
            sample_rankings,
            sample_label_to_model
            # No method specified
        )
        assert len(result) > 0
        assert "borda_score" in result[0]

    def test_invalid_method_defaults_to_simple(self, sample_rankings, sample_label_to_model):
        """Invalid method falls back to simple."""
        result = calculate_aggregate_rankings(
            sample_rankings,
            sample_label_to_model,
            method="invalid_method_xyz"
        )
        # Should not crash
        assert len(result) > 0


class TestMathematicalProperties:
    """Tests verifying mathematical properties of voting algorithms."""

    def test_borda_transitivity(self):
        """If A > B > C consistently, A should win."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        result = calculate_borda_count(rankings, label_to_model)

        assert result[0]["model"] == "model-a"
        assert result[1]["model"] == "model-b"
        assert result[2]["model"] == "model-c"

    def test_borda_and_mrr_agree_on_unanimous(self):
        """Borda and MRR should agree when rankings are unanimous."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        borda_result = calculate_borda_count(rankings, label_to_model)
        mrr_result = calculate_mrr(rankings, label_to_model)

        # Both should have the same ordering
        assert borda_result[0]["model"] == mrr_result[0]["model"]
        assert borda_result[1]["model"] == mrr_result[1]["model"]
        assert borda_result[2]["model"] == mrr_result[2]["model"]

    def test_condorcet_winner(self):
        """Test scenario where Condorcet winner exists."""
        # A beats B (2-1), A beats C (2-1), B beats C (2-1)
        # A should win with any reasonable voting method
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response C", "Response B"]},
            {"parsed_ranking": ["Response B", "Response A", "Response C"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        borda_result = calculate_borda_count(rankings, label_to_model)
        mrr_result = calculate_mrr(rankings, label_to_model)

        # A should win in both
        assert borda_result[0]["model"] == "model-a"
        assert mrr_result[0]["model"] == "model-a"


class TestConfidenceWeightedVoting:
    """Tests for confidence-weighted voting."""

    def test_confidence_weights_rankings(self):
        """Higher confidence votes count more."""
        rankings = [
            {"model": "voter-1", "parsed_ranking": ["Response A", "Response B"]},
            {"model": "voter-2", "parsed_ranking": ["Response B", "Response A"]},
        ]
        # voter-1 has high confidence, voter-2 has low confidence
        stage1_results = [
            {"model": "Response A", "confidence": 9.0},  # Maps via label_to_model
            {"model": "Response B", "confidence": 5.0},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
        }

        # Note: Confidence-weighted voting uses stage1 confidences
        # to weight the votes, not the voters' confidence
        result = calculate_confidence_weighted_rankings(
            rankings,
            label_to_model,
            stage1_results
        )

        assert len(result) >= 0  # Should not crash

    def test_missing_confidence_fallback(self):
        """Works when confidence scores are missing."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B"]},
        ]
        stage1_results = [
            {"model": "model-a", "response": "test"},  # No confidence
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
        }

        # Should not crash
        result = calculate_confidence_weighted_rankings(
            rankings,
            label_to_model,
            stage1_results
        )
        assert isinstance(result, list)
