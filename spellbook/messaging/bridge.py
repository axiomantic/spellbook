"""MessageBridge: SSE-to-inbox daemon thread.

Consumes the SSE stream from the spellbook MCP server and writes
per-message JSON files to an inbox directory. A hook reads and
injects these messages into the AI session.
"""

import json
import logging
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class MessageBridge:
    """Consumes SSE stream and writes per-message files to inbox directory for AI session injection."""

    def __init__(
        self,
        alias: str,
        server_url: str,
        token: str,
        inbox_dir: Path,
    ):
        self.alias = alias
        self.server_url = server_url
        self.token = token
        self.inbox_dir = inbox_dir
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the bridge in a daemon thread."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(
            target=self._run,
            name=f"msg-bridge-{self.alias}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the bridge to stop."""
        self._stop_event.set()

    def _run(self) -> None:
        """Main loop: connect to SSE, write messages to inbox directory.

        SSE line-type filtering: skip empty lines, comment lines (starting
        with ':'), 'event:' lines, and 'id:' lines. Only process 'data:'
        lines.
        """
        url = f"{self.server_url}/messaging/stream/{self.alias}"
        headers = {"Authorization": f"Bearer {self.token}"}
        backoff = 1

        while not self._stop_event.is_set():
            try:
                with httpx.stream("GET", url, headers=headers, timeout=None) as response:
                    response.raise_for_status()
                    backoff = 1  # Reset on successful connect
                    data_buffer: list[str] = []
                    for line in response.iter_lines():
                        if self._stop_event.is_set():
                            break
                        # SSE spec: accumulate data: lines, dispatch on empty line
                        if line.startswith("data:"):
                            value = line[5:]
                            if value.startswith(" "):
                                value = value[1:]
                            data_buffer.append(value)
                        elif line == "" and data_buffer:
                            self._write_to_inbox("\n".join(data_buffer))
                            data_buffer = []
                        # Skip comment lines (:), event lines, id lines
            except Exception:
                logger.debug(f"Bridge reconnecting in {backoff}s", exc_info=True)
                self._stop_event.wait(backoff)
                backoff = min(backoff * 2, 30)

    def _write_to_inbox(self, data: str) -> None:
        """Write message as individual file in inbox directory.

        Uses atomic write (temp file + rename) to prevent partial reads.
        """
        try:
            msg_id = json.loads(data).get("id", uuid.uuid4().hex)
            final_path = self.inbox_dir / f"{msg_id}.json"
            # Atomic write: write to temp file in same directory, then rename
            fd, tmp_path = tempfile.mkstemp(dir=self.inbox_dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(data)
                os.rename(tmp_path, final_path)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception:
            logger.error("Failed to write to inbox", exc_info=True)
