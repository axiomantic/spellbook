"""Tests for spellbook.sessions domain modules.

Verifies that all public exports from spellbook_mcp session modules
exist in the corresponding spellbook.sessions modules.
"""

import inspect
from typing import Callable


class TestSessionsParserImports:
    """Test that spellbook.sessions.parser has key exports from session_ops.py."""

    def test_import_load_jsonl(self):
        from spellbook.sessions.parser import load_jsonl

        assert callable(load_jsonl)

    def test_import_find_last_compact_boundary(self):
        from spellbook.sessions.parser import find_last_compact_boundary

        assert callable(find_last_compact_boundary)

    def test_import_extract_custom_title(self):
        from spellbook.sessions.parser import extract_custom_title

        assert callable(extract_custom_title)

    def test_import_split_by_char_limit(self):
        from spellbook.sessions.parser import split_by_char_limit

        assert callable(split_by_char_limit)

    def test_import_list_sessions_with_samples(self):
        from spellbook.sessions.parser import list_sessions_with_samples

        assert callable(list_sessions_with_samples)

    def test_all_public_exports_match(self):
        """Every public callable in spellbook_mcp.session_ops must exist."""
        import spellbook_mcp.session_ops as old_mod
        import spellbook.sessions.parser as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and callable(obj)
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and callable(obj)
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.sessions.parser: {missing}"


class TestSessionsResumeImports:
    """Test that spellbook.sessions.resume has key exports from resume.py."""

    def test_import_detect_continuation_intent(self):
        from spellbook.sessions.resume import detect_continuation_intent

        assert callable(detect_continuation_intent)

    def test_import_generate_boot_prompt(self):
        from spellbook.sessions.resume import generate_boot_prompt

        assert callable(generate_boot_prompt)

    def test_import_get_resume_fields(self):
        from spellbook.sessions.resume import get_resume_fields

        assert callable(get_resume_fields)

    def test_import_continuation_intent(self):
        from spellbook.sessions.resume import ContinuationIntent

        assert ContinuationIntent is not None

    def test_import_resume_fields(self):
        from spellbook.sessions.resume import ResumeFields

        assert ResumeFields is not None

    def test_import_validate_workflow_state(self):
        from spellbook.sessions.resume import validate_workflow_state

        assert callable(validate_workflow_state)

    def test_import_load_workflow_state(self):
        from spellbook.sessions.resume import load_workflow_state

        assert callable(load_workflow_state)

    def test_all_public_exports_match(self):
        """Every public callable/class in spellbook_mcp.resume must exist."""
        import spellbook_mcp.resume as old_mod
        import spellbook.sessions.resume as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and callable(obj)
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and callable(obj)
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.sessions.resume: {missing}"


class TestSessionsCompactionImports:
    """Test that spellbook.sessions.compaction has key exports from compaction_detector.py."""

    def test_import_compaction_event(self):
        from spellbook.sessions.compaction import CompactionEvent

        assert CompactionEvent is not None

    def test_import_check_for_compaction(self):
        from spellbook.sessions.compaction import check_for_compaction

        assert callable(check_for_compaction)

    def test_import_get_pending_context(self):
        from spellbook.sessions.compaction import get_pending_context

        assert callable(get_pending_context)

    def test_import_compaction_watcher(self):
        from spellbook.sessions.compaction import CompactionWatcher

        assert CompactionWatcher is not None

    def test_all_public_exports_match(self):
        """Every public callable/class in spellbook_mcp.compaction_detector must exist."""
        import spellbook_mcp.compaction_detector as old_mod
        import spellbook.sessions.compaction as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and callable(obj)
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and callable(obj)
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.sessions.compaction: {missing}"


class TestSessionsWatcherImports:
    """Test that spellbook.sessions.watcher has key exports from watcher.py."""

    def test_import_session_watcher(self):
        from spellbook.sessions.watcher import SessionWatcher

        assert SessionWatcher is not None

    def test_import_session_skill_state(self):
        from spellbook.sessions.watcher import SessionSkillState

        assert SessionSkillState is not None

    def test_import_is_heartbeat_fresh(self):
        from spellbook.sessions.watcher import is_heartbeat_fresh

        assert callable(is_heartbeat_fresh)

    def test_on_compaction_hooks_parameter(self):
        """SessionWatcher.__init__ accepts on_compaction_hooks parameter."""
        import inspect as _inspect

        from spellbook.sessions.watcher import SessionWatcher

        sig = _inspect.signature(SessionWatcher.__init__)
        params = list(sig.parameters.keys())
        assert "on_compaction_hooks" in params, (
            f"SessionWatcher.__init__ must accept on_compaction_hooks parameter. "
            f"Found params: {params}"
        )

    def test_on_compaction_hooks_default_none(self):
        """on_compaction_hooks defaults to None and stores as empty list."""
        import inspect as _inspect

        from spellbook.sessions.watcher import SessionWatcher

        sig = _inspect.signature(SessionWatcher.__init__)
        param = sig.parameters["on_compaction_hooks"]
        assert param.default is None, (
            f"on_compaction_hooks default should be None, got {param.default}"
        )

    def test_all_public_exports_match(self):
        """Every public callable/class in spellbook_mcp.watcher must exist."""
        import spellbook_mcp.watcher as old_mod
        import spellbook.sessions.watcher as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and callable(obj)
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and callable(obj)
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.sessions.watcher: {missing}"


class TestSessionsSkillAnalyzerImports:
    """Test that spellbook.sessions.skill_analyzer has key exports."""

    def test_import_skill_invocation(self):
        from spellbook.sessions.skill_analyzer import SkillInvocation

        assert SkillInvocation is not None

    def test_import_skill_metrics(self):
        from spellbook.sessions.skill_analyzer import SkillMetrics

        assert SkillMetrics is not None

    def test_import_extract_skill_invocations(self):
        from spellbook.sessions.skill_analyzer import extract_skill_invocations

        assert callable(extract_skill_invocations)

    def test_import_analyze_sessions(self):
        from spellbook.sessions.skill_analyzer import analyze_sessions

        assert callable(analyze_sessions)

    def test_import_get_analytics_summary(self):
        from spellbook.sessions.skill_analyzer import get_analytics_summary

        assert callable(get_analytics_summary)

    def test_all_public_exports_match(self):
        """Every public callable/class in spellbook_mcp.skill_analyzer must exist."""
        import spellbook_mcp.skill_analyzer as old_mod
        import spellbook.sessions.skill_analyzer as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and callable(obj)
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and callable(obj)
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.sessions.skill_analyzer: {missing}"


class TestSessionsInjectionImports:
    """Test that spellbook.sessions.injection has key exports."""

    def test_import_should_inject(self):
        from spellbook.sessions.injection import should_inject

        assert callable(should_inject)

    def test_import_wrap_with_reminder(self):
        from spellbook.sessions.injection import wrap_with_reminder

        assert callable(wrap_with_reminder)

    def test_import_build_recovery_context(self):
        from spellbook.sessions.injection import build_recovery_context

        assert callable(build_recovery_context)

    def test_import_get_recovery_context(self):
        from spellbook.sessions.injection import get_recovery_context

        assert callable(get_recovery_context)

    def test_import_inject_recovery_context(self):
        from spellbook.sessions.injection import inject_recovery_context

        assert callable(inject_recovery_context)

    def test_all_public_exports_match(self):
        """Every public callable in spellbook_mcp.injection must exist."""
        import spellbook_mcp.injection as old_mod
        import spellbook.sessions.injection as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and callable(obj)
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and callable(obj)
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.sessions.injection: {missing}"


class TestSessionsSoulExtractorImports:
    """Test that spellbook.sessions.soul_extractor has key exports."""

    def test_import_read_jsonl(self):
        from spellbook.sessions.soul_extractor import read_jsonl

        assert callable(read_jsonl)

    def test_import_extract_soul(self):
        from spellbook.sessions.soul_extractor import extract_soul

        assert callable(extract_soul)

    def test_all_public_exports_match(self):
        """Every public callable in spellbook_mcp.soul_extractor must exist."""
        import spellbook_mcp.soul_extractor as old_mod
        import spellbook.sessions.soul_extractor as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and callable(obj)
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and callable(obj)
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.sessions.soul_extractor: {missing}"
