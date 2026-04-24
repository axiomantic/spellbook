"""Port probe for local OpenAI-compatible endpoints.

Used by the installer wizard and ``spellbook worker-llm doctor`` to enumerate
locally-running inference servers. Probes happen concurrently within a total
time budget so the installer never blocks for more than a second or two even
when a port is black-holed.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import httpx

COMMON_PORTS: list[tuple[int, str]] = [
    (11434, "Ollama"),
    (1234,  "LM Studio"),
    (8080,  "llama.cpp/mlx"),
    (8000,  "vLLM"),
    (4000,  "LiteLLM"),
]


@dataclass
class DetectedEndpoint:
    base_url: str
    label: str
    models: list[str] = field(default_factory=list)
    reachable: bool = False
    error: str | None = None


async def _probe_one(port: int, label: str, timeout_s: float) -> DetectedEndpoint:
    """Probe a single ``localhost:<port>/v1/models`` endpoint."""
    base_url = f"http://localhost:{port}/v1"
    ep = DetectedEndpoint(base_url=base_url, label=label)
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as http:
            r = await http.get(f"{base_url}/models")
        if r.status_code != 200:
            ep.error = f"HTTP {r.status_code}"
            return ep
        data = r.json()
        ep.reachable = True
        ep.models = [
            m.get("id", "") for m in data.get("data", []) if m.get("id")
        ]
    except Exception as e:
        ep.error = f"{type(e).__name__}: {e}"
    return ep


async def probe_all(timeout_total_s: float = 2.0) -> list[DetectedEndpoint]:
    """Probe common local ports concurrently within a total time budget.

    Returns only reachable endpoints. Each endpoint's ``models`` list is
    populated from the ``/v1/models`` response.
    """
    per_call = max(0.3, timeout_total_s / len(COMMON_PORTS))
    tasks = [_probe_one(p, lbl, per_call) for p, lbl in COMMON_PORTS]
    results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=False),
        timeout=timeout_total_s + 0.2,
    )
    return [ep for ep in results if ep.reachable]
