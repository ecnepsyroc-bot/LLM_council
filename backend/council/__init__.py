"""
Council package for LLM Council deliberation.

This package provides all the components for the 3-stage council process:
- Stage 1: Collect individual responses
- Stage 2: Anonymous peer evaluation and ranking
- Stage 3: Chairman synthesis

Modules:
- voting: Voting methods (Borda, MRR, confidence-weighted)
- parsing: Response and ranking parsing
- consensus: Consensus detection
- stages: Stage implementations
- orchestration: Main council orchestration
- cache: Response caching layer
- hallucination: Peer-based hallucination detection
"""

# Voting methods
from .voting import (
    VotingMethod,
    calculate_aggregate_rankings,
    calculate_borda_count,
    calculate_confidence_weighted_rankings,
    calculate_mrr,
)

# Parsing functions
from .parsing import (
    DEFAULT_RUBRIC,
    build_rubric_prompt,
    parse_confidence_from_response,
    parse_ranking_from_text,
    parse_rubric_scores,
)

# Consensus detection
from .consensus import check_stage1_consensus, detect_consensus

# Stage implementations
from .stages import (
    generate_conversation_title,
    run_debate_round,
    select_rotating_chairman,
    stage1_collect_responses,
    stage1_self_moa,
    stage1_stream_responses,
    stage2_collect_rankings,
    stage2_with_debate,
    stage3_synthesize_final,
    stage3_with_meta_evaluation,
)

# Main orchestration
from .orchestration import run_full_council

# Caching
from .cache import (
    ResponseCache,
    get_cache,
    configure_cache,
    cached_council_query,
)

# Hallucination detection
from .hallucination import (
    detect_hallucinations,
    analyze_response_consistency,
    HallucinationReport,
    HallucinationSignal,
)

__all__ = [
    # Voting
    "VotingMethod",
    "calculate_aggregate_rankings",
    "calculate_borda_count",
    "calculate_mrr",
    "calculate_confidence_weighted_rankings",
    # Parsing
    "parse_ranking_from_text",
    "parse_confidence_from_response",
    "build_rubric_prompt",
    "parse_rubric_scores",
    "DEFAULT_RUBRIC",
    # Consensus
    "detect_consensus",
    "check_stage1_consensus",
    # Stage 1
    "stage1_collect_responses",
    "stage1_stream_responses",
    "stage1_self_moa",
    # Stage 2
    "stage2_collect_rankings",
    "stage2_with_debate",
    "run_debate_round",
    # Stage 3
    "stage3_synthesize_final",
    "stage3_with_meta_evaluation",
    "select_rotating_chairman",
    "generate_conversation_title",
    # Orchestration
    "run_full_council",
    # Caching
    "ResponseCache",
    "get_cache",
    "configure_cache",
    "cached_council_query",
    # Hallucination detection
    "detect_hallucinations",
    "analyze_response_consistency",
    "HallucinationReport",
    "HallucinationSignal",
]
