"""Tests for pr_distill pattern definitions."""

import re
from spellbook_mcp.pr_distill.patterns import (
    BUILTIN_PATTERNS,
    ALWAYS_REVIEW_PATTERNS,
    HIGH_CONFIDENCE_PATTERNS,
    MEDIUM_CONFIDENCE_PATTERNS,
    get_pattern_by_id,
    get_all_pattern_ids,
    Pattern,
)


class TestPatternDefinitions:
    def test_total_pattern_count(self):
        assert len(BUILTIN_PATTERNS) == 15

    def test_always_review_count(self):
        assert len(ALWAYS_REVIEW_PATTERNS) == 6

    def test_high_confidence_count(self):
        assert len(HIGH_CONFIDENCE_PATTERNS) == 5

    def test_medium_confidence_count(self):
        assert len(MEDIUM_CONFIDENCE_PATTERNS) == 4

    def test_all_patterns_have_required_fields(self):
        for pattern in BUILTIN_PATTERNS:
            assert pattern.id
            assert 0 <= pattern.confidence <= 100
            assert pattern.default_category in {
                "REVIEW_REQUIRED", "LIKELY_REVIEW", "UNCERTAIN",
                "LIKELY_SKIP", "SAFE_TO_SKIP"
            }
            assert pattern.priority in {"always_review", "high", "medium"}
            assert pattern.description
            # Must have at least one matcher
            assert pattern.match_file or pattern.match_line


class TestPatternMatching:
    def test_migration_file_pattern(self):
        pattern = get_pattern_by_id("migration-file")
        assert pattern is not None
        assert pattern.match_file.search("/app/migrations/0001_initial.py")
        assert not pattern.match_file.search("/app/models.py")

    def test_permission_change_pattern(self):
        pattern = get_pattern_by_id("permission-change")
        assert pattern is not None
        assert pattern.match_line.search("permission_classes = [IsAuthenticated]")
        assert pattern.match_line.search("class MyPermission(BasePermission)")
        assert not pattern.match_line.search("class MyModel(models.Model)")

    def test_model_change_pattern(self):
        pattern = get_pattern_by_id("model-change")
        assert pattern is not None
        assert pattern.match_file.search("/app/models.py")
        assert not pattern.match_file.search("/app/views.py")

    def test_signal_handler_pattern(self):
        pattern = get_pattern_by_id("signal-handler")
        assert pattern is not None
        assert pattern.match_line.search("@receiver(post_save)")
        assert pattern.match_line.search("my_signal = Signal()")
        assert not pattern.match_line.search("def handler():")

    def test_endpoint_change_pattern(self):
        pattern = get_pattern_by_id("endpoint-change")
        assert pattern is not None
        assert pattern.match_file.search("/app/urls.py")
        assert pattern.match_file.search("/app/views.py")
        assert not pattern.match_file.search("/app/models.py")

    def test_settings_change_pattern(self):
        pattern = get_pattern_by_id("settings-change")
        assert pattern is not None
        assert pattern.match_file.search("/app/settings/base.py")
        assert not pattern.match_file.search("/app/views.py")

    def test_query_count_json_pattern(self):
        pattern = get_pattern_by_id("query-count-json")
        assert pattern is not None
        assert pattern.match_file.search("/tests/query-counts/test-query-counts.json")
        assert not pattern.match_file.search("/tests/test.json")

    def test_debug_print_pattern(self):
        pattern = get_pattern_by_id("debug-print-removal")
        assert pattern is not None
        assert pattern.match_line.search("print(debug)")
        assert pattern.match_line.search("    print(x)")
        assert not pattern.match_line.search("# print(x)")

    def test_import_cleanup_pattern(self):
        pattern = get_pattern_by_id("import-cleanup")
        assert pattern is not None
        assert pattern.match_line.search("import os")
        assert pattern.match_line.search("from django import forms")
        assert not pattern.match_line.search("# import os")

    def test_gitignore_pattern(self):
        pattern = get_pattern_by_id("gitignore-addition")
        assert pattern is not None
        assert pattern.match_file.search("/.gitignore")
        assert pattern.match_file.search("/app/.gitignore")
        assert not pattern.match_file.search("/app/config.txt")

    def test_backfill_command_pattern(self):
        pattern = get_pattern_by_id("backfill-command-deletion")
        assert pattern is not None
        assert pattern.match_file.search("/app/management/commands/backfill.py")
        assert not pattern.match_file.search("/app/views.py")

    def test_decorator_removal_pattern(self):
        pattern = get_pattern_by_id("decorator-removal")
        assert pattern is not None
        assert pattern.match_line.search("@login_required")
        assert pattern.match_line.search("    @property")
        assert not pattern.match_line.search("email@example.com")

    def test_factory_setup_pattern(self):
        pattern = get_pattern_by_id("factory-setup")
        assert pattern is not None
        assert pattern.match_line.search("UserFactory()")
        assert pattern.match_line.search("user = MyFactory(name='test')")
        assert not pattern.match_line.search("factory = None")

    def test_test_rename_pattern(self):
        pattern = get_pattern_by_id("test-rename")
        assert pattern is not None
        assert pattern.match_line.search("def test_something():")
        assert pattern.match_line.search("    def test_other():")
        assert not pattern.match_line.search("def something():")

    def test_test_assertion_pattern(self):
        pattern = get_pattern_by_id("test-assertion-addition")
        assert pattern is not None
        assert pattern.match_line.search("self.assertEqual(a, b)")
        assert pattern.match_line.search("assert_called_once()")
        assert not pattern.match_line.search("# assert something")


class TestPatternLookup:
    def test_get_pattern_by_id_found(self):
        pattern = get_pattern_by_id("migration-file")
        assert pattern is not None
        assert pattern.id == "migration-file"

    def test_get_pattern_by_id_not_found(self):
        pattern = get_pattern_by_id("nonexistent")
        assert pattern is None

    def test_get_all_pattern_ids(self):
        ids = get_all_pattern_ids()
        assert len(ids) == 15
        assert "migration-file" in ids
        assert "test-assertion-addition" in ids


class TestPatternPriorities:
    def test_always_review_patterns_priority(self):
        for pattern in ALWAYS_REVIEW_PATTERNS:
            assert pattern.priority == "always_review"
            assert pattern.default_category == "REVIEW_REQUIRED"

    def test_high_confidence_patterns_priority(self):
        for pattern in HIGH_CONFIDENCE_PATTERNS:
            assert pattern.priority == "high"
            assert pattern.confidence == 95
            assert pattern.default_category == "SAFE_TO_SKIP"

    def test_medium_confidence_patterns_priority(self):
        for pattern in MEDIUM_CONFIDENCE_PATTERNS:
            assert pattern.priority == "medium"
            assert 70 <= pattern.confidence <= 85
            assert pattern.default_category == "LIKELY_SKIP"
