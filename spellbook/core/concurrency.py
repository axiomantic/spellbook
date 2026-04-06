"""Concurrency manager for z.AI model rate limiting.

Provides per-model concurrency control with configurable limits from
spellbook configuration and model-specific overrides via ModelRegistry.
"""

import asyncio
import logging
from typing import Dict, Optional
from spellbook.core.config import config_get


class ConcurrencyManager:
    """Manages concurrent access to z.AI models with rate limiting.
    
    Uses asyncio.Semaphore per model to enforce concurrency limits,
    with configurable defaults and model-specific overrides.
    """
    
    def __init__(self):
        """Initialize with configurable limits from config."""
        # Get config values with defaults
        self._max_concurrent_per_model = config_get("zai_concurrency_limits.max_concurrent_per_model") or 10
        self._global_max_concurrent = config_get("zai_concurrency_limits.global_max_concurrent") or 20
        
        # Track model semaphores and usage
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._usage_counts: Dict[str, int] = {}
        self._global_semaphore = asyncio.Semaphore(self._global_max_concurrent)
        
        # Lazy import for ModelRegistry (handles case where zai_models doesn't exist yet)
        self._model_registry = None
    
    def _get_model_registry(self):
        """Lazy import of ModelRegistry."""
        if self._model_registry is None:
            try:
                from spellbook.core.zai_models import get_registry
                self._model_registry = get_registry()
            except ImportError:
                logging.getLogger(__name__).debug(
                    "Could not import zai_models ModelRegistry", exc_info=True
                )
        return self._model_registry
    
    def _get_semaphore_limit(self, model_id: str) -> int:
        """Calculate the effective semaphore limit for a model.
        
        Priority: min(model.max_concurrent, max_concurrent_per_model, global_max_concurrent)
        
        Args:
            model_id: The model identifier
            
        Returns:
            The maximum concurrent requests allowed for this model
        """
        # Start with per-model config limit
        limit = self._max_concurrent_per_model
        
        # If ModelRegistry is available, check model-specific limit
        registry = self._get_model_registry()
        if registry:
            model = registry.get_model(model_id)
            if model:
                limit = min(limit, model.max_concurrent)
        
        # Apply global limit as the final constraint
        return min(limit, self._global_max_concurrent)
    
    def _get_semaphore(self, model_id: str) -> asyncio.Semaphore:
        """Get or create asyncio.Semaphore for model.
        
        Args:
            model_id: The model identifier
            
        Returns:
            The semaphore for this model
        """
        if model_id not in self._model_semaphores:
            limit = self._get_semaphore_limit(model_id)
            self._model_semaphores[model_id] = asyncio.Semaphore(limit)
            self._usage_counts[model_id] = 0
        
        return self._model_semaphores[model_id]
    
    async def acquire(self, model_id: str) -> Optional[asyncio.Semaphore]:
        """Acquire global and model-specific semaphore with timeout.
        
        Args:
            model_id: The model identifier
            
        Returns:
            The model semaphore if acquired, None on timeout
        """
        acquired_global = False
        try:
            # Acquire global semaphore first
            await asyncio.wait_for(self._global_semaphore.acquire(), timeout=30.0)
            acquired_global = True

            # Then acquire model-specific semaphore
            model_semaphore = self._get_semaphore(model_id)
            await asyncio.wait_for(model_semaphore.acquire(), timeout=30.0)

            # Track usage
            self._usage_counts[model_id] += 1

            return model_semaphore

        except asyncio.TimeoutError:
            # If we acquired the global semaphore but timed out on the model one, release global
            if acquired_global:
                self._global_semaphore.release()
            return None
    
    def release(self, model_id: str, semaphore: asyncio.Semaphore) -> None:
        """Release both model and global semaphores.
        
        Args:
            model_id: The model identifier
            semaphore: The model semaphore to release
        """
        # Release semaphores. Note: asyncio semaphores do not track ownership,
        # so we rely on the caller to only call release if they successfully acquired.
        semaphore.release()
        self._global_semaphore.release()
        
        # Decrement usage count
        if model_id in self._usage_counts:
            self._usage_counts[model_id] = max(0, self._usage_counts[model_id] - 1)
    
    def get_current_usage(self, model_id: str) -> int:
        """Return current usage count for model.
        
        Args:
            model_id: The model identifier
            
        Returns:
            Current number of active requests for this model
        """
        return self._usage_counts.get(model_id, 0)
    
    def get_all_usage(self) -> Dict[str, int]:
        """Return copy of all usage counts.
        
        Returns:
            Copy of the usage counts dictionary
        """
        return self._usage_counts.copy()
    
    def get_semaphore_limit(self, model_id: str) -> int:
        """Return the semaphore limit for a model.
        
        Args:
            model_id: The model identifier
            
        Returns:
            The maximum concurrent requests allowed for this model
        """
        return self._get_semaphore_limit(model_id)
    
    def reset_usage(self, model_id: str) -> None:
        """Reset usage count for a model.
        
        Args:
            model_id: The model identifier
        """
        if model_id in self._usage_counts:
            self._usage_counts[model_id] = 0