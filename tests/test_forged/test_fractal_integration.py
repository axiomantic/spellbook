"""Integration tests for fractal feedback pipeline.

Tests that fractal_feedback.py components and roundtable._determine_return_stage
work together correctly as a pipeline: harvest result -> fractal_to_feedback ->
suggest_return_stage -> _determine_return_stage -> (stage, needs_confirm).
"""

from spellbook_mcp.forged.fractal_feedback import (
    fractal_to_feedback,
    suggest_return_stage,
)
from spellbook_mcp.forged.models import Feedback
from spellbook_mcp.forged.roundtable import _determine_return_stage


class TestEscalationNotTriggeredIteration1:
    """When iteration=1 and <2 blocking items, fractal should NOT be called.

    This tests the escalation condition logic: iteration 1 with only 1 blocking
    item should produce standard feedback, not fractal-derived feedback. The
    escalation decision lives in reflexion-analyze (a command), but we verify
    the condition here by showing that a single blocking item on iteration 1
    produces a normal (non-fractal) feedback set when processed through the
    mapper -- demonstrating that the mapper itself works correctly regardless,
    and the escalation gate is purely the caller's responsibility.

    The local arithmetic escalation condition tests (e.g. test_escalation_conditions_not_met)
    document the contract for the reflexion-analyze command's escalation logic, which lives
    in a markdown command file and is not directly testable as Python.
    """

    def test_iteration_1_single_blocking_produces_standard_feedback(self):
        """Iteration 1 with 1 blocking item: fractal_to_feedback still works,
        but the escalation condition (iteration >= 2 OR 2+ blocking) is not met.

        We verify by showing that even if someone passes iteration=1 data through
        the mapper, the output is well-formed but the escalation decision is
        external. The key integration point: the feedback produced has
        source='fractal-analysis', which the caller would only see if they
        incorrectly escalated.
        """
        # Simulate a harvest result that would come from fractal analysis
        # In practice, this would NOT be generated for iteration=1 with <2 blocking
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "Minor code style issue",
                    "supporting_nodes": 2,
                }
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        # The mapper produces feedback regardless of iteration number
        result = fractal_to_feedback(harvest, "IMPLEMENT", 1)

        # Verify: mapper works, but all items are fractal-analysis sourced
        # The escalation gate (iteration >= 2 OR 2+ blocking) is the caller's job
        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Fractal convergence (2 branches): Minor code style issue",
                evidence="Identified via fractal exploration with 2 independent branches converging on same conclusion",
                suggestion="Address the root cause identified by fractal analysis: Minor code style issue",
                severity="blocking",
                iteration=1,
            )
        ]

    def test_escalation_conditions_not_met(self):
        """Verify the escalation condition logic directly.

        Escalation triggers when EITHER:
        1. iteration >= 2 AND same stage as previous iteration
        2. 2+ blocking items in current feedback

        This test shows condition evaluation for iteration=1, 1 blocking item.
        """
        iteration = 1
        blocking_count = 1
        current_stage = "IMPLEMENT"
        previous_stage = None  # No previous iteration

        # Condition 1: iteration >= 2 AND same stage
        condition_1 = iteration >= 2 and current_stage == previous_stage
        # Condition 2: 2+ blocking items
        condition_2 = blocking_count >= 2

        should_escalate = condition_1 or condition_2

        assert should_escalate == False
        assert condition_1 == False
        assert condition_2 == False


class TestEscalationTriggeredRepeatedStage:
    """When iteration >= 2 on same stage, full flow works end-to-end.

    The inline escalation condition checks (condition_1 assertions) document the contract
    for the reflexion-analyze command's escalation logic, which lives in a markdown command
    file and is not directly testable as Python.
    """

    def test_repeated_stage_iteration_2_full_flow(self):
        """Iteration 2 on same stage: harvest -> fractal_to_feedback -> Feedback
        objects with source='fractal-analysis'.
        """
        # Escalation condition check
        iteration = 2
        current_stage = "IMPLEMENT"
        previous_stage = "IMPLEMENT"
        condition_1 = iteration >= 2 and current_stage == previous_stage

        assert condition_1 == True

        # Simulate fractal harvest result from the escalated analysis
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "The API contract between services is inconsistent",
                    "supporting_nodes": 3,
                },
                {
                    "type": "tension",
                    "status": "UNRESOLVED",
                    "description": "REST vs GraphQL approach conflict",
                },
            ],
            "boundary_questions": [
                {
                    "question": "Does the auth layer affect API contracts?",
                    "status": "answered",
                    "finding": "Auth middleware modifies request shapes",
                },
            ],
            "synthesis_chain": [
                {"synthesis": "The interface mismatch and coupling between services is the root cause"}
            ],
        }

        # Run the mapper
        feedbacks = fractal_to_feedback(harvest, current_stage, iteration)

        # Verify all feedback has fractal-analysis source
        assert len(feedbacks) == 3

        # synthesis has "interface mismatch" + "coupling" -> 2 DESIGN keyword hits
        # So convergence return_to should be DESIGN
        assert feedbacks == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="DESIGN",
                critique="Fractal convergence (3 branches): The API contract between services is inconsistent",
                evidence="Identified via fractal exploration with 3 independent branches converging on same conclusion",
                suggestion="The interface mismatch and coupling between services is the root cause",
                severity="blocking",
                iteration=2,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Unresolved tension: REST vs GraphQL approach conflict",
                evidence="Fractal exploration found contradictory approaches that have not been reconciled",
                suggestion="Resolve the tension between the competing approaches before proceeding. Consider: REST vs GraphQL approach conflict",
                severity="significant",
                iteration=2,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Cross-cutting insight: Does the auth layer affect API contracts?",
                evidence="Boundary exploration between converging branches: Auth middleware modifies request shapes",
                suggestion="Auth middleware modifies request shapes",
                severity="significant",
                iteration=2,
            ),
        ]

    def test_repeated_stage_iteration_3(self):
        """Iteration 3 on same stage also triggers escalation."""
        iteration = 3
        current_stage = "DESIGN"
        previous_stage = "DESIGN"
        condition_1 = iteration >= 2 and current_stage == previous_stage

        assert condition_1 == True

        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "requirements missing and stakeholder needs not gathered",
                    "supporting_nodes": 4,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "The requirements gap and undiscovered use case missing from initial analysis"}
            ],
        }

        feedbacks = fractal_to_feedback(harvest, current_stage, iteration)

        # DISCOVER keywords: "requirements missing" (insight), "stakeholder" (insight),
        # "not gathered" (insight), "requirements gap" (synthesis), "undiscovered" (synthesis),
        # "use case missing" (synthesis) -> 6 hits for DISCOVER
        # But current_stage is DESIGN, and DISCOVER is earlier, so return_to = DISCOVER
        assert feedbacks == [
            Feedback(
                source="fractal-analysis",
                stage="DESIGN",
                return_to="DISCOVER",
                critique="Fractal convergence (4 branches): requirements missing and stakeholder needs not gathered",
                evidence="Identified via fractal exploration with 4 independent branches converging on same conclusion",
                suggestion="The requirements gap and undiscovered use case missing from initial analysis",
                severity="blocking",
                iteration=3,
            )
        ]


class TestEscalationTriggeredMultipleBlocking:
    """When 2+ blocking items exist, fractal_to_feedback produces correct Feedback set.

    The inline escalation condition checks (condition_2 assertions) document the contract
    for the reflexion-analyze command's escalation logic, which lives in a markdown command
    file and is not directly testable as Python.
    """

    def test_two_blocking_items_triggers_escalation(self):
        """2 blocking items on iteration 1 triggers condition 2."""
        iteration = 1
        blocking_count = 2

        # Condition 2: 2+ blocking items
        condition_2 = blocking_count >= 2

        assert condition_2 == True

        # Simulate the fractal harvest from this escalation
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "Database schema design is fundamentally flawed",
                    "supporting_nodes": 3,
                },
                {
                    "type": "convergence",
                    "insight": "Error handling architecture has design flaw and coupling issues",
                    "supporting_nodes": 2,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "Multiple architecture problems stem from a design decision made early on"}
            ],
        }

        feedbacks = fractal_to_feedback(harvest, "IMPLEMENT", iteration)

        # Both convergence findings should be blocking
        assert len(feedbacks) == 2

        # DESIGN keywords in corpus:
        # synthesis: "architecture", "design decision" -> 2 hits
        # insight 1: none specific to DESIGN stage keywords
        # insight 2: "design flaw", "coupling" -> 2 more hits
        # Total DESIGN hits: 4 -> return_to = DESIGN
        assert feedbacks == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="DESIGN",
                critique="Fractal convergence (3 branches): Database schema design is fundamentally flawed",
                evidence="Identified via fractal exploration with 3 independent branches converging on same conclusion",
                suggestion="Multiple architecture problems stem from a design decision made early on",
                severity="blocking",
                iteration=1,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="DESIGN",
                critique="Fractal convergence (2 branches): Error handling architecture has design flaw and coupling issues",
                evidence="Identified via fractal exploration with 2 independent branches converging on same conclusion",
                suggestion="Multiple architecture problems stem from a design decision made early on",
                severity="blocking",
                iteration=1,
            ),
        ]

    def test_three_blocking_items_also_triggers(self):
        """3 blocking items also satisfies condition 2."""
        blocking_count = 3
        condition_2 = blocking_count >= 2

        assert condition_2 == True

        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "Issue one",
                    "supporting_nodes": 2,
                },
                {
                    "type": "convergence",
                    "insight": "Issue two",
                    "supporting_nodes": 3,
                },
                {
                    "type": "convergence",
                    "insight": "Issue three",
                    "supporting_nodes": 2,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        feedbacks = fractal_to_feedback(harvest, "PLAN", 1)

        assert len(feedbacks) == 3
        assert feedbacks == [
            Feedback(
                source="fractal-analysis",
                stage="PLAN",
                return_to="PLAN",
                critique="Fractal convergence (2 branches): Issue one",
                evidence="Identified via fractal exploration with 2 independent branches converging on same conclusion",
                suggestion="Address the root cause identified by fractal analysis: Issue one",
                severity="blocking",
                iteration=1,
            ),
            Feedback(
                source="fractal-analysis",
                stage="PLAN",
                return_to="PLAN",
                critique="Fractal convergence (3 branches): Issue two",
                evidence="Identified via fractal exploration with 3 independent branches converging on same conclusion",
                suggestion="Address the root cause identified by fractal analysis: Issue two",
                severity="blocking",
                iteration=1,
            ),
            Feedback(
                source="fractal-analysis",
                stage="PLAN",
                return_to="PLAN",
                critique="Fractal convergence (2 branches): Issue three",
                evidence="Identified via fractal exploration with 2 independent branches converging on same conclusion",
                suggestion="Address the root cause identified by fractal analysis: Issue three",
                severity="blocking",
                iteration=1,
            ),
        ]


class TestFractalFeedbackToReturnStagePipeline:
    """End-to-end: harvest -> fractal_to_feedback + suggest_return_stage ->
    _determine_return_stage -> correct (stage, needs_confirm) tuple.
    """

    def test_full_pipeline_plan_suggestion_from_implement(self):
        """Full pipeline: IMPLEMENT -> fractal suggests PLAN -> _determine_return_stage."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "The task breakdown has dependency missing in the ordering of work",
                    "supporting_nodes": 4,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "Work sequence estimation was fundamentally flawed"}
            ],
        }

        # Step 1: Map harvest to feedback
        feedbacks = fractal_to_feedback(harvest, "IMPLEMENT", 2)

        # Step 2: Get stage suggestion
        suggested_stage = suggest_return_stage(harvest, "IMPLEMENT")

        # PLAN keywords: "task breakdown", "dependency missing", "ordering" (insight),
        # "work sequence", "estimation" (synthesis) -> 5 hits
        assert suggested_stage == "PLAN"

        # Step 3: Apply guardrails via _determine_return_stage
        stage, needs_confirm = _determine_return_stage("IMPLEMENT", fractal_suggestion=suggested_stage)

        # IMPLEMENT (idx 3) -> PLAN (idx 2) is 1 stage back, auto-approved
        assert stage == "PLAN"
        assert needs_confirm == False

        # Step 4: Verify feedback return_to matches
        assert feedbacks[0].return_to == "PLAN"

    def test_full_pipeline_discover_suggestion_from_implement(self):
        """Full pipeline: IMPLEMENT -> fractal suggests DISCOVER -> needs confirmation."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "requirements missing from stakeholder analysis not gathered properly",
                    "supporting_nodes": 5,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "The requirements gap and undiscovered needs are fundamental"}
            ],
        }

        # Step 1: Map harvest to feedback
        feedbacks = fractal_to_feedback(harvest, "IMPLEMENT", 3)

        # Step 2: Get stage suggestion
        suggested_stage = suggest_return_stage(harvest, "IMPLEMENT")

        # DISCOVER keywords: "requirements missing" (insight), "stakeholder" (insight),
        # "not gathered" (insight), "requirements gap" (synthesis), "undiscovered" (synthesis)
        assert suggested_stage == "DISCOVER"

        # Step 3: Apply guardrails
        stage, needs_confirm = _determine_return_stage("IMPLEMENT", fractal_suggestion=suggested_stage)

        # IMPLEMENT -> DISCOVER is 3 stages back, needs confirmation
        assert stage == "DISCOVER"
        assert needs_confirm == True

        # Step 4: Verify feedback return_to matches
        assert feedbacks[0].return_to == "DISCOVER"

    def test_full_pipeline_no_suggestion(self):
        """Full pipeline: no stage keywords -> stays at current stage."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "General code quality concern",
                    "supporting_nodes": 2,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "The code has some quality issues that need attention"}
            ],
        }

        feedbacks = fractal_to_feedback(harvest, "IMPLEMENT", 2)
        suggested_stage = suggest_return_stage(harvest, "IMPLEMENT")

        assert suggested_stage is None

        stage, needs_confirm = _determine_return_stage("IMPLEMENT", fractal_suggestion=suggested_stage)

        assert stage == "IMPLEMENT"
        assert needs_confirm == False
        assert feedbacks[0].return_to == "IMPLEMENT"


class TestReturnStageGuardrail1Back:
    """Pipeline with 1-stage-back suggestion produces auto-approved result."""

    def test_implement_to_plan_auto_approved(self):
        """IMPLEMENT -> PLAN is 1 stage back, auto-approved."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "The task breakdown has a dependency missing in ordering",
                    "supporting_nodes": 3,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "Work sequence estimation was incorrect"}
            ],
        }

        suggested = suggest_return_stage(harvest, "IMPLEMENT")

        # PLAN keywords: "task breakdown", "dependency missing", "ordering" (insight),
        # "work sequence", "estimation" (synthesis) -> 5 hits for PLAN
        assert suggested == "PLAN"

        stage, needs_confirm = _determine_return_stage("IMPLEMENT", fractal_suggestion=suggested)

        assert stage == "PLAN"
        assert needs_confirm == False

    def test_plan_to_design_auto_approved(self):
        """PLAN -> DESIGN is 1 stage back, auto-approved."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "The architecture and coupling between modules is problematic",
                    "supporting_nodes": 2,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "A design flaw in the abstraction layer causes cascading issues"}
            ],
        }

        suggested = suggest_return_stage(harvest, "PLAN")

        # DESIGN keywords: "architecture", "coupling" (insight),
        # "design flaw", "abstraction" (synthesis) -> 4 hits
        assert suggested == "DESIGN"

        stage, needs_confirm = _determine_return_stage("PLAN", fractal_suggestion=suggested)

        assert stage == "DESIGN"
        assert needs_confirm == False

    def test_design_to_discover_auto_approved(self):
        """DESIGN -> DISCOVER is 1 stage back, auto-approved."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "Critical requirements missing from stakeholder input not gathered",
                    "supporting_nodes": 3,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "The scope unclear and use case missing from initial discovery"}
            ],
        }

        suggested = suggest_return_stage(harvest, "DESIGN")

        # DISCOVER keywords: "requirements missing" (insight), "stakeholder" (insight),
        # "not gathered" (insight), "scope unclear" (synthesis), "use case missing" (synthesis)
        assert suggested == "DISCOVER"

        stage, needs_confirm = _determine_return_stage("DESIGN", fractal_suggestion=suggested)

        assert stage == "DISCOVER"
        assert needs_confirm == False


class TestReturnStageGuardrail2PlusBack:
    """Pipeline with 2-stage-back suggestion produces needs_confirmation=True."""

    def test_implement_to_discover_3_back(self):
        """IMPLEMENT -> DISCOVER is 3 stages back (needs confirmation)."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "requirements missing from stakeholder needs not gathered",
                    "supporting_nodes": 4,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "Undiscovered use case missing from initial requirements gap analysis"}
            ],
        }

        suggested = suggest_return_stage(harvest, "IMPLEMENT")

        # DISCOVER keywords: "requirements missing", "stakeholder", "not gathered" (insight),
        # "undiscovered", "use case missing", "requirements gap" (synthesis) -> 6 hits
        assert suggested == "DISCOVER"

        stage, needs_confirm = _determine_return_stage("IMPLEMENT", fractal_suggestion=suggested)

        # IMPLEMENT (idx 3) -> DISCOVER (idx 0) = distance 3, needs confirmation
        assert stage == "DISCOVER"
        assert needs_confirm == True

    def test_complete_to_design_3_back(self):
        """COMPLETE -> DESIGN is 3 stages back, needs confirmation."""
        stage, needs_confirm = _determine_return_stage("COMPLETE", fractal_suggestion="DESIGN")

        # COMPLETE (idx 4) -> DESIGN (idx 1) = distance 3
        assert stage == "DESIGN"
        assert needs_confirm == True

    def test_complete_to_discover_4_back(self):
        """COMPLETE -> DISCOVER is 4 stages back, needs confirmation."""
        stage, needs_confirm = _determine_return_stage("COMPLETE", fractal_suggestion="DISCOVER")

        # COMPLETE (idx 4) -> DISCOVER (idx 0) = distance 4
        assert stage == "DISCOVER"
        assert needs_confirm == True

    def test_implement_to_discover_3_back_via_full_pipeline(self):
        """Full pipeline: IMPLEMENT -> DISCOVER (3 back) needs confirmation."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "The stakeholder requirements missing were not gathered properly",
                    "supporting_nodes": 5,
                },
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "Scope unclear and undiscovered needs are the root cause"}
            ],
        }

        feedbacks = fractal_to_feedback(harvest, "IMPLEMENT", 3)
        suggested = suggest_return_stage(harvest, "IMPLEMENT")

        assert suggested == "DISCOVER"

        stage, needs_confirm = _determine_return_stage("IMPLEMENT", fractal_suggestion=suggested)

        assert stage == "DISCOVER"
        assert needs_confirm == True
        assert feedbacks[0].return_to == "DISCOVER"


class TestEmptyFractalResultGraceful:
    """Empty/error harvest result -> graceful degradation through the pipeline."""

    def test_empty_harvest_produces_empty_feedback(self):
        """Empty harvest -> fractal_to_feedback returns [] -> suggest_return_stage
        returns None -> _determine_return_stage returns (current_stage, False).
        """
        harvest = {}

        feedbacks = fractal_to_feedback(harvest, "IMPLEMENT", 2)
        assert feedbacks == []

        suggested = suggest_return_stage(harvest, "IMPLEMENT")
        assert suggested is None

        stage, needs_confirm = _determine_return_stage("IMPLEMENT", fractal_suggestion=suggested)
        assert stage == "IMPLEMENT"
        assert needs_confirm == False

    def test_harvest_with_empty_lists(self):
        """Harvest with empty findings/boundary_questions/synthesis_chain."""
        harvest = {
            "findings": [],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        feedbacks = fractal_to_feedback(harvest, "DESIGN", 3)
        assert feedbacks == []

        suggested = suggest_return_stage(harvest, "DESIGN")
        assert suggested is None

        stage, needs_confirm = _determine_return_stage("DESIGN", fractal_suggestion=suggested)
        assert stage == "DESIGN"
        assert needs_confirm == False

    def test_harvest_with_only_resolved_tensions(self):
        """Harvest with only resolved tensions produces no feedback."""
        harvest = {
            "findings": [
                {"type": "tension", "status": "RESOLVED", "description": "Already handled"},
                {"type": "tension", "status": "RESOLVED", "description": "Also handled"},
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        feedbacks = fractal_to_feedback(harvest, "IMPLEMENT", 2)
        assert feedbacks == []

        suggested = suggest_return_stage(harvest, "IMPLEMENT")
        assert suggested is None

        stage, needs_confirm = _determine_return_stage("IMPLEMENT", fractal_suggestion=suggested)
        assert stage == "IMPLEMENT"
        assert needs_confirm == False

    def test_harvest_with_error_status_fields(self):
        """Harvest with no usable findings degrades gracefully."""
        harvest = {
            "findings": [
                {"type": "unknown_type", "data": "irrelevant"},
            ],
            "boundary_questions": [
                {"question": "Open question", "status": "open", "finding": None},
            ],
            "synthesis_chain": [
                {"synthesis": ""}
            ],
        }

        feedbacks = fractal_to_feedback(harvest, "PLAN", 1)
        assert feedbacks == []

        suggested = suggest_return_stage(harvest, "PLAN")
        assert suggested is None

        stage, needs_confirm = _determine_return_stage("PLAN", fractal_suggestion=suggested)
        assert stage == "PLAN"
        assert needs_confirm == False


class TestSuggestReturnStageMinimumThreshold:
    """Verify that a harvest with only 1 keyword hit does NOT trigger stage return."""

    def test_single_keyword_hit_no_suggestion(self):
        """1 keyword hit for DESIGN at IMPLEMENT does not suggest return."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "There is an architecture problem in the system"}
            ],
        }

        # Only "architecture" matches for DESIGN -- that's 1 hit, needs >= 2
        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result is None

    def test_single_keyword_hit_in_findings_no_suggestion(self):
        """1 keyword hit from findings only does not suggest return."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "There is coupling between the services",
                },
            ],
            "synthesis_chain": [
                {"synthesis": "Services need to be decoupled for better reliability"}
            ],
        }

        # Only "coupling" matches for DESIGN from insight -- 1 hit
        # "decoupled" does not match "coupling" (substring match, not word match,
        # but "coupling" is not in "decoupled")
        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result is None

    def test_exactly_two_hits_triggers_suggestion(self):
        """Exactly 2 keyword hits for DESIGN at IMPLEMENT triggers suggestion."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "The architecture has coupling issues"}
            ],
        }

        # "architecture" + "coupling" = 2 hits for DESIGN
        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result == "DESIGN"

    def test_single_discover_keyword_no_suggestion(self):
        """1 DISCOVER keyword hit from DESIGN does not suggest return."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "The stakeholder needs are partially unclear"}
            ],
        }

        # Only "stakeholder" matches for DISCOVER -- 1 hit
        result = suggest_return_stage(harvest, "DESIGN")

        assert result is None

    def test_two_discover_keywords_triggers_from_design(self):
        """2 DISCOVER keyword hits from DESIGN triggers suggestion."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "The stakeholder requirements missing from analysis"}
            ],
        }

        # "stakeholder" + "requirements missing" = 2 hits for DISCOVER
        result = suggest_return_stage(harvest, "DESIGN")

        assert result == "DISCOVER"

    def test_single_plan_keyword_no_suggestion(self):
        """1 PLAN keyword hit from IMPLEMENT does not suggest return."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "The ordering of tasks needs revision"}
            ],
        }

        # Only "ordering" matches for PLAN -- 1 hit
        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result is None

    def test_zero_keyword_hits_no_suggestion(self):
        """0 keyword hits returns None."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "The code is just poorly written",
                },
            ],
            "synthesis_chain": [
                {"synthesis": "General quality issues need resolution"}
            ],
        }

        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result is None
