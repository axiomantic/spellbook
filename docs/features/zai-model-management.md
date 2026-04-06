# z.AI Model Management

Spellbook provides first-class support for z.AI (GLM) models via OpenCode. This includes a built-in model registry with 18 GLM models, per-model concurrency control, task-to-model routing, and MCP tools for runtime configuration.

## Overview

The z.AI integration has three components:

| Component | Module | Purpose |
|-----------|--------|---------|
| Model Registry | `spellbook.core.zai_models` | 18 built-in GLM models + user-configured models |
| Concurrency Manager | `spellbook.core.concurrency` | Per-model semaphores with configurable limits |
| Configuration | `spellbook.core.zai_config` | API key, default model, task routing, concurrency limits |

All components are accessible via MCP tools, so you can configure z.AI from any assistant session without editing config files directly.

## Available Models

18 GLM models are registered by default. User-configured models are loaded from spellbook config and merged with built-in definitions.

### Text Models

| Model | Display Name | Concurrency | Context | Use Cases |
|-------|-------------|-------------|---------|-----------|
| `zai-coding-plan/glm-5` | GLM-5 | 2 | 200K | Complex coding, architecture, review |
| `zai-coding-plan/glm-5-turbo` | GLM-5 Turbo | 1 | 128K | Agent workflows, chat |
| `zai-coding-plan/glm-4.7` | GLM-4.7 | 2 | 128K | General coding, analysis |
| `zai-coding-plan/glm-4.6` | GLM-4.6 | 3 | 128K | General coding, analysis |
| `zai-coding-plan/glm-4.5` | GLM-4.5 | 10 | 128K | Bulk processing, simple tasks |
| `zai-coding-plan/glm-4-plus` | GLM-4-Plus | 2 | 128K | Enhanced coding, complex tasks |
| `zai-coding-plan/glm-4.5-air` | GLM-4.5-Air | 2 | 128K | Efficient processing, streaming |
| `zai-coding-plan/glm-4.5-airx` | GLM-4.5-AirX | 2 | 128K | Enhanced efficient, streaming+ |
| `zai-coding-plan/glm-4.5-flash` | GLM-4.5-Flash | 5 | 128K | Fast processing, streaming |
| `zai-coding-plan/glm-4.7-flashx` | GLM-4.7-FlashX | 5 | 128K | Rapid prototyping, brainstorming |
| `zai-coding-plan/glm-4-32b-0414-128k` | GLM-4-32B-0414-128k | 1 | 128K | Long context, document processing |

### Vision Models

| Model | Display Name | Concurrency | Context | Use Cases |
|-------|-------------|-------------|---------|-----------|
| `zai-coding-plan/glm-5` | GLM-5 | 2 | 200K | Complex coding with vision |
| `zai-coding-plan/glm-4.6v` | GLM-4.6V | 2 | 128K | Vision tasks, multimodal |
| `zai-coding-plan/glm-4.5v` | GLM-4.5V | 2 | 128K | Vision tasks, multimodal |
| `zai-coding-plan/glm-4.6v-flashx` | GLM-4.6V-FlashX | 5 | 128K | Fast vision, multimodal |
| `zai-coding-plan/glm-4.6v-flash` | GLM-4.6V-Flash | 5 | 128K | Fast vision, multimodal |
| `zai-coding-plan/glm-5v-turbo` | GLM-5V-Turbo | 1 | 128K | Vision-optimized, multimodal |
| `zai-coding-plan/glm-ocr` | GLM-OCR | 2 | 128K | OCR, document analysis |
| `zai-coding-plan/glm-image` | GLM-Image | 2 | 128K | Image processing, visual content |

The default model is `glm-4.7` (`zai-coding-plan/glm-4.7`).

## MCP Tools

Six MCP tools are available for z.AI model management:

### zai_list_models

List all registered models (built-in + user-configured).

```python
# Returns dict with "models" list
zai_list_models()
```

Each model entry includes: `id`, `name`, `display_name`, `max_concurrent`, `context_size`, `description`, `use_cases`, `deprecated`, `vision_capable`.

### zai_get_model_info

Get detailed info for a specific model, including current concurrency usage.

```python
zai_get_model_info(model_id="zai-coding-plan/glm-5")
# Returns model fields + "current_concurrent" count
```

### zai_set_default_model

Set the default model. Validates that the model exists in the registry.

```python
zai_set_default_model(model_id="zai-coding-plan/glm-5")
# Returns {"status": "ok", "model_id": "zai-coding-plan/glm-5"}
```

### zai_configure_task_routing

Map task types to model IDs. All model IDs are validated before persisting.

```python
zai_configure_task_routing(routing_config={
    "coding": "zai-coding-plan/glm-5",
    "review": "zai-coding-plan/glm-4.7",
    "chat": "zai-coding-plan/glm-5-turbo"
})
```

### zai_set_api_key

Set the z.AI API key. Minimum 10 characters. Persisted to spellbook config.

```python
zai_set_api_key(api_key="your-api-key-here")
```

### zai_concurrency_status

Get per-model concurrency usage and limits.

```python
zai_concurrency_status()
# Returns {"models": {model_id: {"current_concurrent": N, "limit": M}, ...}}
```

## Configuration

### Config Keys

| Key | Default | Description |
|-----|---------|-------------|
| `zai_default_model` | `glm-4.7` | Default model for tasks without routing |
| `zai_api_key` | None | API key (prefer `ZAI_API_KEY` env var) |
| `zai_task_routing` | `{}` | Task-to-model mapping |
| `zai_concurrency_limits.max_concurrent_per_model` | `10` | Upper bound per model |
| `zai_concurrency_limits.global_max_concurrent` | `20` | Total concurrent across all models |
| `zai_models` | `[]` | User-configured model definitions |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ZAI_API_KEY` | API key (overrides config value). Preferred over config for security. |

### Adding Custom Models

Add models to the `zai_models` config key as a list of model definitions:

```json
{
  "zai_models": [
    {
      "id": "zai-coding-plan/my-custom-model",
      "name": "my-custom-model",
      "display_name": "My Custom Model",
      "max_concurrent": 3,
      "context_size": 128000,
      "description": "Custom model for specialized tasks",
      "use_cases": ["specialized_task"],
      "vision_capable": false,
      "deprecated": false
    }
  ]
}
```

Model IDs must start with `zai-coding-plan/`. User models override built-in models with the same ID.

## Task Routing

Task routing maps task types (e.g., "coding", "review", "chat") to specific model IDs. When a task has a routed model, that model is used instead of the default.

```python
# Configure routing via MCP tool
zai_configure_task_routing({
    "coding": "zai-coding-plan/glm-5",
    "review": "zai-coding-plan/glm-4.7",
    "chat": "zai-coding-plan/glm-5-turbo",
    "vision": "zai-coding-plan/glm-4.6v"
})
```

Tasks without a routing entry use the default model.

## Concurrency Management

The ConcurrencyManager enforces rate limits per model using asyncio semaphores. Limits are resolved in priority order:

1. Model-specific `max_concurrent` from the registry
2. `zai_concurrency_limits.max_concurrent_per_model` config (default: 10)
3. `zai_concurrency_limits.global_max_concurrent` config (default: 20)

The effective limit for a model is the minimum of these three values. A global semaphore enforces total concurrency across all models.

Acquire and release pattern:

```python
manager = ConcurrencyManager()
semaphore = await manager.acquire("zai-coding-plan/glm-5")
try:
    # Make API call
    result = await call_model(...)
finally:
    manager.release("zai-coding-plan/glm-5", semaphore)
```

Acquisition has a 30-second timeout for both global and model semaphores. If the model semaphore times out, the global semaphore is released automatically.

## Troubleshooting

### "Model not found" errors

The model ID must include the `zai-coding-plan/` prefix. Use `zai_list_models` to see valid IDs.

### API key not recognized

Check resolution order: `ZAI_API_KEY` environment variable takes priority over config. Verify with:

```python
# Via MCP tool
zai_get_model_info(model_id="zai-coding-plan/glm-4.7")
```

If `is_zai_configured()` returns `False`, set the key via `zai_set_api_key` or the `ZAI_API_KEY` environment variable.

### Concurrency limits too restrictive

Default limits are 10 per model and 20 global. Override via config:

```json
{
  "zai_concurrency_limits": {
    "max_concurrent_per_model": 15,
    "global_max_concurrent": 50
  }
}
```

### Custom model not loading

Verify the model definition:
- `id` must start with `zai-coding-plan/`
- Required fields: `id`, `name`, `max_concurrent`, `context_size`
- `max_concurrent` and `context_size` must be integers
- Invalid entries are skipped silently (check the registry with `zai_list_models`)
