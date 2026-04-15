"""Shared pytest marker for tests requiring QMD and Serena binaries."""
import shutil

import pytest

requires_memory_tools = pytest.mark.skipif(
    not (shutil.which("qmd") and shutil.which("serena")),
    reason="QMD and Serena required",
)
