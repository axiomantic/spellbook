"""Tests for TTS device auto-detection."""

import bigfoot
import pytest

from spellbook.tts.device import detect_device


class TestDetectDevice:
    def test_user_override_returns_configured_value(self):
        mock_cfg = bigfoot.mock("spellbook.tts.device:config_get")
        mock_cfg.returns("cuda")

        with bigfoot:
            result = detect_device()

        assert result == "cuda"
        mock_cfg.assert_call(args=("tts_device",), kwargs={})

    def test_apple_silicon_returns_mps(self):
        mock_cfg = bigfoot.mock("spellbook.tts.device:config_get")
        mock_cfg.returns("auto")
        mock_system = bigfoot.mock("spellbook.tts.device:plat.system")
        mock_system.returns("Darwin")
        mock_machine = bigfoot.mock("spellbook.tts.device:plat.machine")
        mock_machine.returns("arm64")

        with bigfoot:
            result = detect_device()

        assert result == "mps"
        mock_cfg.assert_call(args=("tts_device",), kwargs={})
        mock_system.assert_call(args=(), kwargs={})
        mock_machine.assert_call(args=(), kwargs={})

    def test_intel_mac_no_gpu_returns_cpu(self):
        mock_cfg = bigfoot.mock("spellbook.tts.device:config_get")
        mock_cfg.returns("auto")
        mock_system = bigfoot.mock("spellbook.tts.device:plat.system")
        mock_system.returns("Darwin")
        mock_machine = bigfoot.mock("spellbook.tts.device:plat.machine")
        mock_machine.returns("x86_64")
        mock_which = bigfoot.mock("spellbook.tts.device:shutil.which")
        mock_which.returns(None)

        with bigfoot:
            result = detect_device()

        assert result == "cpu"
        mock_cfg.assert_call(args=("tts_device",), kwargs={})
        mock_system.assert_call(args=(), kwargs={})
        mock_machine.assert_call(args=(), kwargs={})
        mock_which.assert_call(args=("nvidia-smi",), kwargs={})

    @pytest.mark.allow("subprocess")
    def test_nvidia_gpu_returns_cuda(self):
        mock_cfg = bigfoot.mock("spellbook.tts.device:config_get")
        mock_cfg.returns("auto")
        mock_system = bigfoot.mock("spellbook.tts.device:plat.system")
        mock_system.returns("Linux")
        mock_which = bigfoot.mock("spellbook.tts.device:shutil.which")
        mock_which.returns("/usr/bin/nvidia-smi")
        bigfoot.subprocess_mock.mock_run(
            command=["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            returncode=0,
            stdout="NVIDIA GeForce RTX 3090\n",
        )

        with bigfoot:
            result = detect_device()

        assert result == "cuda"
        mock_cfg.assert_call(args=("tts_device",), kwargs={})
        mock_system.assert_call(args=(), kwargs={})
        mock_which.assert_call(args=("nvidia-smi",), kwargs={})
        bigfoot.subprocess_mock.assert_run(
            command=["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            returncode=0,
            stdout="NVIDIA GeForce RTX 3090\n",
            stderr="",
        )

    @pytest.mark.allow("subprocess")
    def test_nvidia_smi_fails_returns_cpu(self):
        mock_cfg = bigfoot.mock("spellbook.tts.device:config_get")
        mock_cfg.returns("auto")
        mock_system = bigfoot.mock("spellbook.tts.device:plat.system")
        mock_system.returns("Linux")
        mock_which = bigfoot.mock("spellbook.tts.device:shutil.which")
        mock_which.returns("/usr/bin/nvidia-smi")
        bigfoot.subprocess_mock.mock_run(
            command=["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            returncode=1,
            stdout="",
        )

        with bigfoot:
            result = detect_device()

        assert result == "cpu"
        mock_cfg.assert_call(args=("tts_device",), kwargs={})
        mock_system.assert_call(args=(), kwargs={})
        mock_which.assert_call(args=("nvidia-smi",), kwargs={})
        bigfoot.subprocess_mock.assert_run(
            command=["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            returncode=1,
            stdout="",
            stderr="",
        )

    def test_linux_no_nvidia_smi_returns_cpu(self):
        mock_cfg = bigfoot.mock("spellbook.tts.device:config_get")
        mock_cfg.returns("auto")
        mock_system = bigfoot.mock("spellbook.tts.device:plat.system")
        mock_system.returns("Linux")
        mock_which = bigfoot.mock("spellbook.tts.device:shutil.which")
        mock_which.returns(None)

        with bigfoot:
            result = detect_device()

        assert result == "cpu"
        mock_cfg.assert_call(args=("tts_device",), kwargs={})
        mock_system.assert_call(args=(), kwargs={})
        mock_which.assert_call(args=("nvidia-smi",), kwargs={})

    def test_none_config_treated_as_auto(self):
        mock_cfg = bigfoot.mock("spellbook.tts.device:config_get")
        mock_cfg.returns(None)
        mock_system = bigfoot.mock("spellbook.tts.device:plat.system")
        mock_system.returns("Darwin")
        mock_machine = bigfoot.mock("spellbook.tts.device:plat.machine")
        mock_machine.returns("arm64")

        with bigfoot:
            result = detect_device()

        assert result == "mps"
        mock_cfg.assert_call(args=("tts_device",), kwargs={})
        mock_system.assert_call(args=(), kwargs={})
        mock_machine.assert_call(args=(), kwargs={})
