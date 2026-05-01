# Spellbook Code Review Style Guide

## Version Bump and Changelog (Required)

Every PR must include:

1. **A version bump in the `.version` file** (which `pyproject.toml` reads via `dynamic = ["version"]`) following semantic versioning:
   - **patch** (0.x.Y): bug fixes, internal refactors, test-only changes
   - **minor** (0.X.0): new features, new MCP tools, new skills/commands, behavioral changes
   - **major** (X.0.0): only when crossing the 1.0 threshold (project is pre-1.0)
2. **A corresponding CHANGELOG.md entry** under an `## Unreleased` or `## [version]` heading describing what changed

**Enforcement rules:**
- The version MUST increment by exactly 1 from the current version on the base branch (no gaps like 0.39.0 to 0.41.0)
- The bump level (patch vs minor) must match the scope of changes in the PR
- If the PR description or a comment says "no version bump needed" or "skip version bump", this requirement is waived

Flag as **high severity** if the version bump or changelog entry is missing. Flag as **medium severity** if the bump level seems incorrect for the scope of changes.

## General Review Focus

- Python code should follow PEP 8 and use type hints
- All MCP tool functions must have `@mcp.tool()` and `@inject_recovery_context` decorators
- Silent `except Exception: pass` blocks should log the exception
- Prefer top-level imports over function-level imports unless there is a circular dependency

## Mocking -- tripwire is the ONLY acceptable framework

**This rule is absolute. There are no substitutes. Do not suggest alternatives.**

The framework is `pytest-tripwire` (formerly `python-tripwire`), imported as `tripwire`. The pyproject configuration section is `[tool.tripwire]`. The earlier `bigfoot` package name and any `bigfoot.*_mock` / `tripwire.*_mock` plugin aliases are no longer used in this repo; flag PRs that reintroduce them.

### Tripwire is a different paradigm, not a drop-in patch replacement

Before flagging or recommending, understand the model. tripwire is NOT "`unittest.mock` with a different import." It is a full-certainty sandbox framework with three guarantees `unittest.mock` does not provide:

1. **Every external call must be pre-authorized** -- unmocked I/O raises `UnmockedInteractionError`
2. **Every recorded interaction must be explicitly asserted** -- forgotten asserts raise `UnassertedInteractionsError` at teardown
3. **Every registered mock must actually fire** -- unused mocks raise `UnusedMocksError` at teardown

The project's `pyproject.toml` sets `guard = "error"`, so any unmocked network / subprocess / DB call fails tests immediately.

### The tripwire flow: register, sandbox, assert

```python
import tripwire

def test_example():
    # 1. REGISTER mocks BEFORE the sandbox
    tripwire.http.mock_response("POST", "https://api.example.com/x",
                               json={"id": "abc"}, status=200)

    # 2. EXECUTE inside the sandbox
    with tripwire:
        result = my_function()

    # 3. ASSERT interactions AFTER the sandbox (REQUIRED)
    tripwire.http.assert_request("POST", "https://api.example.com/x",
                                headers=IsInstance(dict), body=...) \
                .assert_response(200, IsInstance(dict), ...)
```

For async code: `async with tripwire:` instead of `with tripwire:`. The API is otherwise identical.

### What is forbidden in tests

Flag as **high severity** any use of:

- `unittest.mock` in any form: `patch`, `patch.object`, `patch.dict`, `MagicMock`, `AsyncMock`, `Mock`, `NonCallableMock`, `mock_open`, `PropertyMock`, `create_autospec`, `call`, `ANY`, `DEFAULT`, `sentinel`, etc.
- `pytest-mock` / the `mocker` fixture
- `monkeypatch.setattr`, `monkeypatch.setitem`, `monkeypatch.delattr`, `monkeypatch.delitem` -- when used to replace functions, methods, class attributes, or module-level callables (i.e., used as a mocking mechanism)
- Hand-rolled stub classes, fake objects, or `@pytest.fixture` factories that exist solely to stand in for a real dependency
- Any library that patches at the Python import-hook level as a substitute for tripwire

### The correct tripwire APIs

When suggesting a rewrite, use the real API surface. Do NOT invent names.

**General module / attribute mocking:**

- `tripwire.mock("module.path:attribute")` -- colon-separated import path (NOT dotted). Returns a proxy where you call `.returns(value)`, `.raises(exc)`, or `.calls(fn)`. Must be followed by `.assert_call(args=..., kwargs=..., returned=...)` after the sandbox.
- `tripwire.mock.object(obj, "attr_name")` -- patch an attribute on a specific live object.
- `tripwire.spy("module.path:attribute")` -- call the real implementation AND record; still requires assertion.

**Domain plugin proxies** (use these instead of generic `mock(...)` when applicable):

- `tripwire.http` -- httpx, requests, urllib, aiohttp. Methods: `mock_response(method, url, json=..., status=...)`, `mock_error(...)`, `assert_request(...).assert_response(...)`.
- `tripwire.subprocess` -- `subprocess.run`, `shutil.which`. Methods: `mock_run(cmd, returncode=..., stdout=...)`, `assert_run(cmd, ...)`.
- `tripwire.popen` -- `subprocess.Popen`.
- `tripwire.async_subprocess` -- `asyncio.create_subprocess_*`.
- `tripwire.db` -- sqlite3 / generic DB. State-machine plugin with step sentinels `tripwire.db.connect`, `.execute`, `.commit`, `.rollback`, `.close`, and matching assertion methods: `tripwire.db.assert_connect(database=...)`, `.assert_execute(sql=..., parameters=...)`, `.assert_commit()`, `.assert_rollback()`, `.assert_close()`. Transitions: `disconnected -> connected -> in_transaction -> connected -> closed`.
- `tripwire.socket` -- raw socket operations.
- `tripwire.smtp`, `tripwire.redis`, `tripwire.mongo`, `tripwire.boto3`, `tripwire.pika`, `tripwire.ssh`, `tripwire.log`, `tripwire.jwt`, `tripwire.crypto`, `tripwire.file_io`, etc.

**Naming after the python-tripwire 0.20 / pytest-tripwire 0.21 rebrand:** The `_mock` suffix was dropped on domain plugin proxies. Canonical names are now without the suffix (e.g. `tripwire.subprocess`, not `tripwire.subprocess_mock`). The `_mock` aliases are no longer available.

**Do NOT write** `tripwire.subprocess_mock`, `tripwire.db_mock`, `tripwire.log_mock`, `tripwire.popen_mock`, `tripwire.async_subprocess_mock`, `tripwire.socket_mock`, `tripwire.smtp_mock`, `tripwire.redis_mock`, `tripwire.mongo_mock`, `tripwire.boto3_mock`, `tripwire.pika_mock`, `tripwire.ssh_mock`, `tripwire.jwt_mock`, `tripwire.crypto_mock`, `tripwire.file_io_mock` -- those are pre-rebrand aliases that no longer exist. Use `tripwire.subprocess`, `tripwire.db`, `tripwire.log`, etc.

**Do NOT write** `tripwire.database`, `tripwire.mock_patch`, `tripwire.MagicMock`, `tripwire.Mock`, `@tripwire.patch(...)` -- none of these exist.

### The narrow, explicit allowlist for `monkeypatch`

`monkeypatch` (pytest-builtin) is permitted ONLY for:

- `monkeypatch.setenv(...)` / `monkeypatch.delenv(...)` -- environment variables
- `monkeypatch.chdir(...)` -- working directory
- `monkeypatch.syspath_prepend(...)` -- `sys.path` manipulation

Anything else is forbidden. `monkeypatch.setattr` used to replace functions / methods / class attrs / module-level callables is a mocking use and is NOT allowed.

### Review language reviewers MUST NOT use

The following review phrasings are incorrect and will confuse contributors. Do not emit them:

- ❌ "Please use the tripwire testing framework or monkeypatch"
- ❌ "Use tripwire or a pytest-mock alternative"
- ❌ "Consider switching to monkeypatch"
- ❌ "unittest.mock is okay for simple cases"
- ❌ "Use `tripwire.patch(...)`" or "Use `@tripwire.mock` as a decorator" -- these are not real APIs
- "Replace with `tripwire.database`" -- real name is `tripwire.db` (post-rebrand) or the legacy `tripwire.db_mock` (pre-rebrand, no longer valid)
- "Replace with `tripwire.subprocess_mock` / `tripwire.db_mock` / `tripwire.log_mock`" -- those `_mock` aliases were dropped in python-tripwire 0.20 (now pytest-tripwire 0.21+); use `tripwire.subprocess`, `tripwire.db`, `tripwire.log`
- Suggesting tripwire without the surrounding `with tripwire:` sandbox and the post-sandbox `.assert_call(...)` / `.assert_request(...)` -- omitting either step makes the rewrite non-functional

### Correct review language

When flagging a violation, use language that matches the rule and the paradigm:

- ✅ "This uses `unittest.mock.patch`, which is forbidden. Rewrite using tripwire's three-step flow: register a mock (e.g. `m = tripwire.mock(\"<module>:<attr>\"); m.returns(<value>)`), execute under `with tripwire:`, then assert after (`m.assert_call(args=..., kwargs=...)`)."
- ✅ "`monkeypatch.setattr` used to replace a function -- tripwire is required for mocking. Convert to `tripwire.mock(\"<module>:<attr>\").returns(...)` plus `with tripwire:` sandbox plus `.assert_call(...)`. `monkeypatch` is only allowed for env vars, cwd, and sys.path."
- ✅ "`MagicMock` is forbidden. For async code, the flow is the same but use `async with tripwire:` instead of `with tripwire:`."
- ✅ "For HTTP calls, prefer the domain plugin: `tripwire.http.mock_response(method, url, json=..., status=...)` before the sandbox, then `tripwire.http.assert_request(...).assert_response(...)` after."

### Rationale (for your context, not for the review body)

tripwire's three guarantees (pre-authorization, required assertion, required usage) are the reason this project uses it. Suggesting `monkeypatch`, `unittest.mock`, or hand-rolled stubs as substitutes breaks the guarantees and has already caused CI regressions and false-confidence test passes in this repo. Suggesting tripwire APIs that don't exist (`tripwire.patch`, `tripwire.database`, decorator-style usage) wastes contributor time and erodes trust in automated review.
