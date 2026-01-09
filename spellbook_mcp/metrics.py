"""Feature implementation metrics logging."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any


def get_spellbook_config_dir() -> Path:
    """
    Get the spellbook configuration directory.

    Resolution order:
    1. SPELLBOOK_CONFIG_DIR environment variable
    2. ~/.local/spellbook (default)
    """
    config_dir = os.environ.get('SPELLBOOK_CONFIG_DIR')
    if config_dir:
        return Path(config_dir)

    return Path.home() / '.local' / 'spellbook'


def log_feature_metrics(
    feature_slug: str,
    execution_mode: str,
    oversight_mode: str,
    estimated_tokens: int,
    estimated_percentage: float,
    num_tasks: int,
    num_tracks: int,
    design_context_kb: int,
    impl_plan_kb: int,
    outcome: str,
    duration_minutes: float,
    tracks: List[Dict[str, Any]],
    project_encoded: str
):
    """
    Log feature implementation metrics.

    Args:
        feature_slug: Feature identifier
        execution_mode: swarmed/sequential/delegated/direct
        oversight_mode: autonomous/checkpointed/guided
        estimated_tokens: Token estimate used for mode selection
        estimated_percentage: Percentage of context window
        num_tasks: Total number of tasks
        num_tracks: Number of parallel tracks
        design_context_kb: Size of design context in KB
        impl_plan_kb: Size of impl plan in KB
        outcome: success/failure/aborted
        duration_minutes: Total duration
        tracks: List of track outcomes
        project_encoded: Encoded project path for log directory
    """
    log_dir = get_spellbook_config_dir() / "logs" / project_encoded
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "implement-feature-metrics.jsonl"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "feature_slug": feature_slug,
        "execution_mode": execution_mode,
        "oversight_mode": oversight_mode,
        "estimated_tokens": estimated_tokens,
        "estimated_percentage": estimated_percentage,
        "num_tasks": num_tasks,
        "num_tracks": num_tracks,
        "design_context_kb": design_context_kb,
        "impl_plan_kb": impl_plan_kb,
        "outcome": outcome,
        "duration_minutes": round(duration_minutes, 2),
        "tracks": tracks
    }

    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def get_project_encoded() -> str:
    """
    Get encoded project path for log directories.

    Returns:
        Encoded path like 'Users-alice-Development-myproject'
    """
    import subprocess
    import os

    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        if result.returncode == 0:
            root = result.stdout.strip()
            return root.lstrip('/').replace('/', '-')
    except Exception:
        pass

    return "unknown-project"
