"""
Startup validation for LLM Council.

Called from main.py before the application starts.
Validates configuration and dependencies.
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional

from .settings import get_settings, Settings

logger = logging.getLogger(__name__)


class StartupError(Exception):
    """Raised when startup validation fails."""
    pass


class StartupValidator:
    """Validates application configuration on startup."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> bool:
        """
        Run all validation checks.

        Returns:
            True if validation passed, False otherwise
        """
        self.validate_api_key()
        self.validate_database()
        self.validate_models()
        self.validate_directories()

        # Log results
        self._log_results()

        return len(self.errors) == 0

    def validate_api_key(self):
        """Validate OpenRouter API key is configured."""
        if not self.settings.openrouter_api_key:
            if self.settings.bypass_auth:
                self.warnings.append(
                    "OPENROUTER_API_KEY not set. API calls will fail. "
                    "Set the key in .env or environment variables."
                )
            else:
                self.errors.append(
                    "OPENROUTER_API_KEY is required. "
                    "Get your key at https://openrouter.ai/keys"
                )

    def validate_database(self):
        """Validate database is accessible."""
        try:
            from .database.connection import init_database, get_connection

            # Ensure database directory exists
            db_path = self.settings.database_path_absolute
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # Initialize database
            init_database()

            # Test connection
            conn = get_connection()
            result = conn.execute("SELECT 1").fetchone()
            if result[0] != 1:
                self.errors.append("Database connection test failed")

        except Exception as e:
            self.errors.append(f"Database initialization failed: {e}")

    def validate_models(self):
        """Validate model configuration."""
        models = self.settings.council_models_list

        if not models:
            self.errors.append("No council models configured")
            return

        if len(models) < 2:
            self.warnings.append(
                f"Only {len(models)} council model configured. "
                "Consider adding more models for better deliberation."
            )

        # Check for duplicate models
        if len(models) != len(set(models)):
            self.warnings.append("Duplicate models in council configuration")

        # Validate chairman is a known model format
        chairman = self.settings.chairman_model
        if "/" not in chairman:
            self.warnings.append(
                f"Chairman model '{chairman}' may be invalid. "
                "Expected format: provider/model-name"
            )

    def validate_directories(self):
        """Validate required directories exist or can be created."""
        required_dirs = [
            self.settings.database_path_absolute.parent,
            Path(__file__).parent.parent / "logs",
            Path(__file__).parent.parent / "backups",
        ]

        for dir_path in required_dirs:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.errors.append(f"Cannot create directory {dir_path}: {e}")

    def _log_results(self):
        """Log validation results."""
        # Log configuration summary
        logger.info("=" * 60)
        logger.info("LLM Council Startup")
        logger.info("=" * 60)

        safe_config = self.settings.to_safe_dict()
        logger.info("Configuration:")
        for key, value in safe_config.items():
            logger.info(f"  {key}: {value}")

        # Log warnings
        if self.warnings:
            logger.warning("-" * 60)
            logger.warning(f"Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  ⚠ {warning}")

        # Log errors
        if self.errors:
            logger.error("-" * 60)
            logger.error(f"Errors ({len(self.errors)}):")
            for error in self.errors:
                logger.error(f"  ✗ {error}")

        logger.info("=" * 60)


def validate_startup(settings: Optional[Settings] = None) -> bool:
    """
    Validate application startup.

    Args:
        settings: Optional settings instance (uses default if not provided)

    Returns:
        True if validation passed

    Raises:
        StartupError: If validation fails with errors
    """
    validator = StartupValidator(settings)
    passed = validator.validate_all()

    if not passed:
        error_msg = "Startup validation failed:\n" + "\n".join(
            f"  - {e}" for e in validator.errors
        )
        raise StartupError(error_msg)

    return True


async def check_openrouter_connectivity() -> dict:
    """
    Check connectivity to OpenRouter API.

    Returns:
        dict with connectivity status and details
    """
    import aiohttp
    from .settings import get_settings

    settings = get_settings()
    result = {
        "connected": False,
        "error": None,
        "latency_ms": None,
    }

    if not settings.openrouter_api_key:
        result["error"] = "API key not configured"
        return result

    try:
        import time
        start = time.time()

        async with aiohttp.ClientSession() as session:
            # Use a lightweight models endpoint to check connectivity
            async with session.get(
                "https://openrouter.ai/api/v1/models",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                latency = (time.time() - start) * 1000

                if response.status == 200:
                    result["connected"] = True
                    result["latency_ms"] = round(latency, 2)
                elif response.status == 401:
                    result["error"] = "Invalid API key"
                else:
                    result["error"] = f"HTTP {response.status}"

    except aiohttp.ClientError as e:
        result["error"] = f"Connection error: {e}"
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"

    return result
