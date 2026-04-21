"""Tests for Alembic multi-database migration configuration."""

import configparser
import importlib.util
import sys
from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "spellbook" / "db" / "migrations"


class _FakeModule:
    """Fake module object that auto-creates attributes on access.

    Replaces MagicMock for sys.modules injection: any attribute access
    returns another _FakeModule, and instances are callable (returning
    themselves by default).
    """

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, name):
        obj = _FakeModule()
        object.__setattr__(self, name, obj)
        return obj

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


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
class TestEnvPyStructure:
    """Verify env.py has correct DB_CONFIGS and imports."""

    @pytest.fixture()
    def env_module(self, monkeypatch):
        """Import env.py as a module without executing migration logic.

        We inject fake alembic.context and alembic.op modules into
        sys.modules so env.py can import them.  The fake context's
        is_offline_mode returns True so the module-level code takes the
        offline branch (whose calls are all no-ops on the fake),
        avoiding asyncio.run() which would try to connect to real databases.
        """
        # Create a fake alembic.context module so env.py can import it
        fake_config = _FakeModule(config_file_name=None)
        fake_context = _FakeModule(config=fake_config)
        fake_context.is_offline_mode = lambda: False
        fake_context.get_x_argument = lambda **kwargs: {}

        # Temporarily replace alembic.context and alembic.op.
        #
        # `from alembic import X` resolves X both through sys.modules AND
        # by caching X as an attribute on the `alembic` package. We must
        # restore BOTH, otherwise a later `from alembic import op` (e.g.,
        # in the 0001 revision module loaded by
        # TestWorkerLLMCallsMigration) will pick up the fake module and
        # silently no-op the migration calls.
        import alembic as _alembic_pkg

        had_ctx_attr = hasattr(_alembic_pkg, "context")
        had_op_attr = hasattr(_alembic_pkg, "op")
        original_ctx_attr = getattr(_alembic_pkg, "context", None)
        original_op_attr = getattr(_alembic_pkg, "op", None)

        fake_op_module = _FakeModule()
        monkeypatch.setitem(sys.modules, "alembic.context", fake_context)
        monkeypatch.setitem(sys.modules, "alembic.op", fake_op_module)
        # Also overwrite package attributes so `from alembic import context`
        # / `from alembic import op` inside env.py resolve to the fakes
        # even if the real submodules have already been imported earlier
        # in the test session.
        _alembic_pkg.context = fake_context
        _alembic_pkg.op = fake_op_module

        env_path = MIGRATIONS_DIR / "env.py"
        spec = importlib.util.spec_from_file_location(
            "spellbook_migrations_env", str(env_path)
        )
        module = importlib.util.module_from_spec(spec)

        # env.py has module-level code that calls run_migrations_online()
        # which invokes asyncio.run(run_async_migrations()).  Set
        # is_offline_mode to return True so env.py takes the offline
        # branch instead (configure/begin_transaction/run_migrations
        # are all no-ops on the fake module).
        fake_context.is_offline_mode = lambda: True
        spec.loader.exec_module(module)
        try:
            yield module
        finally:
            # Restore package attributes so `from alembic import op` in
            # later tests picks up the real submodule.
            if had_ctx_attr:
                _alembic_pkg.context = original_ctx_attr
            elif hasattr(_alembic_pkg, "context"):
                delattr(_alembic_pkg, "context")
            if had_op_attr:
                _alembic_pkg.op = original_op_attr
            elif hasattr(_alembic_pkg, "op"):
                delattr(_alembic_pkg, "op")

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


class TestPerDbVersionLocations:
    """Verify ``alembic.ini`` declares every per-DB versions directory so
    ``alembic upgrade head -x db=<name>`` actually discovers migrations under
    ``versions/<name>/`` instead of silently no-op'ing.

    Alembic builds its ``ScriptDirectory`` from config BEFORE ``env.py``
    runs, so ``version_locations`` must live in the .ini file rather than
    being set dynamically from env.py. Without it, revisions under
    ``versions/<db>/`` subdirectories are invisible to Alembic's default
    flat ``versions/`` scanner and every ``upgrade head`` reports no work.

    Alembic uses ScriptDirectory to walk ALL discovered revisions across
    every listed location; per-DB filtering at run time is handled by
    ``env.py``'s ``-x db=<name>`` argument (which selects the engine).
    Revision ids are namespaced per-DB (e.g. ``0001_worker_llm_calls``
    belongs only to the spellbook DB), so cross-DB scanning is safe.
    """

    @pytest.fixture()
    def parsed_ini(self) -> configparser.ConfigParser:
        """Parse ``alembic.ini`` with the ``%(here)s`` default resolved so
        ``version_locations`` comes back as real filesystem paths.
        """
        ini_path = MIGRATIONS_DIR / "alembic.ini"
        parser = configparser.ConfigParser(
            defaults={"here": str(MIGRATIONS_DIR.resolve())}
        )
        parser.read(str(ini_path))
        return parser

    def test_ini_sets_version_path_separator_to_space(self, parsed_ini):
        """Alembic needs an explicit separator to split multiple version
        locations; we use ``space`` so the four per-DB paths are parsed as
        four entries.
        """
        assert parsed_ini.get("alembic", "version_path_separator") == "space"

    def test_ini_version_locations_contains_every_per_db_directory(
        self, parsed_ini
    ):
        """Every DB's ``versions/<db_name>/`` absolute path must appear in
        ``version_locations``. Missing any one would silently skip all
        revisions for that DB.
        """
        value = parsed_ini.get("alembic", "version_locations")
        # Alembic's "space" separator splits on a single space character.
        actual_locations = value.split(" ")
        expected_locations = [
            str((MIGRATIONS_DIR.resolve() / "versions" / db_name))
            for db_name in ("spellbook", "fractal", "forged", "coordination")
        ]
        # Assert EXACT equality against the complete expected list (order
        # matches ini file order). Broken implementation caught by this
        # assertion: dropping any entry, reordering across DBs silently,
        # or pointing at wrong subdirectory.
        assert actual_locations == expected_locations

    @pytest.mark.parametrize(
        "db_name", ["spellbook", "fractal", "forged", "coordination"]
    )
    def test_ini_version_locations_entry_is_absolute_and_exists(
        self, parsed_ini, db_name
    ):
        """Each version_locations entry must be an absolute path pointing
        to a real ``versions/<db_name>/`` directory on disk. Catches typos
        in DB names and relative-path regressions (%(here)s dropped).
        """
        value = parsed_ini.get("alembic", "version_locations")
        actual_locations = value.split(" ")
        expected_path = MIGRATIONS_DIR.resolve() / "versions" / db_name
        expected_str = str(expected_path)
        assert expected_str in actual_locations, (
            f"version_locations missing entry for {db_name!r}: "
            f"expected {expected_str!r} in {actual_locations!r}"
        )
        assert Path(expected_str).is_absolute()
        assert expected_path.is_dir(), (
            f"version_locations entry {expected_str!r} is not a directory"
        )


class TestWorkerLLMCallsMigration:
    """Verify the 0001_worker_llm_calls Alembic revision creates and drops
    the ``worker_llm_calls`` table with its 5 indexes.

    Tests the migration module's ``upgrade()`` and ``downgrade()`` directly
    against a temporary SQLite database, so we exercise the exact SQL the
    revision will emit at deploy time without needing a configured env.py
    to target the temp DB. This catches:
      - missing/renamed columns (SELECT on the table after upgrade would fail)
      - missing indexes (sqlite_master lookup)
      - downgrade leaving orphan indexes or the table itself
    """

    REVISION_PATH = (
        MIGRATIONS_DIR / "versions" / "spellbook" / "0001_add_worker_llm_calls.py"
    )

    EXPECTED_COLUMNS = {
        "id",
        "timestamp",
        "task",
        "model",
        "status",
        "latency_ms",
        "prompt_len",
        "response_len",
        "error",
        "override_loaded",
    }

    EXPECTED_INDEXES = {
        "ix_worker_llm_calls_timestamp",
        "ix_worker_llm_calls_task",
        "ix_worker_llm_calls_status",
        "ix_worker_llm_calls_ts_status",
        "ix_worker_llm_calls_ts_task",
    }

    def _load_revision_module(self):
        """Import the revision file as a standalone module."""
        spec = importlib.util.spec_from_file_location(
            "spellbook_migration_0001", str(self.REVISION_PATH)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_revision_file_exists(self):
        assert self.REVISION_PATH.is_file(), (
            f"expected migration file at {self.REVISION_PATH}"
        )

    def test_revision_metadata(self):
        module = self._load_revision_module()
        assert module.revision == "0001_worker_llm_calls"
        assert module.down_revision is None
        assert module.branch_labels is None
        assert module.depends_on is None

    def test_upgrade_creates_table_with_all_columns_and_indexes(self, tmp_path):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from sqlalchemy import create_engine, inspect

        db_path = tmp_path / "test_migration.db"
        engine = create_engine(f"sqlite:///{db_path}")
        module = self._load_revision_module()

        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                module.upgrade()

        inspector = inspect(engine)

        # Table and all columns exist with the exact expected set.
        assert "worker_llm_calls" in inspector.get_table_names()
        actual_columns = {c["name"] for c in inspector.get_columns("worker_llm_calls")}
        assert actual_columns == self.EXPECTED_COLUMNS

        # All 5 indexes (3 single-col + 2 compound) exist with exact names.
        actual_indexes = {
            idx["name"] for idx in inspector.get_indexes("worker_llm_calls")
        }
        assert actual_indexes == self.EXPECTED_INDEXES

        # Compound indexes cover the correct columns in the correct order.
        indexes_by_name = {
            idx["name"]: idx for idx in inspector.get_indexes("worker_llm_calls")
        }
        assert indexes_by_name["ix_worker_llm_calls_ts_status"]["column_names"] == [
            "timestamp",
            "status",
        ]
        assert indexes_by_name["ix_worker_llm_calls_ts_task"]["column_names"] == [
            "timestamp",
            "task",
        ]
        assert indexes_by_name["ix_worker_llm_calls_timestamp"]["column_names"] == [
            "timestamp",
        ]
        assert indexes_by_name["ix_worker_llm_calls_task"]["column_names"] == [
            "task",
        ]
        assert indexes_by_name["ix_worker_llm_calls_status"]["column_names"] == [
            "status",
        ]

        engine.dispose()

    def test_downgrade_drops_table_and_all_indexes(self, tmp_path):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from sqlalchemy import create_engine, inspect

        db_path = tmp_path / "test_migration.db"
        engine = create_engine(f"sqlite:///{db_path}")
        module = self._load_revision_module()

        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                module.upgrade()

        # Sanity check: table+indexes exist after upgrade.
        inspector = inspect(engine)
        assert "worker_llm_calls" in inspector.get_table_names()

        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                module.downgrade()

        inspector = inspect(engine)
        # Table gone.
        assert "worker_llm_calls" not in inspector.get_table_names()
        # No orphan indexes (SQLite drops indexes with the table, but we verify
        # the downgrade code explicitly ran without errors and left nothing).
        # sqlite_master listing: no rows whose name begins with
        # ix_worker_llm_calls_.
        from sqlalchemy import text

        with engine.connect() as conn:
            orphan_indexes = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name LIKE 'ix_worker_llm_calls_%'"
                )
            ).fetchall()
        assert orphan_indexes == []

        engine.dispose()
