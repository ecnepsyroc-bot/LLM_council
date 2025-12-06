"""Configuration for the LLM Council."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "anthropic/claude-opus-4",
    "openai/o1",
    "google/gemini-2.5-pro-preview-06-05",
    "x-ai/grok-3-beta",
    "deepseek/deepseek-r1",
]

CHAIRMAN_MODEL = "anthropic/claude-opus-4"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
# Data directory for conversation storage
DATA_DIR = str(Path(__file__).resolve().parent.parent / "data" / "conversations")