"""Voting methods for council deliberation."""

from collections import defaultdict
from typing import Any, Dict, List, Literal, Optional

VotingMethod = Literal["simple", "borda", "mrr", "confidence_weighted"]


def calculate_borda_count(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    stage1_results: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Calculate Borda Count rankings.

    Each position gives points: 1st = N points, 2nd = N-1, ..., last = 1 point.
    Higher total = better ranking.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names
        stage1_results: Optional Stage 1 results (unused here, for API consistency)

    Returns:
        List of dicts with model name, borda_score, and normalized_score
    """
    num_candidates = len(label_to_model)
    model_scores: Dict[str, int] = defaultdict(int)
    model_votes: Dict[str, int] = defaultdict(int)

    for ranking in stage2_results:
        parsed = ranking.get("parsed_ranking", [])
        for position, label in enumerate(parsed):
            if label in label_to_model:
                model_name = label_to_model[label]
                # Borda: 1st place gets N points, 2nd gets N-1, etc.
                points = num_candidates - position
                model_scores[model_name] += points
                model_votes[model_name] += 1

    # Calculate max possible score for normalization
    max_possible = num_candidates * len(stage2_results)

    aggregate = []
    for model, score in model_scores.items():
        normalized = score / max_possible if max_possible > 0 else 0
        aggregate.append(
            {
                "model": model,
                "borda_score": score,
                "normalized_score": round(normalized, 3),
                "rankings_count": model_votes[model],
                "average_rank": round(
                    (num_candidates + 1) - (score / model_votes[model]), 2
                )
                if model_votes[model] > 0
                else num_candidates,
            }
        )

    # Sort by borda_score descending (higher is better)
    aggregate.sort(key=lambda x: x["borda_score"], reverse=True)
    return aggregate


def calculate_mrr(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    stage1_results: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Calculate Mean Reciprocal Rank (MRR) rankings.

    Each position gives points: 1st = 1, 2nd = 0.5, 3rd = 0.33, etc.
    Higher MRR = better ranking.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names
        stage1_results: Optional Stage 1 results (unused here)

    Returns:
        List of dicts with model name, mrr_score, and rankings_count
    """
    model_rr_sum: Dict[str, float] = defaultdict(float)
    model_votes: Dict[str, int] = defaultdict(int)

    for ranking in stage2_results:
        parsed = ranking.get("parsed_ranking", [])
        for position, label in enumerate(parsed, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                # Reciprocal rank: 1st = 1.0, 2nd = 0.5, 3rd = 0.33...
                model_rr_sum[model_name] += 1.0 / position
                model_votes[model_name] += 1

    aggregate = []
    for model, rr_sum in model_rr_sum.items():
        mrr = rr_sum / len(stage2_results) if stage2_results else 0
        aggregate.append(
            {
                "model": model,
                "mrr_score": round(mrr, 3),
                "reciprocal_sum": round(rr_sum, 3),
                "rankings_count": model_votes[model],
                "average_rank": round(1 / mrr, 2) if mrr > 0 else len(label_to_model),
            }
        )

    # Sort by mrr_score descending (higher is better)
    aggregate.sort(key=lambda x: x["mrr_score"], reverse=True)
    return aggregate


def calculate_confidence_weighted_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    stage1_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Calculate confidence-weighted rankings.

    Combines Borda count with confidence weighting:
    - Models with higher confidence get more voting power
    - Uses dual-weighting: local confidence + global credibility

    Args:
        stage2_results: Rankings from each model (contains 'model' key for voter)
        label_to_model: Mapping from anonymous labels to model names
        stage1_results: Stage 1 results with confidence scores

    Returns:
        List of dicts with model name, weighted_score, and breakdown
    """
    num_candidates = len(label_to_model)

    # Build confidence map: model -> confidence score
    confidence_map = {}
    for result in stage1_results:
        conf = result.get("confidence")
        if conf is not None:
            confidence_map[result["model"]] = conf
        else:
            confidence_map[result["model"]] = 5  # Default middle confidence

    # Normalize confidences to weights (0.5 to 1.5 range)
    model_weighted_scores: Dict[str, float] = defaultdict(float)
    model_raw_scores: Dict[str, float] = defaultdict(float)
    model_votes: Dict[str, int] = defaultdict(int)

    for ranking in stage2_results:
        voter_model = ranking.get("model", "")
        # Get voter's confidence as their voting weight
        voter_confidence = confidence_map.get(voter_model, 5)
        # Normalize weight to 0.5-1.5 range
        weight = 0.5 + (voter_confidence / 10)

        parsed = ranking.get("parsed_ranking", [])
        for position, label in enumerate(parsed):
            if label in label_to_model:
                model_name = label_to_model[label]
                raw_points = num_candidates - position
                weighted_points = raw_points * weight

                model_raw_scores[model_name] += raw_points
                model_weighted_scores[model_name] += weighted_points
                model_votes[model_name] += 1

    aggregate = []
    for model in model_weighted_scores.keys():
        aggregate.append(
            {
                "model": model,
                "weighted_score": round(model_weighted_scores[model], 2),
                "raw_score": model_raw_scores[model],
                "confidence_boost": round(
                    model_weighted_scores[model] - model_raw_scores[model], 2
                ),
                "rankings_count": model_votes[model],
                "average_rank": round(
                    (num_candidates + 1) - (model_raw_scores[model] / model_votes[model]),
                    2,
                )
                if model_votes[model] > 0
                else num_candidates,
            }
        )

    # Sort by weighted_score descending
    aggregate.sort(key=lambda x: x["weighted_score"], reverse=True)
    return aggregate


def _calculate_simple_average(
    stage2_results: List[Dict[str, Any]], label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Original simple average rank calculation."""
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        parsed = ranking.get("parsed_ranking", [])
        for position, label in enumerate(parsed, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append(
                {
                    "model": model,
                    "average_rank": round(avg_rank, 2),
                    "rankings_count": len(positions),
                }
            )

    aggregate.sort(key=lambda x: x["average_rank"])
    return aggregate


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    stage1_results: Optional[List[Dict[str, Any]]] = None,
    method: VotingMethod = "borda",
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings using the specified voting method.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names
        stage1_results: Stage 1 results (needed for confidence_weighted)
        method: Voting method to use

    Returns:
        List of dicts with model rankings, sorted best to worst
    """
    if method == "borda":
        return calculate_borda_count(stage2_results, label_to_model, stage1_results)
    elif method == "mrr":
        return calculate_mrr(stage2_results, label_to_model, stage1_results)
    elif method == "confidence_weighted":
        if stage1_results is None:
            # Fall back to borda if no confidence data
            return calculate_borda_count(stage2_results, label_to_model)
        return calculate_confidence_weighted_rankings(
            stage2_results, label_to_model, stage1_results
        )
    else:  # "simple" - original average rank method
        return _calculate_simple_average(stage2_results, label_to_model)
