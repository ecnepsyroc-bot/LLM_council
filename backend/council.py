"""3-stage LLM Council orchestration with advanced voting and deliberation features."""

from typing import List, Dict, Any, Tuple, Optional, AsyncGenerator, Literal
import asyncio
import random
from collections import defaultdict
from .openrouter import query_models_parallel, query_model, stream_model_response
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL
import re


# =============================================================================
# VOTING METHODS
# =============================================================================

VotingMethod = Literal["simple", "borda", "mrr", "confidence_weighted"]


def calculate_borda_count(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    stage1_results: Optional[List[Dict[str, Any]]] = None
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
        parsed = ranking.get('parsed_ranking', [])
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
        aggregate.append({
            "model": model,
            "borda_score": score,
            "normalized_score": round(normalized, 3),
            "rankings_count": model_votes[model],
            "average_rank": round((num_candidates + 1) - (score / model_votes[model]), 2) if model_votes[model] > 0 else num_candidates
        })

    # Sort by borda_score descending (higher is better)
    aggregate.sort(key=lambda x: x['borda_score'], reverse=True)
    return aggregate


def calculate_mrr(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    stage1_results: Optional[List[Dict[str, Any]]] = None
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
        parsed = ranking.get('parsed_ranking', [])
        for position, label in enumerate(parsed, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                # Reciprocal rank: 1st = 1.0, 2nd = 0.5, 3rd = 0.33...
                model_rr_sum[model_name] += 1.0 / position
                model_votes[model_name] += 1

    aggregate = []
    for model, rr_sum in model_rr_sum.items():
        mrr = rr_sum / len(stage2_results) if stage2_results else 0
        aggregate.append({
            "model": model,
            "mrr_score": round(mrr, 3),
            "reciprocal_sum": round(rr_sum, 3),
            "rankings_count": model_votes[model],
            "average_rank": round(1 / mrr, 2) if mrr > 0 else len(label_to_model)
        })

    # Sort by mrr_score descending (higher is better)
    aggregate.sort(key=lambda x: x['mrr_score'], reverse=True)
    return aggregate


def calculate_confidence_weighted_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    stage1_results: List[Dict[str, Any]]
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
        conf = result.get('confidence')
        if conf is not None:
            confidence_map[result['model']] = conf
        else:
            confidence_map[result['model']] = 5  # Default middle confidence

    # Normalize confidences to weights (0.5 to 1.5 range)
    avg_confidence = sum(confidence_map.values()) / len(confidence_map) if confidence_map else 5

    model_weighted_scores: Dict[str, float] = defaultdict(float)
    model_raw_scores: Dict[str, float] = defaultdict(float)
    model_votes: Dict[str, int] = defaultdict(int)

    for ranking in stage2_results:
        voter_model = ranking.get('model', '')
        # Get voter's confidence as their voting weight
        voter_confidence = confidence_map.get(voter_model, 5)
        # Normalize weight to 0.5-1.5 range
        weight = 0.5 + (voter_confidence / 10)

        parsed = ranking.get('parsed_ranking', [])
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
        aggregate.append({
            "model": model,
            "weighted_score": round(model_weighted_scores[model], 2),
            "raw_score": model_raw_scores[model],
            "confidence_boost": round(model_weighted_scores[model] - model_raw_scores[model], 2),
            "rankings_count": model_votes[model],
            "average_rank": round((num_candidates + 1) - (model_raw_scores[model] / model_votes[model]), 2) if model_votes[model] > 0 else num_candidates
        })

    # Sort by weighted_score descending
    aggregate.sort(key=lambda x: x['weighted_score'], reverse=True)
    return aggregate


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    stage1_results: Optional[List[Dict[str, Any]]] = None,
    method: VotingMethod = "borda"
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
        return calculate_confidence_weighted_rankings(stage2_results, label_to_model, stage1_results)
    else:  # "simple" - original average rank method
        return _calculate_simple_average(stage2_results, label_to_model)


def _calculate_simple_average(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Original simple average rank calculation."""
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        parsed = ranking.get('parsed_ranking', [])
        for position, label in enumerate(parsed, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    aggregate.sort(key=lambda x: x['average_rank'])
    return aggregate


# =============================================================================
# CONFIDENCE PARSING
# =============================================================================

def parse_confidence_from_response(response_text: str) -> Tuple[str, Optional[int]]:
    """
    Parse confidence score from a response that includes it.

    Expected format: Response ends with "CONFIDENCE: X/10" or "Confidence: X"

    Args:
        response_text: The full response text

    Returns:
        Tuple of (cleaned_response, confidence_score or None)
    """
    if not response_text:
        return response_text, None

    patterns = [
        r'\n*\*?\*?CONFIDENCE:?\*?\*?\s*(\d+)\s*/?\s*10\s*$',
        r'\n*\*?\*?Confidence:?\*?\*?\s*(\d+)\s*/?\s*10\s*$',
        r'\n*\[CONFIDENCE:\s*(\d+)/10\]\s*$',
        r'\n*Confidence Score:\s*(\d+)/10\s*$',
    ]

    for pattern in patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            confidence = int(match.group(1))
            confidence = max(1, min(10, confidence))
            cleaned = re.sub(pattern, '', response_text, flags=re.IGNORECASE).strip()
            return cleaned, confidence

    return response_text, None


# =============================================================================
# RUBRIC-BASED EVALUATION
# =============================================================================

DEFAULT_RUBRIC = {
    "accuracy": "How factually correct and accurate is the response? (1-10)",
    "completeness": "How thoroughly does it address all aspects of the question? (1-10)",
    "clarity": "How clear and well-organized is the explanation? (1-10)",
    "reasoning": "How sound is the logical reasoning and argumentation? (1-10)",
    "practicality": "How practical and actionable is the advice given? (1-10)"
}


def build_rubric_prompt(
    user_query: str,
    responses_text: str,
    rubric: Dict[str, str] = None
) -> str:
    """Build a rubric-based evaluation prompt."""
    if rubric is None:
        rubric = DEFAULT_RUBRIC

    rubric_text = "\n".join([
        f"- **{criterion}**: {description}"
        for criterion, description in rubric.items()
    ])

    return f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

## Evaluation Rubric

Score each response on the following criteria (1-10 scale):
{rubric_text}

## Your Task

1. For EACH response, provide scores for each criterion and brief justification.
2. Format each response's evaluation as:

   **Response X Evaluation:**
   - Accuracy: [score]/10 - [brief justification]
   - Completeness: [score]/10 - [brief justification]
   - Clarity: [score]/10 - [brief justification]
   - Reasoning: [score]/10 - [brief justification]
   - Practicality: [score]/10 - [brief justification]
   - **Total: [sum]/50**

3. At the end, provide your FINAL RANKING based on total scores:

FINAL RANKING:
1. Response [letter]
2. Response [letter]
...

Provide your detailed evaluation:"""


def parse_rubric_scores(evaluation_text: str) -> Dict[str, Dict[str, int]]:
    """
    Parse rubric scores from evaluation text.

    Returns:
        Dict mapping response labels to criterion scores
        e.g., {"Response A": {"accuracy": 8, "completeness": 7, ...}, ...}
    """
    scores = {}

    # Find each response evaluation section
    response_pattern = r'\*?\*?Response ([A-Z])\s*Evaluation:?\*?\*?(.*?)(?=\*?\*?Response [A-Z]|FINAL RANKING:|$)'
    matches = re.findall(response_pattern, evaluation_text, re.DOTALL | re.IGNORECASE)

    for label, section in matches:
        response_key = f"Response {label}"
        scores[response_key] = {}

        # Extract individual criterion scores
        for criterion in DEFAULT_RUBRIC.keys():
            pattern = rf'{criterion}:\s*(\d+)/10'
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                scores[response_key][criterion] = int(match.group(1))

    return scores


# =============================================================================
# CONSENSUS DETECTION
# =============================================================================

def detect_consensus(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
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
            "early_exit_eligible": False
        }

    first_place_votes: Dict[str, int] = {}
    total_voters = 0

    for ranking in stage2_results:
        parsed = ranking.get('parsed_ranking', [])
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
            "early_exit_eligible": False
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
        "early_exit_eligible": early_exit_eligible
    }


def check_stage1_consensus(stage1_results: List[Dict[str, Any]], threshold: float = 0.8) -> Dict[str, Any]:
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
        conf = result.get('confidence')
        if conf is not None:
            confidences.append((result['model'], conf))

    if not confidences:
        return {
            "early_exit_possible": False,
            "high_confidence_model": None,
            "reason": "No confidence scores available"
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
                "reason": f"{top_model} has very high confidence ({top_conf}/10) vs others avg ({avg_others:.1f}/10)"
            }

    return {
        "early_exit_possible": False,
        "high_confidence_model": None,
        "reason": "No clear confidence leader"
    }


# =============================================================================
# STAGE 1: COLLECT RESPONSES
# =============================================================================

async def stage1_collect_responses(
    user_query: str,
    include_confidence: bool = True,
    models: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from council models.
    """
    if models is None:
        models = COUNCIL_MODELS

    if include_confidence:
        prompt = f"""{user_query}

After your response, please rate your confidence in your answer on a scale of 1-10 (where 1 is very uncertain and 10 is extremely confident). Format it as:
CONFIDENCE: X/10"""
    else:
        prompt = user_query

    messages = [{"role": "user", "content": prompt}]
    responses = await query_models_parallel(models, messages)

    stage1_results = []
    for model, response in responses.items():
        if response is not None:
            raw_content = response.get('content', '')
            if include_confidence:
                cleaned_response, confidence = parse_confidence_from_response(raw_content)
                stage1_results.append({
                    "model": model,
                    "response": cleaned_response,
                    "confidence": confidence
                })
            else:
                stage1_results.append({
                    "model": model,
                    "response": raw_content
                })

    return stage1_results


async def stage1_stream_responses(
    user_query: str,
    include_confidence: bool = True,
    models: List[str] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stage 1: Stream individual responses from all council models in parallel.
    """
    if models is None:
        models = COUNCIL_MODELS

    if include_confidence:
        prompt = f"""{user_query}

After your response, please rate your confidence in your answer on a scale of 1-10 (where 1 is very uncertain and 10 is extremely confident). Format it as:
CONFIDENCE: X/10"""
    else:
        prompt = user_query

    messages = [{"role": "user", "content": prompt}]
    model_results: Dict[str, Dict[str, Any]] = {}

    for model in models:
        yield {"type": "model_start", "model": model}

    async def stream_single_model(model: str):
        full_content = ""
        async for event in stream_model_response(model, messages):
            if event["type"] == "chunk":
                full_content = event.get("accumulated", full_content + event.get("content", ""))
                yield {
                    "type": "model_chunk",
                    "model": model,
                    "content": event.get("content", ""),
                    "accumulated": full_content
                }
            elif event["type"] == "done":
                full_content = event.get("full_content", full_content)
                if include_confidence:
                    cleaned_response, confidence = parse_confidence_from_response(full_content)
                    result = {"model": model, "response": cleaned_response, "confidence": confidence}
                else:
                    result = {"model": model, "response": full_content}
                model_results[model] = result
                yield {"type": "model_done", "model": model, "response": result}
            elif event["type"] == "error":
                yield {"type": "model_error", "model": model, "error": event.get("error", "Unknown error")}

    async def run_model_stream(model: str):
        events = []
        async for event in stream_single_model(model):
            events.append(event)
        return events

    tasks = {model: asyncio.create_task(run_model_stream(model)) for model in models}
    pending = set(tasks.values())

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            events = task.result()
            for event in events:
                yield event

    final_results = list(model_results.values())
    yield {"type": "all_done", "results": final_results}


# =============================================================================
# SELF-MOA: SINGLE MODEL SAMPLING
# =============================================================================

async def stage1_self_moa(
    user_query: str,
    model: str = None,
    num_samples: int = 5,
    temperature: float = 0.8
) -> List[Dict[str, Any]]:
    """
    Self-MoA: Sample multiple diverse responses from a single top-performing model.

    Instead of querying multiple different models, generate multiple responses
    from one model using temperature sampling for diversity.

    Args:
        user_query: The user's question
        model: Model to use (defaults to CHAIRMAN_MODEL)
        num_samples: Number of diverse samples to generate
        temperature: Sampling temperature for diversity (higher = more diverse)

    Returns:
        List of response dicts, each with a unique "sample_id"
    """
    if model is None:
        model = CHAIRMAN_MODEL

    prompt = f"""{user_query}

After your response, please rate your confidence in your answer on a scale of 1-10 (where 1 is very uncertain and 10 is extremely confident). Format it as:
CONFIDENCE: X/10"""

    messages = [{"role": "user", "content": prompt}]

    # Create multiple concurrent requests to the same model
    async def sample_once(sample_id: int):
        response = await query_model(model, messages, temperature=temperature)
        if response is not None:
            raw_content = response.get('content', '')
            cleaned, confidence = parse_confidence_from_response(raw_content)
            return {
                "model": f"{model}#sample{sample_id}",
                "base_model": model,
                "sample_id": sample_id,
                "response": cleaned,
                "confidence": confidence
            }
        return None

    tasks = [sample_once(i) for i in range(num_samples)]
    results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]


# =============================================================================
# STAGE 2: COLLECT RANKINGS (with rubric option)
# =============================================================================

async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    use_rubric: bool = False,
    rubric: Dict[str, str] = None,
    models: List[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        use_rubric: Whether to use rubric-based evaluation
        rubric: Custom rubric dict (criterion -> description)
        models: Models to use for ranking (defaults to COUNCIL_MODELS)

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    if models is None:
        models = COUNCIL_MODELS

    labels = [chr(65 + i) for i in range(len(stage1_results))]

    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    if use_rubric:
        ranking_prompt = build_rubric_prompt(user_query, responses_text, rubric)
    else:
        ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]
    responses = await query_models_parallel(models, messages)

    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)

            result = {
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            }

            # Add rubric scores if using rubric evaluation
            if use_rubric:
                result["rubric_scores"] = parse_rubric_scores(full_text)

            stage2_results.append(result)

    return stage2_results, label_to_model


# =============================================================================
# MULTI-ROUND DEBATE
# =============================================================================

async def run_debate_round(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    previous_rankings: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    round_number: int
) -> List[Dict[str, Any]]:
    """
    Run a single round of debate where models can revise based on peer feedback.

    Args:
        user_query: Original query
        stage1_results: Initial responses
        previous_rankings: Rankings from previous round
        label_to_model: Label to model mapping
        round_number: Current debate round (1-indexed)

    Returns:
        Updated rankings after this debate round
    """
    labels = list(label_to_model.keys())

    # Build summary of previous rankings
    ranking_summary = []
    for rank in previous_rankings:
        model = rank['model'].split('/')[-1]
        parsed = rank.get('parsed_ranking', [])
        if parsed:
            ranking_summary.append(f"- {model} ranked: {' > '.join(parsed)}")

    ranking_text = "\n".join(ranking_summary)

    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip([l.split()[-1] for l in labels], stage1_results)
    ])

    debate_prompt = f"""This is Round {round_number} of a multi-round evaluation debate.

Original Question: {user_query}

Responses being evaluated:
{responses_text}

Previous round rankings from all evaluators:
{ranking_text}

Considering the collective assessment from the previous round:
1. Reflect on whether you agree or disagree with the emerging consensus
2. Consider perspectives you may have missed
3. Provide your updated evaluation and ranking

If you've changed your ranking, explain why. If you maintain your previous ranking, explain why you believe it's correct despite any disagreement.

End with your FINAL RANKING:
1. Response [letter]
2. Response [letter]
..."""

    messages = [{"role": "user", "content": debate_prompt}]
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    debate_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            debate_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed,
                "debate_round": round_number
            })

    return debate_results


async def stage2_with_debate(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    num_rounds: int = 2,
    use_rubric: bool = False
) -> Tuple[List[Dict[str, Any]], Dict[str, str], List[List[Dict[str, Any]]]]:
    """
    Stage 2 with multi-round debate.

    Args:
        user_query: Original query
        stage1_results: Stage 1 results
        num_rounds: Number of debate rounds (1 = no debate, just initial ranking)
        use_rubric: Whether to use rubric evaluation

    Returns:
        Tuple of (final_rankings, label_to_model, debate_history)
    """
    # Initial ranking round
    rankings, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results, use_rubric=use_rubric
    )

    debate_history = [rankings]

    # Additional debate rounds
    for round_num in range(2, num_rounds + 1):
        rankings = await run_debate_round(
            user_query, stage1_results, rankings, label_to_model, round_num
        )
        debate_history.append(rankings)

    return rankings, label_to_model, debate_history


# =============================================================================
# STAGE 3: CHAIRMAN SYNTHESIS (with rotation option)
# =============================================================================

async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman_model: str = None,
    aggregate_rankings: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        chairman_model: Model to use as chairman (defaults to CHAIRMAN_MODEL)
        aggregate_rankings: Optional aggregate rankings to inform synthesis

    Returns:
        Dict with 'model' and 'response' keys
    """
    if chairman_model is None:
        chairman_model = CHAIRMAN_MODEL

    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    # Add aggregate rankings context if available
    rankings_context = ""
    if aggregate_rankings:
        rankings_list = "\n".join([
            f"{i+1}. {r['model'].split('/')[-1]} (score: {r.get('borda_score', r.get('average_rank', 'N/A'))})"
            for i, r in enumerate(aggregate_rankings[:5])
        ])
        rankings_context = f"""
AGGREGATE RANKINGS (consensus view):
{rankings_list}
"""

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}
{rankings_context}
Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement
- The aggregate rankings showing which responses were most highly rated

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]
    response = await query_model(chairman_model, messages)

    if response is None:
        return {
            "model": chairman_model,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": chairman_model,
        "response": response.get('content', '')
    }


def select_rotating_chairman(
    stage1_results: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]] = None,
    method: Literal["top_ranked", "highest_confidence", "random"] = "top_ranked"
) -> str:
    """
    Select chairman using rotation/selection strategy.

    Args:
        stage1_results: Stage 1 results
        aggregate_rankings: Aggregate rankings from Stage 2
        method: Selection method

    Returns:
        Model identifier for the selected chairman
    """
    if method == "top_ranked" and aggregate_rankings:
        # Select the top-ranked model as chairman
        return aggregate_rankings[0]['model']

    elif method == "highest_confidence":
        # Select model with highest confidence
        best = max(stage1_results, key=lambda x: x.get('confidence', 0))
        return best['model']

    elif method == "random":
        # Random selection
        return random.choice(stage1_results)['model']

    # Default fallback
    return CHAIRMAN_MODEL


async def stage3_with_meta_evaluation(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman_response: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Meta-evaluate the chairman's synthesis.

    Have another model critique the chairman's synthesis to reduce chairman bias.

    Returns:
        Dict with original synthesis and meta-evaluation
    """
    meta_prompt = f"""You are a meta-evaluator reviewing a Chairman's synthesis of multiple AI responses.

Original Question: {user_query}

The Chairman ({chairman_response['model']}) provided this synthesis:
{chairman_response['response']}

Your task:
1. Evaluate whether the synthesis fairly represents the council's collective wisdom
2. Identify any potential biases or omissions
3. Suggest any important points that were missed
4. Rate the synthesis quality (1-10)

Provide your meta-evaluation:"""

    messages = [{"role": "user", "content": meta_prompt}]

    # Use a different model for meta-evaluation
    meta_evaluator = "google/gemini-2.5-pro-preview-06-05"
    if meta_evaluator == chairman_response['model']:
        meta_evaluator = "anthropic/claude-opus-4"

    response = await query_model(meta_evaluator, messages)

    return {
        "synthesis": chairman_response,
        "meta_evaluation": {
            "model": meta_evaluator,
            "evaluation": response.get('content', '') if response else "Meta-evaluation unavailable"
        }
    }


# =============================================================================
# RANKING PARSING
# =============================================================================

def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """Parse the FINAL RANKING section from the model's response."""
    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


# =============================================================================
# TITLE GENERATION
# =============================================================================

async def generate_conversation_title(user_query: str) -> str:
    """Generate a short title for a conversation."""
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()
    title = title.strip('"\'')

    if len(title) > 50:
        title = title[:47] + "..."

    return title


# =============================================================================
# MAIN ORCHESTRATION
# =============================================================================

async def run_full_council(
    user_query: str,
    voting_method: VotingMethod = "borda",
    use_rubric: bool = False,
    debate_rounds: int = 1,
    enable_early_exit: bool = True,
    use_self_moa: bool = False,
    rotating_chairman: bool = False,
    meta_evaluate: bool = False
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
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

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
    if enable_early_exit and consensus.get('early_exit_eligible'):
        # For high consensus, we can provide a simpler synthesis
        early_exit_used = True

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query, stage1_results, stage2_results,
        chairman_model=chairman,
        aggregate_rankings=aggregate_rankings
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
            "chairman_model": chairman
        },
        "stage1_consensus": stage1_consensus
    }

    if debate_history:
        metadata["debate_history"] = debate_history

    return stage1_results, stage2_results, stage3_result, metadata
