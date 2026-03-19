"""Shared MCP server state. Tool files import what they need. Server lifecycle manages init/cleanup."""

import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from spellbook.sessions.watcher import SessionWatcher
    from spellbook.updates.watcher import UpdateWatcher

server_start_time: float = time.time()
first_health_check_done: bool = False
last_full_health_check_time: float = 0.0
FULL_HEALTH_CHECK_INTERVAL_SECONDS: float = 300.0
watcher: Optional["SessionWatcher"] = None
update_watcher: Optional["UpdateWatcher"] = None
