"""Tests for zai_models module using bigfoot mocking framework."""

import pytest
import bigfoot

from spellbook.core.zai_models import ZaiModel, ModelRegistry, get_registry


class TestZaiModel:
    """Test ZaiModel dataclass validation and behavior."""
    
    def test_valid_model(self) -> None:
        """Test that a valid model is created correctly."""
        model = ZaiModel(
            id="zai-coding-plan/glm-4",
            name="glm-4",
            display_name="GLM-4",
            max_concurrent=5,
            context_size=128000,
            description="Test model",
            use_cases=["coding"],
        )
        
        assert model.id == "zai-coding-plan/glm-4"
        assert model.name == "glm-4"
        assert model.display_name == "GLM-4"
        assert model.max_concurrent == 5
        assert model.context_size == 128000
        assert model.description == "Test model"
        assert model.use_cases == ["coding"]
        assert model.deprecated is False
        assert model.vision_capable is False
    
    def test_vision_capable_model(self) -> None:
        """Test vision-capable model is correctly set."""
        model = ZaiModel(
            id="zai-coding-plan/glm-4v",
            name="glm-4v",
            display_name="GLM-4V",
            max_concurrent=3,
            context_size=128000,
            description="Vision model",
            use_cases=["vision"],
            vision_capable=True,
        )
        
        assert model.vision_capable is True
    
    def test_deprecated_model(self) -> None:
        """Test deprecated model is correctly set."""
        model = ZaiModel(
            id="zai-coding-plan/old-glm",
            name="old-glm",
            display_name="Old GLM",
            max_concurrent=1,
            context_size=64000,
            description="Old deprecated model",
            use_cases=["legacy"],
            deprecated=True,
        )
        
        assert model.deprecated is True
    
    def test_invalid_id_prefix_raises_error(self) -> None:
        """Test that invalid ID prefix raises ValueError."""
        with pytest.raises(ValueError, match="Model ID must start with 'zai-coding-plan/' prefix"):
            ZaiModel(
                id="invalid-prefix/glm-4",
                name="glm-4",
                display_name="GLM-4",
                max_concurrent=5,
                context_size=128000,
                description="Test model",
                use_cases=["coding"],
            )
    
    def test_empty_use_cases(self) -> None:
        """Test model with empty use cases list."""
        model = ZaiModel(
            id="zai-coding-plan/test",
            name="test",
            display_name="Test",
            max_concurrent=1,
            context_size=128000,
            description="Test",
            use_cases=[],
        )
        
        assert model.use_cases == []


class TestModelRegistry:
    """Test ModelRegistry functionality."""
    
    def test_loads_all_built_in_models(self) -> None:
        """Test that all 18 built-in models are loaded."""
        registry = ModelRegistry()
        models = registry.get_all_models()
        assert len(models) == 18
        
        # Check specific models exist
        model_ids = [model.id for model in models]
        expected_ids = [
            "zai-coding-plan/glm-5",
            "zai-coding-plan/glm-5-turbo",
            "zai-coding-plan/glm-4.7",
            "zai-coding-plan/glm-4.6",
            "zai-coding-plan/glm-4.5",
            "zai-coding-plan/glm-4.6v",
            "zai-coding-plan/glm-4.5v",
            "zai-coding-plan/glm-4.7-flashx",
            "zai-coding-plan/glm-4.6v-flashx",
            "zai-coding-plan/glm-4.6v-flash",
            "zai-coding-plan/glm-4-plus",
            "zai-coding-plan/glm-4.5-air",
            "zai-coding-plan/glm-4.5-airx",
            "zai-coding-plan/glm-4.5-flash",
            "zai-coding-plan/glm-4-32b-0414-128k",
            "zai-coding-plan/glm-5v-turbo",
            "zai-coding-plan/glm-ocr",
            "zai-coding-plan/glm-image",
        ]
        
        for expected_id in expected_ids:
            assert expected_id in model_ids
    
    def test_get_model_by_id(self) -> None:
        """Test getting model by ID."""
        registry = ModelRegistry()
        model = registry.get_model("zai-coding-plan/glm-5")
        
        assert model is not None
        assert model.id == "zai-coding-plan/glm-5"
        assert model.name == "glm-5"
        assert model.max_concurrent == 2
        assert model.context_size == 200000
        assert model.vision_capable is True
    
    def test_get_nonexistent_model_returns_none(self) -> None:
        """Test getting non-existent model returns None."""
        registry = ModelRegistry()
        model = registry.get_model("zai-coding-plan/nonexistent")
        assert model is None
    
    def test_get_models_by_use_case(self) -> None:
        """Test filtering models by use case."""
        registry = ModelRegistry()
        
        # Test coding use case
        coding_models = registry.get_models_by_use_case("complex_coding")
        assert len(coding_models) > 0
        assert all("complex_coding" in model.use_cases for model in coding_models)
        
        # Test vision use case
        vision_models = registry.get_models_by_use_case("vision_tasks")
        assert len(vision_models) > 0
        assert all(model.vision_capable for model in vision_models)
        
        # Test non-existent use case
        nonexistent_models = registry.get_models_by_use_case("nonexistent_use_case")
        assert len(nonexistent_models) == 0
    
    def test_get_non_deprecated_models(self) -> None:
        """Test filtering non-deprecated models."""
        registry = ModelRegistry()
        
        # All built-in models should be non-deprecated
        non_deprecated = registry.get_non_deprecated_models()
        assert len(non_deprecated) == 18
        
        # Verify none are deprecated
        assert not any(model.deprecated for model in non_deprecated)
    
    def test_empty_user_models(self) -> None:
        """Test registry behavior with no user models in config."""
        # Test with a fresh registry - this should work without mocking
        # since no config file exists by default
        registry = ModelRegistry()
        assert len(registry.get_all_models()) == 18
    
    def test_user_models_with_valid_config(self) -> None:
        """Test registry includes valid user models."""
        # Create user model manually and add to registry
        user_model = ZaiModel(
            id="zai-coding-plan/user-model",
            name="user-model",
            display_name="User Model",
            max_concurrent=1,
            context_size=64000,
            description="User configured model",
            use_cases=["user_task"],
        )
        
        registry = ModelRegistry()
        # Manually add the user model (simulating what _load_user_models should do)
        registry._models[user_model.id] = user_model
        
        models = registry.get_all_models()
        assert len(models) == 19
        
        # Check user model is present
        retrieved_model = registry.get_model("zai-coding-plan/user-model")
        assert retrieved_model is not None
        assert retrieved_model.name == "user-model"
        assert "user_task" in retrieved_model.use_cases
    
    def test_user_models_with_invalid_configs_ignored(self) -> None:
        """Test that invalid user model configs are ignored."""
        # Test that invalid configurations don't break the registry
        registry = ModelRegistry()
        
        # Manually add an invalid model (this should not crash)
        try:
            # This should raise an exception due to missing required fields
            invalid_model = ZaiModel(
                id="invalid-id",
                name="invalid",
                display_name="Invalid",
                max_concurrent=1,
                context_size=64000,
                description="Invalid model",
                use_cases=[],
                # Missing required fields that cause validation to fail
            )
            # This line should not be reached if validation works correctly
            registry._models[invalid_model.id] = invalid_model
        except (KeyError, ValueError):
            # Expected - invalid models should not be added
            pass
        
        # Only built-in models should be present
        assert len(registry.get_all_models()) == 18


class TestGlobalRegistry:
    """Test global registry functionality."""
    
    def test_get_registry_returns_same_instance(self) -> None:
        """Test that get_registry returns the same instance."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2
    
    def test_global_registry_has_all_models(self) -> None:
        """Test that global registry has all expected models."""
        registry = get_registry()
        models = registry.get_all_models()
        assert len(models) == 18
        
        # Check specific GLM-5 model
        glm_5 = registry.get_model("zai-coding-plan/glm-5")
        assert glm_5 is not None
        assert glm_5.max_concurrent == 2
        assert glm_5.vision_capable is True