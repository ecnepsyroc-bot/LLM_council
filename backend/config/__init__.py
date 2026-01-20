"""
Configuration for LLM Council.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default models
DEFAULT_COUNCIL_MODELS = [
    "anthropic/claude-opus-4",
    "openai/o1",
    "google/gemini-2.5-pro-preview-06-05",
    "x-ai/grok-3-beta",
    "deepseek/deepseek-r1",
    "openai/gpt-4.5",
    "meta-llama/llama-4-maverick",
    "qwen/qwen3-235b-a22b",
    "mistralai/mistral-large-2411",
]

DEFAULT_CHAIRMAN_MODEL = "anthropic/claude-opus-4"

# Load from environment or use defaults
_council_env = os.getenv("COUNCIL_MODELS", "")
COUNCIL_MODELS = [m.strip() for m in _council_env.split(",") if m.strip()] if _council_env else DEFAULT_COUNCIL_MODELS
CHAIRMAN_MODEL = os.getenv("CHAIRMAN_MODEL", DEFAULT_CHAIRMAN_MODEL)

# Data directory
DATA_DIR = str(Path(__file__).resolve().parent.parent.parent / "data" / "conversations")

__all__ = [
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_URL",
    "COUNCIL_MODELS",
    "CHAIRMAN_MODEL",
    "DEFAULT_COUNCIL_MODELS",
    "DEFAULT_CHAIRMAN_MODEL",
    "DATA_DIR",
]
