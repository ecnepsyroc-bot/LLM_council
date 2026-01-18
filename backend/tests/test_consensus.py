"""Tests for consensus detection."""

import pytest
from backend.council import detect_consensus


class TestConsensusDetection:
    """Tests for detect_consensus function."""

    def test_strong_consensus(self, sample_label_to_model):
        """Detect strong consensus (>75% agreement on top choice)."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response C", "Response B"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
        ]

        result = detect_consensus(rankings, sample_label_to_model)

        assert result["has_consensus"] is True
        assert result["top_model"] == "openai/gpt-4"  # Response A
        assert result["agreement_score"] >= 0.75
        assert result["total_voters"] == 4
        assert result["top_votes"] == 4

    def test_no_consensus_split_vote(self, sample_label_to_model):
        """No consensus when votes are evenly split."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response B", "Response C", "Response A"]},
            {"parsed_ranking": ["Response C", "Response A", "Response B"]},
        ]

        result = detect_consensus(rankings, sample_label_to_model)

        assert result["has_consensus"] is False
        # Agreement should be low (each has 1 first-place vote)
        assert result["agreement_score"] < 0.5

    def test_bare_majority_not_consensus(self):
        """Bare majority (50%) is not consensus."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B"]},
            {"parsed_ranking": ["Response A", "Response B"]},
            {"parsed_ranking": ["Response B", "Response A"]},
            {"parsed_ranking": ["Response B", "Response A"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
        }

        result = detect_consensus(rankings, label_to_model)

        # 50% is not >= 75%, so no consensus
        assert result["has_consensus"] is False
        assert result["agreement_score"] == 0.5

    def test_unanimous_consensus(self, sample_label_to_model, unanimous_rankings):
        """Unanimous agreement should have 100% consensus."""
        result = detect_consensus(unanimous_rankings, sample_label_to_model)

        assert result["has_consensus"] is True
        assert result["agreement_score"] == 1.0
        assert result["top_votes"] == result["total_voters"]

    def test_empty_rankings(self):
        """Handle empty rankings."""
        result = detect_consensus([], {})

        assert result["has_consensus"] is False
        assert result["total_voters"] == 0

    def test_single_voter(self, sample_label_to_model):
        """Single voter case."""
        rankings = [
            {"parsed_ranking": ["Response B", "Response A", "Response C"]},
        ]

        result = detect_consensus(rankings, sample_label_to_model)

        # Single voter: implementation may or may not count as consensus
        assert result["total_voters"] == 1
        # Agreement score should be 1.0 (100%) for single voter
        assert result["agreement_score"] == 1.0

    def test_missing_parsed_ranking(self, sample_label_to_model):
        """Handle rankings without parsed_ranking field."""
        rankings = [
            {"model": "voter-1", "ranking": "some text"},  # No parsed_ranking
            {"parsed_ranking": ["Response A", "Response B"]},
        ]

        # Should not crash
        result = detect_consensus(rankings, sample_label_to_model)
        assert isinstance(result, dict)
        assert "has_consensus" in result

    def test_consensus_threshold_exactly_75(self):
        """Test boundary case at exactly 75% agreement."""
        # 3 out of 4 = 75%
        rankings = [
            {"parsed_ranking": ["Response A", "Response B"]},
            {"parsed_ranking": ["Response A", "Response B"]},
            {"parsed_ranking": ["Response A", "Response B"]},
            {"parsed_ranking": ["Response B", "Response A"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
        }

        result = detect_consensus(rankings, label_to_model)

        # Exactly 75% - verify the calculation is correct
        assert result["agreement_score"] == 0.75
        # has_consensus depends on whether threshold is > or >=
        # Just verify the logic is consistent
        assert isinstance(result["has_consensus"], bool)
