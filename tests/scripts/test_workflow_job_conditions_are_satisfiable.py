"""Every workflow job's ``if:`` must be reachable from that workflow's triggers.

The defect this guards: ``docs.yml`` carried a ``build`` job gated on
``if: github.event_name == 'pull_request'`` while the workflow declared no
``pull_request`` trigger. The job could not run under any event and never
had. Nothing failed; the job simply did not appear, and a job listed in a
workflow file reads as coverage to anyone auditing CI.

Full GitHub expression evaluation is out of reach, so this check targets one
tractable shape: a job whose ``if:`` compares ``github.event_name`` for
equality against literals, none of which the workflow declares under ``on:``.
Such a predicate is false under every event the workflow can receive.

Known blind spots -- shapes this check deliberately does not decide:

* Inequality and negation (``!=``, ``!``, ``&&`` of two distinct event
  names). A predicate is flagged only when every equality literal it
  mentions is undeclared, which keeps ``||`` chains exact and makes
  ``&&`` chains a false negative rather than a false positive.
* Predicates that reference ``github.event.action``, ``contains()``,
  ``inputs``, secrets, or job/step outputs. Their reachability depends on
  runtime state.
* Step-level ``if:``. Only job-level conditions are examined.
* Trigger filters (``branches``, ``paths``, ``types``). A declared event
  whose filters never match is still counted as declared.
* Reusable workflows invoked via ``workflow_call`` from another workflow --
  the caller's event is not visible here.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# `on` is parsed by PyYAML 1.1 boolean rules as True, not the string "on".
_ON_KEYS = ("on", True)

_EVENT_EQUALITY = re.compile(
    r"github\.event_name\s*==\s*['\"]([A-Za-z_]+)['\"]"
)


def _declared_events(workflow: dict) -> set[str]:
    for key in _ON_KEYS:
        if key in workflow:
            triggers = workflow[key]
            break
    else:
        return set()

    if isinstance(triggers, str):
        return {triggers}
    if isinstance(triggers, list):
        return set(triggers)
    if isinstance(triggers, dict):
        return set(triggers)
    raise TypeError(f"Unrecognized `on:` form: {triggers!r}")


def unreachable_jobs(workflow: dict) -> list[tuple[str, str, set[str]]]:
    """Return ``(job, predicate, tested_events)`` for each unreachable job."""
    declared = _declared_events(workflow)
    findings = []
    for name, job in (workflow.get("jobs") or {}).items():
        condition = job.get("if")
        if not isinstance(condition, str):
            continue
        tested = set(_EVENT_EQUALITY.findall(condition))
        if tested and not (tested & declared):
            findings.append((name, condition, tested))
    return findings


WORKFLOWS = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))


def test_workflows_are_discovered():
    """A glob that silently found nothing would pass every check below."""
    assert WORKFLOWS, f"No workflow files found under {WORKFLOW_DIR}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_job_conditions_are_reachable(path: Path):
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    declared = _declared_events(workflow)
    assert declared, f"{path.name} declares no triggers under `on:`"

    findings = unreachable_jobs(workflow)
    assert not findings, "\n".join(
        f"{path.name}: job {job!r} is gated on {condition!r}, but the "
        f"workflow declares only {sorted(declared)}. The job can never run."
        for job, condition, _ in findings
    )


def test_detector_flags_an_undeclared_event():
    """Negative control: the detector must name a planted unreachable job."""
    planted = yaml.safe_load(
        "on:\n"
        "  push:\n"
        "    branches: [master]\n"
        "jobs:\n"
        "  build:\n"
        "    if: github.event_name == 'pull_request'\n"
        "    runs-on: ubuntu-latest\n"
    )
    assert unreachable_jobs(planted) == [
        ("build", "github.event_name == 'pull_request'", {"pull_request"})
    ]


def test_detector_accepts_a_declared_event_in_an_or_chain():
    """A predicate satisfiable through either branch must not be flagged."""
    accepted = yaml.safe_load(
        "on:\n"
        "  push:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  deploy:\n"
        "    if: github.event_name == 'pull_request' || "
        "github.event_name == 'push'\n"
        "    runs-on: ubuntu-latest\n"
    )
    assert unreachable_jobs(accepted) == []
