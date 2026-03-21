"""Subsystem health matrix API routes.

Probes all four SQLite databases and reports table counts,
last activity, file sizes, and overall status.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from spellbook.admin.auth import require_admin_auth
from spellbook.db import (
    get_coordination_session,
    get_forged_session,
    get_fractal_session,
    get_spellbook_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


def _get_db_paths() -> dict[str, str]:
    """Return mapping of database name to file path."""
    from spellbook.core.db import get_db_path
    from spellbook.fractal.schema import get_fractal_db_path
    from spellbook.forged.schema import get_forged_db_path

    base_dir = Path.home() / ".local" / "spellbook"
    return {
        "spellbook.db": str(get_db_path()),
        "fractal.db": str(get_fractal_db_path()),
        "forged.db": str(get_forged_db_path()),
        "coordination.db": str(base_dir / "coordination.db"),
    }


def _get_session_factory(db_name: str) -> Any:
    """Get the async session context manager factory for a database by name.

    Uses module-level references so patching works in tests.
    """
    return {
        "spellbook.db": get_spellbook_session,
        "fractal.db": get_fractal_session,
        "forged.db": get_forged_session,
        "coordination.db": get_coordination_session,
    }[db_name]


async def _probe_database(
    name: str, path: str, session_factory: Any
) -> dict[str, Any]:
    """Probe a single database and return its health info."""
    if not os.path.exists(path):
        return {
            "name": name,
            "status": "missing",
            "size_bytes": 0,
            "tables": [],
        }

    try:
        size_bytes = os.path.getsize(path)

        async with session_factory() as session:
            # Get table list
            result = await session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            )
            table_rows = result.mappings().all()

            tables = []
            has_recent_activity = False
            now = datetime.now(timezone.utc)

            for table_row in table_rows:
                table_name = table_row["name"]
                table_info: dict[str, Any] = {
                    "name": table_name,
                    "row_count": 0,
                    "last_activity": None,
                    "error_count": None,
                }

                # Row count
                try:
                    count_result = await session.execute(
                        text(f"SELECT COUNT(*) as cnt FROM [{table_name}]")
                    )
                    count_rows = count_result.mappings().all()
                    table_info["row_count"] = count_rows[0]["cnt"] if count_rows else 0
                except Exception:
                    table_info["row_count"] = -1

                # Last activity (try common timestamp column names)
                for ts_col in ("created_at", "updated_at", "timestamp", "last_activity"):
                    try:
                        ts_result = await session.execute(
                            text(f"SELECT MAX([{ts_col}]) as latest FROM [{table_name}]")
                        )
                        ts_rows = ts_result.mappings().all()
                        if ts_rows and ts_rows[0]["latest"]:
                            table_info["last_activity"] = ts_rows[0]["latest"]
                            # Check if recent (within 24h)
                            try:
                                ts = datetime.fromisoformat(
                                    ts_rows[0]["latest"].replace("Z", "+00:00")
                                )
                                if (now - ts).total_seconds() < 86400:
                                    has_recent_activity = True
                            except (ValueError, TypeError):
                                pass
                            break
                    except Exception:
                        continue

                tables.append(table_info)

        status = "healthy" if has_recent_activity else "idle"

        return {
            "name": name,
            "status": status,
            "size_bytes": size_bytes,
            "tables": tables,
        }

    except Exception as exc:
        logger.error(f"Error probing {name}: {exc}")
        return {
            "name": name,
            "status": "error",
            "size_bytes": 0,
            "tables": [],
        }


@router.get("/matrix")
async def health_matrix(
    _session: str = Depends(require_admin_auth),
):
    """Full health matrix across all databases."""
    db_paths = _get_db_paths()

    tasks = []
    for db_name, db_path in db_paths.items():
        session_factory = _get_session_factory(db_name)
        tasks.append(_probe_database(db_name, db_path, session_factory))

    databases = await asyncio.gather(*tasks)

    return {
        "databases": list(databases),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
