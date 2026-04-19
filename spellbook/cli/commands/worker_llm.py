"""``spellbook worker-llm`` commands.

Subcommands:
  doctor    Smoke-test each of the 4 worker-LLM tasks against the configured
            endpoint and report per-task status. Also surfaces active prompt
            overrides, safety-cache state, and feature-flag state.

Exit codes (doctor):
  0  All 4 tasks succeeded, config valid.
  1  Endpoint not configured (``worker_llm_base_url`` or ``worker_llm_model``
     empty).
  2  Endpoint configured but at least one task failed OR a preflight check
     (prompt load, cache touch) failed.

Design reference: worker_llm-design.md §10.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register ``worker-llm`` and its subcommands."""
    parser = subparsers.add_parser(
        "worker-llm",
        help="Worker LLM utilities",
        description="Utilities for the optional worker LLM integration.",
    )
    sub = parser.add_subparsers(dest="worker_llm_subcommand")

    doctor_p = sub.add_parser(
        "doctor",
        help="Smoke-test all 4 worker-LLM tasks against the configured endpoint.",
        description=(
            "Run one call per configured task against the worker LLM endpoint; "
            "report prompt overrides, safety cache state, feature flags, and "
            "daemon reachability. Exit 0 on green, 1 on missing config, 2 on "
            "task or preflight failure."
        ),
    )
    doctor_p.add_argument(
        "--json",
        dest="json",
        action="store_true",
        help="Emit JSON output instead of the human-readable table.",
    )
    doctor_p.add_argument(
        "--bench",
        choices=[
            "tool_safety",
            "transcript_harvest",
            "memory_rerank",
            "roundtable_voice",
        ],
        default=None,
        help="Run N back-to-back calls of a single task and report p50/p95/p99.",
    )
    doctor_p.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of runs for --bench (default: 10).",
    )
    doctor_p.add_argument(
        "--roundtable-sample",
        dest="roundtable_sample",
        type=int,
        nargs="?",
        const=10,
        default=None,
        help=(
            "Run N canned roundtable prompts (default 10) and report "
            "ABSTAIN rate + per-voice verdict breakdown."
        ),
    )
    doctor_p.set_defaults(func=_run_doctor)

    # Parent ``worker-llm`` with no subcommand prints help.
    parser.set_defaults(func=_print_help(parser))


def _print_help(parser: argparse.ArgumentParser):
    def _func(args: argparse.Namespace) -> None:
        if not getattr(args, "worker_llm_subcommand", None):
            parser.print_help()
    return _func


# ---------------------------------------------------------------------------
# Canned task payloads
# ---------------------------------------------------------------------------


def _canned_tasks() -> list[tuple[str, Any]]:
    """Build the (name, callable) pairs the doctor exercises.

    Kept as a function so imports happen lazily — keeps CLI startup fast when
    ``--help`` or unrelated subcommands run.
    """
    from spellbook.worker_llm.tasks import memory_rerank as T_rerank
    from spellbook.worker_llm.tasks import roundtable as T_round
    from spellbook.worker_llm.tasks import tool_safety as T_safety
    from spellbook.worker_llm.tasks import transcript_harvest as T_harvest

    def _roundtable_sync():
        # ``roundtable_voice`` is async by design (the MCP path is inside a
        # FastMCP event loop). The doctor is a plain sync CLI with no loop
        # of its own, so wrap with asyncio.run here. Documented deviation
        # from design §10.1 body which invoked the coroutine without
        # awaiting — that would silently succeed with a coroutine object.
        return asyncio.run(
            T_round.roundtable_voice(
                "**Magician**: Analyze the following artifact.\n\n"
                "<artifact>\nhello\n</artifact>\n\n"
                "End with 'Verdict: APPROVE' or 'Verdict: ITERATE'."
            )
        )

    return [
        (
            "transcript_harvest",
            lambda: T_harvest.transcript_harvest(
                "User preference: always run tests before committing.\n"
                "Why: avoids broken main.\nHow to apply: add a pre-commit hook."
            ),
        ),
        (
            "memory_rerank",
            lambda: T_rerank.memory_rerank(
                "how does stop-hook dedup work",
                [
                    {
                        "id": "a.md",
                        "excerpt": "Stop hook uses SHA256 content-hash dedup.",
                    },
                    {
                        "id": "b.md",
                        "excerpt": "Unrelated memory about git worktrees.",
                    },
                ],
            ),
        ),
        ("roundtable_voice", _roundtable_sync),
        (
            "tool_safety",
            lambda: T_safety.tool_safety(
                "Bash", {"command": "ls -la"}, "user asked to list files"
            ),
        ),
    ]


def _detect_overrides() -> list[str]:
    """Return sorted task names that have an override file on disk.

    Reads the override directory lazily so we do not touch the home dir
    from module import time.
    """
    from spellbook.worker_llm import prompts as _prompts

    override_dir = _prompts.OVERRIDE_PROMPT_DIR
    if not override_dir.exists():
        return []
    known = ("transcript_harvest", "memory_rerank", "roundtable_voice", "tool_safety")
    found = []
    for name in known:
        if (override_dir / f"{name}.md").exists():
            found.append(name)
    return sorted(found)


def _safety_cache_report() -> dict:
    """Report on the on-disk safety cache.

    Returns a small dict: ``{exists, path, size_bytes, verdicts, blocks}``.
    On any read failure we report ``exists=True`` but ``error=<str>`` so the
    operator can see the problem without the doctor crashing.
    """
    from spellbook.worker_llm import safety_cache

    path = safety_cache.CACHE_PATH
    if not path.exists():
        return {"exists": False, "path": str(path)}
    try:
        size = path.stat().st_size
        raw = json.loads(path.read_text(encoding="utf-8"))
        verdicts = len(raw.get("verdicts") or {})
        blocks = len(raw.get("blocks") or {})
        return {
            "exists": True,
            "path": str(path),
            "size_bytes": size,
            "verdicts": verdicts,
            "blocks": blocks,
        }
    except (OSError, json.JSONDecodeError) as e:
        return {
            "exists": True,
            "path": str(path),
            "error": f"{type(e).__name__}: {e}",
        }


def _feature_flags_state() -> dict:
    """Snapshot the 4 feature flags."""
    from spellbook.worker_llm.config import get_worker_config

    cfg = get_worker_config()
    return {
        "transcript_harvest": bool(cfg.feature_transcript_harvest),
        "tool_safety": bool(cfg.feature_tool_safety),
        "memory_rerank": bool(cfg.feature_memory_rerank),
        "roundtable": bool(cfg.feature_roundtable),
        "read_claude_memory": bool(cfg.read_claude_memory),
    }


def _daemon_reachable(timeout: float = 1.0) -> dict:
    """Probe the daemon's ``/api/events/publish`` endpoint with an empty event.

    Uses the same host/port discovery as ``spellbook.worker_llm.events``
    (``SPELLBOOK_MCP_HOST``/``SPELLBOOK_MCP_PORT`` with 127.0.0.1:8765 defaults).
    Swallows all errors and reports them in the returned dict — probing the
    daemon must never crash the doctor.
    """
    import os
    import urllib.error
    import urllib.request
    from pathlib import Path

    host = os.environ.get("SPELLBOOK_MCP_HOST", "127.0.0.1")
    port = os.environ.get("SPELLBOOK_MCP_PORT", "8765")
    url = f"http://{host}:{port}/api/events/publish"
    token_path = Path.home() / ".local" / "spellbook" / ".mcp-token"
    headers = {"Content-Type": "application/json"}
    try:
        if token_path.exists():
            tok = token_path.read_text().strip()
            if tok:
                headers["Authorization"] = f"Bearer {tok}"
    except OSError:
        pass

    payload = json.dumps(
        {
            "subsystem": "worker_llm",
            "event_type": "doctor_probe",
            "data": {"source": "doctor"},
        }
    ).encode()
    req = urllib.request.Request(
        url, data=payload, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
        return {"url": url, "reachable": True, "status": status}
    except urllib.error.HTTPError as e:
        # Auth (401) or similar — the daemon IS running, just rejected us.
        # Still report reachable=True because the TCP/HTTP layer worked.
        return {
            "url": url,
            "reachable": True,
            "status": e.code,
            "note": f"HTTP {e.code} {e.reason}",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "url": url,
            "reachable": False,
            "error": f"{type(e).__name__}: {e}",
        }


# ---------------------------------------------------------------------------
# Doctor entry point
# ---------------------------------------------------------------------------


def _run_doctor(args: argparse.Namespace) -> None:
    """Execute ``spellbook worker-llm doctor``."""
    from spellbook.worker_llm import errors as E
    from spellbook.worker_llm.config import get_worker_config, is_configured

    json_mode = bool(getattr(args, "json", False))
    cfg = get_worker_config()

    # 1) Config check
    if not json_mode:
        print(
            f"Worker LLM endpoint: base_url={cfg.base_url!r} model={cfg.model!r}"
        )
    if not is_configured(cfg):
        msg = (
            "ERROR: worker_llm_base_url or worker_llm_model is not set. "
            "Run `spellbook install --reconfigure` or edit ~/.config/spellbook/"
            "spellbook.json."
        )
        print(msg, file=sys.stderr)
        if json_mode:
            # Still emit a JSON error envelope on stdout so programmatic
            # callers do not have to parse stderr.
            print(
                json.dumps(
                    {
                        "endpoint": cfg.base_url,
                        "model": cfg.model,
                        "error": "not_configured",
                    }
                )
            )
        sys.exit(1)

    # Branch: --bench mode
    bench_task = getattr(args, "bench", None)
    if bench_task:
        _run_bench(cfg, bench_task, max(1, int(getattr(args, "runs", 10) or 10)), json_mode)
        return

    # Branch: --roundtable-sample mode
    sample_n = getattr(args, "roundtable_sample", None)
    if sample_n is not None:
        _run_roundtable_sample(cfg, max(1, int(sample_n)), json_mode)
        return

    # Default: run 4 canned tasks
    tasks = _canned_tasks()
    results: list[dict] = []
    failures = 0
    for name, fn in tasks:
        entry: dict = {"task": name, "ok": False}
        try:
            result = fn()
            entry["ok"] = True
            entry["result_preview"] = _preview(result)
        except E.WorkerLLMError as e:
            failures += 1
            entry["error"] = f"{type(e).__name__}: {e}"
        except Exception as e:  # noqa: BLE001
            failures += 1
            entry["error"] = f"unexpected: {type(e).__name__}: {e}"
        results.append(entry)

    overrides = _detect_overrides()
    cache = _safety_cache_report()
    flags = _feature_flags_state()
    daemon = _daemon_reachable()

    if json_mode:
        print(
            json.dumps(
                {
                    "endpoint": cfg.base_url,
                    "model": cfg.model,
                    "results": results,
                    "overrides": overrides,
                    "safety_cache": cache,
                    "feature_flags": flags,
                    "daemon": daemon,
                },
                indent=2,
            )
        )
    else:
        for r in results:
            status = "OK  " if r["ok"] else "FAIL"
            extra = r.get("result_preview") if r["ok"] else r.get("error", "")
            print(f"  [{status}] {r['task']}: {extra}")
        print()
        if overrides:
            print(f"Prompt overrides active: {', '.join(overrides)}")
        else:
            print("Prompt overrides: none (using packaged defaults)")
        if cache.get("exists"):
            if "error" in cache:
                print(
                    f"Safety cache: present but unreadable ({cache['error']}) "
                    f"at {cache['path']}"
                )
            else:
                print(
                    f"Safety cache: {cache['size_bytes']} bytes, "
                    f"{cache['verdicts']} verdicts, {cache['blocks']} blocks"
                )
        else:
            print("Safety cache: no cache (will create on first block)")
        flags_rendered = ", ".join(
            f"{k}={'on' if v else 'off'}" for k, v in flags.items()
        )
        print(f"Feature flags: {flags_rendered}")
        if daemon.get("reachable"):
            note = daemon.get("note") or f"HTTP {daemon.get('status')}"
            print(f"Daemon: reachable at {daemon['url']} ({note})")
        else:
            print(
                f"Daemon: unreachable at {daemon['url']} "
                f"({daemon.get('error', 'unknown')})"
            )

    sys.exit(2 if failures else 0)


# ---------------------------------------------------------------------------
# --bench and --roundtable-sample implementations
# ---------------------------------------------------------------------------


def _run_bench(cfg, task: str, runs: int, json_mode: bool) -> None:
    """Run ``runs`` calls of a single task and emit percentile stats."""
    from spellbook.worker_llm import errors as E

    tasks = dict(_canned_tasks())
    if task not in tasks:
        print(f"Unknown bench task: {task}", file=sys.stderr)
        sys.exit(2)
    fn = tasks[task]

    durations_ms: list[int] = []
    errors: list[str] = []
    ok = 0
    for _ in range(runs):
        t0 = time.monotonic()
        try:
            fn()
            ok += 1
        except E.WorkerLLMError as e:
            errors.append(f"{type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"unexpected: {type(e).__name__}: {e}")
        finally:
            durations_ms.append(int((time.monotonic() - t0) * 1000))

    p50, p95, p99 = _percentiles(durations_ms, (50, 95, 99))
    payload = {
        "endpoint": cfg.base_url,
        "model": cfg.model,
        "bench": {
            "task": task,
            "runs": runs,
            "ok": ok,
            "failures": runs - ok,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "errors": errors[:10],
        },
    }
    if json_mode:
        print(json.dumps(payload, indent=2))
    else:
        b = payload["bench"]
        print(
            f"bench {task}: runs={b['runs']} ok={b['ok']} "
            f"failures={b['failures']} p50={b['p50_ms']}ms "
            f"p95={b['p95_ms']}ms p99={b['p99_ms']}ms"
        )
        for err in b["errors"]:
            print(f"  error: {err}")
    sys.exit(2 if errors else 0)


def _run_roundtable_sample(cfg, n: int, json_mode: bool) -> None:
    """Run ``n`` canned roundtable prompts and tally voice verdicts.

    Parser choice: uses a lightweight regex ``Verdict:\\s*(APPROVE|ITERATE|ABSTAIN)``
    rather than delegating to ``spellbook.mcp.tools.forged.process_roundtable_response``
    because the MCP parser is an ``async def`` coupled to a running FastMCP
    subagent handle that the CLI does not possess. The regex is deliberately
    permissive: any well-behaved roundtable voice ends with one of these three
    verdict markers.
    """
    import re

    from spellbook.worker_llm.tasks import roundtable as T_round

    verdict_re = re.compile(r"Verdict:\s*(APPROVE|ITERATE|ABSTAIN)", re.IGNORECASE)
    voice_re = re.compile(
        r"\*\*(Magician|Priestess|Fool|Emperor|Empress|Hierophant|Hermit)\*\*",
        re.IGNORECASE,
    )

    per_voice: dict[str, dict[str, int]] = {}
    last_verdicts: dict[str, str] = {}
    abstains = 0
    total_voices = 0
    errors: list[str] = []

    prompt = (
        "**Magician**: Analyze this simple artifact.\n\n"
        "<artifact>\nhello world\n</artifact>\n\n"
        "End with 'Verdict: APPROVE' or 'Verdict: ITERATE' or 'Verdict: ABSTAIN'."
    )

    for _ in range(n):
        try:
            raw = asyncio.run(T_round.roundtable_voice(prompt))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{type(e).__name__}: {e}")
            continue

        voices = voice_re.findall(raw) or ["magician"]
        verdicts = verdict_re.findall(raw)
        run_verdicts: dict[str, str] = {}
        for voice, verdict in zip(
            (v.lower() for v in voices), (v.upper() for v in verdicts)
        ):
            per_voice.setdefault(
                voice, {"APPROVE": 0, "ITERATE": 0, "ABSTAIN": 0}
            )
            per_voice[voice][verdict] = per_voice[voice].get(verdict, 0) + 1
            if verdict == "ABSTAIN":
                abstains += 1
            total_voices += 1
            run_verdicts[voice] = verdict
        last_verdicts = run_verdicts or last_verdicts

    abstain_rate = (abstains / total_voices) if total_voices else 0.0
    payload = {
        "endpoint": cfg.base_url,
        "model": cfg.model,
        "roundtable_sample": {
            "runs": n,
            "abstain_rate": round(abstain_rate, 3),
            "per_voice": per_voice,
            "last_run_verdicts": last_verdicts,
            "errors": errors[:10],
        },
    }
    if json_mode:
        print(json.dumps(payload, indent=2))
    else:
        rs = payload["roundtable_sample"]
        print(
            f"roundtable-sample: runs={rs['runs']} "
            f"abstain_rate={rs['abstain_rate']}"
        )
        for voice, breakdown in rs["per_voice"].items():
            print(f"  {voice}: {breakdown}")
        for err in rs["errors"]:
            print(f"  error: {err}")
    sys.exit(2 if errors else 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _preview(obj: Any) -> str:
    s = repr(obj)
    return s[:200] + ("..." if len(s) > 200 else "")


def _percentiles(
    samples: list[int], percentiles: tuple[int, ...]
) -> tuple[int, ...]:
    """Return the nearest-rank percentile for each value in ``percentiles``.

    Nearest-rank is the right choice for small-N latency stats: no
    interpolation fuzz, and ``p100`` of 3 samples is the max itself.
    """
    if not samples:
        return tuple(0 for _ in percentiles)
    ordered = sorted(samples)
    n = len(ordered)
    out = []
    for p in percentiles:
        # rank = ceil(p/100 * n); clamp to [1, n]
        rank = max(1, min(n, -(-p * n // 100)))
        out.append(ordered[rank - 1])
    return tuple(out)
