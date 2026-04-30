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

## Mocking -- bigfoot is the ONLY acceptable framework

**This rule is absolute. There are no substitutes. Do not suggest alternatives.**

### Note on the bigfoot / python-tripwire rebrand

bigfoot 0.21+ is a thin namespace shim that re-exports `python-tripwire`. The framework itself was renamed; the `bigfoot` import name is preserved as a deprecation alias so existing tests keep working. References to "bigfoot" in this guide mean the framework regardless of which package name a contributor types. Two consequences:

1. The canonical pyproject configuration section is `[tool.tripwire]`, NOT `[tool.bigfoot]`. Flag PRs that introduce a `[tool.bigfoot]` section.
2. python-tripwire 0.20+ dropped the `_mock` suffix on most domain plugin proxies. The current canonical names are `bigfoot.subprocess`, `bigfoot.db`, `bigfoot.log`, etc. (see "Domain plugin proxies" below). The pre-rebrand `_mock`-suffixed aliases (`bigfoot.subprocess_mock`, `bigfoot.db_mock`, `bigfoot.log_mock`, ...) are no longer available and code that uses them will fail at attribute lookup.

### Bigfoot is a different paradigm, not a drop-in patch replacement

Before flagging or recommending, understand the model. bigfoot is NOT "`unittest.mock` with a different import." It is a full-certainty sandbox framework with three guarantees `unittest.mock` does not provide:

1. **Every external call must be pre-authorized** -- unmocked I/O raises `UnmockedInteractionError`
2. **Every recorded interaction must be explicitly asserted** -- forgotten asserts raise `UnassertedInteractionsError` at teardown
3. **Every registered mock must actually fire** -- unused mocks raise `UnusedMocksError` at teardown

The project's `pyproject.toml` sets `guard = "error"`, so any unmocked network / subprocess / DB call fails tests immediately.

### The bigfoot flow: register, sandbox, assert

```python
import bigfoot

def test_example():
    # 1. REGISTER mocks BEFORE the sandbox
    bigfoot.http.mock_response("POST", "https://api.example.com/x",
                               json={"id": "abc"}, status=200)

    # 2. EXECUTE inside the sandbox
    with bigfoot:
        result = my_function()

    # 3. ASSERT interactions AFTER the sandbox (REQUIRED)
    bigfoot.http.assert_request("POST", "https://api.example.com/x",
                                headers=IsInstance(dict), body=...) \
                .assert_response(200, IsInstance(dict), ...)
```

For async code: `async with bigfoot:` instead of `with bigfoot:`. The API is otherwise identical.

### What is forbidden in tests

Flag as **high severity** any use of:

- `unittest.mock` in any form: `patch`, `patch.object`, `patch.dict`, `MagicMock`, `AsyncMock`, `Mock`, `NonCallableMock`, `mock_open`, `PropertyMock`, `create_autospec`, `call`, `ANY`, `DEFAULT`, `sentinel`, etc.
- `pytest-mock` / the `mocker` fixture
- `monkeypatch.setattr`, `monkeypatch.setitem`, `monkeypatch.delattr`, `monkeypatch.delitem` -- when used to replace functions, methods, class attributes, or module-level callables (i.e., used as a mocking mechanism)
- Hand-rolled stub classes, fake objects, or `@pytest.fixture` factories that exist solely to stand in for a real dependency
- Any library that patches at the Python import-hook level as a substitute for bigfoot

### The correct bigfoot APIs

When suggesting a rewrite, use the real API surface. Do NOT invent names.

**General module / attribute mocking:**

- `bigfoot.mock("module.path:attribute")` -- colon-separated import path (NOT dotted). Returns a proxy where you call `.returns(value)`, `.raises(exc)`, or `.calls(fn)`. Must be followed by `.assert_call(args=..., kwargs=..., returned=...)` after the sandbox.
- `bigfoot.mock.object(obj, "attr_name")` -- patch an attribute on a specific live object.
- `bigfoot.spy("module.path:attribute")` -- call the real implementation AND record; still requires assertion.

**Domain plugin proxies** (use these instead of generic `mock(...)` when applicable):

- `bigfoot.http` -- httpx, requests, urllib, aiohttp. Methods: `mock_response(method, url, json=..., status=...)`, `mock_error(...)`, `assert_request(...).assert_response(...)`.
- `bigfoot.subprocess` -- `subprocess.run`, `shutil.which`. Methods: `mock_run(cmd, returncode=..., stdout=...)`, `assert_run(cmd, ...)`.
- `bigfoot.popen` -- `subprocess.Popen`.
- `bigfoot.async_subprocess` -- `asyncio.create_subprocess_*`.
- `bigfoot.db` -- sqlite3 / generic DB. State-machine plugin with step sentinels `bigfoot.db.connect`, `.execute`, `.commit`, `.rollback`, `.close`, and matching assertion methods: `bigfoot.db.assert_connect(database=...)`, `.assert_execute(sql=..., parameters=...)`, `.assert_commit()`, `.assert_rollback()`, `.assert_close()`. Transitions: `disconnected -> connected -> in_transaction -> connected -> closed`.
- `bigfoot.socket` -- raw socket operations.
- `bigfoot.smtp`, `bigfoot.redis`, `bigfoot.mongo`, `bigfoot.boto3`, `bigfoot.pika`, `bigfoot.ssh`, `bigfoot.log`, `bigfoot.jwt`, `bigfoot.crypto`, `bigfoot.file_io`, etc.

**Naming after the python-tripwire 0.20+ rebrand:** The `_mock` suffix was dropped on domain plugin proxies. Canonical names are now without the suffix (e.g. `bigfoot.subprocess`, not `bigfoot.subprocess_mock`). The `_mock` aliases are no longer available.

**Do NOT write** `bigfoot.subprocess_mock`, `bigfoot.db_mock`, `bigfoot.log_mock`, `bigfoot.popen_mock`, `bigfoot.async_subprocess_mock`, `bigfoot.socket_mock`, `bigfoot.smtp_mock`, `bigfoot.redis_mock`, `bigfoot.mongo_mock`, `bigfoot.boto3_mock`, `bigfoot.pika_mock`, `bigfoot.ssh_mock`, `bigfoot.jwt_mock`, `bigfoot.crypto_mock`, `bigfoot.file_io_mock` -- those are pre-rebrand aliases that no longer exist. Use `bigfoot.subprocess`, `bigfoot.db`, `bigfoot.log`, etc.

**Do NOT write** `bigfoot.database`, `bigfoot.mock_patch`, `bigfoot.MagicMock`, `bigfoot.Mock`, `@bigfoot.patch(...)` -- none of these exist.

### The narrow, explicit allowlist for `monkeypatch`

`monkeypatch` (pytest-builtin) is permitted ONLY for:

- `monkeypatch.setenv(...)` / `monkeypatch.delenv(...)` -- environment variables
- `monkeypatch.chdir(...)` -- working directory
- `monkeypatch.syspath_prepend(...)` -- `sys.path` manipulation

Anything else is forbidden. `monkeypatch.setattr` used to replace functions / methods / class attrs / module-level callables is a mocking use and is NOT allowed.

### Review language reviewers MUST NOT use

The following review phrasings are incorrect and will confuse contributors. Do not emit them:

- ❌ "Please use the bigfoot testing framework or monkeypatch"
- ❌ "Use bigfoot or a pytest-mock alternative"
- ❌ "Consider switching to monkeypatch"
- ❌ "unittest.mock is okay for simple cases"
- ❌ "Use `bigfoot.patch(...)`" or "Use `@bigfoot.mock` as a decorator" -- these are not real APIs
- "Replace with `bigfoot.database`" -- real name is `bigfoot.db` (post-rebrand) or the legacy `bigfoot.db_mock` (pre-rebrand, no longer valid)
- "Replace with `bigfoot.subprocess_mock` / `bigfoot.db_mock` / `bigfoot.log_mock`" -- those `_mock` aliases were dropped in python-tripwire 0.20+; use `bigfoot.subprocess`, `bigfoot.db`, `bigfoot.log`
- Suggesting bigfoot without the surrounding `with bigfoot:` sandbox and the post-sandbox `.assert_call(...)` / `.assert_request(...)` -- omitting either step makes the rewrite non-functional

### Correct review language

When flagging a violation, use language that matches the rule and the paradigm:

- ✅ "This uses `unittest.mock.patch`, which is forbidden. Rewrite using bigfoot's three-step flow: register a mock (e.g. `m = bigfoot.mock(\"<module>:<attr>\"); m.returns(<value>)`), execute under `with bigfoot:`, then assert after (`m.assert_call(args=..., kwargs=...)`)."
- ✅ "`monkeypatch.setattr` used to replace a function -- bigfoot is required for mocking. Convert to `bigfoot.mock(\"<module>:<attr>\").returns(...)` plus `with bigfoot:` sandbox plus `.assert_call(...)`. `monkeypatch` is only allowed for env vars, cwd, and sys.path."
- ✅ "`MagicMock` is forbidden. For async code, the flow is the same but use `async with bigfoot:` instead of `with bigfoot:`."
- ✅ "For HTTP calls, prefer the domain plugin: `bigfoot.http.mock_response(method, url, json=..., status=...)` before the sandbox, then `bigfoot.http.assert_request(...).assert_response(...)` after."

### Rationale (for your context, not for the review body)

bigfoot's three guarantees (pre-authorization, required assertion, required usage) are the reason this project uses it. Suggesting `monkeypatch`, `unittest.mock`, or hand-rolled stubs as substitutes breaks the guarantees and has already caused CI regressions and false-confidence test passes in this repo. Suggesting bigfoot APIs that don't exist (`bigfoot.patch`, `bigfoot.database`, decorator-style usage) wastes contributor time and erodes trust in automated review.
