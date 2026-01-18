"""3-stage LLM Council orchestration."""

from typing import List, Dict, Any, Tuple, Optional, AsyncGenerator
import asyncio
from .openrouter import query_models_parallel, query_model, stream_model_response
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL
import re


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

    # Look for confidence pattern at the end of the response
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
            # Clamp to 1-10 range
            confidence = max(1, min(10, confidence))
            # Remove the confidence line from the response
            cleaned = re.sub(pattern, '', response_text, flags=re.IGNORECASE).strip()
            return cleaned, confidence

    return response_text, None


async def stage1_collect_responses(user_query: str, include_confidence: bool = True) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question
        include_confidence: Whether to ask models to rate their confidence

    Returns:
        List of dicts with 'model', 'response', and optionally 'confidence' keys
    """
    # Build the prompt, optionally asking for confidence
    if include_confidence:
        prompt = f"""{user_query}

After your response, please rate your confidence in your answer on a scale of 1-10 (where 1 is very uncertain and 10 is extremely confident). Format it as:
CONFIDENCE: X/10"""
    else:
        prompt = user_query

    messages = [{"role": "user", "content": prompt}]

    # Query all models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
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
    include_confidence: bool = True
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stage 1: Stream individual responses from all council models in parallel.

    Args:
        user_query: The user's question
        include_confidence: Whether to ask models to rate their confidence

    Yields:
        Dict with streaming events:
        - type: 'model_start' | 'model_chunk' | 'model_done' | 'all_done'
        - model: model identifier
        - content: chunk content (for 'model_chunk')
        - accumulated: full content so far (for 'model_chunk')
        - response: parsed response object (for 'model_done')
    """
    # Build the prompt
    if include_confidence:
        prompt = f"""{user_query}

After your response, please rate your confidence in your answer on a scale of 1-10 (where 1 is very uncertain and 10 is extremely confident). Format it as:
CONFIDENCE: X/10"""
    else:
        prompt = user_query

    messages = [{"role": "user", "content": prompt}]

    # Track results from each model
    model_results: Dict[str, Dict[str, Any]] = {}
    active_streams = set(COUNCIL_MODELS)

    # Signal that all models are starting
    for model in COUNCIL_MODELS:
        yield {
            "type": "model_start",
            "model": model
        }

    async def stream_single_model(model: str):
        """Stream a single model and collect results."""
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
                # Parse confidence if enabled
                if include_confidence:
                    cleaned_response, confidence = parse_confidence_from_response(full_content)
                    result = {
                        "model": model,
                        "response": cleaned_response,
                        "confidence": confidence
                    }
                else:
                    result = {
                        "model": model,
                        "response": full_content
                    }
                model_results[model] = result
                yield {
                    "type": "model_done",
                    "model": model,
                    "response": result
                }
            elif event["type"] == "error":
                yield {
                    "type": "model_error",
                    "model": model,
                    "error": event.get("error", "Unknown error")
                }

    # Create tasks for all models
    async def run_model_stream(model: str):
        events = []
        async for event in stream_single_model(model):
            events.append(event)
        return events

    # Run all streams concurrently and merge events
    tasks = {model: asyncio.create_task(run_model_stream(model)) for model in COUNCIL_MODELS}

    # Wait for all to complete, yielding events as they come
    pending = set(tasks.values())
    model_to_task = {id(task): model for model, task in tasks.items()}

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

        for task in done:
            events = task.result()
            for event in events:
                yield event

    # Final event with all results
    final_results = list(model_results.values())
    yield {
        "type": "all_done",
        "results": final_results
    }


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

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

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


def detect_consensus(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> Dict[str, Any]:
    """
    Detect if there is consensus among models on the top-ranked response.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        Dict with consensus metadata:
        - has_consensus: bool - True if all models agree on #1
        - agreement_score: float - 0.0 to 1.0, proportion of models agreeing on #1
        - top_model: str | None - The model that was ranked #1 by consensus
        - top_votes: int - Number of votes for the top model
        - total_voters: int - Total number of models that provided rankings
    """
    if not stage2_results:
        return {
            "has_consensus": False,
            "agreement_score": 0.0,
            "top_model": None,
            "top_votes": 0,
            "total_voters": 0
        }

    # Count first-place votes for each response
    first_place_votes: Dict[str, int] = {}
    total_voters = 0

    for ranking in stage2_results:
        parsed = ranking.get('parsed_ranking', [])
        if parsed:
            first_choice = parsed[0]  # e.g., "Response A"
            first_place_votes[first_choice] = first_place_votes.get(first_choice, 0) + 1
            total_voters += 1

    if total_voters == 0:
        return {
            "has_consensus": False,
            "agreement_score": 0.0,
            "top_model": None,
            "top_votes": 0,
            "total_voters": 0
        }

    # Find the response with the most first-place votes
    top_label = max(first_place_votes, key=first_place_votes.get)
    top_votes = first_place_votes[top_label]

    # Calculate agreement score (proportion that agree on #1)
    agreement_score = top_votes / total_voters

    # Map the label back to the model name
    top_model = label_to_model.get(top_label)

    # Full consensus means everyone agrees
    has_consensus = top_votes == total_voters and total_voters > 1

    return {
        "has_consensus": has_consensus,
        "agreement_score": round(agreement_score, 2),
        "top_model": top_model,
        "top_votes": top_votes,
        "total_voters": total_voters
    }


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(user_query: str) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(user_query)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Detect consensus
    consensus = detect_consensus(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "consensus": consensus
    }

    return stage1_results, stage2_results, stage3_result, metadata
