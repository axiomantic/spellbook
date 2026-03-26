"""Tests for spellbook.cli.commands.events - real-time event streaming command."""

import argparse
import json
import sys
from unittest.mock import patch

import pytest

from spellbook.cli.commands.events import register


class TestRegister:
    """Tests for register()."""

    def test_registers_events_subcommand(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["events"])
        assert hasattr(args, "func")

    def test_events_help_exits_zero(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["events", "--help"])
        assert exc_info.value.code == 0

    def test_events_follow_is_default(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["events"])
        assert args.follow is True

    def test_events_json_flag(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--json", action="store_true", default=False)
        subparsers = parser.add_subparsers()
        register(subparsers)
        args = parser.parse_args(["--json", "events"])
        assert args.json is True


class TestEventsRun:
    """Tests for events command handling no daemon."""

    def test_events_no_daemon_shows_error(self, capsys):
        """Events with no daemon shows clear error message."""
        # Make stream_events raise ConnectionError.
        # Patch on the daemon_client module so the lazy
        # ``from spellbook.cli.daemon_client import stream_events``
        # inside _run_events picks up the mock.
        def fake_stream_events(*args, **kwargs):
            raise ConnectionError("Cannot connect")

        with patch(
            "spellbook.cli.daemon_client.stream_events",
            fake_stream_events,
        ):
            parser = argparse.ArgumentParser()
            parser.add_argument("--json", action="store_true", default=False)
            subparsers = parser.add_subparsers()
            register(subparsers)

            args = parser.parse_args(["events"])
            with pytest.raises(SystemExit) as exc_info:
                args.func(args)
            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "spellbook server start" in captured.err
