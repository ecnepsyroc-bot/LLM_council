"""Sample Stage 2 rankings for testing."""

SAMPLE_LABEL_TO_MODEL = {
    "Response A": "openai/gpt-4",
    "Response B": "anthropic/claude-3",
    "Response C": "google/gemini-pro",
}

SAMPLE_RANKINGS = [
    {
        "model": "openai/gpt-4",
        "ranking": """I've evaluated all responses carefully.

Response B provides the most comprehensive answer with clear reasoning.
Response A is good but lacks some depth.
Response C is adequate but could be more detailed.

FINAL RANKING:
1. Response B
2. Response A
3. Response C""",
        "parsed_ranking": ["Response B", "Response A", "Response C"]
    },
    {
        "model": "anthropic/claude-3",
        "ranking": """After careful analysis:

Response A has strong technical accuracy.
Response B is well-structured.
Response C needs improvement.

FINAL RANKING:
1. Response A
2. Response B
3. Response C""",
        "parsed_ranking": ["Response A", "Response B", "Response C"]
    },
    {
        "model": "google/gemini-pro",
        "ranking": """My evaluation:

FINAL RANKING:
1. Response B
2. Response A
3. Response C""",
        "parsed_ranking": ["Response B", "Response A", "Response C"]
    },
]

# Rankings with unanimous agreement
UNANIMOUS_RANKINGS = [
    {"model": "model-1", "parsed_ranking": ["Response A", "Response B", "Response C"]},
    {"model": "model-2", "parsed_ranking": ["Response A", "Response B", "Response C"]},
    {"model": "model-3", "parsed_ranking": ["Response A", "Response B", "Response C"]},
]

# Rankings with no agreement (circular)
SPLIT_RANKINGS = [
    {"model": "model-1", "parsed_ranking": ["Response A", "Response B", "Response C"]},
    {"model": "model-2", "parsed_ranking": ["Response B", "Response C", "Response A"]},
    {"model": "model-3", "parsed_ranking": ["Response C", "Response A", "Response B"]},
]

# Rankings with confidence scores
RANKINGS_WITH_CONFIDENCE = [
    {
        "model": "model-1",
        "ranking": "FINAL RANKING:\n1. Response A\n2. Response B\n\nCONFIDENCE: 9/10",
        "parsed_ranking": ["Response A", "Response B"]
    },
    {
        "model": "model-2",
        "ranking": "FINAL RANKING:\n1. Response B\n2. Response A\n\nCONFIDENCE: 7/10",
        "parsed_ranking": ["Response B", "Response A"]
    },
]


def make_ranking(
    model: str,
    parsed_ranking: list[str],
    raw_ranking: str = None,
    debate_round: int = 1,
    rubric_scores: dict = None
) -> dict:
    """Create a Stage 2 ranking dict for testing."""
    if raw_ranking is None:
        raw_ranking = "FINAL RANKING:\n" + "\n".join(
            f"{i+1}. {label}" for i, label in enumerate(parsed_ranking)
        )

    result = {
        "model": model,
        "ranking": raw_ranking,
        "parsed_ranking": parsed_ranking,
    }

    if debate_round != 1:
        result["debate_round"] = debate_round
    if rubric_scores is not None:
        result["rubric_scores"] = rubric_scores

    return result
