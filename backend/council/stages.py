"""Stage implementations for council deliberation."""

import asyncio
import random
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Tuple

from ..config import CHAIRMAN_MODEL, COUNCIL_MODELS
from ..openrouter import query_model, query_models_parallel, stream_model_response
from .parsing import (
    build_rubric_prompt,
    parse_confidence_from_response,
    parse_ranking_from_text,
    parse_rubric_scores,
)


# =============================================================================
# STAGE 1: COLLECT RESPONSES
# =============================================================================


async def stage1_collect_responses(
    user_query: str, include_confidence: bool = True, models: List[str] = None
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
            raw_content = response.get("content", "")
            if include_confidence:
                cleaned_response, confidence = parse_confidence_from_response(raw_content)
                stage1_results.append(
                    {"model": model, "response": cleaned_response, "confidence": confidence}
                )
            else:
                stage1_results.append({"model": model, "response": raw_content})

    return stage1_results


async def stage1_stream_responses(
    user_query: str, include_confidence: bool = True, models: List[str] = None
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
                    "accumulated": full_content,
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
                yield {
                    "type": "model_error",
                    "model": model,
                    "error": event.get("error", "Unknown error"),
                }

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
    user_query: str, model: str = None, num_samples: int = 5, temperature: float = 0.8
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
            raw_content = response.get("content", "")
            cleaned, confidence = parse_confidence_from_response(raw_content)
            return {
                "model": f"{model}#sample{sample_id}",
                "base_model": model,
                "sample_id": sample_id,
                "response": cleaned,
                "confidence": confidence,
            }
        return None

    tasks = [sample_once(i) for i in range(num_samples)]
    results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]


# =============================================================================
# STAGE 2: COLLECT RANKINGS
# =============================================================================


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    use_rubric: bool = False,
    rubric: Dict[str, str] = None,
    models: List[str] = None,
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
        f"Response {label}": result["model"] for label, result in zip(labels, stage1_results)
    }

    responses_text = "\n\n".join(
        [f"Response {label}:\n{result['response']}" for label, result in zip(labels, stage1_results)]
    )

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
            full_text = response.get("content", "")
            parsed = parse_ranking_from_text(full_text)

            result = {"model": model, "ranking": full_text, "parsed_ranking": parsed}

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
    round_number: int,
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
        model = rank["model"].split("/")[-1]
        parsed = rank.get("parsed_ranking", [])
        if parsed:
            ranking_summary.append(f"- {model} ranked: {' > '.join(parsed)}")

    ranking_text = "\n".join(ranking_summary)

    responses_text = "\n\n".join(
        [
            f"Response {label}:\n{result['response']}"
            for label, result in zip([lbl.split()[-1] for lbl in labels], stage1_results)
        ]
    )

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
            full_text = response.get("content", "")
            parsed = parse_ranking_from_text(full_text)
            debate_results.append(
                {
                    "model": model,
                    "ranking": full_text,
                    "parsed_ranking": parsed,
                    "debate_round": round_number,
                }
            )

    return debate_results


async def stage2_with_debate(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    num_rounds: int = 2,
    use_rubric: bool = False,
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
# STAGE 3: CHAIRMAN SYNTHESIS
# =============================================================================


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman_model: str = None,
    aggregate_rankings: List[Dict[str, Any]] = None,
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

    stage1_text = "\n\n".join(
        [f"Model: {result['model']}\nResponse: {result['response']}" for result in stage1_results]
    )

    stage2_text = "\n\n".join(
        [f"Model: {result['model']}\nRanking: {result['ranking']}" for result in stage2_results]
    )

    # Add aggregate rankings context if available
    rankings_context = ""
    if aggregate_rankings:
        rankings_list = "\n".join(
            [
                f"{i+1}. {r['model'].split('/')[-1]} (score: {r.get('borda_score', r.get('average_rank', 'N/A'))})"
                for i, r in enumerate(aggregate_rankings[:5])
            ]
        )
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
            "response": "Error: Unable to generate final synthesis.",
        }

    return {"model": chairman_model, "response": response.get("content", "")}


def select_rotating_chairman(
    stage1_results: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]] = None,
    method: Literal["top_ranked", "highest_confidence", "random"] = "top_ranked",
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
        return aggregate_rankings[0]["model"]

    elif method == "highest_confidence":
        # Select model with highest confidence
        best = max(stage1_results, key=lambda x: x.get("confidence", 0))
        return best["model"]

    elif method == "random":
        # Random selection
        return random.choice(stage1_results)["model"]

    # Default fallback
    return CHAIRMAN_MODEL


async def stage3_with_meta_evaluation(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman_response: Dict[str, Any],
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
    if meta_evaluator == chairman_response["model"]:
        meta_evaluator = "anthropic/claude-opus-4"

    response = await query_model(meta_evaluator, messages)

    return {
        "synthesis": chairman_response,
        "meta_evaluation": {
            "model": meta_evaluator,
            "evaluation": response.get("content", "") if response else "Meta-evaluation unavailable",
        },
    }


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

    title = response.get("content", "New Conversation").strip()
    title = title.strip("\"'")

    if len(title) > 50:
        title = title[:47] + "..."

    return title
