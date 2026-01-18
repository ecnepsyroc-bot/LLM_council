"""
Application settings using Pydantic Settings.

Loads configuration from environment variables and .env file.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==========================================================================
    # Required Settings
    # ==========================================================================

    openrouter_api_key: str = Field(
        default="",
        description="OpenRouter API key (required for production)"
    )

    # ==========================================================================
    # Council Configuration
    # ==========================================================================

    council_models: str = Field(
        default="anthropic/claude-opus-4,openai/o1,google/gemini-2.5-pro-preview-06-05,x-ai/grok-3-beta,deepseek/deepseek-r1",
        description="Comma-separated list of OpenRouter model identifiers"
    )

    chairman_model: str = Field(
        default="anthropic/claude-opus-4",
        description="Model used for final synthesis"
    )

    @property
    def council_models_list(self) -> List[str]:
        """Get council models as a list."""
        return [m.strip() for m in self.council_models.split(",") if m.strip()]

    # ==========================================================================
    # Authentication
    # ==========================================================================

    bypass_auth: bool = Field(
        default=False,
        description="Bypass authentication (development only!)"
    )

    # ==========================================================================
    # Rate Limiting
    # ==========================================================================

    rate_limit_per_minute: int = Field(
        default=60,
        description="Maximum requests per minute per API key"
    )

    rate_limit_per_hour: int = Field(
        default=500,
        description="Maximum requests per hour per API key"
    )

    rate_limit_burst: int = Field(
        default=10,
        description="Burst limit for rate limiting"
    )

    # ==========================================================================
    # Database
    # ==========================================================================

    database_path: str = Field(
        default="data/council.db",
        description="Path to SQLite database file"
    )

    @property
    def database_path_absolute(self) -> Path:
        """Get absolute database path."""
        path = Path(self.database_path)
        if not path.is_absolute():
            # Relative to project root
            project_root = Path(__file__).parent.parent
            path = project_root / path
        return path

    # ==========================================================================
    # Logging
    # ==========================================================================

    log_level: str = Field(
        default="INFO",
        description="Log level"
    )

    log_format: str = Field(
        default="text",
        description="Log format: text or json"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        valid_formats = {"text", "json"}
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f"Invalid log format: {v}. Must be one of {valid_formats}")
        return v_lower

    # ==========================================================================
    # Server
    # ==========================================================================

    host: str = Field(
        default="0.0.0.0",
        description="Host to bind to"
    )

    port: int = Field(
        default=8001,
        description="Port to listen on"
    )

    # ==========================================================================
    # OpenRouter Settings
    # ==========================================================================

    openrouter_timeout: int = Field(
        default=60,
        description="Request timeout in seconds"
    )

    openrouter_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts"
    )

    circuit_breaker_threshold: int = Field(
        default=5,
        description="Circuit breaker failure threshold"
    )

    circuit_breaker_timeout: int = Field(
        default=60,
        description="Circuit breaker recovery timeout in seconds"
    )

    # ==========================================================================
    # Computed Properties
    # ==========================================================================

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.bypass_auth and self.openrouter_api_key != ""

    @property
    def openrouter_api_url(self) -> str:
        """OpenRouter API URL."""
        return "https://openrouter.ai/api/v1/chat/completions"

    def to_safe_dict(self) -> dict:
        """Return settings as dict with secrets redacted."""
        data = {
            "council_models": self.council_models_list,
            "chairman_model": self.chairman_model,
            "bypass_auth": self.bypass_auth,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "rate_limit_per_hour": self.rate_limit_per_hour,
            "database_path": str(self.database_path_absolute),
            "log_level": self.log_level,
            "log_format": self.log_format,
            "host": self.host,
            "port": self.port,
            "is_production": self.is_production,
        }

        # Redact secrets
        if self.openrouter_api_key:
            key = self.openrouter_api_key
            data["openrouter_api_key"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
        else:
            data["openrouter_api_key"] = "(not set)"

        return data


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience function to reload settings (clears cache)
def reload_settings() -> Settings:
    """Reload settings from environment."""
    get_settings.cache_clear()
    return get_settings()
