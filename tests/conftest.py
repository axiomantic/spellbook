"""Pytest configuration for spellbook tests."""

import sys
from pathlib import Path

import pytest

# Add project root to path so spellbook_mcp can be imported
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def pytest_addoption(parser):
    parser.addoption(
        "--run-docker",
        action="store_true",
        default=False,
        help="Run docker-marked tests (skipped by default, intended for CI)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-docker"):
        return  # Run everything
    skip_docker = pytest.mark.skip(reason="docker tests only run in CI (use --run-docker)")
    for item in items:
        if "docker" in item.keywords:
            item.add_marker(skip_docker)
