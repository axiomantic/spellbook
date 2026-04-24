"""Hook observability infrastructure.

In-daemon helpers that persist hook dispatcher events into the
``hook_events`` table. Mirrors ``spellbook.worker_llm.observability`` for
subprocess hook runs (``hooks/spellbook_hook.py``), which re-enter the
daemon via ``POST /api/hooks/record`` because they have no event loop.
"""
