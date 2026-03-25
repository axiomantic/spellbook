"""Tests for Alembic multi-database migration configuration."""

import configparser
import importlib.util
import sys
from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "spellbook" / "db" / "migrations"


class TestAlembicFileStructure:
    """Verify all required migration files and directories exist."""

    def test_env_py_exists(self):
        assert MIGRATIONS_DIR / "env.py" == MIGRATIONS_DIR / "env.py"
        assert (MIGRATIONS_DIR / "env.py").is_file()

    def test_alembic_ini_exists(self):
        assert (MIGRATIONS_DIR / "alembic.ini").is_file()

    def test_script_mako_exists(self):
        assert (MIGRATIONS_DIR / "script.py.mako").is_file()

    def test_version_directories_exist(self):
        versions_dir = MIGRATIONS_DIR / "versions"
        expected_dirs = {"spellbook", "fractal", "forged", "coordination"}
        actual_dirs = {d.name for d in versions_dir.iterdir() if d.is_dir()}
        assert actual_dirs == expected_dirs


class TestAlembicIni:
    """Verify alembic.ini is correctly configured."""

    def test_ini_is_parseable_and_has_script_location(self):
        ini_path = MIGRATIONS_DIR / "alembic.ini"
        parser = configparser.ConfigParser()
        parser.read(str(ini_path))
        assert parser.has_section("alembic")
        assert parser.get("alembic", "script_location") == "."


@pytest.mark.allow("asyncio")
@pytest.mark.allow("subprocess")
@pytest.mark.allow("popen")
class TestEnvPyStructure:
    """Verify env.py has correct DB_CONFIGS and imports."""

    @pytest.fixture()
    def env_module(self):
        """Import env.py as a module without executing migration logic.

        We patch alembic.context to avoid runtime errors from Alembic
        expecting to be run inside a migration context.  The mock's
        is_offline_mode returns True so the module-level code takes the
        offline branch (whose calls are all no-ops on the MagicMock),
        avoiding asyncio.run() which would try to connect to real databases.
        """
        from unittest.mock import MagicMock

        # Create a mock alembic.context module so env.py can import it
        mock_context = MagicMock()
        mock_context.config = MagicMock()
        mock_context.config.config_file_name = None
        mock_context.is_offline_mode.return_value = False
        mock_context.get_x_argument.return_value = {}

        # Temporarily replace alembic.context
        original_context = sys.modules.get("alembic.context")
        sys.modules["alembic.context"] = mock_context

        # We also need alembic.op mocked for script imports
        original_op = sys.modules.get("alembic.op")
        sys.modules["alembic.op"] = MagicMock()

        try:
            env_path = MIGRATIONS_DIR / "env.py"
            spec = importlib.util.spec_from_file_location(
                "spellbook_migrations_env", str(env_path)
            )
            module = importlib.util.module_from_spec(spec)

            # env.py has module-level code that calls run_migrations_online()
            # which invokes asyncio.run(run_async_migrations()).  Mock
            # is_offline_mode to return True so env.py takes the offline
            # branch instead, and mock run_migrations_offline via context
            # to be a no-op (context.configure/begin_transaction/run_migrations
            # are already mocked).
            mock_context.is_offline_mode.return_value = True
            spec.loader.exec_module(module)
            yield module
        finally:
            # Restore original modules
            if original_context is not None:
                sys.modules["alembic.context"] = original_context
            else:
                sys.modules.pop("alembic.context", None)
            if original_op is not None:
                sys.modules["alembic.op"] = original_op
            else:
                sys.modules.pop("alembic.op", None)

    def test_db_configs_has_exactly_four_databases(self, env_module):
        assert isinstance(env_module.DB_CONFIGS, dict)
        assert set(env_module.DB_CONFIGS.keys()) == {
            "spellbook",
            "fractal",
            "forged",
            "coordination",
        }

    def test_db_configs_entries_have_required_keys(self, env_module):
        required_keys = {"engine", "metadata", "version_table"}
        for db_name, db_config in env_module.DB_CONFIGS.items():
            assert set(db_config.keys()) == required_keys, (
                f"DB_CONFIGS['{db_name}'] keys {set(db_config.keys())} "
                f"!= expected {required_keys}"
            )

    def test_db_configs_version_tables(self, env_module):
        for db_name, db_config in env_module.DB_CONFIGS.items():
            assert db_config["version_table"] == "alembic_version", (
                f"DB_CONFIGS['{db_name}']['version_table'] "
                f"== {db_config['version_table']!r}, expected 'alembic_version'"
            )

    def test_db_configs_metadata_matches_bases(self, env_module):
        from spellbook.db.base import (
            CoordinationBase,
            ForgedBase,
            FractalBase,
            SpellbookBase,
        )

        expected_metadata = {
            "spellbook": SpellbookBase.metadata,
            "fractal": FractalBase.metadata,
            "forged": ForgedBase.metadata,
            "coordination": CoordinationBase.metadata,
        }
        for db_name, db_config in env_module.DB_CONFIGS.items():
            assert db_config["metadata"] is expected_metadata[db_name], (
                f"DB_CONFIGS['{db_name}']['metadata'] is not "
                f"{expected_metadata[db_name]!r}"
            )

    def test_db_configs_engines_match(self, env_module):
        from spellbook.db.engines import (
            coordination_engine,
            forged_engine,
            fractal_engine,
            spellbook_engine,
        )

        expected_engines = {
            "spellbook": spellbook_engine,
            "fractal": fractal_engine,
            "forged": forged_engine,
            "coordination": coordination_engine,
        }
        for db_name, db_config in env_module.DB_CONFIGS.items():
            assert db_config["engine"] is expected_engines[db_name], (
                f"DB_CONFIGS['{db_name}']['engine'] is not the expected engine"
            )

    def test_env_has_render_as_batch(self):
        """Verify render_as_batch=True is used for SQLite ALTER TABLE support."""
        env_path = MIGRATIONS_DIR / "env.py"
        source = env_path.read_text()
        assert "render_as_batch=True" in source

    def test_env_has_get_target_db_function(self, env_module):
        """Verify _get_target_db function exists for -x db=<name> support."""
        assert hasattr(env_module, "_get_target_db")
        assert callable(env_module._get_target_db)
