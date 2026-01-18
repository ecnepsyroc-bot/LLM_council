"""CORS configuration for LLM Council API."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Environment-specific CORS configurations
CORS_CONFIGS = {
    "development": {
        "allow_origins": [
            "http://localhost:5173",  # Vite dev server
            "http://localhost:3000",  # Alternative dev port
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Request-ID"],
        "max_age": 600,  # Cache preflight for 10 minutes
    },
    "production": {
        "allow_origins": [],  # Must be set via ALLOWED_ORIGINS env var
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PATCH", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization", "X-Request-ID"],
        "max_age": 3600,  # Cache preflight for 1 hour
    },
}


def get_cors_config() -> dict:
    """
    Get CORS configuration based on environment.

    In production, reads ALLOWED_ORIGINS from environment variable.
    Format: comma-separated list of origins (e.g., "https://example.com,https://app.example.com")

    Returns:
        Dict with CORS middleware configuration
    """
    env = os.getenv("ENVIRONMENT", "development")
    config = CORS_CONFIGS.get(env, CORS_CONFIGS["development"]).copy()

    # In production, override origins from environment
    if env == "production":
        allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
        if allowed_origins:
            config["allow_origins"] = [
                origin.strip() for origin in allowed_origins.split(",") if origin.strip()
            ]
        else:
            # Fallback to development origins if not configured
            # Log a warning in real deployment
            print("WARNING: ALLOWED_ORIGINS not set in production, using development origins")
            config["allow_origins"] = CORS_CONFIGS["development"]["allow_origins"]

    return config


def configure_cors(app: FastAPI) -> None:
    """
    Apply CORS middleware to FastAPI application.

    Args:
        app: FastAPI application instance
    """
    config = get_cors_config()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config["allow_origins"],
        allow_credentials=config["allow_credentials"],
        allow_methods=config["allow_methods"],
        allow_headers=config["allow_headers"],
        max_age=config["max_age"],
    )
