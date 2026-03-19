"""Tests for spellbook.memory domain modules.

Verifies that all public exports from spellbook memory modules
exist in the corresponding spellbook.memory modules.
"""

import inspect


class TestMemoryStoreImports:
    """Test that spellbook.memory.store is importable and has key exports."""

    def test_import_do_memory_recall(self):
        from spellbook.memory.store import recall_by_query

        assert callable(recall_by_query)

    def test_import_insert_memory(self):
        from spellbook.memory.store import insert_memory

        assert callable(insert_memory)

    def test_import_soft_delete_memory(self):
        from spellbook.memory.store import soft_delete_memory

        assert callable(soft_delete_memory)

    def test_import_recall_by_file_path(self):
        from spellbook.memory.store import recall_by_file_path

        assert callable(recall_by_file_path)

    def test_import_get_unconsolidated_events(self):
        from spellbook.memory.store import get_unconsolidated_events

        assert callable(get_unconsolidated_events)

    def test_import_log_raw_event(self):
        from spellbook.memory.store import log_raw_event

        assert callable(log_raw_event)

    def test_all_public_exports_match(self):
        """Every public callable in spellbook.memory.store must exist in spellbook.memory.store."""
        import spellbook.memory.store as old_mod
        import spellbook.memory.store as new_mod

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
        assert not missing, f"Missing public exports in spellbook.memory.store: {missing}"


class TestMemoryConsolidationImports:
    """Test that spellbook.memory.consolidation is importable and has key exports."""

    def test_import_should_consolidate(self):
        from spellbook.memory.consolidation import should_consolidate

        assert callable(should_consolidate)

    def test_import_build_consolidation_prompt(self):
        from spellbook.memory.consolidation import build_consolidation_prompt

        assert callable(build_consolidation_prompt)

    def test_import_parse_llm_response(self):
        from spellbook.memory.consolidation import parse_llm_response

        assert callable(parse_llm_response)

    def test_import_consolidate_batch(self):
        from spellbook.memory.consolidation import consolidate_batch

        assert callable(consolidate_batch)

    def test_all_public_exports_match(self):
        """Every public callable in spellbook.memory.consolidation must exist."""
        import spellbook.memory.consolidation as old_mod
        import spellbook.memory.consolidation as new_mod

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
        assert not missing, f"Missing public exports in spellbook.memory.consolidation: {missing}"


class TestMemoryToolsImports:
    """Test that spellbook.memory.tools is importable and has key exports."""

    def test_import_do_memory_recall(self):
        from spellbook.memory.tools import do_memory_recall

        assert callable(do_memory_recall)

    def test_import_do_store_memories(self):
        from spellbook.memory.tools import do_store_memories

        assert callable(do_store_memories)

    def test_import_do_memory_forget(self):
        from spellbook.memory.tools import do_memory_forget

        assert callable(do_memory_forget)

    def test_import_do_get_unconsolidated(self):
        from spellbook.memory.tools import do_get_unconsolidated

        assert callable(do_get_unconsolidated)

    def test_all_public_exports_match(self):
        """Every public callable in spellbook.memory.tools must exist."""
        import spellbook.memory.tools as old_mod
        import spellbook.memory.tools as new_mod

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
        assert not missing, f"Missing public exports in spellbook.memory.tools: {missing}"


class TestExtractorsImports:
    """Test that spellbook.memory.extractors is importable and has all submodules."""

    def test_import_extractors_types(self):
        from spellbook.memory.extractors.types import Soul

        assert Soul is not None

    def test_import_extractors_todos(self):
        from spellbook.memory.extractors.todos import extract_todos

        assert callable(extract_todos)

    def test_import_extractors_skill(self):
        from spellbook.memory.extractors.skill import extract_active_skill

        assert callable(extract_active_skill)

    def test_import_extractors_skill_phase(self):
        from spellbook.memory.extractors.skill_phase import extract_skill_phase

        assert callable(extract_skill_phase)

    def test_import_extractors_persona(self):
        from spellbook.memory.extractors.persona import extract_persona

        assert callable(extract_persona)

    def test_import_extractors_files(self):
        from spellbook.memory.extractors.files import extract_recent_files

        assert callable(extract_recent_files)

    def test_import_extractors_position(self):
        from spellbook.memory.extractors.position import extract_position

        assert callable(extract_position)

    def test_import_extractors_workflow(self):
        from spellbook.memory.extractors.workflow import extract_workflow_pattern

        assert callable(extract_workflow_pattern)

    def test_import_extractors_message_utils(self):
        from spellbook.memory.extractors import message_utils

        assert message_utils is not None
