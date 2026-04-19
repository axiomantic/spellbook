"""Execute a roundtable dialogue locally against the worker LLM.

Thin async passthrough: load the ``roundtable_voice`` system prompt, call
the OpenAI-compat endpoint with a 2048-token ceiling, and return the raw
string. The caller (``spellbook.mcp.tools.forged.forge_roundtable_convene_local``)
feeds the raw text to ``process_roundtable_response`` for voice/verdict
parsing.

**Async by design.** The MCP tool that calls this function runs inside a
FastMCP-owned event loop; a sync wrapper would internally call
``asyncio.run(...)`` and raise ``RuntimeError: asyncio.run() cannot be
called from a running event loop``. We expose the async primitive so the
MCP wrapper can simply ``await`` it. Stop-hook / CLI callers that need a
sync entry point can wrap this with ``asyncio.run`` themselves.

**max_tokens=2048 (per design §6.3 amendment).** The default
``worker_llm_max_tokens`` (1024) truncates multi-archetype roundtable
output. This task always sends a 2048-token ceiling at the call site; it
is a structural requirement of the format, not a taste knob, so it is
not a separate config key.

See design doc §2.7, §6.3, §5.4 and impl plan Task C3.
"""

from __future__ import annotations

from spellbook.worker_llm import client, prompts


async def roundtable_voice(dialogue_prompt: str) -> str:
    """Execute a roundtable dialogue and return the raw string.

    Args:
        dialogue_prompt: The dialogue scaffolding produced by
            ``roundtable_convene`` (archetype list + instructions).

    Returns:
        Raw assistant text. Voice parsing is the caller's responsibility.

    Raises:
        WorkerLLMTimeout, WorkerLLMUnreachable, WorkerLLMBadResponse,
        WorkerLLMNotConfigured: Propagated unchanged from ``client.call``;
            the MCP wrapper renders these as ``<worker-llm-error>`` blocks
            so the orchestrator can fall back to local execution.
    """
    system, override = prompts.load("roundtable_voice")
    return await client.call(
        system_prompt=system,
        user_prompt=dialogue_prompt,
        max_tokens=2048,
        task="roundtable_voice",
        override_loaded=override,
    )
