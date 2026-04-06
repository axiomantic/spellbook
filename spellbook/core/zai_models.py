"""Zai model registry and dataclasses for OpenCode/z.AI support."""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from spellbook.core.config import config_get


@dataclass
class ZaiModel:
    """Dataclass representing a z.AI model with metadata and constraints."""
    id: str
    name: str
    display_name: str
    max_concurrent: int
    context_size: int
    description: str
    use_cases: List[str]
    deprecated: bool = False
    vision_capable: bool = False

    def __post_init__(self) -> None:
        """Validate that model ID starts with required prefix."""
        if not self.id.startswith("zai-coding-plan/"):
            raise ValueError(f"Model ID must start with 'zai-coding-plan/' prefix. Got: {self.id}")


@dataclass
class ModelRegistry:
    """Registry for z.AI models with built-in and user-configured models."""
    
    def __init__(self) -> None:
        """Initialize registry with built-in models and load user models."""
        self._models: Dict[str, ZaiModel] = {}
        self._load_built_in_models()
        self._load_user_models()
    
    def _load_built_in_models(self) -> None:
        """Load the 18 built-in z.AI models."""
        built_in_models = [
            ZaiModel(
                id="zai-coding-plan/glm-5",
                name="glm-5",
                display_name="GLM-5",
                max_concurrent=2,
                context_size=200000,
                description="Most capable model with vision support, ideal for complex tasks",
                use_cases=["complex_coding", "architecture", "review"],
                vision_capable=True,
            ),
            ZaiModel(
                id="zai-coding-plan/glm-5-turbo",
                name="glm-5-turbo",
                display_name="GLM-5 Turbo",
                max_concurrent=1,
                context_size=128000,
                description="Fast model optimized for agent workflows and chat",
                use_cases=["agent_workflows", "chat"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.7",
                name="glm-4.7",
                display_name="GLM-4.7",
                max_concurrent=2,
                context_size=128000,
                description="Versatile model for general coding and analysis",
                use_cases=["general_coding", "analysis"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.6",
                name="glm-4.6",
                display_name="GLM-4.6",
                max_concurrent=3,
                context_size=128000,
                description="Balanced model for coding and analysis tasks",
                use_cases=["general_coding", "analysis"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.5",
                name="glm-4.5",
                display_name="GLM-4.5",
                max_concurrent=10,
                context_size=128000,
                description="High-throughput model for bulk processing",
                use_cases=["bulk_processing", "simple_tasks"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.6v",
                name="glm-4.6v",
                display_name="GLM-4.6V",
                max_concurrent=2,
                context_size=128000,
                description="Vision-capable model for multimodal tasks",
                use_cases=["vision_tasks", "multimodal"],
                vision_capable=True,
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.5v",
                name="glm-4.5v",
                display_name="GLM-4.5V",
                max_concurrent=2,
                context_size=128000,
                description="Vision model for visual tasks",
                use_cases=["vision_tasks", "multimodal"],
                vision_capable=True,
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.7-flashx",
                name="glm-4.7-flashx",
                display_name="GLM-4.7-FlashX",
                max_concurrent=5,
                context_size=128000,
                description="Rapid prototyping and brainstorming model",
                use_cases=["rapid_prototyping", "brainstorming"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.6v-flashx",
                name="glm-4.6v-flashx",
                display_name="GLM-4.6V-FlashX",
                max_concurrent=5,
                context_size=128000,
                description="Fast vision model for multimodal tasks",
                use_cases=["rapid_vision_tasks", "multimodal"],
                vision_capable=True,
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.6v-flash",
                name="glm-4.6v-flash",
                display_name="GLM-4.6V-Flash",
                max_concurrent=5,
                context_size=128000,
                description="Fast processing with vision capabilities",
                use_cases=["fast_vision_tasks", "multimodal"],
                vision_capable=True,
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4-plus",
                name="glm-4-plus",
                display_name="GLM-4-Plus",
                max_concurrent=2,
                context_size=128000,
                description="Enhanced model for complex coding tasks",
                use_cases=["enhanced_coding", "complex_tasks"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.5-air",
                name="glm-4.5-air",
                display_name="GLM-4.5-Air",
                max_concurrent=2,
                context_size=128000,
                description="Efficient model for streaming and processing",
                use_cases=["efficient_processing", "streaming"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.5-airx",
                name="glm-4.5-airx",
                display_name="GLM-4.5-AirX",
                max_concurrent=2,
                context_size=128000,
                description="Enhanced efficient model with streaming+",
                use_cases=["enhanced_efficient", "streaming_plus"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4.5-flash",
                name="glm-4.5-flash",
                display_name="GLM-4.5-Flash",
                max_concurrent=5,
                context_size=128000,
                description="Fast processing model with streaming support",
                use_cases=["fast_processing", "streaming"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-4-32b-0414-128k",
                name="glm-4-32b-0414-128k",
                display_name="GLM-4-32B-0414-128k",
                max_concurrent=1,
                context_size=128000,
                description="Long-context 32B model for document processing",
                use_cases=["long_context", "document_processing"],
            ),
            ZaiModel(
                id="zai-coding-plan/glm-5v-turbo",
                name="glm-5v-turbo",
                display_name="GLM-5V-Turbo",
                max_concurrent=1,
                context_size=128000,
                description="Vision-optimized model for multimodal tasks",
                use_cases=["vision_optimized", "multimodal"],
                vision_capable=True,
            ),
            ZaiModel(
                id="zai-coding-plan/glm-ocr",
                name="glm-ocr",
                display_name="GLM-OCR",
                max_concurrent=2,
                context_size=128000,
                description="Specialized OCR model for document analysis",
                use_cases=["ocr_tasks", "document_analysis"],
                vision_capable=True,
            ),
            ZaiModel(
                id="zai-coding-plan/glm-image",
                name="glm-image",
                display_name="GLM-Image",
                max_concurrent=2,
                context_size=128000,
                description="Model for image processing and visual content",
                use_cases=["image_processing", "visual_content"],
                vision_capable=True,
            ),
        ]
        
        for model in built_in_models:
            self._models[model.id] = model
    
    def _load_user_models(self) -> None:
        """Load user-configured models from config."""
        user_models = config_get("zai_models")
        if not isinstance(user_models, list):
            return
        
        for model_config in user_models:
            if not isinstance(model_config, dict):
                continue
            
            try:
                model = ZaiModel(
                    id=model_config["id"],
                    name=model_config["name"],
                    display_name=model_config.get("display_name", model_config["name"]),
                    max_concurrent=int(model_config["max_concurrent"]),
                    context_size=int(model_config["context_size"]),
                    description=model_config.get("description", ""),
                    use_cases=model_config.get("use_cases", []),
                    deprecated=model_config.get("deprecated", False),
                    vision_capable=model_config.get("vision_capable", False),
                )
                self._models[model.id] = model
            except (KeyError, ValueError) as e:
                # Skip invalid user models without crashing
                logging.getLogger(__name__).warning(
                    "Skipping invalid user model config: %s", model_config, exc_info=True
                )
                continue
    
    def get_all_models(self) -> List[ZaiModel]:
        """Get all models (built-in + user-configured)."""
        return list(self._models.values())
    
    def get_model(self, model_id: str) -> Optional[ZaiModel]:
        """Get model by ID. Returns None if not found."""
        return self._models.get(model_id)
    
    def get_models_by_use_case(self, use_case: str) -> List[ZaiModel]:
        """Get all models that support the given use case."""
        return [model for model in self._models.values() if use_case in model.use_cases]
    
    def get_non_deprecated_models(self) -> List[ZaiModel]:
        """Get all non-deprecated models."""
        return [model for model in self._models.values() if not model.deprecated]


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    """Get or create the global model registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry