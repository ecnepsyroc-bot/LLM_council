"""Model configuration with validation support."""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModelCapability(str, Enum):
    """Model capabilities."""

    TEXT = "text"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    REASONING = "reasoning"  # Extended thinking (o1, etc.)


@dataclass
class ModelConfig:
    """Configuration for a single model."""

    id: str  # e.g., "openai/gpt-4"
    display_name: str = ""  # e.g., "GPT-4"
    provider: str = ""  # e.g., "openai"

    # Capabilities
    capabilities: List[ModelCapability] = field(default_factory=list)
    context_window: int = 8192
    max_output_tokens: int = 4096

    # Rate limits
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000

    # Custom settings
    default_temperature: float = 0.7
    supports_streaming: bool = True

    # Validation
    is_validated: bool = False
    last_validated: Optional[str] = None
    validation_error: Optional[str] = None

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.id.split("/")[-1] if "/" in self.id else self.id
        if not self.provider:
            self.provider = self.id.split("/")[0] if "/" in self.id else "unknown"


@dataclass
class CouncilConfig:
    """Configuration for the council."""

    council_models: List[ModelConfig] = field(default_factory=list)
    chairman_model: Optional[ModelConfig] = None
    fallback_models: List[ModelConfig] = field(default_factory=list)

    # Voting
    default_voting_method: str = "borda"

    # Timeouts
    default_timeout: int = 120

    @classmethod
    def from_env(cls) -> "CouncilConfig":
        """Load configuration from environment variables."""
        # Get model IDs from environment or use defaults
        council_ids_str = os.getenv("COUNCIL_MODELS", "")
        if council_ids_str:
            council_ids = [m.strip() for m in council_ids_str.split(",") if m.strip()]
        else:
            council_ids = DEFAULT_COUNCIL_MODELS

        chairman_id = os.getenv("CHAIRMAN_MODEL", DEFAULT_CHAIRMAN_MODEL)

        # Create model configs
        council = [ModelConfig(id=model_id) for model_id in council_ids]

        chairman = ModelConfig(id=chairman_id)

        return cls(council_models=council, chairman_model=chairman)

    @property
    def council_model_ids(self) -> List[str]:
        """Get list of council model IDs."""
        return [m.id for m in self.council_models]

    @property
    def chairman_model_id(self) -> str:
        """Get chairman model ID."""
        return self.chairman_model.id if self.chairman_model else DEFAULT_CHAIRMAN_MODEL


# Default configuration
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


class ConfigValidator:
    """Validates model configuration."""

    def __init__(self, client=None):
        """
        Initialize validator.

        Args:
            client: OpenRouter client for validation (optional)
        """
        self.client = client
        self.results: Dict[str, Any] = {}

    async def validate_all(self, config: CouncilConfig) -> Dict[str, Any]:
        """Validate all configured models."""
        logger.info("Validating model configuration...")

        all_models = list(config.council_models)
        if config.chairman_model:
            all_models.append(config.chairman_model)
        if config.fallback_models:
            all_models.extend(config.fallback_models)

        # Validate each model
        results = []
        for model in all_models:
            result = await self._validate_model(model)
            results.append(result)

        valid_count = sum(1 for r in results if r.get("valid", False))

        summary = {
            "total": len(all_models),
            "valid": valid_count,
            "invalid": len(all_models) - valid_count,
            "models": {model.id: results[i] for i, model in enumerate(all_models)},
        }

        if valid_count == 0:
            logger.error("No valid models configured!")
        elif valid_count < len(all_models):
            logger.warning(
                f"Some models invalid: {valid_count}/{len(all_models)} valid"
            )
        else:
            logger.info(f"All {valid_count} models validated successfully")

        return summary

    async def _validate_model(self, model: ModelConfig) -> Dict[str, Any]:
        """Validate a single model."""
        if not self.client:
            # No client provided, assume valid
            model.is_validated = True
            return {"valid": True, "model": model.id, "error": None}

        try:
            is_valid = await self.client.validate_model(model.id)

            model.is_validated = is_valid
            model.validation_error = None if is_valid else "Model not accessible"

            return {"valid": is_valid, "model": model.id, "error": model.validation_error}

        except Exception as e:
            model.is_validated = False
            model.validation_error = str(e)

            return {"valid": False, "model": model.id, "error": str(e)}


async def validate_config_on_startup(client=None) -> CouncilConfig:
    """Validate configuration when application starts."""
    config = CouncilConfig.from_env()
    validator = ConfigValidator(client)

    await validator.validate_all(config)

    # Filter to only valid council models (if validation was done)
    if client:
        config.council_models = [m for m in config.council_models if m.is_validated]

        if not config.council_models:
            logger.error("No valid council models available")
            # Use defaults without validation
            config = CouncilConfig.from_env()

        if config.chairman_model and not config.chairman_model.is_validated:
            # Try to use first valid council model as chairman
            if config.council_models:
                logger.warning(
                    f"Chairman model invalid, using {config.council_models[0].id}"
                )
                config.chairman_model = config.council_models[0]

    return config
