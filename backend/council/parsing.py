"""Parsing functions for council responses."""

import re
from typing import Dict, List, Optional, Tuple

# Default evaluation rubric
DEFAULT_RUBRIC = {
    "accuracy": "How factually correct and accurate is the response? (1-10)",
    "completeness": "How thoroughly does it address all aspects of the question? (1-10)",
    "clarity": "How clear and well-organized is the explanation? (1-10)",
    "reasoning": "How sound is the logical reasoning and argumentation? (1-10)",
    "practicality": "How practical and actionable is the advice given? (1-10)",
}


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """Parse the FINAL RANKING section from the model's response."""
    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            numbered_matches = re.findall(r"\d+\.\s*Response [A-Z]", ranking_section)
            if numbered_matches:
                return [re.search(r"Response [A-Z]", m).group() for m in numbered_matches]
            matches = re.findall(r"Response [A-Z]", ranking_section)
            return matches

    matches = re.findall(r"Response [A-Z]", ranking_text)
    return matches


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
        r"\n*\*?\*?CONFIDENCE:?\*?\*?\s*(\d+)\s*/?\s*10\s*$",
        r"\n*\*?\*?Confidence:?\*?\*?\s*(\d+)\s*/?\s*10\s*$",
        r"\n*\[CONFIDENCE:\s*(\d+)/10\]\s*$",
        r"\n*Confidence Score:\s*(\d+)/10\s*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            confidence = int(match.group(1))
            confidence = max(1, min(10, confidence))
            cleaned = re.sub(pattern, "", response_text, flags=re.IGNORECASE).strip()
            return cleaned, confidence

    return response_text, None


def build_rubric_prompt(
    user_query: str, responses_text: str, rubric: Dict[str, str] = None
) -> str:
    """Build a rubric-based evaluation prompt."""
    if rubric is None:
        rubric = DEFAULT_RUBRIC

    rubric_text = "\n".join(
        [f"- **{criterion}**: {description}" for criterion, description in rubric.items()]
    )

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
    response_pattern = (
        r"\*?\*?Response ([A-Z])\s*Evaluation:?\*?\*?(.*?)(?=\*?\*?Response [A-Z]|FINAL RANKING:|$)"
    )
    matches = re.findall(response_pattern, evaluation_text, re.DOTALL | re.IGNORECASE)

    for label, section in matches:
        response_key = f"Response {label}"
        scores[response_key] = {}

        # Extract individual criterion scores
        for criterion in DEFAULT_RUBRIC.keys():
            pattern = rf"{criterion}:\s*(\d+)/10"
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                scores[response_key][criterion] = int(match.group(1))

    return scores
