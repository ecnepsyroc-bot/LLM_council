"""
Configuration package for LLM Council.

Provides model configuration and validation, as well as basic app settings.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from .models import (
    CouncilConfig,
    ConfigValidator,
    ModelCapability,
    ModelConfig,
    DEFAULT_CHAIRMAN_MODEL,
    DEFAULT_COUNCIL_MODELS,
    validate_config_on_startup,
)

# Load .env from project root (parent of backend/)
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = str(Path(__file__).resolve().parent.parent.parent / "data" / "conversations")

# Legacy exports - use DEFAULT_COUNCIL_MODELS and DEFAULT_CHAIRMAN_MODEL for new code
COUNCIL_MODELS = DEFAULT_COUNCIL_MODELS
CHAIRMAN_MODEL = DEFAULT_CHAIRMAN_MODEL

__all__ = [
    # New config classes
    "ModelConfig",
    "ModelCapability",
    "CouncilConfig",
    "ConfigValidator",
    "DEFAULT_COUNCIL_MODELS",
    "DEFAULT_CHAIRMAN_MODEL",
    "validate_config_on_startup",
    # Legacy config values
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_URL",
    "COUNCIL_MODELS",
    "CHAIRMAN_MODEL",
    "DATA_DIR",
]
