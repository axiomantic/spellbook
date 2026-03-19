"""Output formatting for the spellbook CLI.

Provides a unified ``output()`` function that handles JSON, key-value,
tabular, and plain-string rendering.
"""

from __future__ import annotations

import json
import sys
from typing import IO, Any, Sequence


def output(
    data: Any,
    *,
    json_mode: bool = False,
    headers: Sequence[str] | None = None,
    file: IO[str] | None = None,
) -> None:
    """Format and print *data* according to its type and *json_mode*.

    Parameters
    ----------
    data:
        The data to render.  Supported shapes: ``dict``, ``list[dict]``,
        ``str``, or any object convertible via ``str()``.
    json_mode:
        When ``True``, emit ``json.dumps(data, indent=2, default=str)``.
    headers:
        Column headers for tabular (list-of-dicts) output.  Ignored in
        JSON mode.  When ``None``, headers are inferred from dict keys.
    file:
        Writable text stream.  Defaults to ``sys.stdout``.
    """
    if file is None:
        file = sys.stdout

    if json_mode:
        _render_json(data, file)
    elif isinstance(data, dict):
        _render_dict(data, file)
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        _render_table(data, headers, file)
    else:
        print(data, file=file)


# -- private renderers -------------------------------------------------------


def _render_json(data: Any, file: IO[str]) -> None:
    print(json.dumps(data, indent=2, default=str), file=file)


def _render_dict(data: dict, file: IO[str]) -> None:
    if not data:
        return
    max_key = max(len(str(k)) for k in data)
    for key, value in data.items():
        print(f"{str(key):>{max_key}}: {value}", file=file)


def _render_table(
    rows: list[dict],
    headers: Sequence[str] | None,
    file: IO[str],
) -> None:
    if not rows:
        return

    cols = list(headers) if headers else list(rows[0].keys())

    # Calculate column widths (header vs data)
    widths: dict[str, int] = {}
    for col in cols:
        header_len = len(col)
        data_len = max((len(str(row.get(col, ""))) for row in rows), default=0)
        widths[col] = max(header_len, data_len)

    # Header row
    header_line = "  ".join(
        f"{col.upper():<{widths[col]}}" for col in cols
    )
    print(header_line, file=file)

    # Data rows
    for row in rows:
        line = "  ".join(
            f"{str(row.get(col, '')):<{widths[col]}}" for col in cols
        )
        print(line, file=file)
