"""Main orchestration for council deliberation."""

from typing import Any, Dict, List, Tuple

from ..config import CHAIRMAN_MODEL
from .consensus import check_stage1_consensus, detect_consensus
from .stages import (
    select_rotating_chairman,
    stage1_collect_responses,
    stage1_self_moa,
    stage2_collect_rankings,
    stage2_with_debate,
    stage3_synthesize_final,
    stage3_with_meta_evaluation,
)
from .voting import VotingMethod, calculate_aggregate_rankings


async def run_full_council(
    user_query: str,
    voting_method: VotingMethod = "borda",
    use_rubric: bool = False,
    debate_rounds: int = 1,
    enable_early_exit: bool = True,
    use_self_moa: bool = False,
    rotating_chairman: bool = False,
    meta_evaluate: bool = False,
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete council process with configurable features.

    Args:
        user_query: The user's question
        voting_method: "simple", "borda", "mrr", or "confidence_weighted"
        use_rubric: Whether to use rubric-based evaluation
        debate_rounds: Number of debate rounds (1 = no debate)
        enable_early_exit: Whether to allow early exit on high consensus
        use_self_moa: Use Self-MoA instead of multi-model
        rotating_chairman: Select chairman based on rankings
        meta_evaluate: Add meta-evaluation of chairman's synthesis

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 1: Collect responses
    if use_self_moa:
        stage1_results = await stage1_self_moa(user_query)
    else:
        stage1_results = await stage1_collect_responses(user_query)

    if not stage1_results:
        return (
            [],
            [],
            {"model": "error", "response": "All models failed to respond. Please try again."},
            {},
        )

    # Check for early exit based on Stage 1 confidence
    stage1_consensus = check_stage1_consensus(stage1_results)

    # Stage 2: Collect rankings (with optional debate)
    if debate_rounds > 1:
        stage2_results, label_to_model, debate_history = await stage2_with_debate(
            user_query, stage1_results, num_rounds=debate_rounds, use_rubric=use_rubric
        )
    else:
        stage2_results, label_to_model = await stage2_collect_rankings(
            user_query, stage1_results, use_rubric=use_rubric
        )
        debate_history = None

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(
        stage2_results, label_to_model, stage1_results, method=voting_method
    )

    # Detect consensus
    consensus = detect_consensus(stage2_results, label_to_model)

    # Determine chairman
    if rotating_chairman and aggregate_rankings:
        chairman = select_rotating_chairman(stage1_results, aggregate_rankings, "top_ranked")
    else:
        chairman = CHAIRMAN_MODEL

    # Early exit check
    early_exit_used = False
    if enable_early_exit and consensus.get("early_exit_eligible"):
        # For high consensus, we can provide a simpler synthesis
        early_exit_used = True

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        chairman_model=chairman,
        aggregate_rankings=aggregate_rankings,
    )

    # Optional meta-evaluation
    if meta_evaluate:
        stage3_result = await stage3_with_meta_evaluation(
            user_query, stage1_results, stage2_results, stage3_result
        )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "consensus": consensus,
        "voting_method": voting_method,
        "features": {
            "use_rubric": use_rubric,
            "debate_rounds": debate_rounds,
            "early_exit_used": early_exit_used,
            "use_self_moa": use_self_moa,
            "rotating_chairman": rotating_chairman,
            "meta_evaluate": meta_evaluate,
            "chairman_model": chairman,
        },
        "stage1_consensus": stage1_consensus,
    }

    if debate_history:
        metadata["debate_history"] = debate_history

    return stage1_results, stage2_results, stage3_result, metadata
