# Development Environment

Setup guide and workflows for LLM Council development.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org/) |
| Python | 3.10+ | [python.org](https://www.python.org/) |
| uv | Latest | [docs.astral.sh/uv](https://docs.astral.sh/uv/) |
| Git | Latest | [git-scm.com](https://git-scm.com/) |

---

## Quick Start

```bash
# Clone and enter directory
git clone https://github.com/karpathy/llm-council.git
cd llm-council

# Install all dependencies
npm run install:all

# Configure API key
echo "OPENROUTER_API_KEY=sk-or-v1-your-key-here" > .env

# Start development servers
npm run dev
```

Open http://localhost:5173

---

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start both frontend and backend |
| `npm run dev:frontend` | Start only frontend (port 5173) |
| `npm run dev:backend` | Start only backend (port 8001) |
| `npm run build` | Build frontend for production |
| `npm run lint` | Run ESLint on frontend |
| `npm run install:all` | Install all dependencies |
| `npm run clean` | Remove generated files |

---

## Running Separately

### Backend
```bash
npm run dev:backend
# or directly:
uv run python -m backend.main
```

### Frontend
```bash
npm run dev:frontend
# or directly:
cd frontend && npm run dev
```

---

## Windows System Tray

Double-click `LLMCouncil.vbs` for tray app:
- 🔔 Tray icon with context menu
- 🌐 Double-click to open browser
- 🔄 Right-click → Restart Services
- ❌ Right-click → Exit

**Add to Startup:** Press `Win+R`, type `shell:startup`, paste shortcut

---

## VS Code Setup

Open `llm-council.code-workspace` for multi-root workspace.

### Debug Configurations
- **Backend**: FastAPI with hot reload
- **Frontend**: Vite dev server
- **Chrome**: Debug frontend in browser
- **Full Stack**: Run both simultaneously

### Build Task
Press `Ctrl+Shift+B` to run default build.

---

## Project Structure

```
llm-council/
├── backend/           # FastAPI Python backend
│   ├── main.py       # API endpoints
│   ├── council.py    # 3-stage deliberation
│   ├── openrouter.py # LLM communication
│   ├── storage.py    # JSON persistence
│   └── config.py     # Model configuration
├── frontend/          # React + Vite frontend
├── data/              # Conversation storage
├── memory-bank/       # Project context
└── docs/              # Documentation
```

---

## Common Issues

| Problem | Solution |
|---------|----------|
| Module import errors | Run as `python -m backend.main` from root |
| CORS errors | Check allowed origins in `main.py` |
| Port 8001 in use | Another app on that port; change in config |
| API key missing | Create `.env` file with `OPENROUTER_API_KEY` |
