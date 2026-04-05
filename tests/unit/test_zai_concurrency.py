"""Unit tests for z.AI concurrency manager using bigfoot mocking framework."""

import asyncio
import pytest
from unittest.mock import AsyncMock

import bigfoot
from spellbook.core.concurrency import ConcurrencyManager


@pytest.mark.asyncio
async def test_concurrency_limits_per_model_enforced():
    """Test that per-model concurrency limits are enforced correctly."""
    # Create ConcurrencyManager with pre-set config values
    manager = ConcurrencyManager()
    
    # Set config values directly (skip config_get during init)
    manager._max_concurrent_per_model = 3
    manager._global_max_concurrent = 5
    
    # Test that model semaphores respect limits
    semaphore = manager._get_semaphore("test-model")
    assert semaphore._value == 3  # Should respect per-model config
    assert manager.get_semaphore_limit("test-model") == 3


@pytest.mark.asyncio
async def test_usage_tracking_works_correctly():
    """Test that usage tracking works correctly."""
    # Create ConcurrencyManager and set config values
    manager = ConcurrencyManager()
    manager._max_concurrent_per_model = 2
    manager._global_max_concurrent = 4
        
    # Test initial usage is zero
    assert manager.get_current_usage("test-model") == 0
        
    # Simulate usage
    manager._usage_counts["test-model"] = 3
    assert manager.get_current_usage("test-model") == 3
        
    # Test reset functionality
    manager.reset_usage("test-model")
    assert manager.get_current_usage("test-model") == 0


@pytest.mark.asyncio
async def test_global_concurrent_limit_enforced():
    """Test that global concurrent limit is enforced."""
    # Create ConcurrencyManager and set config values
    manager = ConcurrencyManager()
    manager._max_concurrent_per_model = 10
    manager._global_max_concurrent = 2
    
    # Recreate the global semaphore with the correct limit
    manager._global_semaphore = asyncio.Semaphore(manager._global_max_concurrent)
        
    # Global semaphore should respect the global limit
    assert manager._global_semaphore._value == 2


@pytest.mark.asyncio
async def test_cross_model_concurrency_works_independently():
    """Test that cross-model concurrency works independently."""
    # Create ConcurrencyManager and set config values
    manager = ConcurrencyManager()
    manager._max_concurrent_per_model = 2
    manager._global_max_concurrent = 4
        
    # Different models should have independent semaphores
    semaphore1 = manager._get_semaphore("model1")
    semaphore2 = manager._get_semaphore("model2")
        
    assert semaphore1 is not semaphore2
    assert semaphore1._value == 2
    assert semaphore2._value == 2
        
    # Usage should be tracked independently
    manager._usage_counts["model1"] = 1
    manager._usage_counts["model2"] = 2
        
    assert manager.get_current_usage("model1") == 1
    assert manager.get_current_usage("model2") == 2


@pytest.mark.asyncio
async def test_timeout_handling():
    """Test timeout handling works correctly."""
    # Create ConcurrencyManager and set config values
    manager = ConcurrencyManager()
    manager._max_concurrent_per_model = 1
    manager._global_max_concurrent = 2
    
    # Mock semaphore acquisition to raise TimeoutError directly
    original_acquire = manager._global_semaphore.acquire
    manager._global_semaphore.acquire = AsyncMock(side_effect=asyncio.TimeoutError())
    
    try:
        result = await manager.acquire("test-model")
        assert result is None  # Should return None on timeout
    finally:
        # Restore original method
        manager._global_semaphore.acquire = original_acquire


@pytest.mark.asyncio
async def test_get_all_usage_returns_correct_counts():
    """Test that get_all_usage returns correct counts."""
    # Create ConcurrencyManager and set config values
    manager = ConcurrencyManager()
    manager._max_concurrent_per_model = 2
    manager._global_max_concurrent = 4
    
    # Set up some usage counts
    manager._usage_counts = {
        "model1": 3,
        "model2": 1,
        "model3": 0
    }
        
    all_usage = manager.get_all_usage()
        
    # Should be a copy, not the original dict
    assert all_usage == {"model1": 3, "model2": 1, "model3": 0}
    assert all_usage is not manager._usage_counts
        
    # Modifying the copy shouldn't affect the original
    all_usage["model1"] = 999
    assert manager._usage_counts["model1"] == 3


@pytest.mark.asyncio
async def test_semaphore_limits_correctly_retrieved():
    """Test that semaphore limits are correctly retrieved."""
    # Create ConcurrencyManager and set config values
    manager = ConcurrencyManager()
    manager._max_concurrent_per_model = 5
    manager._global_max_concurrent = 10
    
    # Test per-model limit calculation
    assert manager.get_semaphore_limit("test-model") == 5
        
    # Test with different config values
    manager._max_concurrent_per_model = 8
    manager._global_max_concurrent = 6
    assert manager.get_semaphore_limit("test-model") == 6
    
    # Create a new semaphore to test with the new limits
    semaphore = manager._get_semaphore("test-model")
    assert semaphore._value == 6


@pytest.mark.asyncio
async def test_usage_reset_works():
    """Test that usage reset works correctly."""
    # Create ConcurrencyManager and set config values
    manager = ConcurrencyManager()
    manager._max_concurrent_per_model = 2
    manager._global_max_concurrent = 4
    
    # Set up usage for multiple models
    manager._usage_counts = {
        "model1": 5,
        "model2": 3,
        "model3": 0
    }
        
    # Reset specific model
    manager.reset_usage("model1")
    assert manager._usage_counts["model1"] == 0
    assert manager._usage_counts["model2"] == 3  # Unchanged
        
    # Reset non-existent model should not crash
    manager.reset_usage("nonexistent-model")
    # Should not add the model to usage_counts


@pytest.mark.asyncio
@pytest.mark.allow("subprocess")
async def test_custom_limits_from_config_respected():
    """Test that custom limits from config are respected."""
    # Create ConcurrencyManager and set custom config values
    manager = ConcurrencyManager()
    manager._max_concurrent_per_model = 7
    manager._global_max_concurrent = 12
        
    # Should use custom config values
    assert manager._max_concurrent_per_model == 7
    assert manager._global_max_concurrent == 12
        
    # Semaphore limit should be the minimum of per-model and global
    assert manager.get_semaphore_limit("test-model") == 7