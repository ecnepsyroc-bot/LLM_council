"""Event types for streaming responses."""

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    """Types of streaming events."""

    # Stage lifecycle
    STAGE_START = "stage_start"
    STAGE_COMPLETE = "stage_complete"
    STAGE_ERROR = "stage_error"

    # Model events
    MODEL_START = "model_start"
    MODEL_CHUNK = "model_chunk"
    MODEL_COMPLETE = "model_complete"
    MODEL_ERROR = "model_error"

    # Overall
    DELIBERATION_START = "deliberation_start"
    DELIBERATION_COMPLETE = "deliberation_complete"
    DELIBERATION_ERROR = "deliberation_error"

    # Progress
    PROGRESS = "progress"

    # Title
    TITLE_COMPLETE = "title_complete"


@dataclass
class StreamEvent:
    """Base class for streaming events."""

    type: EventType

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format."""
        data = asdict(self)
        data["type"] = self.type.value
        return f"data: {json.dumps(data)}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["type"] = self.type.value
        return data


@dataclass
class StageStartEvent(StreamEvent):
    """Emitted when a stage begins."""

    type: EventType = EventType.STAGE_START
    stage: int = 0
    stage_name: str = ""
    models: Optional[List[str]] = None

    def __post_init__(self):
        if self.models is None:
            self.models = []


@dataclass
class StageCompleteEvent(StreamEvent):
    """Emitted when a stage completes successfully."""

    type: EventType = EventType.STAGE_COMPLETE
    stage: int = 0
    stage_name: str = ""
    duration_ms: int = 0
    results_count: int = 0


@dataclass
class StageErrorEvent(StreamEvent):
    """Emitted when a stage fails."""

    type: EventType = EventType.STAGE_ERROR
    stage: int = 0
    stage_name: str = ""
    error: str = ""
    partial_results: int = 0
    can_continue: bool = False


@dataclass
class ModelStartEvent(StreamEvent):
    """Emitted when a model starts processing."""

    type: EventType = EventType.MODEL_START
    model: str = ""
    stage: int = 0


@dataclass
class ModelChunkEvent(StreamEvent):
    """Emitted for streaming content chunks."""

    type: EventType = EventType.MODEL_CHUNK
    model: str = ""
    stage: int = 0
    content: str = ""
    full_content: str = ""


@dataclass
class ModelCompleteEvent(StreamEvent):
    """Emitted when a model completes."""

    type: EventType = EventType.MODEL_COMPLETE
    model: str = ""
    stage: int = 0
    content: str = ""
    confidence: Optional[float] = None
    duration_ms: int = 0


@dataclass
class ModelErrorEvent(StreamEvent):
    """Emitted when a model fails."""

    type: EventType = EventType.MODEL_ERROR
    model: str = ""
    stage: int = 0
    error: str = ""
    error_code: Optional[str] = None
    retryable: bool = False


@dataclass
class ProgressEvent(StreamEvent):
    """Emitted to indicate overall progress."""

    type: EventType = EventType.PROGRESS
    stage: int = 0
    completed_models: int = 0
    total_models: int = 0
    percentage: float = 0.0


@dataclass
class DeliberationStartEvent(StreamEvent):
    """Emitted when deliberation begins."""

    type: EventType = EventType.DELIBERATION_START
    question: str = ""
    council_models: Optional[List[str]] = None
    chairman_model: str = ""

    def __post_init__(self):
        if self.council_models is None:
            self.council_models = []


@dataclass
class DeliberationCompleteEvent(StreamEvent):
    """Emitted when entire deliberation completes."""

    type: EventType = EventType.DELIBERATION_COMPLETE
    total_duration_ms: int = 0
    stage1_count: int = 0
    stage2_count: int = 0
    has_synthesis: bool = False
    consensus_reached: bool = False


@dataclass
class DeliberationErrorEvent(StreamEvent):
    """Emitted when deliberation fails completely."""

    type: EventType = EventType.DELIBERATION_ERROR
    error: str = ""
    failed_stage: int = 0
    partial_results: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.partial_results is None:
            self.partial_results = {}


@dataclass
class TitleCompleteEvent(StreamEvent):
    """Emitted when title generation completes."""

    type: EventType = EventType.TITLE_COMPLETE
    title: str = ""
