"""Map FractalResult harvest output to Forged Feedback objects.

Transforms fractal thinking findings (convergence points, tensions,
boundary questions, synthesis chain) into structured Feedback that
the Forge iteration system can act on.
"""

from spellbook_mcp.forged.models import Feedback


def fractal_to_feedback(
    harvest_result: dict,
    current_stage: str,
    iteration: int,
) -> list[Feedback]:
    """Convert a FractalResult harvest JSON to Feedback objects.

    Mapping rules:
    - Convergence findings -> Feedback with concrete remediation suggestions
    - Unresolved tensions -> Feedback highlighting the tension to resolve
    - Boundary questions with findings -> Feedback with cross-cutting insights
    - Gaps -> Feedback noting unexplored areas (severity: minor)
    - Synthesis chain depth-1 entries -> Return-stage recommendations

    Args:
        harvest_result: The full JSON output from fractal-think-harvest
        current_stage: The Forge stage where ITERATE occurred
        iteration: Current iteration number

    Returns:
        List of Feedback objects, ordered by severity (blocking first)
    """
    feedbacks = []

    # Compute suggested return stage ONCE for all convergence findings
    suggested_stage = suggest_return_stage(harvest_result, current_stage)

    # Map convergence findings (HIGH confidence -> blocking/significant)
    for finding in harvest_result.get("findings", []):
        if finding.get("type") == "convergence":
            feedbacks.append(
                _convergence_to_feedback(finding, current_stage, iteration, suggested_stage, harvest_result)
            )
        elif finding.get("type") == "tension" and finding.get("status") == "UNRESOLVED":
            feedbacks.append(
                _tension_to_feedback(finding, current_stage, iteration)
            )
        elif finding.get("type") == "gap":
            feedbacks.append(
                _gap_to_feedback(finding, current_stage, iteration)
            )

    # Map boundary question findings
    for bq in harvest_result.get("boundary_questions", []):
        if bq.get("status") in ("answered", "synthesized") and bq.get("finding"):
            feedbacks.append(
                _boundary_to_feedback(bq, current_stage, iteration)
            )

    # Sort: blocking first, then significant, then minor
    severity_order = {"blocking": 0, "significant": 1, "minor": 2}
    feedbacks.sort(key=lambda f: severity_order.get(f.severity, 3))

    return feedbacks


def suggest_return_stage(
    harvest_result: dict,
    current_stage: str,
) -> str | None:
    """Analyze fractal synthesis to recommend a return stage.

    Examines the synthesis chain and findings to determine if the
    root cause lives in an earlier stage than the current one.

    Returns:
        Suggested stage name, or None if current stage is appropriate.
        Caller is responsible for applying guardrails (1-stage auto,
        2+ stages needs confirmation).
    """
    # Stage ordering for distance calculation
    stage_order = ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]

    if current_stage not in stage_order:
        return None

    current_idx = stage_order.index(current_stage)

    # Scan synthesis chain for stage-indicating keywords
    synthesis_chain = harvest_result.get("synthesis_chain", [])
    root_synthesis = ""
    if synthesis_chain:
        root_synthesis = synthesis_chain[0].get("synthesis", "")

    # Scan convergence findings for root cause location hints
    findings = harvest_result.get("findings", [])

    # Keyword-to-stage mapping for root cause detection
    stage_indicators = {
        "DISCOVER": [
            "requirements missing",
            "requirements gap",
            "undiscovered",
            "not gathered",
            "stakeholder",
            "use case missing",
            "scope unclear",
        ],
        "DESIGN": [
            "architecture",
            "design flaw",
            "interface mismatch",
            "abstraction",
            "coupling",
            "design decision",
            "component boundary",
            "API contract",
        ],
        "PLAN": [
            "task breakdown",
            "dependency missing",
            "ordering",
            "estimation",
            "plan gap",
            "work sequence",
        ],
    }

    # Only consider stages earlier than current
    candidate_stages = {}
    for stage, keywords in stage_indicators.items():
        stage_idx = stage_order.index(stage)
        if stage_idx >= current_idx:
            continue
        # Count keyword hits across root synthesis + convergence insights
        text_corpus = root_synthesis.lower()
        for f in findings:
            if f.get("type") == "convergence" and f.get("insight"):
                text_corpus += " " + f["insight"].lower()
        hits = sum(1 for kw in keywords if kw in text_corpus)
        if hits >= 2:
            candidate_stages[stage] = hits

    if not candidate_stages:
        return None

    # Return the stage with the most keyword hits
    return max(candidate_stages, key=candidate_stages.get)


def _convergence_to_feedback(
    finding: dict,
    stage: str,
    iteration: int,
    suggested_stage: str | None,
    harvest_result: dict | None = None,
) -> Feedback:
    """Map a convergence finding to Feedback."""
    supporting = finding.get("supporting_nodes", "multiple")
    insight = finding.get("insight", "Fractal analysis identified convergent concern")

    return Feedback(
        source="fractal-analysis",
        stage=stage,
        return_to=suggested_stage or stage,
        critique=f"Fractal convergence ({supporting} branches): {insight}",
        evidence=(
            f"Identified via fractal exploration with {supporting} "
            f"independent branches converging on same conclusion"
        ),
        suggestion=_extract_remediation(insight, harvest_result or {}),
        severity="blocking",
        iteration=iteration,
    )


def _tension_to_feedback(
    finding: dict,
    stage: str,
    iteration: int,
) -> Feedback:
    """Map an unresolved tension to Feedback."""
    description = finding.get("description", "Unresolved architectural tension")

    return Feedback(
        source="fractal-analysis",
        stage=stage,
        return_to=stage,
        critique=f"Unresolved tension: {description}",
        evidence=(
            "Fractal exploration found contradictory approaches "
            "that have not been reconciled"
        ),
        suggestion=(
            f"Resolve the tension between the competing approaches "
            f"before proceeding. Consider: {description}"
        ),
        severity="significant",
        iteration=iteration,
    )


def _gap_to_feedback(
    finding: dict,
    stage: str,
    iteration: int,
) -> Feedback:
    """Map an unexplored gap to Feedback."""
    question = finding.get("question", "Unexplored area identified")
    reason = finding.get("reason", "not_reached")

    return Feedback(
        source="fractal-analysis",
        stage=stage,
        return_to=stage,
        critique=f"Unexplored area: {question}",
        evidence=(
            f"Fractal exploration could not reach this area "
            f"(reason: {reason})"
        ),
        suggestion=f"Consider investigating: {question}",
        severity="minor",
        iteration=iteration,
    )


def _boundary_to_feedback(
    boundary_question: dict,
    stage: str,
    iteration: int,
) -> Feedback:
    """Map a boundary question finding to Feedback."""
    question = boundary_question.get("question", "Cross-cutting concern")
    finding_text = boundary_question.get("finding", "")

    return Feedback(
        source="fractal-analysis",
        stage=stage,
        return_to=stage,
        critique=f"Cross-cutting insight: {question}",
        evidence=(
            f"Boundary exploration between converging branches: "
            f"{finding_text[:200]}"
        ),
        suggestion=(
            finding_text[:500]
            if finding_text
            else f"Investigate cross-cutting concern: {question}"
        ),
        severity="significant",
        iteration=iteration,
    )


def _extract_remediation(insight: str, harvest_result: dict) -> str:
    """Extract a concrete remediation plan from the fractal synthesis.

    Uses the root synthesis as the primary source for remediation
    guidance, falling back to the convergence insight itself.
    """
    synthesis_chain = harvest_result.get("synthesis_chain", [])
    if synthesis_chain:
        root_synthesis = synthesis_chain[0].get("synthesis", "")
        if root_synthesis:
            # Truncate to reasonable suggestion length
            return root_synthesis[:800]
    return f"Address the root cause identified by fractal analysis: {insight}"
