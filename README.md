# LLM Council

![llmcouncil](header.jpg)

A multi-LLM deliberation system where multiple AI models collaborate to answer your questions. Instead of asking a single LLM, you can assemble your own "Council" of models that discuss, review each other's work, and synthesize a final response.

## How It Works

When you submit a query, the council goes through three stages:

1. **Stage 1: First Opinions** - Your query is sent to all council models in parallel. Each model provides its independent response, displayed in a tab view for comparison.

2. **Stage 2: Peer Review** - Each model reviews and ranks the other responses. Identities are anonymized (Response A, B, C...) to prevent bias. Models evaluate based on accuracy and insight.

3. **Stage 3: Final Synthesis** - The designated Chairman model compiles all responses and rankings into a final, comprehensive answer.

## Quick Start

### Prerequisites

- [Node.js](https://nodejs.org/) 18+
- [Python](https://www.python.org/) 3.10+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [OpenRouter API Key](https://openrouter.ai/)

### Installation

```bash
# Clone the repository
git clone https://github.com/karpathy/llm-council.git
cd llm-council

# Install all dependencies
npm run install:all

# Or install separately:
npm run install:backend   # Python dependencies via uv
npm run install:frontend  # Node dependencies
```

### Configuration

1. Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

2. (Optional) Customize the council in `backend/config.py`:

```python
# Council members - add or remove models as desired
COUNCIL_MODELS = [
    "anthropic/claude-opus-4",
    "openai/o1",
    "google/gemini-2.5-pro-preview-06-05",
    "x-ai/grok-3-beta",
    "deepseek/deepseek-r1",
]

# The model that synthesizes the final answer
CHAIRMAN_MODEL = "anthropic/claude-opus-4"
```

Available models can be found at [openrouter.ai/models](https://openrouter.ai/models).

### Running the Application

**Option 1: Single Command (Recommended)**

```bash
npm run dev
```

This starts both backend and frontend concurrently.

**Option 2: Separate Terminals**

Terminal 1 (Backend):
```bash
npm run dev:backend
# or: uv run python -m backend.main
```

Terminal 2 (Frontend):
```bash
npm run dev:frontend
# or: cd frontend && npm run dev
```

**Option 3: Use the start script**

```bash
./start.sh
```

### Access the Application

Open http://localhost:5173 in your browser.

## Architecture

```
llm-council/
├── backend/              # FastAPI Python backend
│   ├── main.py          # API endpoints
│   ├── council.py       # 3-stage deliberation logic
│   ├── openrouter.py    # OpenRouter API client
│   ├── storage.py       # JSON file storage
│   └── config.py        # Model configuration
├── frontend/            # React + Vite frontend
│   └── src/
│       ├── App.tsx      # Main application
│       ├── components/  # React components
│       └── store/       # Zustand state management
├── data/                # Conversation storage (gitignored)
├── .idx/                # Google IDX configuration
├── .vscode/             # VS Code configuration
└── package.json         # Root scripts for convenience
```

### Port Assignments

| Service  | Port | URL                    |
|----------|------|------------------------|
| Frontend | 5173 | http://localhost:5173  |
| Backend  | 8001 | http://localhost:8001  |

### Tech Stack

- **Backend**: FastAPI, Python 3.10+, async httpx, Pydantic
- **Frontend**: React 19, Vite, TypeScript, Tailwind CSS, Zustand
- **API Integration**: OpenRouter (multi-provider LLM gateway)
- **Storage**: JSON files in `data/conversations/`
- **Package Management**: uv (Python), npm (JavaScript)

## Development

### IDE Setup

The project includes configurations for:

- **VS Code**: Open `llm-council.code-workspace` for multi-root workspace
- **Google IDX**: `.idx/dev.nix` configures the cloud development environment

### Available Scripts

```bash
npm run dev           # Start both frontend and backend
npm run dev:frontend  # Start only frontend (port 5173)
npm run dev:backend   # Start only backend (port 8001)
npm run build         # Build frontend for production
npm run lint          # Run ESLint on frontend
npm run install:all   # Install all dependencies
npm run clean         # Remove generated files
```

### VS Code Tasks

Press `Ctrl+Shift+B` (or `Cmd+Shift+B` on Mac) to run the default build task, or access all tasks via the Command Palette (`Tasks: Run Task`).

### Debug Configurations

Launch configurations are provided for:
- Backend: FastAPI with hot reload
- Frontend: Vite dev server
- Chrome: Debug frontend in browser
- Full Stack: Run both simultaneously

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/api/conversations` | List all conversations |
| POST | `/api/conversations` | Create new conversation |
| GET | `/api/conversations/{id}` | Get conversation details |
| POST | `/api/conversations/{id}/message` | Send message (batch) |
| POST | `/api/conversations/{id}/message/stream` | Send message (streaming) |

### Example Request

```bash
curl -X POST http://localhost:8001/api/conversations/{id}/message \
  -H "Content-Type: application/json" \
  -d '{"content": "What is the meaning of life?"}'
```

## Acknowledgments

This project was vibe-coded as a Saturday hack by [Andrej Karpathy](https://x.com/karpathy) to explore and evaluate multiple LLMs side by side.

## License

MIT
