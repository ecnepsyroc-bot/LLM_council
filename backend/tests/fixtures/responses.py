"""Sample Stage 1 responses for testing."""

SAMPLE_STAGE1_RESPONSES = [
    {
        "model": "openai/gpt-4",
        "response": "The answer is 42. This is based on careful analysis of the question."
    },
    {
        "model": "anthropic/claude-3",
        "response": "I believe the answer is 42, derived from mathematical reasoning."
    },
    {
        "model": "google/gemini-pro",
        "response": "After consideration, the answer appears to be 42."
    },
]

SAMPLE_STAGE1_WITH_CONFIDENCE = [
    {
        "model": "openai/gpt-4",
        "response": "The answer is 42.",
        "confidence": 8.5
    },
    {
        "model": "anthropic/claude-3",
        "response": "I believe the answer is 42.",
        "confidence": 9.0
    },
    {
        "model": "google/gemini-pro",
        "response": "The answer appears to be 42.",
        "confidence": 7.0
    },
]

SAMPLE_SELF_MOA_RESPONSES = [
    {
        "model": "openai/gpt-4#sample1",
        "base_model": "openai/gpt-4",
        "sample_id": 1,
        "response": "Sample 1 response",
        "confidence": 8.0
    },
    {
        "model": "openai/gpt-4#sample2",
        "base_model": "openai/gpt-4",
        "sample_id": 2,
        "response": "Sample 2 response",
        "confidence": 7.5
    },
]


def make_stage1_response(
    model: str,
    response: str,
    confidence: float = None,
    base_model: str = None,
    sample_id: int = None
) -> dict:
    """Create a Stage 1 response dict for testing."""
    result = {"model": model, "response": response}
    if confidence is not None:
        result["confidence"] = confidence
    if base_model is not None:
        result["base_model"] = base_model
    if sample_id is not None:
        result["sample_id"] = sample_id
    return result
