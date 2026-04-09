"""Tests for TTS venv creation."""

import collections
import sys
from pathlib import Path

import bigfoot
import pytest

from spellbook.tts.venv import (
    TTS_MIN_DISK_SPACE_BYTES,
    _resolve_uv,
    create_tts_venv,
    get_tts_python,
    get_tts_venv_dir,
)

DiskUsage = collections.namedtuple("usage", ["total", "used", "free"])

PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


class TestGetTtsPython:
    def test_unix_path(self):
        venv = Path("/opt/tts-venv")
        result = get_tts_python(venv)
        if sys.platform == "win32":
            assert result == Path("/opt/tts-venv/Scripts/python.exe")
        else:
            assert result == Path("/opt/tts-venv/bin/python")

    def test_returns_path_object(self):
        result = get_tts_python(Path("/tmp/venv"))
        assert isinstance(result, Path)


class TestGetTtsVenvDir:
    def test_default_location(self):
        from spellbook.core.paths import get_data_dir

        venv_dir = get_tts_venv_dir()
        assert venv_dir == get_data_dir() / "tts-venv"


class TestConstants:
    def test_min_disk_space_is_3gb(self):
        assert TTS_MIN_DISK_SPACE_BYTES == 3_221_225_472


class TestCreateTtsVenv:
    @pytest.mark.asyncio
    async def test_insufficient_disk_space(self, tmp_path):
        mock_du = bigfoot.mock("spellbook.tts.venv:shutil.disk_usage")
        mock_du.returns(DiskUsage(total=10_000_000_000, used=9_000_000_000, free=1_000_000_000))

        async with bigfoot:
            success, msg = await create_tts_venv(tmp_path / "tts-venv")

        assert success is False
        assert msg == (
            "Insufficient disk space: 0.9GB free, need 3GB"
        )
        mock_du.assert_call(args=(str(tmp_path),), kwargs={})

    @pytest.mark.asyncio
    @pytest.mark.allow("subprocess")
    async def test_venv_creation_success(self, tmp_path):
        mock_du = bigfoot.mock("spellbook.tts.venv:shutil.disk_usage")
        mock_du.returns(DiskUsage(total=10_000_000_000, used=5_000_000_000, free=5_000_000_000))
        mock_uv = bigfoot.mock("spellbook.tts.venv:_resolve_uv")
        mock_uv.returns("uv")

        tts_python = get_tts_python(tmp_path / "tts-venv")

        # Session 1: uv venv
        bigfoot.async_subprocess_mock.new_session().expect(
            "spawn", returns=None,
        ).expect(
            "communicate", returns=(b"", b"", 0),
        )

        # Session 2: uv pip install
        bigfoot.async_subprocess_mock.new_session().expect(
            "spawn", returns=None,
        ).expect(
            "communicate", returns=(b"", b"", 0),
        )

        async with bigfoot:
            success, msg = await create_tts_venv(tmp_path / "tts-venv")

        assert success is True
        assert msg == "TTS venv created and wyoming-kokoro-torch installed"
        # Assertions must be in timeline order: disk_usage, _resolve_uv, then subprocesses
        mock_du.assert_call(args=(str(tmp_path),), kwargs={})
        mock_uv.assert_call(args=(), kwargs={})
        bigfoot.async_subprocess_mock.assert_spawn(
            command=["uv", "venv", str(tmp_path / "tts-venv"), "--python", PYTHON_VERSION, "--seed"],
            stdin=None,
        )
        bigfoot.async_subprocess_mock.assert_communicate(input=None)
        # Assert spawn for pip install
        bigfoot.async_subprocess_mock.assert_spawn(
            command=[
                "uv", "pip", "install",
                "--python", str(tts_python),
                "wyoming-kokoro-torch>=3.0.0",
            ],
            stdin=None,
        )
        bigfoot.async_subprocess_mock.assert_communicate(input=None)

    @pytest.mark.asyncio
    @pytest.mark.allow("subprocess")
    async def test_venv_creation_failure(self, tmp_path):
        mock_du = bigfoot.mock("spellbook.tts.venv:shutil.disk_usage")
        mock_du.returns(DiskUsage(total=10_000_000_000, used=5_000_000_000, free=5_000_000_000))
        mock_uv = bigfoot.mock("spellbook.tts.venv:_resolve_uv")
        mock_uv.returns("uv")

        bigfoot.async_subprocess_mock.new_session().expect(
            "spawn", returns=None,
        ).expect(
            "communicate", returns=(b"", b"error: python 3.12 not found", 1),
        )

        async with bigfoot:
            success, msg = await create_tts_venv(tmp_path / "tts-venv")

        assert success is False
        assert msg == "Failed to create TTS venv: error: python 3.12 not found"
        mock_du.assert_call(args=(str(tmp_path),), kwargs={})
        mock_uv.assert_call(args=(), kwargs={})
        bigfoot.async_subprocess_mock.assert_spawn(
            command=["uv", "venv", str(tmp_path / "tts-venv"), "--python", PYTHON_VERSION, "--seed"],
            stdin=None,
        )
        bigfoot.async_subprocess_mock.assert_communicate(input=None)

    @pytest.mark.asyncio
    @pytest.mark.allow("subprocess")
    async def test_pip_install_failure(self, tmp_path):
        mock_du = bigfoot.mock("spellbook.tts.venv:shutil.disk_usage")
        mock_du.returns(DiskUsage(total=10_000_000_000, used=5_000_000_000, free=5_000_000_000))
        mock_uv = bigfoot.mock("spellbook.tts.venv:_resolve_uv")
        mock_uv.returns("uv")

        tts_python = get_tts_python(tmp_path / "tts-venv")

        # Session 1: uv venv (succeeds)
        bigfoot.async_subprocess_mock.new_session().expect(
            "spawn", returns=None,
        ).expect(
            "communicate", returns=(b"", b"", 0),
        )

        # Session 2: uv pip install (fails)
        bigfoot.async_subprocess_mock.new_session().expect(
            "spawn", returns=None,
        ).expect(
            "communicate", returns=(b"", b"error: package not found", 1),
        )

        async with bigfoot:
            success, msg = await create_tts_venv(tmp_path / "tts-venv")

        assert success is False
        assert msg == "Failed to install wyoming-kokoro-torch: error: package not found"
        mock_du.assert_call(args=(str(tmp_path),), kwargs={})
        mock_uv.assert_call(args=(), kwargs={})
        bigfoot.async_subprocess_mock.assert_spawn(
            command=["uv", "venv", str(tmp_path / "tts-venv"), "--python", PYTHON_VERSION, "--seed"],
            stdin=None,
        )
        bigfoot.async_subprocess_mock.assert_communicate(input=None)
        bigfoot.async_subprocess_mock.assert_spawn(
            command=[
                "uv", "pip", "install",
                "--python", str(tts_python),
                "wyoming-kokoro-torch>=3.0.0",
            ],
            stdin=None,
        )
        bigfoot.async_subprocess_mock.assert_communicate(input=None)

    @pytest.mark.asyncio
    @pytest.mark.allow("subprocess")
    async def test_progress_callback_called(self, tmp_path):
        mock_du = bigfoot.mock("spellbook.tts.venv:shutil.disk_usage")
        mock_du.returns(DiskUsage(total=10_000_000_000, used=5_000_000_000, free=5_000_000_000))
        mock_uv = bigfoot.mock("spellbook.tts.venv:_resolve_uv")
        mock_uv.returns("uv")

        tts_python = get_tts_python(tmp_path / "tts-venv")

        bigfoot.async_subprocess_mock.new_session().expect(
            "spawn", returns=None,
        ).expect(
            "communicate", returns=(b"", b"", 0),
        )
        bigfoot.async_subprocess_mock.new_session().expect(
            "spawn", returns=None,
        ).expect(
            "communicate", returns=(b"", b"", 0),
        )

        stages = []

        def cb(stage, pct):
            stages.append((stage, pct))

        async with bigfoot:
            await create_tts_venv(tmp_path / "tts-venv", progress_callback=cb)

        assert stages == [
            ("Creating TTS venv", 0.1),
            ("Installing wyoming-kokoro-torch", 0.3),
            ("TTS venv ready", 1.0),
        ]
        # Assertions in timeline order
        mock_du.assert_call(args=(str(tmp_path),), kwargs={})
        mock_uv.assert_call(args=(), kwargs={})
        bigfoot.async_subprocess_mock.assert_spawn(
            command=["uv", "venv", str(tmp_path / "tts-venv"), "--python", PYTHON_VERSION, "--seed"],
            stdin=None,
        )
        bigfoot.async_subprocess_mock.assert_communicate(input=None)
        bigfoot.async_subprocess_mock.assert_spawn(
            command=[
                "uv", "pip", "install",
                "--python", str(tts_python),
                "wyoming-kokoro-torch>=3.0.0",
            ],
            stdin=None,
        )
        bigfoot.async_subprocess_mock.assert_communicate(input=None)
