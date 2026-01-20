"""Tests for configuration module."""

import os
import pytest
from unittest.mock import patch

from backend.config import (
    DEFAULT_COUNCIL_MODELS,
    DEFAULT_CHAIRMAN_MODEL,
    COUNCIL_MODELS,
    CHAIRMAN_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_API_URL,
    DATA_DIR,
)


class TestConfigDefaults:
    """Tests for configuration defaults."""

    def test_default_council_models_not_empty(self):
        """Default council models list is not empty."""
        assert len(DEFAULT_COUNCIL_MODELS) > 0

    def test_default_chairman_model_set(self):
        """Default chairman model is set."""
        assert DEFAULT_CHAIRMAN_MODEL is not None
        assert len(DEFAULT_CHAIRMAN_MODEL) > 0

    def test_default_chairman_in_council(self):
        """Default chairman is one of the council models."""
        # Chairman should typically be a capable model from the council
        assert DEFAULT_CHAIRMAN_MODEL in DEFAULT_COUNCIL_MODELS

    def test_openrouter_url_set(self):
        """OpenRouter API URL is configured."""
        assert OPENROUTER_API_URL == "https://openrouter.ai/api/v1/chat/completions"

    def test_data_dir_is_absolute_path(self):
        """Data directory is an absolute path."""
        assert os.path.isabs(DATA_DIR)


class TestEnvironmentOverrides:
    """Tests for environment variable overrides."""

    def test_council_models_from_env(self, monkeypatch):
        """COUNCIL_MODELS env var overrides defaults."""
        monkeypatch.setenv("COUNCIL_MODELS", "model1,model2,model3")

        # Re-import to get fresh config with env var
        import importlib
        import backend.config as config_module
        importlib.reload(config_module)

        assert config_module.COUNCIL_MODELS == ["model1", "model2", "model3"]

        # Clean up - restore defaults
        monkeypatch.delenv("COUNCIL_MODELS", raising=False)
        importlib.reload(config_module)

    def test_chairman_model_from_env(self, monkeypatch):
        """CHAIRMAN_MODEL env var overrides default."""
        monkeypatch.setenv("CHAIRMAN_MODEL", "custom/chairman")

        import importlib
        import backend.config as config_module
        importlib.reload(config_module)

        assert config_module.CHAIRMAN_MODEL == "custom/chairman"

        # Clean up
        monkeypatch.delenv("CHAIRMAN_MODEL", raising=False)
        importlib.reload(config_module)

    def test_empty_council_models_uses_defaults(self, monkeypatch):
        """Empty COUNCIL_MODELS falls back to defaults."""
        monkeypatch.setenv("COUNCIL_MODELS", "")

        import importlib
        import backend.config as config_module
        importlib.reload(config_module)

        assert config_module.COUNCIL_MODELS == DEFAULT_COUNCIL_MODELS

        # Clean up
        monkeypatch.delenv("COUNCIL_MODELS", raising=False)
        importlib.reload(config_module)

    def test_whitespace_handling_in_council_models(self, monkeypatch):
        """Whitespace in COUNCIL_MODELS is trimmed."""
        monkeypatch.setenv("COUNCIL_MODELS", " model1 , model2 , model3 ")

        import importlib
        import backend.config as config_module
        importlib.reload(config_module)

        assert config_module.COUNCIL_MODELS == ["model1", "model2", "model3"]

        # Clean up
        monkeypatch.delenv("COUNCIL_MODELS", raising=False)
        importlib.reload(config_module)


class TestModelIdentifiers:
    """Tests for model identifier format."""

    def test_default_models_have_provider_prefix(self):
        """Default models follow provider/model format."""
        for model in DEFAULT_COUNCIL_MODELS:
            assert "/" in model, f"Model {model} should have provider prefix"

    def test_chairman_has_provider_prefix(self):
        """Chairman model follows provider/model format."""
        assert "/" in DEFAULT_CHAIRMAN_MODEL


class TestConfigExports:
    """Tests for module exports."""

    def test_all_exports_available(self):
        """All expected exports are available from config module."""
        from backend import config

        expected = [
            "OPENROUTER_API_KEY",
            "OPENROUTER_API_URL",
            "COUNCIL_MODELS",
            "CHAIRMAN_MODEL",
            "DEFAULT_COUNCIL_MODELS",
            "DEFAULT_CHAIRMAN_MODEL",
            "DATA_DIR",
        ]

        for name in expected:
            assert hasattr(config, name), f"Missing export: {name}"
