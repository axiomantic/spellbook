# Canvas, Worker-LLM, and TTS Removal Summary

## Deleted Directories
- `spellbook/canvas/` (entire directory: store.py, decision_contract.py, __init__.py)
- `spellbook/worker_llm/` (entire directory: 11 files + tasks/ subdir + default_prompts/)

## Deleted Files
- `spellbook/mcp/tools/canvas.py`
- `spellbook/cli/commands/worker_llm.py`
- `installer/wizards/worker_llm.py`

## Modified Files

### CANVAS Removal
- `spellbook/mcp/tools/__init__.py` — removed `canvas` from imports
- `spellbook/events.py` — removed `CANVAS` subsystem enum value and all `CANVAS_*` event constants

### WORKER_LLM Removal
- `spellbook/mcp/server.py` — removed `close_all_shared_clients_sync()` call in shutdown
- `spellbook/mcp/routes.py` — removed `/api/worker-llm/enqueue` route, `_resolve_task_callback`, worker_llm event publish block in `/api/events/publish`; replaced `_spawn_background` with `asyncio.get_running_loop().run_in_executor()` in hooks/record route
- `spellbook/core/config.py` — removed all 23 `worker_llm_*` config keys and comments
- `spellbook/db/spellbook_models.py` — removed `WorkerLLMCall` model (table `worker_llm_calls`)
- `spellbook/events.py` — removed `WORKER_LLM` subsystem enum value
- `spellbook/cli/main.py` — removed `worker_llm` command registration
- `spellbook/cli/commands/install.py` — removed `run_worker_llm_wizard` imports, calls, and backward-compat shim
- `spellbook/cli/daemon_client.py` — inlined `build_host_url` function (was imported from deleted `spellbook.worker_llm.net`)
- `spellbook/mcp/tools/forged.py` — removed `forge_roundtable_convene_local` MCP tool (depended on worker_llm roundtable feature)
- `spellbook/hooks/__init__.py` — updated comment referencing worker_llm
- `spellbook/hooks/observability.py` — updated 5 comments referencing worker_llm
- `install.py` — removed `run_worker_llm_wizard` imports and calls (2 occurrences)
- `installer/wizards/__init__.py` — removed `run_worker_llm_wizard` import and `__all__` entry

### TTS Removal
- `spellbook/core/config.py` — updated docstring to remove tts reference
- `spellbook/core/state.py` — removed `tts_enabled` and `tts_volume` from `_DEAD_CONFIG_KEYS`; updated comments
- `installer/components/hooks.py` — removed 7 tts references from comments/strings
- `installer/renderer.py` — removed TTS reference from comment
- `scripts/migrate_imports.py` — removed `spellbook.notifications.tts` line

## Not Modified (no references found)
- `spellbook/core/db.py` — no canvas or worker_llm references found
- `installer/core.py` — no worker_llm references found
- `pyproject.toml` — no canvas or worker_llm references found
