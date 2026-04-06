"""Tests for z.AI MCP tools using bigfoot mocking framework."""

import pytest

import bigfoot

from spellbook.core.zai_models import ModelRegistry, ZaiModel
from spellbook.core.concurrency import ConcurrencyManager


def _make_model(
    model_id: str = "zai-coding-plan/glm-5",
    name: str = "glm-5",
    display_name: str = "GLM-5",
    max_concurrent: int = 2,
    context_size: int = 200000,
    description: str = "Most capable model",
    use_cases: list | None = None,
    deprecated: bool = False,
    vision_capable: bool = True,
) -> ZaiModel:
    """Create a ZaiModel with sensible defaults for testing."""
    return ZaiModel(
        id=model_id,
        name=name,
        display_name=display_name,
        max_concurrent=max_concurrent,
        context_size=context_size,
        description=description,
        use_cases=use_cases or ["complex_coding", "architecture"],
        deprecated=deprecated,
        vision_capable=vision_capable,
    )


def _make_registry() -> ModelRegistry:
    """Create a real ModelRegistry for testing."""
    return ModelRegistry()


def _make_manager() -> ConcurrencyManager:
    """Create a real ConcurrencyManager for testing."""
    manager = ConcurrencyManager()
    manager._max_concurrent_per_model = 2
    manager._global_max_concurrent = 4
    return manager


class TestZaiListModels:
    """Tests for zai_list_models MCP tool."""

    def test_returns_model_list(self) -> None:
        """Returns list of models from registry.

        ESCAPE: test_returns_model_list
          CLAIM: zai_list_models returns all models from the registry as dicts
          PATH:  _get_registry() returns a registry, get_all_models() returns
                 list of ZaiModel, result contains "models" key with list of dicts
          CHECK: result["models"] is a list with length > 0 and each item is a dict
          MUTATION: Returning empty list always -> assertion fails
          ESCAPE: None — checks list is non-empty and items are dicts
          IMPACT: Models not discoverable via MCP
        """
        registry = _make_registry()
        model = _make_model()
        registry._models["zai-coding-plan/glm-5"] = model

        mock_gr = bigfoot.mock(
            "spellbook.mcp.tools.zai_models:_get_registry"
        )
        mock_gr.returns(registry)

        with bigfoot:
            from spellbook.mcp.tools.zai_models import zai_list_models

            result = zai_list_models(ctx=None)

        assert "models" in result
        assert isinstance(result["models"], list)
        assert len(result["models"]) >= 1

        glm5 = next(
            m for m in result["models"] if m["id"] == "zai-coding-plan/glm-5"
        )
        assert glm5["name"] == "glm-5"
        assert glm5["display_name"] == "GLM-5"
        assert glm5["max_concurrent"] == 2
        assert glm5["context_size"] == 200000
        assert glm5["vision_capable"] is True

        mock_gr.assert_call(args=(), kwargs={})


class TestZaiGetModelInfo:
    """Tests for zai_get_model_info MCP tool."""

    def test_returns_model_details(self) -> None:
        """Returns model details with concurrency info.

        ESCAPE: test_returns_model_details
          CLAIM: zai_get_model_info returns model fields plus current_concurrent
          PATH:  registry.get_model() returns ZaiModel, ConcurrencyManager.get_current_usage()
                 returns 1, result dict has all model fields plus "current_concurrent"
          CHECK: result["id"] matches, result["current_concurrent"] == 1
          MUTATION: Omitting current_concurrent -> KeyError on assertion
          ESCAPE: None — exact field values verified
          IMPACT: Model info incomplete for monitoring
        """
        registry = _make_registry()
        model = _make_model()
        registry._models["zai-coding-plan/glm-5"] = model

        manager = _make_manager()

        mock_gr = bigfoot.mock(
            "spellbook.mcp.tools.zai_models:_get_registry"
        )
        mock_gr.returns(registry)

        mock_gm = bigfoot.mock(
            "spellbook.mcp.tools.zai_models:_get_concurrency_manager"
        )
        mock_gm.returns(manager)

        mock_gcu = bigfoot.mock.object(manager, "get_current_usage")
        mock_gcu.returns(1)

        with bigfoot:
            from spellbook.mcp.tools.zai_models import zai_get_model_info

            result = zai_get_model_info(
                ctx=None, model_id="zai-coding-plan/glm-5"
            )

        assert result["id"] == "zai-coding-plan/glm-5"
        assert result["name"] == "glm-5"
        assert result["current_concurrent"] == 1
        assert result["max_concurrent"] == 2
        assert result["vision_capable"] is True

        mock_gr.assert_call(args=(), kwargs={})
        mock_gm.assert_call(args=(), kwargs={})
        mock_gcu.assert_call(
            args=("zai-coding-plan/glm-5",), kwargs={}
        )

    def test_raises_for_nonexistent_model(self) -> None:
        """Raises ValueError when model ID is not found.

        ESCAPE: test_raises_for_nonexistent_model
          CLAIM: zai_get_model_info raises ValueError for unknown model_id
          PATH:  registry.get_model() returns None, function raises ValueError
          CHECK: ValueError raised with "Model not found" in message
          MUTATION: Returning empty dict instead of raising -> no exception caught
          ESCAPE: None — exact exception type and partial message verified
          IMPACT: Silent failure on invalid model IDs
        """
        registry = _make_registry()

        mock_gr = bigfoot.mock(
            "spellbook.mcp.tools.zai_models:_get_registry"
        )
        mock_gr.returns(registry)

        with bigfoot:
            from spellbook.mcp.tools.zai_models import zai_get_model_info

            with pytest.raises(ValueError, match="Model not found"):
                zai_get_model_info(
                    ctx=None, model_id="zai-coding-plan/nonexistent"
                )

        mock_gr.assert_call(args=(), kwargs={})


class TestZaiSetDefaultModel:
    """Tests for zai_set_default_model MCP tool."""

    def test_validates_and_sets_model(self) -> None:
        """Validates model exists and persists default.

        ESCAPE: test_validates_and_sets_model
          CLAIM: zai_set_default_model validates model exists then calls set_zai_default_model
          PATH:  registry.get_model() returns model, set_zai_default_model() called
          CHECK: result["status"] == "ok" and result["model_id"] matches input
          MUTATION: Not calling set_zai_default_model -> assert_call fails
          ESCAPE: None — both validation and persistence verified
          IMPACT: Invalid model set as default or config not persisted
        """
        registry = _make_registry()
        model = _make_model()
        registry._models["zai-coding-plan/glm-5"] = model

        mock_gr = bigfoot.mock(
            "spellbook.mcp.tools.zai_models:_get_registry"
        )
        mock_gr.returns(registry)

        mock_sdm = bigfoot.mock(
            "spellbook.core.zai_config:set_zai_default_model"
        )
        mock_sdm.returns(None)

        with bigfoot:
            from spellbook.mcp.tools.zai_models import zai_set_default_model

            result = zai_set_default_model(
                ctx=None, model_id="zai-coding-plan/glm-5"
            )

        assert result["status"] == "ok"
        assert result["model_id"] == "zai-coding-plan/glm-5"
        mock_gr.assert_call(args=(), kwargs={})
        mock_sdm.assert_call(
            args=("zai-coding-plan/glm-5",), kwargs={}
        )

    def test_raises_for_invalid_model(self) -> None:
        """Raises ValueError when model ID is not found.

        ESCAPE: test_raises_for_invalid_model
          CLAIM: zai_set_default_model raises ValueError for unknown model_id
          PATH:  registry.get_model() returns None, function raises ValueError
          CHECK: ValueError raised with "Model not found"
          MUTATION: Setting default without validation -> no exception
          ESCAPE: None — exception type and message verified
          IMPACT: Invalid model saved as default, causing API errors
        """
        registry = _make_registry()

        mock_gr = bigfoot.mock(
            "spellbook.mcp.tools.zai_models:_get_registry"
        )
        mock_gr.returns(registry)

        with bigfoot:
            from spellbook.mcp.tools.zai_models import zai_set_default_model

            with pytest.raises(ValueError, match="Model not found"):
                zai_set_default_model(
                    ctx=None, model_id="zai-coding-plan/nonexistent"
                )

        mock_gr.assert_call(args=(), kwargs={})


class TestZaiSetApiKey:
    """Tests for zai_set_api_key MCP tool."""

    def test_validates_and_sets_key(self) -> None:
        """Validates key length and persists to config.

        ESCAPE: test_validates_and_sets_key
          CLAIM: zai_set_api_key validates key >= 10 chars then calls set_zai_api_key
          PATH:  Key "sk-abc123456" passes validation, set_zai_api_key() called
          CHECK: result["status"] == "ok" and set_zai_api_key called with exact key
          MUTATION: Not calling set_zai_api_key -> assert_call fails
          ESCAPE: None — both validation and persistence verified
          IMPACT: API key not stored or stored without validation
        """
        mock_sak = bigfoot.mock(
            "spellbook.core.zai_config:set_zai_api_key"
        )
        mock_sak.returns(None)

        with bigfoot:
            from spellbook.mcp.tools.zai_models import zai_set_api_key

            result = zai_set_api_key(ctx=None, api_key="sk-abc123456")

        assert result["status"] == "ok"
        mock_sak.assert_call(args=("sk-abc123456",), kwargs={})

    def test_raises_for_empty_key(self) -> None:
        """Raises ValueError for empty API key.

        ESCAPE: test_raises_for_empty_key
          CLAIM: zai_set_api_key raises ValueError for empty string
          PATH:  api_key="" fails validation
          CHECK: ValueError raised with "non-empty string"
          MUTATION: Accepting empty string -> no exception
          ESCAPE: None — exact exception type and message verified
          IMPACT: Empty API key stored, causing auth failures
        """
        with bigfoot:
            from spellbook.mcp.tools.zai_models import zai_set_api_key

            with pytest.raises(ValueError, match="non-empty string"):
                zai_set_api_key(ctx=None, api_key="")

    def test_raises_for_short_key(self) -> None:
        """Raises ValueError for API key shorter than 10 characters.

        ESCAPE: test_raises_for_short_key
          CLAIM: zai_set_api_key raises ValueError for keys < 10 chars
          PATH:  api_key="short" (5 chars) fails validation
          CHECK: ValueError raised with "at least 10 characters"
          MUTATION: Accepting short key -> no exception
          ESCAPE: None — exact exception type and message verified
          IMPACT: Invalid key stored, causing auth failures
        """
        with bigfoot:
            from spellbook.mcp.tools.zai_models import zai_set_api_key

            with pytest.raises(ValueError, match="at least 10 characters"):
                zai_set_api_key(ctx=None, api_key="short")


class TestZaiConcurrencyStatus:
    """Tests for zai_concurrency_status MCP tool."""

    def test_returns_usage_info(self) -> None:
        """Returns per-model concurrency usage and limits.

        ESCAPE: test_returns_usage_info
          CLAIM: zai_concurrency_status returns model usage counts and limits
          PATH:  ConcurrencyManager.get_all_usage() returns usage dict,
                 ModelRegistry.get_all_models() returns models,
                 result contains "models" with usage and limit per model
          CHECK: result["models"] has entry for model with correct usage/limit
          MUTATION: Returning empty dict always -> assertion fails
          ESCAPE: None — exact usage and limit values verified
          IMPACT: Concurrency monitoring broken
        """
        registry = _make_registry()
        model = _make_model()
        registry._models["zai-coding-plan/glm-5"] = model

        manager = _make_manager()

        mock_gm = bigfoot.mock(
            "spellbook.mcp.tools.zai_models:_get_concurrency_manager"
        )
        mock_gm.returns(manager)

        mock_gau = bigfoot.mock.object(manager, "get_all_usage")
        mock_gau.returns({"zai-coding-plan/glm-5": 1})

        mock_gr = bigfoot.mock(
            "spellbook.mcp.tools.zai_models:_get_registry"
        )
        mock_gr.returns(registry)

        with bigfoot:
            from spellbook.mcp.tools.zai_models import zai_concurrency_status

            result = zai_concurrency_status(ctx=None)

        assert "models" in result
        models = result["models"]
        assert "zai-coding-plan/glm-5" in models
        assert models["zai-coding-plan/glm-5"]["current_concurrent"] == 1
        assert models["zai-coding-plan/glm-5"]["limit"] == 2

        mock_gm.assert_call(args=(), kwargs={})
        mock_gau.assert_call(args=(), kwargs={})
        mock_gr.assert_call(args=(), kwargs={})
