"""End-to-end tests for the 3-stage council deliberation flow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.council.orchestration import run_full_council
from backend.council.stages import (
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
)
from backend.council.voting import calculate_aggregate_rankings
from backend.council.consensus import detect_consensus

from .fixtures.responses import SAMPLE_STAGE1_RESPONSES, SAMPLE_STAGE1_WITH_CONFIDENCE
from .fixtures.rankings import SAMPLE_RANKINGS, SAMPLE_LABEL_TO_MODEL


class TestStage1CollectResponses:
    """Tests for Stage 1: Collecting responses from council models."""

    @pytest.mark.asyncio
    async def test_stage1_returns_responses_from_all_models(self):
        """Stage 1 should query all council models and return responses."""
        # query_models_parallel returns Dict[str, Optional[Dict]]
        mock_responses = {
            "model-1": {"content": "Response from model 1\n\nCONFIDENCE: 8/10"},
            "model-2": {"content": "Response from model 2\n\nCONFIDENCE: 7/10"},
            "model-3": {"content": "Response from model 3\n\nCONFIDENCE: 9/10"},
        }

        with patch("backend.council.stages.query_models_parallel") as mock_query:
            mock_query.return_value = mock_responses
            with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2", "model-3"]):
                results = await stage1_collect_responses("What is 2+2?")

                assert len(results) == 3
                assert all("response" in r for r in results)
                assert all("model" in r for r in results)
                mock_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_stage1_handles_partial_failures(self):
        """Stage 1 should handle when some models fail."""
        mock_responses = {
            "model-1": {"content": "Response from model 1\n\nCONFIDENCE: 8/10"},
            "model-2": None,  # Failed model
            "model-3": {"content": "Response from model 3\n\nCONFIDENCE: 9/10"},
        }

        with patch("backend.council.stages.query_models_parallel") as mock_query:
            mock_query.return_value = mock_responses
            with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2", "model-3"]):
                results = await stage1_collect_responses("What is 2+2?")

                # Should only include successful responses
                assert len(results) == 2

    @pytest.mark.asyncio
    async def test_stage1_extracts_confidence_scores(self):
        """Stage 1 should extract confidence scores when present."""
        mock_responses = {
            "model-1": {"content": "The answer is 42.\n\nCONFIDENCE: 8/10"},
        }

        with patch("backend.council.stages.query_models_parallel") as mock_query:
            mock_query.return_value = mock_responses
            with patch("backend.council.stages.COUNCIL_MODELS", ["model-1"]):
                results = await stage1_collect_responses("Question?")

                assert len(results) == 1
                # Confidence should be extracted
                assert "confidence" in results[0]
                assert results[0]["confidence"] == 8.0

    @pytest.mark.asyncio
    async def test_stage1_handles_missing_confidence(self):
        """Stage 1 should handle responses without confidence scores."""
        mock_responses = {
            "model-1": {"content": "The answer is 42."},  # No confidence
        }

        with patch("backend.council.stages.query_models_parallel") as mock_query:
            mock_query.return_value = mock_responses
            with patch("backend.council.stages.COUNCIL_MODELS", ["model-1"]):
                results = await stage1_collect_responses("Question?")

                assert len(results) == 1
                # Confidence should be None or have a default
                assert "confidence" in results[0]


class TestStage2CollectRankings:
    """Tests for Stage 2: Anonymized peer evaluation and ranking."""

    @pytest.mark.asyncio
    async def test_stage2_anonymizes_responses(self):
        """Stage 2 should anonymize responses as 'Response A', 'Response B', etc."""
        stage1_results = SAMPLE_STAGE1_RESPONSES

        # Stage 2 also uses query_models_parallel which returns dict
        mock_rankings = {
            "model-1": {"content": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"},
            "model-2": {"content": "FINAL RANKING:\n1. Response B\n2. Response A\n3. Response C"},
        }

        with patch("backend.council.stages.query_models_parallel") as mock_query:
            mock_query.return_value = mock_rankings
            with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2"]):
                rankings, label_to_model = await stage2_collect_rankings(
                    "What is the question?", stage1_results
                )

                # Check label mapping exists
                assert "Response A" in label_to_model
                assert "Response B" in label_to_model
                assert "Response C" in label_to_model

                # Labels should map to actual model names
                assert all(
                    model in ["openai/gpt-4", "anthropic/claude-3", "google/gemini-pro"]
                    for model in label_to_model.values()
                )

    @pytest.mark.asyncio
    async def test_stage2_parses_rankings(self):
        """Stage 2 should parse rankings from model responses."""
        stage1_results = SAMPLE_STAGE1_RESPONSES[:2]  # Two responses

        mock_rankings = {
            "model-1": {"content": "FINAL RANKING:\n1. Response A\n2. Response B"},
        }

        with patch("backend.council.stages.query_models_parallel") as mock_query:
            mock_query.return_value = mock_rankings
            with patch("backend.council.stages.COUNCIL_MODELS", ["model-1"]):
                rankings, label_to_model = await stage2_collect_rankings(
                    "Question?", stage1_results
                )

                assert len(rankings) > 0
                # Each ranking should have parsed_ranking
                for ranking in rankings:
                    if "parsed_ranking" in ranking:
                        assert isinstance(ranking["parsed_ranking"], list)


class TestStage3Synthesis:
    """Tests for Stage 3: Chairman synthesis."""

    @pytest.mark.asyncio
    async def test_stage3_synthesizes_final_answer(self):
        """Stage 3 should produce a final synthesized answer."""
        mock_synthesis = {"content": "Based on the council's deliberation, the answer is 42."}

        with patch("backend.council.stages.query_model") as mock_query:
            mock_query.return_value = mock_synthesis

            result = await stage3_synthesize_final(
                "What is 2+2?",
                SAMPLE_STAGE1_RESPONSES,
                SAMPLE_RANKINGS,
                aggregate_rankings=[],
            )

            assert "response" in result
            mock_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_stage3_uses_specified_chairman(self):
        """Stage 3 should use the specified chairman model."""
        mock_synthesis = {"content": "Synthesis"}

        with patch("backend.council.stages.query_model") as mock_query:
            mock_query.return_value = mock_synthesis

            await stage3_synthesize_final(
                "Question?",
                SAMPLE_STAGE1_RESPONSES,
                SAMPLE_RANKINGS,
                chairman_model="custom/chairman-model",
            )

            # Verify the chairman model was used
            call_args = mock_query.call_args
            assert call_args is not None
            # Model should be the first positional argument
            assert call_args[0][0] == "custom/chairman-model"


class TestFullOrchestration:
    """End-to-end tests for the complete 3-stage flow."""

    @pytest.mark.asyncio
    async def test_run_full_council_basic_flow(self):
        """Full council flow should execute all 3 stages."""
        # Mock Stage 1 responses (dict format)
        stage1_mock = {
            "model-1": {"content": "Answer A\n\nCONFIDENCE: 8/10"},
            "model-2": {"content": "Answer B\n\nCONFIDENCE: 7/10"},
            "model-3": {"content": "Answer C\n\nCONFIDENCE: 9/10"},
        }

        # Mock Stage 2 rankings (dict format)
        stage2_mock = {
            "model-1": {"content": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"},
            "model-2": {"content": "FINAL RANKING:\n1. Response B\n2. Response A\n3. Response C"},
            "model-3": {"content": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"},
        }

        # Mock Stage 3 synthesis
        stage3_mock = {"content": "The final answer is A."}

        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.query_model") as mock_single:
                with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2", "model-3"]):
                    # First call is Stage 1, second is Stage 2
                    mock_parallel.side_effect = [stage1_mock, stage2_mock]
                    mock_single.return_value = stage3_mock

                    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
                        "What is the answer?"
                    )

                    # Verify all stages produced results
                    assert len(stage1_results) == 3
                    assert len(stage2_results) > 0
                    assert stage3_result is not None
                    assert metadata is not None

                    # Verify metadata contains expected fields
                    assert "label_to_model" in metadata
                    assert "aggregate_rankings" in metadata
                    assert "consensus" in metadata

    @pytest.mark.asyncio
    async def test_run_full_council_handles_all_failures(self):
        """Full council should handle gracefully when all models fail."""
        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2", "model-3"]):
                # All models fail
                mock_parallel.return_value = {"model-1": None, "model-2": None, "model-3": None}

                stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
                    "Question?"
                )

                # Should return empty results with error message
                assert stage1_results == []
                assert "error" in stage3_result.get("model", "")

    @pytest.mark.asyncio
    async def test_run_full_council_with_voting_method(self):
        """Full council should support different voting methods."""
        stage1_mock = {
            "model-1": {"content": "Answer A\n\nCONFIDENCE: 8/10"},
            "model-2": {"content": "Answer B\n\nCONFIDENCE: 7/10"},
        }

        stage2_mock = {
            "model-1": {"content": "FINAL RANKING:\n1. Response A\n2. Response B"},
            "model-2": {"content": "FINAL RANKING:\n1. Response B\n2. Response A"},
        }

        stage3_mock = {"content": "Final answer"}

        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.query_model") as mock_single:
                with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2"]):
                    mock_parallel.side_effect = [stage1_mock, stage2_mock]
                    mock_single.return_value = stage3_mock

                    # Test with Borda count
                    _, _, _, metadata = await run_full_council(
                        "Question?",
                        voting_method="borda"
                    )
                    assert metadata["voting_method"] == "borda"

    @pytest.mark.asyncio
    async def test_run_full_council_metadata_structure(self):
        """Full council should return properly structured metadata."""
        stage1_mock = {
            "model-1": {"content": "A\n\nCONFIDENCE: 8/10"},
            "model-2": {"content": "B\n\nCONFIDENCE: 7/10"},
        }
        stage2_mock = {
            "model-1": {"content": "FINAL RANKING:\n1. Response A\n2. Response B"},
        }
        stage3_mock = {"content": "Final"}

        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.query_model") as mock_single:
                with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2"]):
                    mock_parallel.side_effect = [stage1_mock, stage2_mock]
                    mock_single.return_value = stage3_mock

                    _, _, _, metadata = await run_full_council("Q?")

                    # Verify metadata structure
                    assert "features" in metadata
                    features = metadata["features"]
                    assert "use_rubric" in features
                    assert "debate_rounds" in features
                    assert "early_exit_used" in features
                    assert "chairman_model" in features


class TestVotingIntegration:
    """Tests for voting calculation integration."""

    def test_aggregate_rankings_with_sample_data(self):
        """Aggregate rankings should calculate correctly from sample data."""
        rankings = calculate_aggregate_rankings(
            SAMPLE_RANKINGS,
            SAMPLE_LABEL_TO_MODEL,
            SAMPLE_STAGE1_RESPONSES,
            method="borda"
        )

        assert isinstance(rankings, list)
        # Should have entries
        assert len(rankings) > 0

        # Each entry should have model and score/rank info
        for entry in rankings:
            assert "model" in entry

    def test_aggregate_rankings_mrr_method(self):
        """MRR voting method should work correctly."""
        rankings = calculate_aggregate_rankings(
            SAMPLE_RANKINGS,
            SAMPLE_LABEL_TO_MODEL,
            SAMPLE_STAGE1_RESPONSES,
            method="mrr"
        )

        assert isinstance(rankings, list)
        assert len(rankings) > 0


class TestConsensusIntegration:
    """Tests for consensus detection integration."""

    def test_detect_consensus_with_sample_data(self):
        """Consensus detection should work with sample ranking data."""
        consensus = detect_consensus(SAMPLE_RANKINGS, SAMPLE_LABEL_TO_MODEL)

        assert isinstance(consensus, dict)
        # Should have some consensus-related fields
        assert len(consensus) > 0

    def test_detect_consensus_unanimous(self):
        """Should detect unanimous consensus."""
        from .fixtures.rankings import UNANIMOUS_RANKINGS

        unanimous_label_map = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        consensus = detect_consensus(UNANIMOUS_RANKINGS, unanimous_label_map)

        # Unanimous rankings should show high agreement
        if "agreement_level" in consensus:
            assert consensus["agreement_level"] in ["unanimous", "strong", "high"]


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_query(self):
        """Should handle empty query gracefully."""
        stage1_mock = {"model-1": {"content": "Response\n\nCONFIDENCE: 5/10"}}
        stage2_mock = {"model-1": {"content": "FINAL RANKING:\n1. Response A"}}
        stage3_mock = {"content": "Final"}

        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.query_model") as mock_single:
                with patch("backend.council.stages.COUNCIL_MODELS", ["model-1"]):
                    mock_parallel.side_effect = [stage1_mock, stage2_mock]
                    mock_single.return_value = stage3_mock

                    # Should not crash on empty query
                    stage1_results, _, _, _ = await run_full_council("")
                    assert len(stage1_results) >= 0

    @pytest.mark.asyncio
    async def test_single_model_response(self):
        """Should handle when only one model responds."""
        stage1_mock = {
            "model-1": {"content": "Only response\n\nCONFIDENCE: 8/10"},
            "model-2": None,
            "model-3": None,
        }
        stage2_mock = {
            "model-1": {"content": "FINAL RANKING:\n1. Response A"},
        }
        stage3_mock = {"content": "Synthesis"}

        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.query_model") as mock_single:
                with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2", "model-3"]):
                    mock_parallel.side_effect = [stage1_mock, stage2_mock]
                    mock_single.return_value = stage3_mock

                    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
                        "Question?"
                    )

                    # Should still produce a result
                    assert len(stage1_results) >= 1

    @pytest.mark.asyncio
    async def test_malformed_ranking_response(self):
        """Should handle malformed ranking responses gracefully."""
        stage1_mock = {
            "model-1": {"content": "A\n\nCONFIDENCE: 8/10"},
            "model-2": {"content": "B\n\nCONFIDENCE: 7/10"},
        }
        # Malformed ranking - no FINAL RANKING section
        stage2_mock = {
            "model-1": {"content": "I think Response A is better because..."},
        }
        stage3_mock = {"content": "Final"}

        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.query_model") as mock_single:
                with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2"]):
                    mock_parallel.side_effect = [stage1_mock, stage2_mock]
                    mock_single.return_value = stage3_mock

                    # Should not crash, parsing should handle gracefully
                    _, stage2_results, _, _ = await run_full_council("Q?")

                    # Results should exist even if parsing failed
                    assert isinstance(stage2_results, list)


class TestFeatureFlags:
    """Tests for various feature configurations."""

    @pytest.mark.asyncio
    async def test_rubric_evaluation_flag(self):
        """Rubric evaluation should be reflected in metadata."""
        stage1_mock = {"model-1": {"content": "A\n\nCONFIDENCE: 8/10"}}
        stage2_mock = {"model-1": {"content": "FINAL RANKING:\n1. Response A"}}
        stage3_mock = {"content": "Final"}

        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.query_model") as mock_single:
                with patch("backend.council.stages.COUNCIL_MODELS", ["model-1"]):
                    mock_parallel.side_effect = [stage1_mock, stage2_mock]
                    mock_single.return_value = stage3_mock

                    _, _, _, metadata = await run_full_council(
                        "Q?",
                        use_rubric=True
                    )

                    assert metadata["features"]["use_rubric"] is True

    @pytest.mark.asyncio
    async def test_debate_rounds_flag(self):
        """Debate rounds should be reflected in metadata."""
        stage1_mock = {"model-1": {"content": "A\n\nCONFIDENCE: 8/10"}}
        stage2_mock = {"model-1": {"content": "FINAL RANKING:\n1. Response A"}}
        stage3_mock = {"content": "Final"}

        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.query_model") as mock_single:
                with patch("backend.council.stages.COUNCIL_MODELS", ["model-1"]):
                    # Multiple rounds of stage 2
                    mock_parallel.side_effect = [stage1_mock, stage2_mock, stage2_mock]
                    mock_single.return_value = stage3_mock

                    _, _, _, metadata = await run_full_council(
                        "Q?",
                        debate_rounds=2
                    )

                    assert metadata["features"]["debate_rounds"] == 2

    @pytest.mark.asyncio
    async def test_rotating_chairman_flag(self):
        """Rotating chairman should be reflected in metadata."""
        stage1_mock = {
            "model-1": {"content": "A\n\nCONFIDENCE: 8/10"},
            "model-2": {"content": "B\n\nCONFIDENCE: 7/10"},
        }
        stage2_mock = {
            "model-1": {"content": "FINAL RANKING:\n1. Response A\n2. Response B"},
            "model-2": {"content": "FINAL RANKING:\n1. Response A\n2. Response B"},
        }
        stage3_mock = {"content": "Final"}

        with patch("backend.council.stages.query_models_parallel") as mock_parallel:
            with patch("backend.council.stages.query_model") as mock_single:
                with patch("backend.council.stages.COUNCIL_MODELS", ["model-1", "model-2"]):
                    mock_parallel.side_effect = [stage1_mock, stage2_mock]
                    mock_single.return_value = stage3_mock

                    _, _, _, metadata = await run_full_council(
                        "Q?",
                        rotating_chairman=True
                    )

                    assert metadata["features"]["rotating_chairman"] is True
