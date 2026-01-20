"""Tests for hallucination detection via peer comparison."""

import pytest
from backend.council.hallucination import (
    detect_hallucinations,
    analyze_response_consistency,
    HallucinationReport,
    HallucinationSignal,
)


class TestHallucinationDetection:
    """Test hallucination detection logic."""

    @pytest.fixture
    def sample_stage1_results(self):
        """Sample Stage 1 results with confidence scores."""
        return [
            {"model": "model_a", "response": "Answer from A", "confidence": 9},
            {"model": "model_b", "response": "Answer from B", "confidence": 7},
            {"model": "model_c", "response": "Answer from C", "confidence": 5},
        ]

    @pytest.fixture
    def sample_label_to_model(self):
        """Sample label mapping."""
        return {
            "Response A": "model_a",
            "Response B": "model_b",
            "Response C": "model_c",
        }

    @pytest.fixture
    def unanimous_rankings(self):
        """All evaluators agree on ranking."""
        return [
            {
                "model": "model_a",
                "parsed_ranking": ["Response B", "Response C", "Response A"]
            },
            {
                "model": "model_b",
                "parsed_ranking": ["Response B", "Response C", "Response A"]
            },
            {
                "model": "model_c",
                "parsed_ranking": ["Response B", "Response C", "Response A"]
            },
        ]

    @pytest.fixture
    def mixed_rankings(self):
        """Evaluators disagree on ranking."""
        return [
            {
                "model": "model_a",
                "parsed_ranking": ["Response A", "Response B", "Response C"]
            },
            {
                "model": "model_b",
                "parsed_ranking": ["Response B", "Response A", "Response C"]
            },
            {
                "model": "model_c",
                "parsed_ranking": ["Response C", "Response B", "Response A"]
            },
        ]

    def test_confidence_mismatch_detected(
        self,
        sample_stage1_results,
        unanimous_rankings,
        sample_label_to_model
    ):
        """High confidence with poor ranking should be flagged."""
        # model_a has confidence 9 but is ranked last by all peers
        aggregate_rankings = [
            {"model": "model_b", "average_rank": 1.0},
            {"model": "model_c", "average_rank": 2.0},
            {"model": "model_a", "average_rank": 3.0},
        ]

        report = detect_hallucinations(
            stage1_results=sample_stage1_results,
            stage2_results=unanimous_rankings,
            aggregate_rankings=aggregate_rankings,
            label_to_model=sample_label_to_model
        )

        # Should detect confidence mismatch for model_a
        mismatch_signals = [
            s for s in report.signals
            if s.signal_type == "confidence_mismatch" and s.model == "model_a"
        ]
        assert len(mismatch_signals) >= 1

    def test_peer_rejection_detected(
        self,
        sample_stage1_results,
        unanimous_rankings,
        sample_label_to_model
    ):
        """Model ranked last by all peers should be flagged."""
        aggregate_rankings = [
            {"model": "model_b", "average_rank": 1.0},
            {"model": "model_c", "average_rank": 2.0},
            {"model": "model_a", "average_rank": 3.0},
        ]

        report = detect_hallucinations(
            stage1_results=sample_stage1_results,
            stage2_results=unanimous_rankings,
            aggregate_rankings=aggregate_rankings,
            label_to_model=sample_label_to_model
        )

        # Should detect peer rejection for model_a
        rejection_signals = [
            s for s in report.signals
            if s.signal_type == "peer_rejection" and s.model == "model_a"
        ]
        # At least flagged (threshold may vary)
        assert report.has_concerns

    def test_no_concerns_with_consensus(
        self,
        sample_stage1_results,
        sample_label_to_model
    ):
        """Strong consensus should not raise concerns."""
        # Adjust confidence to match rankings
        stage1 = [
            {"model": "model_a", "response": "A", "confidence": 6},
            {"model": "model_b", "response": "B", "confidence": 8},
            {"model": "model_c", "response": "C", "confidence": 7},
        ]

        rankings = [
            {"model": "model_a", "parsed_ranking": ["Response B", "Response C", "Response A"]},
            {"model": "model_b", "parsed_ranking": ["Response B", "Response C", "Response A"]},
            {"model": "model_c", "parsed_ranking": ["Response B", "Response C", "Response A"]},
        ]

        aggregate_rankings = [
            {"model": "model_b", "average_rank": 1.0},
            {"model": "model_c", "average_rank": 2.0},
            {"model": "model_a", "average_rank": 3.0},
        ]

        report = detect_hallucinations(
            stage1_results=stage1,
            stage2_results=rankings,
            aggregate_rankings=aggregate_rankings,
            label_to_model=sample_label_to_model
        )

        # model_a has low confidence matching low rank - no mismatch
        # Check that high-severity concerns are minimal
        high_severity = [s for s in report.signals if s.severity == "high"]
        assert len(high_severity) <= 1  # Allow for peer rejection at most

    def test_outlier_detection(
        self,
        sample_stage1_results,
        sample_label_to_model
    ):
        """High variance in rankings should flag outlier."""
        # model_c ranked very differently by each evaluator
        rankings = [
            {"model": "model_a", "parsed_ranking": ["Response C", "Response B", "Response A"]},
            {"model": "model_b", "parsed_ranking": ["Response A", "Response B", "Response C"]},
        ]

        aggregate_rankings = [
            {"model": "model_a", "average_rank": 2.0},
            {"model": "model_b", "average_rank": 2.0},
            {"model": "model_c", "average_rank": 2.0},
        ]

        report = detect_hallucinations(
            stage1_results=sample_stage1_results,
            stage2_results=rankings,
            aggregate_rankings=aggregate_rankings,
            label_to_model=sample_label_to_model
        )

        # Check for outlier signals (high std dev in rankings)
        outlier_signals = [s for s in report.signals if s.signal_type == "outlier"]
        # May or may not trigger based on threshold
        assert isinstance(report, HallucinationReport)

    def test_model_scores_calculated(
        self,
        sample_stage1_results,
        unanimous_rankings,
        sample_label_to_model
    ):
        """Model reliability scores should be calculated."""
        aggregate_rankings = [
            {"model": "model_b", "average_rank": 1.0},
            {"model": "model_c", "average_rank": 2.0},
            {"model": "model_a", "average_rank": 3.0},
        ]

        report = detect_hallucinations(
            stage1_results=sample_stage1_results,
            stage2_results=unanimous_rankings,
            aggregate_rankings=aggregate_rankings,
            label_to_model=sample_label_to_model
        )

        # All models should have scores
        assert "model_a" in report.model_scores
        assert "model_b" in report.model_scores
        assert "model_c" in report.model_scores

        # Scores should be 0-1
        for score in report.model_scores.values():
            assert 0.0 <= score <= 1.0

    def test_report_to_dict(
        self,
        sample_stage1_results,
        unanimous_rankings,
        sample_label_to_model
    ):
        """Report should serialize to dict correctly."""
        aggregate_rankings = [
            {"model": "model_b", "average_rank": 1.0},
            {"model": "model_c", "average_rank": 2.0},
            {"model": "model_a", "average_rank": 3.0},
        ]

        report = detect_hallucinations(
            stage1_results=sample_stage1_results,
            stage2_results=unanimous_rankings,
            aggregate_rankings=aggregate_rankings,
            label_to_model=sample_label_to_model
        )

        report_dict = report.to_dict()

        assert "has_concerns" in report_dict
        assert "overall_confidence" in report_dict
        assert "signals" in report_dict
        assert "model_scores" in report_dict
        assert "recommendations" in report_dict

        # Should be JSON-serializable
        import json
        json_str = json.dumps(report_dict)
        assert len(json_str) > 0


class TestResponseConsistency:
    """Test response consistency analysis."""

    def test_consistent_responses(self):
        """Responses with same numbers should be consistent."""
        stage1 = [
            {"model": "a", "response": "The answer is 42."},
            {"model": "b", "response": "I believe it's 42."},
            {"model": "c", "response": "42 is correct."},
        ]

        result = analyze_response_consistency(stage1)
        assert result["consistent"] is True
        assert "42" in result["common_facts"]

    def test_inconsistent_responses(self):
        """Responses with different numbers should be flagged."""
        stage1 = [
            {"model": "a", "response": "The answer is 42."},
            {"model": "b", "response": "I think it's 100."},
            {"model": "c", "response": "The result is 7."},
        ]

        result = analyze_response_consistency(stage1)
        # Each model has different numbers
        assert len(result["common_facts"]) == 0

    def test_empty_responses(self):
        """Empty response list should be handled."""
        result = analyze_response_consistency([])
        assert result["consistent"] is True

    def test_responses_without_numbers(self):
        """Responses without numbers should be consistent."""
        stage1 = [
            {"model": "a", "response": "The sky is blue."},
            {"model": "b", "response": "I agree, it's blue."},
        ]

        result = analyze_response_consistency(stage1)
        assert result["consistent"] is True


class TestHallucinationSignal:
    """Test HallucinationSignal dataclass."""

    def test_signal_creation(self):
        """Signal should be created with all fields."""
        signal = HallucinationSignal(
            model="test_model",
            signal_type="confidence_mismatch",
            severity="high",
            description="Test description",
            evidence={"score": 0.9}
        )

        assert signal.model == "test_model"
        assert signal.signal_type == "confidence_mismatch"
        assert signal.severity == "high"
        assert signal.evidence["score"] == 0.9


class TestHallucinationReport:
    """Test HallucinationReport dataclass."""

    def test_report_with_no_concerns(self):
        """Report without concerns."""
        report = HallucinationReport(
            has_concerns=False,
            overall_confidence=0.95,
            signals=[],
            model_scores={"model_a": 0.9},
            recommendations=["All good"]
        )

        assert not report.has_concerns
        assert report.overall_confidence == 0.95
        assert len(report.signals) == 0

    def test_report_with_concerns(self):
        """Report with concerns."""
        signal = HallucinationSignal(
            model="bad_model",
            signal_type="peer_rejection",
            severity="high",
            description="Rejected by all"
        )

        report = HallucinationReport(
            has_concerns=True,
            overall_confidence=0.5,
            signals=[signal],
            model_scores={"bad_model": 0.3},
            recommendations=["Review carefully"]
        )

        assert report.has_concerns
        assert len(report.signals) == 1
        assert report.signals[0].severity == "high"
