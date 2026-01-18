"""Test fixtures for LLM Council tests."""

from .responses import (
    SAMPLE_STAGE1_RESPONSES,
    SAMPLE_STAGE1_WITH_CONFIDENCE,
    make_stage1_response,
)
from .rankings import (
    SAMPLE_RANKINGS,
    SAMPLE_LABEL_TO_MODEL,
    make_ranking,
)

__all__ = [
    "SAMPLE_STAGE1_RESPONSES",
    "SAMPLE_STAGE1_WITH_CONFIDENCE",
    "make_stage1_response",
    "SAMPLE_RANKINGS",
    "SAMPLE_LABEL_TO_MODEL",
    "make_ranking",
]
