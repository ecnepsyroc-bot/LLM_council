"""
Hallucination detection via peer comparison.

Analyzes Stage 1 responses and Stage 2 peer rankings to identify
potential hallucinations through cross-model disagreement patterns.
"""

from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class HallucinationSignal:
    """A single hallucination signal for a response."""

    model: str
    signal_type: str  # confidence_mismatch, peer_rejection, outlier, contradiction
    severity: str  # low, medium, high
    description: str
    evidence: dict = field(default_factory=dict)


@dataclass
class HallucinationReport:
    """Complete hallucination analysis report."""

    has_concerns: bool
    overall_confidence: float  # 0-1, higher = more confident in responses
    signals: list[HallucinationSignal] = field(default_factory=list)
    model_scores: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "has_concerns": self.has_concerns,
            "overall_confidence": round(self.overall_confidence, 3),
            "signals": [
                {
                    "model": s.model,
                    "signal_type": s.signal_type,
                    "severity": s.severity,
                    "description": s.description,
                    "evidence": s.evidence
                }
                for s in self.signals
            ],
            "model_scores": {k: round(v, 3) for k, v in self.model_scores.items()},
            "recommendations": self.recommendations
        }


def detect_hallucinations(
    stage1_results: list[dict],
    stage2_results: list[dict],
    aggregate_rankings: list[dict],
    label_to_model: dict[str, str],
    thresholds: Optional[dict] = None
) -> HallucinationReport:
    """
    Analyze council results for potential hallucinations.

    Detection strategies:
    1. Confidence-Ranking Mismatch: High self-confidence but low peer ranking
    2. Peer Rejection: Response ranked last by multiple peers
    3. Outlier Detection: Response significantly diverges from consensus
    4. Rubric Score Variance: Large disagreement in evaluation scores

    Args:
        stage1_results: List of model responses with confidence scores
        stage2_results: List of peer rankings
        aggregate_rankings: Calculated aggregate rankings
        label_to_model: Mapping of anonymous labels to model IDs
        thresholds: Optional custom thresholds

    Returns:
        HallucinationReport with analysis results
    """
    # Default thresholds
    thresholds = thresholds or {}
    CONFIDENCE_MISMATCH_THRESHOLD = thresholds.get("confidence_mismatch", 3.0)
    PEER_REJECTION_THRESHOLD = thresholds.get("peer_rejection", 0.7)
    RANK_VARIANCE_THRESHOLD = thresholds.get("rank_variance", 2.0)

    signals: list[HallucinationSignal] = []
    model_scores: dict[str, float] = {}

    # Build reverse mapping: model -> label
    model_to_label = {v: k for k, v in label_to_model.items()}

    # Extract confidence scores from stage1
    confidence_map: dict[str, float] = {}
    for result in stage1_results:
        model = result.get("model", "")
        confidence = result.get("confidence")
        if confidence is not None:
            confidence_map[model] = float(confidence)

    # Build ranking position map from aggregate rankings
    position_map: dict[str, float] = {}
    for item in aggregate_rankings:
        model = item.get("model", "")
        avg_rank = item.get("average_rank", item.get("avg_position", 0))
        position_map[model] = float(avg_rank)

    # Build per-evaluator rankings
    evaluator_rankings: dict[str, list[str]] = {}
    for ranking in stage2_results:
        evaluator = ranking.get("model", ranking.get("evaluator_model", ""))
        parsed = ranking.get("parsed_ranking", [])
        if parsed:
            evaluator_rankings[evaluator] = parsed

    num_models = len(stage1_results)

    # === Detection Strategy 1: Confidence-Ranking Mismatch ===
    for model, confidence in confidence_map.items():
        if model not in position_map:
            continue

        avg_rank = position_map[model]
        # Normalize: confidence is 1-10, rank is 1-N
        # High confidence (8-10) with low rank (close to N) is suspicious
        normalized_confidence = confidence / 10.0  # 0-1
        normalized_rank = (num_models - avg_rank + 1) / num_models  # 1 is best -> 1.0

        mismatch = normalized_confidence - normalized_rank

        if mismatch > CONFIDENCE_MISMATCH_THRESHOLD / 10:
            severity = "high" if mismatch > 0.5 else "medium" if mismatch > 0.3 else "low"
            signals.append(HallucinationSignal(
                model=model,
                signal_type="confidence_mismatch",
                severity=severity,
                description=f"High confidence ({confidence}/10) but ranked #{avg_rank:.1f} by peers",
                evidence={
                    "self_confidence": confidence,
                    "peer_avg_rank": round(avg_rank, 2),
                    "mismatch_score": round(mismatch, 3)
                }
            ))

    # === Detection Strategy 2: Peer Rejection ===
    for model in [r.get("model", "") for r in stage1_results]:
        label = model_to_label.get(model)
        if not label:
            continue

        # Count how many evaluators ranked this response last
        last_place_count = 0
        total_evaluators = 0

        for evaluator, rankings in evaluator_rankings.items():
            if evaluator == model:  # Skip self-evaluation
                continue
            total_evaluators += 1
            if rankings and rankings[-1] == label:
                last_place_count += 1

        if total_evaluators > 0:
            rejection_rate = last_place_count / total_evaluators

            if rejection_rate >= PEER_REJECTION_THRESHOLD:
                severity = "high" if rejection_rate >= 0.9 else "medium"
                signals.append(HallucinationSignal(
                    model=model,
                    signal_type="peer_rejection",
                    severity=severity,
                    description=f"Ranked last by {last_place_count}/{total_evaluators} peers ({rejection_rate:.0%})",
                    evidence={
                        "last_place_count": last_place_count,
                        "total_evaluators": total_evaluators,
                        "rejection_rate": round(rejection_rate, 3)
                    }
                ))

    # === Detection Strategy 3: Rank Variance (Outlier) ===
    for model in [r.get("model", "") for r in stage1_results]:
        label = model_to_label.get(model)
        if not label:
            continue

        # Collect all rank positions for this response
        rank_positions = []
        for evaluator, rankings in evaluator_rankings.items():
            if evaluator == model:
                continue
            try:
                pos = rankings.index(label) + 1  # 1-indexed
                rank_positions.append(pos)
            except ValueError:
                continue

        if len(rank_positions) >= 2:
            # Calculate variance
            mean_rank = sum(rank_positions) / len(rank_positions)
            variance = sum((r - mean_rank) ** 2 for r in rank_positions) / len(rank_positions)
            std_dev = variance ** 0.5

            if std_dev >= RANK_VARIANCE_THRESHOLD:
                signals.append(HallucinationSignal(
                    model=model,
                    signal_type="outlier",
                    severity="medium",
                    description=f"High disagreement among peers (std dev: {std_dev:.2f})",
                    evidence={
                        "rank_positions": rank_positions,
                        "mean_rank": round(mean_rank, 2),
                        "std_dev": round(std_dev, 2)
                    }
                ))

    # === Detection Strategy 4: Rubric Score Analysis ===
    # Analyze rubric scores if available
    for ranking in stage2_results:
        rubric_scores = ranking.get("rubric_scores", {})
        if not rubric_scores:
            continue

        evaluator = ranking.get("model", ranking.get("evaluator_model", ""))

        for label, scores in rubric_scores.items():
            if not isinstance(scores, dict):
                continue

            model = label_to_model.get(label)
            if not model:
                continue

            # Check for very low accuracy scores
            accuracy = scores.get("accuracy", scores.get("factual_accuracy"))
            if accuracy is not None and accuracy <= 3:
                signals.append(HallucinationSignal(
                    model=model,
                    signal_type="low_accuracy_score",
                    severity="medium" if accuracy <= 2 else "low",
                    description=f"Low accuracy score ({accuracy}/10) from {evaluator}",
                    evidence={
                        "evaluator": evaluator,
                        "accuracy_score": accuracy,
                        "all_scores": scores
                    }
                ))

    # === Calculate Model Reliability Scores ===
    for model in [r.get("model", "") for r in stage1_results]:
        base_score = 1.0

        # Deduct for signals
        model_signals = [s for s in signals if s.model == model]
        for signal in model_signals:
            if signal.severity == "high":
                base_score -= 0.3
            elif signal.severity == "medium":
                base_score -= 0.15
            else:
                base_score -= 0.05

        # Boost for good peer ranking
        if model in position_map:
            avg_rank = position_map[model]
            if avg_rank <= 1.5:  # Top ranked
                base_score += 0.1

        model_scores[model] = max(0.0, min(1.0, base_score))

    # === Generate Report ===
    has_concerns = any(s.severity in ("high", "medium") for s in signals)
    overall_confidence = sum(model_scores.values()) / len(model_scores) if model_scores else 0.5

    recommendations = []
    if has_concerns:
        high_severity = [s for s in signals if s.severity == "high"]
        if high_severity:
            recommendations.append(
                "High-severity concerns detected. Consider requesting clarification or "
                "cross-referencing with external sources."
            )

        confidence_mismatches = [s for s in signals if s.signal_type == "confidence_mismatch"]
        if confidence_mismatches:
            recommendations.append(
                "Some models show overconfidence. Peer rankings may be more reliable "
                "than self-reported confidence scores."
            )

        peer_rejections = [s for s in signals if s.signal_type == "peer_rejection"]
        if peer_rejections:
            rejected_models = [s.model for s in peer_rejections]
            recommendations.append(
                f"Response(s) from {', '.join(rejected_models)} were consistently ranked "
                "poorly by peers. Exercise caution with these responses."
            )
    else:
        recommendations.append(
            "No significant hallucination signals detected. Peer consensus appears strong."
        )

    return HallucinationReport(
        has_concerns=has_concerns,
        overall_confidence=overall_confidence,
        signals=signals,
        model_scores=model_scores,
        recommendations=recommendations
    )


def analyze_response_consistency(
    stage1_results: list[dict],
    keywords: Optional[list[str]] = None
) -> dict:
    """
    Analyze consistency of factual claims across responses.

    Simple heuristic: check if key terms/numbers appear consistently.

    Args:
        stage1_results: Stage 1 responses
        keywords: Optional list of keywords to check for

    Returns:
        Consistency analysis dict
    """
    responses = [r.get("response", "") for r in stage1_results]
    models = [r.get("model", "") for r in stage1_results]

    if not responses:
        return {"consistent": True, "analysis": "No responses to analyze"}

    # Extract numbers from responses
    import re
    number_pattern = r'\b\d+(?:\.\d+)?(?:\s*%|\s*percent)?\b'

    numbers_by_model = {}
    for model, response in zip(models, responses):
        numbers = re.findall(number_pattern, response.lower())
        numbers_by_model[model] = set(numbers)

    # Find common and unique numbers
    if numbers_by_model:
        all_numbers = set()
        for nums in numbers_by_model.values():
            all_numbers.update(nums)

        common_numbers = all_numbers.copy()
        for nums in numbers_by_model.values():
            common_numbers &= nums

        # Calculate consistency score
        if all_numbers:
            consistency_score = len(common_numbers) / len(all_numbers)
        else:
            consistency_score = 1.0
    else:
        consistency_score = 1.0
        common_numbers = set()

    return {
        "consistent": consistency_score > 0.5,
        "consistency_score": round(consistency_score, 3),
        "common_facts": list(common_numbers)[:10],  # Limit output
        "numbers_by_model": {k: list(v)[:10] for k, v in numbers_by_model.items()}
    }
