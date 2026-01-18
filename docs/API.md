# LLM Council API Documentation

This document describes the REST API for LLM Council.

## Base URL

```
http://localhost:8001
```

For production deployments, replace with your server's URL.

---

## Authentication

LLM Council supports API key authentication for production use.

### API Key Header

Include the API key in the `X-API-Key` header:

```http
X-API-Key: lc_your_api_key_here
```

### Bearer Token

Alternatively, use the Authorization header:

```http
Authorization: Bearer lc_your_api_key_here
```

### Query Parameter (SSE/WebSocket)

For streaming endpoints, you can pass the key as a query parameter:

```
/api/conversations/{id}/message/stream?api_key=lc_your_api_key_here
```

### Bypassing Authentication (Development)

Set `BYPASS_AUTH=true` in your environment to disable authentication during development.

---

## Rate Limiting

API requests are rate-limited per API key (or IP if unauthenticated).

### Default Limits

| Window | Limit |
|--------|-------|
| Per second (burst) | 10 |
| Per minute | 60 |
| Per hour | 500 |

### Rate Limit Headers

Responses include rate limit information:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 35
X-RateLimit-Window: 60
```

### Rate Limit Exceeded

When rate limited, you'll receive:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 15

{
  "detail": "Rate limit exceeded (60 requests per minute). Try again in 15 seconds."
}
```

---

## Endpoints

### Health

#### GET /health

Basic health check. Always returns 200 if the service is running.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-18T12:00:00Z"
}
```

#### GET /health/ready

Readiness check for load balancers.

**Response:**
```json
{
  "status": "ready",
  "timestamp": "2024-01-18T12:00:00Z",
  "checks": {
    "database": true,
    "config": true
  }
}
```

#### GET /health/detailed

Detailed health status (requires admin authentication).

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-18T12:00:00Z",
  "uptime_seconds": 3600,
  "database": {
    "connected": true,
    "conversations": 42,
    "messages": 156,
    "api_keys": 3
  },
  "openrouter": {
    "configured": true,
    "last_check": null
  },
  "config": {
    "council_models": ["anthropic/claude-opus-4", "openai/gpt-4.5"],
    "chairman_model": "anthropic/claude-opus-4",
    "bypass_auth": false
  }
}
```

---

### Configuration

#### GET /api/config

Get current council configuration.

**Response:**
```json
{
  "council_models": [
    "anthropic/claude-opus-4",
    "openai/gpt-4.5",
    "google/gemini-2.5-pro"
  ],
  "chairman_model": "anthropic/claude-opus-4"
}
```

---

### Conversations

#### GET /api/conversations

List all conversations.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `include_hidden` | boolean | Include hidden conversations (default: false) |

**Response:**
```json
[
  {
    "id": "conv_123abc",
    "title": "Discussion about quantum computing",
    "created_at": "2024-01-18T10:00:00Z",
    "updated_at": "2024-01-18T11:30:00Z",
    "is_pinned": false,
    "is_hidden": false,
    "message_count": 4
  }
]
```

#### POST /api/conversations

Create a new conversation.

**Request Body:**
```json
{
  "title": "My new conversation"
}
```

**Response:**
```json
{
  "id": "conv_456def",
  "title": "My new conversation",
  "created_at": "2024-01-18T12:00:00Z",
  "messages": []
}
```

#### GET /api/conversations/{id}

Get a conversation with all messages.

**Response:**
```json
{
  "id": "conv_123abc",
  "title": "Discussion about quantum computing",
  "created_at": "2024-01-18T10:00:00Z",
  "messages": [
    {
      "role": "user",
      "content": "What is quantum computing?"
    },
    {
      "role": "assistant",
      "stage1": [...],
      "stage2": [...],
      "stage3": {...}
    }
  ]
}
```

#### PUT /api/conversations/{id}

Update conversation metadata.

**Request Body:**
```json
{
  "title": "New title",
  "is_pinned": true,
  "is_hidden": false
}
```

#### DELETE /api/conversations/{id}

Delete a conversation.

**Response:**
```json
{
  "success": true
}
```

---

### Messages

#### POST /api/conversations/{id}/message

Send a message and get the council's response.

**Request Body:**
```json
{
  "content": "What are the implications of quantum computing for cryptography?"
}
```

**Response:**
```json
{
  "user_message": {
    "role": "user",
    "content": "What are the implications..."
  },
  "assistant_message": {
    "role": "assistant",
    "stage1": [
      {
        "model": "anthropic/claude-opus-4",
        "response": "Quantum computing poses significant...",
        "confidence": 0.92
      },
      {
        "model": "openai/gpt-4.5",
        "response": "The implications are profound...",
        "confidence": 0.88
      }
    ],
    "stage2": [
      {
        "model": "anthropic/claude-opus-4",
        "ranking": "After careful evaluation...\n\nFINAL RANKING:\n1. Response B\n2. Response A\n3. Response C",
        "parsed_ranking": ["Response B", "Response A", "Response C"]
      }
    ],
    "stage3": {
      "model": "anthropic/claude-opus-4",
      "response": "Quantum computing represents a paradigm shift..."
    }
  },
  "metadata": {
    "label_to_model": {
      "Response A": "anthropic/claude-opus-4",
      "Response B": "openai/gpt-4.5"
    },
    "aggregate_rankings": [
      {"model": "openai/gpt-4.5", "avg_rank": 1.5, "votes": 3},
      {"model": "anthropic/claude-opus-4", "avg_rank": 2.0, "votes": 3}
    ]
  }
}
```

#### POST /api/conversations/{id}/message/stream

Send a message and stream the response via Server-Sent Events (SSE).

**Request Body:**
```json
{
  "content": "Explain machine learning"
}
```

**Response:** Server-Sent Events stream

```
event: stage1_start
data: {"message": "Starting Stage 1: Collecting responses"}

event: stage1_model_start
data: {"model": "anthropic/claude-opus-4"}

event: stage1_model_complete
data: {"model": "anthropic/claude-opus-4", "response": "Machine learning is..."}

event: stage1_complete
data: {"responses": [...]}

event: stage2_start
data: {"message": "Starting Stage 2: Peer evaluation"}

event: stage2_complete
data: {"rankings": [...]}

event: stage3_start
data: {"message": "Starting Stage 3: Synthesis"}

event: stage3_complete
data: {"synthesis": {...}}

event: complete
data: {"assistant_message": {...}, "metadata": {...}}
```

---

### API Keys (Admin)

#### POST /api/keys

Create a new API key (requires admin permission).

**Request Body:**
```json
{
  "name": "Production Key",
  "permissions": ["read", "write"],
  "expires_in_days": 90
}
```

**Response:**
```json
{
  "api_key": "lc_abc123...",
  "key": {
    "id": "key_123",
    "name": "Production Key",
    "key_prefix": "lc_abc1",
    "permissions": ["read", "write"],
    "created_at": "2024-01-18T12:00:00Z",
    "expires_at": "2024-04-18T12:00:00Z"
  }
}
```

#### GET /api/keys

List all API keys (requires admin permission).

**Response:**
```json
[
  {
    "id": "key_123",
    "name": "Production Key",
    "key_prefix": "lc_abc1",
    "permissions": ["read", "write"],
    "created_at": "2024-01-18T12:00:00Z",
    "expires_at": "2024-04-18T12:00:00Z",
    "is_active": true,
    "last_used_at": "2024-01-18T11:30:00Z"
  }
]
```

#### DELETE /api/keys/{id}

Revoke an API key (requires admin permission).

**Response:**
```json
{
  "success": true
}
```

---

## Error Handling

### Error Response Format

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

### Common Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid API key |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limited |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Dependency failure |

### Error Examples

**Invalid API Key:**
```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: ApiKey

{
  "detail": "Invalid API key"
}
```

**Insufficient Permissions:**
```http
HTTP/1.1 403 Forbidden

{
  "detail": "Admin permission required"
}
```

**Resource Not Found:**
```http
HTTP/1.1 404 Not Found

{
  "detail": "Conversation not found"
}
```

---

## SDKs and Examples

### Python

```python
import requests

API_URL = "http://localhost:8001"
API_KEY = "lc_your_key_here"

headers = {"X-API-Key": API_KEY}

# Create conversation
response = requests.post(
    f"{API_URL}/api/conversations",
    headers=headers,
    json={"title": "Test conversation"}
)
conv_id = response.json()["id"]

# Send message
response = requests.post(
    f"{API_URL}/api/conversations/{conv_id}/message",
    headers=headers,
    json={"content": "What is the meaning of life?"}
)
result = response.json()
print(result["assistant_message"]["stage3"]["response"])
```

### JavaScript

```javascript
const API_URL = "http://localhost:8001";
const API_KEY = "lc_your_key_here";

const headers = {
  "Content-Type": "application/json",
  "X-API-Key": API_KEY,
};

// Create conversation
const convResponse = await fetch(`${API_URL}/api/conversations`, {
  method: "POST",
  headers,
  body: JSON.stringify({ title: "Test conversation" }),
});
const { id: convId } = await convResponse.json();

// Send message
const msgResponse = await fetch(
  `${API_URL}/api/conversations/${convId}/message`,
  {
    method: "POST",
    headers,
    body: JSON.stringify({ content: "What is the meaning of life?" }),
  }
);
const result = await msgResponse.json();
console.log(result.assistant_message.stage3.response);
```

### cURL

```bash
# Create conversation
curl -X POST http://localhost:8001/api/conversations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: lc_your_key_here" \
  -d '{"title": "Test"}'

# Send message
curl -X POST http://localhost:8001/api/conversations/CONV_ID/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: lc_your_key_here" \
  -d '{"content": "What is AI?"}'
```

---

## WebSocket/SSE Connection

For streaming responses, connect to the SSE endpoint:

```javascript
const eventSource = new EventSource(
  `${API_URL}/api/conversations/${convId}/message/stream?api_key=${API_KEY}`
);

eventSource.addEventListener("stage1_complete", (e) => {
  const data = JSON.parse(e.data);
  console.log("Stage 1 complete:", data.responses);
});

eventSource.addEventListener("complete", (e) => {
  const data = JSON.parse(e.data);
  console.log("Final response:", data.assistant_message);
  eventSource.close();
});

eventSource.onerror = (e) => {
  console.error("SSE error:", e);
  eventSource.close();
};

// Send the message via POST to start the stream
fetch(`${API_URL}/api/conversations/${convId}/message/stream`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  },
  body: JSON.stringify({ content: "Your question here" }),
});
```
