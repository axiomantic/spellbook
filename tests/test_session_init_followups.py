"""Tests for open Follow-up-Tasks count surfacing in session_init (Task 20, §7.4).

session_init runs a count-only memory_recall(tags="follow-up-task") scoped to the
project and, when the count is > 0, includes an additive `follow_up_tasks_open`
field plus a one-line greeting note. Absent/zero is backward-compatible: no field,
no note.

TDD RED phase: written before the implementation exists.
"""

import datetime
import hashlib
import os

import tripwire
import yaml

from tests._memory_marker import requires_memory_tools


# ---------------------------------------------------------------------------
# Helpers (mirror tests/test_memory_tools_integration.py seeding)
# ---------------------------------------------------------------------------


def _content_hash(content: str) -> str:
    """Mirror the content hash logic used by filestore."""
    normalized = " ".join(content.lower().split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _write_memory_file(path: str, type_: str, content: str, **extra_fm):
    """Write a minimal memory file for test setup."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fm = {
        "type": type_,
        "created": datetime.date(2026, 5, 24),
        "content_hash": _content_hash(content),
    }
    fm.update(extra_fm)
    yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    with open(path, "w") as f:
        f.write(f"---\n{yaml_str}---\n\n{content}\n")


# ---------------------------------------------------------------------------
# _get_open_followup_count: real seeded-data count
# ---------------------------------------------------------------------------


@requires_memory_tools
class TestGetOpenFollowupCount:
    """_get_open_followup_count returns the exact count of follow-up-task memories."""

    def test_counts_two_seeded_followups(self, tmp_path, monkeypatch):
        """Two follow-up-task memories -> count is exactly 2."""
        from spellbook.core.config import _get_open_followup_count

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        _write_memory_file(
            os.path.join(memory_dir, "project", "fut-tdd-criteria.md"),
            type_="project",
            content="Follow-up: define precise checkable criteria for waiving TDD-first",
            kind="decision",
            tags=["follow-up-task", "develop-deferred"],
        )
        _write_memory_file(
            os.path.join(memory_dir, "project", "fut-second.md"),
            type_="project",
            content="Follow-up: revisit the blocker option annotation wording in develop",
            kind="decision",
            tags=["follow-up-task", "develop-deferred"],
        )
        # A non-follow-up memory must NOT be counted.
        _write_memory_file(
            os.path.join(memory_dir, "project", "unrelated-fact.md"),
            type_="project",
            content="The config module reads spellbook.json with fallback defaults",
            kind="fact",
            tags=["config"],
        )

        assert _get_open_followup_count("/Users/test/proj") == 2

    def test_zero_when_none_seeded(self, tmp_path, monkeypatch):
        """No follow-up-task memories -> count is exactly 0."""
        from spellbook.core.config import _get_open_followup_count

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        _write_memory_file(
            os.path.join(memory_dir, "project", "unrelated-fact.md"),
            type_="project",
            content="The scoring system uses BM25 with temporal decay and branch multiplier",
            kind="fact",
            tags=["scoring"],
        )

        assert _get_open_followup_count("/Users/test/proj") == 0


class TestGetOpenFollowupCountFailOpen:
    """_get_open_followup_count fails open to 0 on any error (no real memory tools)."""

    def test_returns_zero_when_project_path_none(self):
        """None project_path -> 0 (no recall attempted)."""
        from spellbook.core.config import _get_open_followup_count

        assert _get_open_followup_count(None) == 0

    def test_returns_zero_on_recall_exception(self, monkeypatch):
        """do_memory_recall raising -> fail-open 0."""
        from spellbook.core.config import _get_open_followup_count

        def _boom(**kwargs):
            raise RuntimeError("memory backend down")

        monkeypatch.setattr("spellbook.memory.tools.do_memory_recall", _boom)

        assert _get_open_followup_count("/Users/test/proj") == 0

    def test_returns_zero_when_recall_reports_unavailable(self, monkeypatch):
        """do_memory_recall returning an error/unavailable dict -> 0 (no count key)."""
        from spellbook.core.config import _get_open_followup_count

        monkeypatch.setattr(
            "spellbook.memory.tools.do_memory_recall",
            lambda **kwargs: {"error": "memory system unavailable", "status": "unavailable"},
        )

        assert _get_open_followup_count("/Users/test/proj") == 0

    def test_passes_followup_tag_and_encoded_namespace(self, monkeypatch):
        """Helper queries the follow-up-task tag with the encoded project namespace."""
        from spellbook.core.config import _get_open_followup_count

        recorded: dict = {}

        def _spy(**kwargs):
            recorded.update(kwargs)
            return {"memories": [], "count": 3, "query": "", "namespace": "x"}

        monkeypatch.setattr("spellbook.memory.tools.do_memory_recall", _spy)

        result = _get_open_followup_count("/Users/alice/project")

        assert result == 3
        assert recorded == {
            "query": "",
            "namespace": "Users-alice-project",
            "tags": ["follow-up-task"],
            "scope": "project",
            "limit": 1000,
        }


# ---------------------------------------------------------------------------
# session_init wiring: additive field + note, backward compatible
# ---------------------------------------------------------------------------


_PROJECT = "/Users/alice/project"


def _base_session_init_mocks():
    """Mock every collaborator session_init calls EXCEPT the followup helper.

    Returns a dict of all mocks so each test sets the followup count and
    asserts every recorded interaction (tripwire StrictVerifier requires it).
    """
    mock_session_state = tripwire.mock("spellbook.core.config:_get_session_state")
    mock_session_state.returns({})

    # config_get: "session_mode", "fun_mode", "profile.default"
    mock_config_get = tripwire.mock("spellbook.core.config:config_get")
    mock_config_get.returns("none").returns(None).returns(None)

    mock_update_notif = tripwire.mock("spellbook.core.config:_add_update_notification")
    mock_update_notif.returns(None)

    mock_regen = tripwire.mock("spellbook.core.config:_regenerate_memory_md")
    mock_regen.returns(None)

    mock_resume = tripwire.mock("spellbook.core.config:_get_resume_context")
    mock_resume.returns({"resume_available": False})

    mock_admin_url = tripwire.mock("spellbook.core.config:_get_admin_url")
    mock_admin_url.returns(None)

    mock_repairs = tripwire.mock("spellbook.core.config:_get_repairs")
    mock_repairs.returns([])

    mock_followups = tripwire.mock("spellbook.core.config:_get_open_followup_count")

    return {
        "session_state": mock_session_state,
        "config_get": mock_config_get,
        "update_notif": mock_update_notif,
        "regen": mock_regen,
        "resume": mock_resume,
        "admin_url": mock_admin_url,
        "repairs": mock_repairs,
        "followups": mock_followups,
    }


def _assert_base_calls(mocks: dict, final_result: dict) -> None:
    """Assert every standard session_init interaction (StrictVerifier).

    ``_add_update_notification`` receives the result dict by reference; tripwire
    records the live object, so by assertion time it reflects the FINAL mutated
    payload (mirrors tests/test_spellbook_mcp/test_memory_session_init.py).
    """
    mocks["session_state"].assert_call(args=(None,), kwargs={})
    mocks["config_get"].assert_call(args=("session_mode",), kwargs={})
    mocks["config_get"].assert_call(args=("fun_mode",), kwargs={})
    mocks["update_notif"].assert_call(args=(final_result,), kwargs={})
    mocks["regen"].assert_call(args=(_PROJECT,), kwargs={})
    mocks["resume"].assert_call(args=(None, _PROJECT), kwargs={})
    mocks["admin_url"].assert_call(args=(), kwargs={})
    mocks["config_get"].assert_call(args=("profile.default",), kwargs={})
    mocks["repairs"].assert_call(args=(), kwargs={})
    mocks["followups"].assert_call(args=(_PROJECT,), kwargs={})


class TestSessionInitSurfacesFollowups:
    """session_init adds follow_up_tasks_open + note iff count > 0."""

    def test_adds_field_and_note_when_count_positive(self):
        """count == 2 -> follow_up_tasks_open and follow_up_tasks_note both present."""
        mocks = _base_session_init_mocks()
        mocks["followups"].returns(2)

        with tripwire:
            from spellbook.core.config import session_init
            result = session_init(project_path=_PROJECT)

        expected = {
            "mode": {"type": "none"},
            "fun_mode": "no",
            "platform": None,
            "resume_available": False,
            "follow_up_tasks_open": 2,
            "follow_up_tasks_note": (
                "2 open Follow-up Task(s) from prior develop work — "
                "say 'show follow-ups' to review."
            ),
        }
        assert result == expected
        _assert_base_calls(mocks, expected)

    def test_singular_note_wording_for_one(self):
        """count == 1 still uses the same parameterized note string with N=1."""
        mocks = _base_session_init_mocks()
        mocks["followups"].returns(1)

        with tripwire:
            from spellbook.core.config import session_init
            result = session_init(project_path=_PROJECT)

        expected = {
            "mode": {"type": "none"},
            "fun_mode": "no",
            "platform": None,
            "resume_available": False,
            "follow_up_tasks_open": 1,
            "follow_up_tasks_note": (
                "1 open Follow-up Task(s) from prior develop work — "
                "say 'show follow-ups' to review."
            ),
        }
        assert result == expected
        _assert_base_calls(mocks, expected)

    def test_no_field_when_count_zero(self):
        """count == 0 -> backward compatible: neither field nor note present."""
        mocks = _base_session_init_mocks()
        mocks["followups"].returns(0)

        with tripwire:
            from spellbook.core.config import session_init
            result = session_init(project_path=_PROJECT)

        expected = {
            "mode": {"type": "none"},
            "fun_mode": "no",
            "platform": None,
            "resume_available": False,
        }
        assert result == expected
        _assert_base_calls(mocks, expected)
