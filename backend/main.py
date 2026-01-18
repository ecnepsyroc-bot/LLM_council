"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage1_stream_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    detect_consensus,
)
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL
from .security import (
    configure_cors,
    RateLimitMiddleware,
    RateLimitConfig,
    validate_message_content,
    validate_conversation_update,
    sanitize_for_prompt,
    ValidationError,
)

import os

app = FastAPI(title="LLM Council API")

# Configure CORS (environment-aware)
configure_cors(app)

# Add rate limiting middleware (disabled in testing)
is_testing = os.getenv("TESTING", "").lower() in ("1", "true", "yes")
app.add_middleware(
    RateLimitMiddleware,
    config=RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=500,
        burst_limit=10,
        excluded_paths=["/", "/api/config"],
        enabled=not is_testing,
    )
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class DeliberationOptions(BaseModel):
    """Options for the deliberation process."""
    voting_method: str = "borda"  # simple, borda, mrr, confidence_weighted
    use_rubric: bool = False
    debate_rounds: int = 1
    enable_early_exit: bool = True
    use_self_moa: bool = False
    rotating_chairman: bool = False
    meta_evaluate: bool = False


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    images: List[str] = []
    options: DeliberationOptions | None = None


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    is_pinned: bool = False
    is_hidden: bool = False
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    is_pinned: bool = False
    is_hidden: bool = False
    messages: List[Dict[str, Any]]


class UpdateConversationRequest(BaseModel):
    """Request to update conversation fields."""
    title: str | None = None
    is_pinned: bool | None = None
    is_hidden: bool | None = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.get("/api/config")
async def get_config():
    """Get council configuration."""
    return {
        "council_models": COUNCIL_MODELS,
        "chairman_model": CHAIRMAN_MODEL
    }


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.patch("/api/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, request: UpdateConversationRequest):
    """Update conversation fields (title, pin, hide)."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Validate and sanitize input
    try:
        validated = validate_conversation_update(
            title=request.title,
            is_pinned=request.is_pinned,
            is_hidden=request.is_hidden
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Apply validated updates
    for field, value in validated.items():
        storage.update_conversation_field(conversation_id, field, value)

    return storage.get_conversation(conversation_id)


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Validate and sanitize input
    try:
        validated_content, validated_images = validate_message_content(
            request.content, request.images
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Sanitize content for prompt injection protection
    safe_content = sanitize_for_prompt(validated_content)

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message (store original content, not sanitized)
    storage.add_user_message(conversation_id, validated_content, validated_images)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(validated_content)
        storage.update_conversation_field(conversation_id, "title", title)

    # Run the 3-stage council process with sanitized content
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        safe_content
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events with real-time updates for each model in Stage 1.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Validate and sanitize input (before starting stream)
    try:
        validated_content, validated_images = validate_message_content(
            request.content, request.images
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Sanitize content for prompt injection protection
    safe_content = sanitize_for_prompt(validated_content)

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message (store original content)
            storage.add_user_message(conversation_id, validated_content, validated_images)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(validated_content))

            # Get options with defaults
            opts = request.options or DeliberationOptions()

            # Stage 1: Stream responses from all models in parallel (use sanitized content)
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"

            stage1_results = []
            async for event in stage1_stream_responses(safe_content):
                if event["type"] == "model_start":
                    yield f"data: {json.dumps({'type': 'model_start', 'model': event['model']})}\n\n"
                elif event["type"] == "model_chunk":
                    yield f"data: {json.dumps({'type': 'model_chunk', 'model': event['model'], 'content': event['content'], 'accumulated': event['accumulated']})}\n\n"
                elif event["type"] == "model_done":
                    yield f"data: {json.dumps({'type': 'model_done', 'model': event['model'], 'response': event['response']})}\n\n"
                elif event["type"] == "model_error":
                    yield f"data: {json.dumps({'type': 'model_error', 'model': event['model'], 'error': event.get('error', 'Unknown error')})}\n\n"
                elif event["type"] == "all_done":
                    stage1_results = event["results"]

            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings (with rubric option, use sanitized content)
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(
                safe_content,
                stage1_results,
                use_rubric=opts.use_rubric
            )

            # Calculate rankings with chosen voting method
            aggregate_rankings = calculate_aggregate_rankings(
                stage2_results,
                label_to_model,
                stage1_results=stage1_results if opts.voting_method == "confidence_weighted" else None,
                method=opts.voting_method
            )
            consensus = detect_consensus(stage2_results, label_to_model)

            # Build features metadata
            features = {
                'use_rubric': opts.use_rubric,
                'debate_rounds': opts.debate_rounds,
                'early_exit_used': False,
                'use_self_moa': opts.use_self_moa,
                'rotating_chairman': opts.rotating_chairman,
                'meta_evaluate': opts.meta_evaluate,
                'chairman_model': CHAIRMAN_MODEL
            }

            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings, 'consensus': consensus, 'voting_method': opts.voting_method, 'features': features}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"

            # Determine chairman (rotating or fixed)
            chairman = CHAIRMAN_MODEL
            if opts.rotating_chairman and aggregate_rankings:
                chairman = aggregate_rankings[0].get('model', CHAIRMAN_MODEL)

            stage3_result = await stage3_synthesize_final(
                safe_content,
                stage1_results,
                stage2_results,
                chairman_model=chairman,
                aggregate_rankings=aggregate_rankings
            )
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_field(conversation_id, "title", title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    success = storage.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok", "id": conversation_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
