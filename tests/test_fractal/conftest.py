"""Pytest fixtures for fractal thinking tests."""

import pytest


@pytest.fixture
def fractal_db(tmp_path):
    """Create a temporary fractal database for testing.

    Initializes the schema, yields the db_path, and cleans up connections
    on teardown.
    """
    from spellbook_mcp.fractal.schema import (
        close_all_fractal_connections,
        init_fractal_schema,
    )

    db_path = str(tmp_path / "fractal.db")
    init_fractal_schema(db_path)
    yield db_path
    close_all_fractal_connections()
