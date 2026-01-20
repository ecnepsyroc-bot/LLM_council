"""FastAPI backend for LLM Council."""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import storage
from .config import CHAIRMAN_MODEL, COUNCIL_MODELS
from .council import (
    calculate_aggregate_rankings,
    detect_consensus,
    generate_conversation_title,
    run_full_council,
    stage1_stream_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
)
from .health import router as health_router
from .metrics import router as metrics_router
from .logging_config import setup_logging
from .security import (
    ValidationError,
    configure_cors,
    sanitize_for_prompt,
    validate_conversation_update,
    validate_message_content,
    RateLimitMiddleware,
    RateLimitConfig,
    SecurityHeadersMiddleware,
)
from .auth.middleware import AuthenticationMiddleware
from .auth.service import APIKeyService
from .auth.exceptions import AuthenticationError

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LLM Council API",
    version="1.0.0",
    description="Multi-LLM deliberation system",
)

# Configure CORS
configure_cors(app)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiting middleware
rate_limit_config = RateLimitConfig(
    requests_per_minute=60,
    burst_limit=10,
)
app.add_middleware(RateLimitMiddleware, config=rate_limit_config)

# Add authentication middleware (disabled by default via BYPASS_AUTH env var)
app.add_middleware(AuthenticationMiddleware, bypass_auth=True)

# Include health router
app.include_router(health_router)

# Include metrics router
app.include_router(metrics_router)

logger.info("LLM Council API starting")


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class DeliberationOptions(BaseModel):
    """Options for the deliberation process."""
    voting_method: str = "borda"
    use_rubric: bool = False
    debate_rounds: int = 1
    enable_early_exit: bool = True
    rotating_chairman: bool = False


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    images: List[str] = []
    options: DeliberationOptions | None = None


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    updated_at: str = ""
    title: str
    is_pinned: bool = False
    is_hidden: bool = False
    message_count: int = 0


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
    """Root endpoint."""
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


@app.get("/api/auth/me")
async def get_current_user(request: "Request"):
    """Get current authenticated user info."""
    auth = getattr(request.state, 'auth', None)
    if not auth:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    return {
        "api_key_id": auth.api_key_id,
        "key_prefix": auth.key_prefix,
        "permissions": [p.value for p in auth.permissions],
        "rate_limit": auth.rate_limit,
        "request_id": auth.request_id
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

    try:
        validated = validate_conversation_update(
            title=request.title,
            is_pinned=request.is_pinned,
            is_hidden=request.is_hidden
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    for field, value in validated.items():
        storage.update_conversation_field(conversation_id, field, value)

    return storage.get_conversation(conversation_id)


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """Send a message and run the 3-stage council process."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        validated_content, validated_images = validate_message_content(
            request.content, request.images
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    safe_content = sanitize_for_prompt(validated_content)
    is_first_message = len(conversation["messages"]) == 0

    storage.add_user_message(conversation_id, validated_content, validated_images)

    if is_first_message:
        title = await generate_conversation_title(validated_content)
        storage.update_conversation_field(conversation_id, "title", title)

    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        safe_content
    )

    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """Send a message and stream the 3-stage council process."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        validated_content, validated_images = validate_message_content(
            request.content, request.images
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    safe_content = sanitize_for_prompt(validated_content)
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            storage.add_user_message(conversation_id, validated_content, validated_images)

            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(validated_content))

            opts = request.options or DeliberationOptions()

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

            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(
                safe_content,
                stage1_results,
                use_rubric=opts.use_rubric
            )

            aggregate_rankings = calculate_aggregate_rankings(
                stage2_results,
                label_to_model,
                stage1_results=stage1_results if opts.voting_method == "confidence_weighted" else None,
                method=opts.voting_method
            )
            consensus = detect_consensus(stage2_results, label_to_model)

            features = {
                'use_rubric': opts.use_rubric,
                'debate_rounds': opts.debate_rounds,
                'rotating_chairman': opts.rotating_chairman,
                'chairman_model': CHAIRMAN_MODEL
            }

            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings, 'consensus': consensus, 'voting_method': opts.voting_method, 'features': features}})}\n\n"

            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"

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

            if title_task:
                title = await title_task
                storage.update_conversation_field(conversation_id, "title", title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            logger.exception(f"Error in streaming: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred during deliberation.'})}\n\n"

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
