"""Worker-LLM task implementations.

Each task module owns its own prompt loading, client invocation, and parse
logic. Tasks raise ``WorkerLLMBadResponse`` on malformed output; callers
decide fail-open vs surface-error policy per-integration.
"""
