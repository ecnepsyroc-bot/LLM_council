"""Tests for streaming events."""

import json
import pytest

from backend.streaming import (
    EventType,
    StreamEvent,
    StageStartEvent,
    StageCompleteEvent,
    StageErrorEvent,
    ModelStartEvent,
    ModelChunkEvent,
    ModelCompleteEvent,
    ModelErrorEvent,
    ProgressEvent,
    DeliberationStartEvent,
    DeliberationCompleteEvent,
    DeliberationErrorEvent,
    TitleCompleteEvent,
)


class TestEventType:
    """Tests for event type enum."""

    def test_event_type_values(self):
        """Event types have correct string values."""
        assert EventType.STAGE_START.value == "stage_start"
        assert EventType.MODEL_CHUNK.value == "model_chunk"
        assert EventType.DELIBERATION_COMPLETE.value == "deliberation_complete"


class TestStreamEvent:
    """Tests for base StreamEvent."""

    def test_to_sse_format(self):
        """Events convert to SSE format correctly."""
        event = StageStartEvent(stage=1, stage_name="Response Collection")
        sse = event.to_sse()

        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")

        # Parse JSON content
        json_str = sse[6:-2]  # Remove "data: " and "\n\n"
        data = json.loads(json_str)

        assert data["type"] == "stage_start"
        assert data["stage"] == 1
        assert data["stage_name"] == "Response Collection"

    def test_to_dict(self):
        """Events convert to dict correctly."""
        event = ModelCompleteEvent(
            model="openai/gpt-4",
            stage=1,
            content="Test response",
            confidence=0.85,
            duration_ms=1500,
        )
        data = event.to_dict()

        assert data["type"] == "model_complete"
        assert data["model"] == "openai/gpt-4"
        assert data["content"] == "Test response"
        assert data["confidence"] == 0.85
        assert data["duration_ms"] == 1500


class TestStageEvents:
    """Tests for stage lifecycle events."""

    def test_stage_start_event(self):
        """StageStartEvent has correct fields."""
        event = StageStartEvent(
            stage=1,
            stage_name="Response Collection",
            models=["model1", "model2"],
        )

        assert event.type == EventType.STAGE_START
        assert event.stage == 1
        assert event.stage_name == "Response Collection"
        assert event.models == ["model1", "model2"]

    def test_stage_start_default_models(self):
        """StageStartEvent defaults to empty models list."""
        event = StageStartEvent(stage=1, stage_name="Test")
        assert event.models == []

    def test_stage_complete_event(self):
        """StageCompleteEvent has correct fields."""
        event = StageCompleteEvent(
            stage=2,
            stage_name="Peer Evaluation",
            duration_ms=5000,
            results_count=5,
        )

        assert event.type == EventType.STAGE_COMPLETE
        assert event.duration_ms == 5000
        assert event.results_count == 5

    def test_stage_error_event(self):
        """StageErrorEvent has correct fields."""
        event = StageErrorEvent(
            stage=1,
            stage_name="Response Collection",
            error="Timeout",
            partial_results=3,
            can_continue=True,
        )

        assert event.type == EventType.STAGE_ERROR
        assert event.error == "Timeout"
        assert event.partial_results == 3
        assert event.can_continue is True


class TestModelEvents:
    """Tests for model-level events."""

    def test_model_start_event(self):
        """ModelStartEvent has correct fields."""
        event = ModelStartEvent(model="openai/gpt-4", stage=1)

        assert event.type == EventType.MODEL_START
        assert event.model == "openai/gpt-4"
        assert event.stage == 1

    def test_model_chunk_event(self):
        """ModelChunkEvent has correct fields."""
        event = ModelChunkEvent(
            model="openai/gpt-4",
            stage=1,
            content="Hello",
            full_content="Hello, world",
        )

        assert event.type == EventType.MODEL_CHUNK
        assert event.content == "Hello"
        assert event.full_content == "Hello, world"

    def test_model_complete_event(self):
        """ModelCompleteEvent has correct fields."""
        event = ModelCompleteEvent(
            model="openai/gpt-4",
            stage=1,
            content="Full response",
            confidence=0.9,
            duration_ms=2000,
        )

        assert event.type == EventType.MODEL_COMPLETE
        assert event.confidence == 0.9
        assert event.duration_ms == 2000

    def test_model_complete_no_confidence(self):
        """ModelCompleteEvent confidence can be None."""
        event = ModelCompleteEvent(
            model="openai/gpt-4",
            stage=1,
            content="Response",
        )

        assert event.confidence is None

    def test_model_error_event(self):
        """ModelErrorEvent has correct fields."""
        event = ModelErrorEvent(
            model="openai/gpt-4",
            stage=1,
            error="Rate limit exceeded",
            error_code="RateLimitError",
            retryable=True,
        )

        assert event.type == EventType.MODEL_ERROR
        assert event.error == "Rate limit exceeded"
        assert event.error_code == "RateLimitError"
        assert event.retryable is True


class TestProgressEvent:
    """Tests for progress event."""

    def test_progress_event(self):
        """ProgressEvent has correct fields."""
        event = ProgressEvent(
            stage=1,
            completed_models=3,
            total_models=5,
            percentage=60.0,
        )

        assert event.type == EventType.PROGRESS
        assert event.completed_models == 3
        assert event.total_models == 5
        assert event.percentage == 60.0


class TestDeliberationEvents:
    """Tests for deliberation lifecycle events."""

    def test_deliberation_start_event(self):
        """DeliberationStartEvent has correct fields."""
        event = DeliberationStartEvent(
            question="What is AI?",
            council_models=["model1", "model2"],
            chairman_model="chairman",
        )

        assert event.type == EventType.DELIBERATION_START
        assert event.question == "What is AI?"
        assert event.council_models == ["model1", "model2"]
        assert event.chairman_model == "chairman"

    def test_deliberation_complete_event(self):
        """DeliberationCompleteEvent has correct fields."""
        event = DeliberationCompleteEvent(
            total_duration_ms=30000,
            stage1_count=5,
            stage2_count=5,
            has_synthesis=True,
            consensus_reached=True,
        )

        assert event.type == EventType.DELIBERATION_COMPLETE
        assert event.total_duration_ms == 30000
        assert event.has_synthesis is True
        assert event.consensus_reached is True

    def test_deliberation_error_event(self):
        """DeliberationErrorEvent has correct fields."""
        event = DeliberationErrorEvent(
            error="All models failed",
            failed_stage=1,
            partial_results={"stage1_count": 2},
        )

        assert event.type == EventType.DELIBERATION_ERROR
        assert event.error == "All models failed"
        assert event.failed_stage == 1
        assert event.partial_results == {"stage1_count": 2}

    def test_deliberation_error_default_partial(self):
        """DeliberationErrorEvent defaults to empty partial results."""
        event = DeliberationErrorEvent(error="Failed", failed_stage=0)
        assert event.partial_results == {}


class TestTitleEvent:
    """Tests for title event."""

    def test_title_complete_event(self):
        """TitleCompleteEvent has correct fields."""
        event = TitleCompleteEvent(title="Discussion about AI")

        assert event.type == EventType.TITLE_COMPLETE
        assert event.title == "Discussion about AI"


class TestEventSerialization:
    """Tests for event serialization."""

    def test_all_events_serialize_to_valid_json(self):
        """All event types serialize to valid JSON."""
        events = [
            StageStartEvent(stage=1, stage_name="Test"),
            StageCompleteEvent(stage=1, stage_name="Test", duration_ms=100, results_count=1),
            StageErrorEvent(stage=1, stage_name="Test", error="Error"),
            ModelStartEvent(model="test", stage=1),
            ModelChunkEvent(model="test", stage=1, content="chunk", full_content="full"),
            ModelCompleteEvent(model="test", stage=1, content="response"),
            ModelErrorEvent(model="test", stage=1, error="error"),
            ProgressEvent(stage=1, completed_models=1, total_models=2, percentage=50.0),
            DeliberationStartEvent(question="test"),
            DeliberationCompleteEvent(total_duration_ms=1000, stage1_count=1, stage2_count=1),
            DeliberationErrorEvent(error="error", failed_stage=1),
            TitleCompleteEvent(title="Test"),
        ]

        for event in events:
            sse = event.to_sse()
            json_str = sse[6:-2]
            # Should not raise
            data = json.loads(json_str)
            assert "type" in data
