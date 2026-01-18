"""Tests for configuration module."""

import os
import pytest
from unittest.mock import AsyncMock, patch

from backend.config import (
    ModelConfig,
    ModelCapability,
    CouncilConfig,
    ConfigValidator,
    DEFAULT_COUNCIL_MODELS,
    DEFAULT_CHAIRMAN_MODEL,
    validate_config_on_startup,
)


class TestModelConfig:
    """Tests for ModelConfig."""

    def test_model_config_defaults(self):
        """ModelConfig has sensible defaults."""
        config = ModelConfig(id="openai/gpt-4")

        assert config.id == "openai/gpt-4"
        assert config.display_name == "gpt-4"
        assert config.provider == "openai"
        assert config.is_validated is False

    def test_model_config_custom_display_name(self):
        """ModelConfig uses custom display name if provided."""
        config = ModelConfig(id="openai/gpt-4", display_name="GPT-4 Custom")

        assert config.display_name == "GPT-4 Custom"

    def test_model_config_no_slash(self):
        """ModelConfig handles IDs without slash."""
        config = ModelConfig(id="gpt-4")

        assert config.display_name == "gpt-4"
        assert config.provider == "unknown"

    def test_model_config_capabilities(self):
        """ModelConfig can store capabilities."""
        config = ModelConfig(
            id="openai/gpt-4",
            capabilities=[ModelCapability.TEXT, ModelCapability.VISION],
        )

        assert ModelCapability.TEXT in config.capabilities
        assert ModelCapability.VISION in config.capabilities


class TestCouncilConfig:
    """Tests for CouncilConfig."""

    def test_default_from_env(self, monkeypatch):
        """from_env uses defaults when no env vars set."""
        # Clear env vars
        monkeypatch.delenv("COUNCIL_MODELS", raising=False)
        monkeypatch.delenv("CHAIRMAN_MODEL", raising=False)

        config = CouncilConfig.from_env()

        assert len(config.council_models) == len(DEFAULT_COUNCIL_MODELS)
        assert config.chairman_model.id == DEFAULT_CHAIRMAN_MODEL

    def test_from_env_with_custom_models(self, monkeypatch):
        """from_env respects environment variables."""
        monkeypatch.setenv("COUNCIL_MODELS", "model1,model2,model3")
        monkeypatch.setenv("CHAIRMAN_MODEL", "chairman-model")

        config = CouncilConfig.from_env()

        assert len(config.council_models) == 3
        assert config.council_models[0].id == "model1"
        assert config.chairman_model.id == "chairman-model"

    def test_council_model_ids_property(self, monkeypatch):
        """council_model_ids property returns list of IDs."""
        monkeypatch.setenv("COUNCIL_MODELS", "model1,model2")
        monkeypatch.delenv("CHAIRMAN_MODEL", raising=False)

        config = CouncilConfig.from_env()

        ids = config.council_model_ids
        assert ids == ["model1", "model2"]

    def test_chairman_model_id_property(self, monkeypatch):
        """chairman_model_id property returns chairman ID."""
        monkeypatch.setenv("CHAIRMAN_MODEL", "my-chairman")
        monkeypatch.delenv("COUNCIL_MODELS", raising=False)

        config = CouncilConfig.from_env()

        assert config.chairman_model_id == "my-chairman"


class TestConfigValidator:
    """Tests for ConfigValidator."""

    @pytest.mark.asyncio
    async def test_validator_without_client(self):
        """Validator assumes valid without client."""
        validator = ConfigValidator(client=None)
        model = ModelConfig(id="test-model")

        result = await validator._validate_model(model)

        assert result["valid"] is True
        assert model.is_validated is True

    @pytest.mark.asyncio
    async def test_validator_with_mock_client(self):
        """Validator uses client for validation."""
        mock_client = AsyncMock()
        mock_client.validate_model.return_value = True

        validator = ConfigValidator(client=mock_client)
        model = ModelConfig(id="test-model")

        result = await validator._validate_model(model)

        assert result["valid"] is True
        assert model.is_validated is True
        mock_client.validate_model.assert_called_once_with("test-model")

    @pytest.mark.asyncio
    async def test_validator_handles_client_error(self):
        """Validator handles client errors gracefully."""
        mock_client = AsyncMock()
        mock_client.validate_model.side_effect = Exception("API Error")

        validator = ConfigValidator(client=mock_client)
        model = ModelConfig(id="test-model")

        result = await validator._validate_model(model)

        assert result["valid"] is False
        assert model.is_validated is False
        assert "API Error" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_all(self):
        """validate_all validates all models in config."""
        mock_client = AsyncMock()
        mock_client.validate_model.return_value = True

        validator = ConfigValidator(client=mock_client)
        config = CouncilConfig(
            council_models=[
                ModelConfig(id="model1"),
                ModelConfig(id="model2"),
            ],
            chairman_model=ModelConfig(id="chairman"),
        )

        summary = await validator.validate_all(config)

        assert summary["total"] == 3
        assert summary["valid"] == 3
        assert summary["invalid"] == 0


class TestValidateConfigOnStartup:
    """Tests for validate_config_on_startup function."""

    @pytest.mark.asyncio
    async def test_startup_without_client(self, monkeypatch):
        """Startup validation works without client."""
        monkeypatch.setenv("COUNCIL_MODELS", "model1,model2")
        monkeypatch.setenv("CHAIRMAN_MODEL", "chairman")

        config = await validate_config_on_startup(client=None)

        assert len(config.council_models) == 2
        assert config.chairman_model.id == "chairman"

    @pytest.mark.asyncio
    async def test_startup_filters_invalid_models(self, monkeypatch):
        """Startup validation filters invalid models."""
        monkeypatch.setenv("COUNCIL_MODELS", "good1,bad_model,good2")
        monkeypatch.setenv("CHAIRMAN_MODEL", "chairman")

        mock_client = AsyncMock()
        # Only validate models with 'good' in name
        mock_client.validate_model.side_effect = lambda m: "good" in m

        config = await validate_config_on_startup(client=mock_client)

        # Should only have valid models
        valid_ids = [m.id for m in config.council_models]
        assert "good1" in valid_ids
        assert "good2" in valid_ids
        assert "bad_model" not in valid_ids
