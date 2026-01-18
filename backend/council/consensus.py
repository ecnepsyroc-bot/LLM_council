"""Consensus detection for council deliberation."""

from typing import Any, Dict, List


def detect_consensus(
    stage2_results: List[Dict[str, Any]], label_to_model: Dict[str, str]
) -> Dict[str, Any]:
    """
    Detect if there is consensus among models on the top-ranked response.
    """
    if not stage2_results:
        return {
            "has_consensus": False,
            "agreement_score": 0.0,
            "top_model": None,
            "top_votes": 0,
            "total_voters": 0,
            "early_exit_eligible": False,
        }

    first_place_votes: Dict[str, int] = {}
    total_voters = 0

    for ranking in stage2_results:
        parsed = ranking.get("parsed_ranking", [])
        if parsed:
            first_choice = parsed[0]
            first_place_votes[first_choice] = first_place_votes.get(first_choice, 0) + 1
            total_voters += 1

    if total_voters == 0:
        return {
            "has_consensus": False,
            "agreement_score": 0.0,
            "top_model": None,
            "top_votes": 0,
            "total_voters": 0,
            "early_exit_eligible": False,
        }

    top_label = max(first_place_votes, key=first_place_votes.get)
    top_votes = first_place_votes[top_label]
    agreement_score = top_votes / total_voters
    top_model = label_to_model.get(top_label)
    has_consensus = top_votes == total_voters and total_voters > 1

    # Early exit eligible if >75% agreement
    early_exit_eligible = agreement_score >= 0.75

    return {
        "has_consensus": has_consensus,
        "agreement_score": round(agreement_score, 2),
        "top_model": top_model,
        "top_votes": top_votes,
        "total_voters": total_voters,
        "early_exit_eligible": early_exit_eligible,
    }


def check_stage1_consensus(
    stage1_results: List[Dict[str, Any]], threshold: float = 0.8
) -> Dict[str, Any]:
    """
    Check for early consensus in Stage 1 based on confidence scores.

    If one model has very high confidence (>=9) and others have low confidence,
    we might skip extended deliberation.

    Args:
        stage1_results: Stage 1 results with confidence scores
        threshold: Confidence threshold for early exit consideration

    Returns:
        Dict with early_exit_possible, high_confidence_model, and reason
    """
    confidences = []
    for result in stage1_results:
        conf = result.get("confidence")
        if conf is not None:
            confidences.append((result["model"], conf))

    if not confidences:
        return {
            "early_exit_possible": False,
            "high_confidence_model": None,
            "reason": "No confidence scores available",
        }

    # Sort by confidence descending
    confidences.sort(key=lambda x: x[1], reverse=True)
    top_model, top_conf = confidences[0]

    # Check if top model has significantly higher confidence
    if top_conf >= 9:
        other_confs = [c for _, c in confidences[1:]]
        avg_others = sum(other_confs) / len(other_confs) if other_confs else 0

        if top_conf - avg_others >= 3:
            return {
                "early_exit_possible": True,
                "high_confidence_model": top_model,
                "top_confidence": top_conf,
                "avg_other_confidence": round(avg_others, 2),
                "reason": f"{top_model} has very high confidence ({top_conf}/10) vs others avg ({avg_others:.1f}/10)",
            }

    return {
        "early_exit_possible": False,
        "high_confidence_model": None,
        "reason": "No clear confidence leader",
    }
