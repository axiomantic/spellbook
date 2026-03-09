"""Tests for FractalResult-to-Feedback mapper.

Tests the fractal_feedback module which transforms fractal thinking harvest
JSON into Forged Feedback objects for the iteration system.
"""

from spellbook_mcp.forged.fractal_feedback import (
    fractal_to_feedback,
    suggest_return_stage,
    _convergence_to_feedback,
    _tension_to_feedback,
    _gap_to_feedback,
    _boundary_to_feedback,
    _extract_remediation,
)
from spellbook_mcp.forged.models import Feedback


class TestConvergenceToFeedback:
    """Test convergence finding -> Feedback mapping."""

    def test_convergence_finding_maps_to_blocking_feedback(self):
        """Single convergence finding produces blocking Feedback with all fields."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "API contract mismatch causes integration failures",
                    "supporting_nodes": 3,
                }
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "The root cause is an API contract mismatch between services"}
            ],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 2)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Fractal convergence (3 branches): API contract mismatch causes integration failures",
                evidence="Identified via fractal exploration with 3 independent branches converging on same conclusion",
                suggestion="The root cause is an API contract mismatch between services",
                severity="blocking",
                iteration=2,
            )
        ]

    def test_convergence_with_synthesis_suggesting_earlier_stage(self):
        """Convergence with synthesis keywords pointing to DESIGN sets return_to."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "architecture design flaw in component boundary",
                    "supporting_nodes": 4,
                }
            ],
            "boundary_questions": [],
            "synthesis_chain": [
                {"synthesis": "The design decision and interface mismatch are the root causes"}
            ],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 3)

        # suggest_return_stage should find DESIGN keywords: "architecture",
        # "design flaw", "interface mismatch", "design decision", "component boundary"
        # That's 5 hits for DESIGN, well above the >= 2 threshold
        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="DESIGN",
                critique="Fractal convergence (4 branches): architecture design flaw in component boundary",
                evidence="Identified via fractal exploration with 4 independent branches converging on same conclusion",
                suggestion="The design decision and interface mismatch are the root causes",
                severity="blocking",
                iteration=3,
            )
        ]

    def test_convergence_defaults_when_no_supporting_nodes(self):
        """Convergence without supporting_nodes uses 'multiple' as default."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "Data flow issue",
                }
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "PLAN", 1)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="PLAN",
                return_to="PLAN",
                critique="Fractal convergence (multiple branches): Data flow issue",
                evidence="Identified via fractal exploration with multiple independent branches converging on same conclusion",
                suggestion="Address the root cause identified by fractal analysis: Data flow issue",
                severity="blocking",
                iteration=1,
            )
        ]


class TestTensionToFeedback:
    """Test unresolved tension -> Feedback mapping."""

    def test_unresolved_tension_maps_to_significant_feedback(self):
        """Unresolved tension produces significant Feedback."""
        harvest = {
            "findings": [
                {
                    "type": "tension",
                    "status": "UNRESOLVED",
                    "description": "Caching vs consistency trade-off not resolved",
                }
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "DESIGN", 2)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="DESIGN",
                return_to="DESIGN",
                critique="Unresolved tension: Caching vs consistency trade-off not resolved",
                evidence="Fractal exploration found contradictory approaches that have not been reconciled",
                suggestion="Resolve the tension between the competing approaches before proceeding. Consider: Caching vs consistency trade-off not resolved",
                severity="significant",
                iteration=2,
            )
        ]

    def test_resolved_tension_is_excluded(self):
        """Resolved tensions are not mapped to Feedback."""
        harvest = {
            "findings": [
                {
                    "type": "tension",
                    "status": "RESOLVED",
                    "description": "Already resolved tension",
                }
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "DESIGN", 1)

        assert result == []

    def test_tension_defaults_when_no_description(self):
        """Tension without description uses default text."""
        harvest = {
            "findings": [
                {
                    "type": "tension",
                    "status": "UNRESOLVED",
                }
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 1)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Unresolved tension: Unresolved architectural tension",
                evidence="Fractal exploration found contradictory approaches that have not been reconciled",
                suggestion="Resolve the tension between the competing approaches before proceeding. Consider: Unresolved architectural tension",
                severity="significant",
                iteration=1,
            )
        ]


class TestGapToFeedback:
    """Test gap finding -> Feedback mapping."""

    def test_gap_maps_to_minor_feedback(self):
        """Gap produces minor Feedback."""
        harvest = {
            "findings": [
                {
                    "type": "gap",
                    "question": "How does the system handle concurrent writes?",
                    "reason": "budget_exhausted",
                }
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 2)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Unexplored area: How does the system handle concurrent writes?",
                evidence="Fractal exploration could not reach this area (reason: budget_exhausted)",
                suggestion="Consider investigating: How does the system handle concurrent writes?",
                severity="minor",
                iteration=2,
            )
        ]

    def test_gap_defaults_when_no_question_or_reason(self):
        """Gap without question/reason uses defaults."""
        harvest = {
            "findings": [
                {
                    "type": "gap",
                }
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "PLAN", 1)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="PLAN",
                return_to="PLAN",
                critique="Unexplored area: Unexplored area identified",
                evidence="Fractal exploration could not reach this area (reason: not_reached)",
                suggestion="Consider investigating: Unexplored area identified",
                severity="minor",
                iteration=1,
            )
        ]


class TestBoundaryToFeedback:
    """Test boundary question -> Feedback mapping."""

    def test_answered_boundary_maps_to_significant_feedback(self):
        """Answered boundary question with finding produces significant Feedback."""
        harvest = {
            "findings": [],
            "boundary_questions": [
                {
                    "question": "Does the auth layer affect data flow?",
                    "status": "answered",
                    "finding": "Yes, the auth middleware intercepts and transforms payloads",
                }
            ],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 2)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Cross-cutting insight: Does the auth layer affect data flow?",
                evidence="Boundary exploration between converging branches: Yes, the auth middleware intercepts and transforms payloads",
                suggestion="Yes, the auth middleware intercepts and transforms payloads",
                severity="significant",
                iteration=2,
            )
        ]

    def test_synthesized_boundary_also_maps(self):
        """Synthesized boundary question with finding also produces Feedback."""
        harvest = {
            "findings": [],
            "boundary_questions": [
                {
                    "question": "Cross-cutting concern about error handling",
                    "status": "synthesized",
                    "finding": "Error handling is inconsistent across modules",
                }
            ],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "DESIGN", 1)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="DESIGN",
                return_to="DESIGN",
                critique="Cross-cutting insight: Cross-cutting concern about error handling",
                evidence="Boundary exploration between converging branches: Error handling is inconsistent across modules",
                suggestion="Error handling is inconsistent across modules",
                severity="significant",
                iteration=1,
            )
        ]

    def test_open_boundary_is_excluded(self):
        """Open boundary questions (no finding) are not mapped."""
        harvest = {
            "findings": [],
            "boundary_questions": [
                {
                    "question": "Some open question",
                    "status": "open",
                    "finding": None,
                }
            ],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "PLAN", 1)

        assert result == []

    def test_boundary_without_finding_is_excluded(self):
        """Answered boundary without finding text is excluded."""
        harvest = {
            "findings": [],
            "boundary_questions": [
                {
                    "question": "Some question",
                    "status": "answered",
                    # no "finding" key
                }
            ],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "PLAN", 1)

        assert result == []

    def test_boundary_long_finding_truncated_in_evidence(self):
        """Boundary finding text is truncated to 200 chars in evidence."""
        long_finding = "A" * 300
        harvest = {
            "findings": [],
            "boundary_questions": [
                {
                    "question": "Long finding question",
                    "status": "answered",
                    "finding": long_finding,
                }
            ],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 1)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Cross-cutting insight: Long finding question",
                evidence="Boundary exploration between converging branches: " + "A" * 200,
                suggestion="A" * 300,
                severity="significant",
                iteration=1,
            )
        ]

    def test_boundary_very_long_finding_truncated_in_suggestion(self):
        """Boundary finding text is truncated to 500 chars in suggestion."""
        long_finding = "B" * 600
        harvest = {
            "findings": [],
            "boundary_questions": [
                {
                    "question": "Very long finding",
                    "status": "answered",
                    "finding": long_finding,
                }
            ],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 1)

        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Cross-cutting insight: Very long finding",
                evidence="Boundary exploration between converging branches: " + "B" * 200,
                suggestion="B" * 500,
                severity="significant",
                iteration=1,
            )
        ]


class TestEmptyAndMinimalHarvest:
    """Test edge cases with empty/minimal harvest data."""

    def test_empty_harvest_produces_empty_list(self):
        """Completely empty harvest dict produces no Feedback."""
        result = fractal_to_feedback({}, "IMPLEMENT", 1)

        assert result == []

    def test_minimal_harvest_with_empty_lists(self):
        """Harvest with empty findings and boundary_questions produces no Feedback."""
        harvest = {
            "findings": [],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "DESIGN", 1)

        assert result == []

    def test_unknown_finding_type_ignored(self):
        """Findings with unrecognized types are skipped."""
        harvest = {
            "findings": [
                {"type": "unknown_type", "data": "something"},
            ],
            "boundary_questions": [],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 1)

        assert result == []


class TestSeverityOrdering:
    """Test that output is sorted by severity: blocking > significant > minor."""

    def test_mixed_severities_sorted_correctly(self):
        """Multiple finding types produce correctly ordered Feedback."""
        harvest = {
            "findings": [
                {
                    "type": "gap",
                    "question": "Unexplored concurrency area",
                    "reason": "not_reached",
                },
                {
                    "type": "tension",
                    "status": "UNRESOLVED",
                    "description": "Caching vs consistency",
                },
                {
                    "type": "convergence",
                    "insight": "Core integration issue",
                    "supporting_nodes": 2,
                },
            ],
            "boundary_questions": [
                {
                    "question": "Cross-cutting auth concern",
                    "status": "answered",
                    "finding": "Auth affects everything",
                },
            ],
            "synthesis_chain": [],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 2)

        # Verify ordering: blocking (convergence), significant (tension, boundary), minor (gap)
        assert len(result) == 4
        assert result[0].severity == "blocking"
        assert result[0].source == "fractal-analysis"
        assert result[0].stage == "IMPLEMENT"
        assert result[0].return_to == "IMPLEMENT"
        assert result[0].critique == "Fractal convergence (2 branches): Core integration issue"
        assert result[0].evidence == "Identified via fractal exploration with 2 independent branches converging on same conclusion"
        assert result[0].suggestion == "Address the root cause identified by fractal analysis: Core integration issue"
        assert result[0].iteration == 2

        assert result[1].severity == "significant"
        assert result[1].critique == "Unresolved tension: Caching vs consistency"

        assert result[2].severity == "significant"
        assert result[2].critique == "Cross-cutting insight: Cross-cutting auth concern"

        assert result[3].severity == "minor"
        assert result[3].critique == "Unexplored area: Unexplored concurrency area"

        # Full object verification for all items
        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Fractal convergence (2 branches): Core integration issue",
                evidence="Identified via fractal exploration with 2 independent branches converging on same conclusion",
                suggestion="Address the root cause identified by fractal analysis: Core integration issue",
                severity="blocking",
                iteration=2,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Unresolved tension: Caching vs consistency",
                evidence="Fractal exploration found contradictory approaches that have not been reconciled",
                suggestion="Resolve the tension between the competing approaches before proceeding. Consider: Caching vs consistency",
                severity="significant",
                iteration=2,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Cross-cutting insight: Cross-cutting auth concern",
                evidence="Boundary exploration between converging branches: Auth affects everything",
                suggestion="Auth affects everything",
                severity="significant",
                iteration=2,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Unexplored area: Unexplored concurrency area",
                evidence="Fractal exploration could not reach this area (reason: not_reached)",
                suggestion="Consider investigating: Unexplored concurrency area",
                severity="minor",
                iteration=2,
            ),
        ]


class TestSuggestReturnStage:
    """Test suggest_return_stage() logic."""

    def test_keyword_matches_return_earlier_stage(self):
        """Synthesis with DESIGN keywords at IMPLEMENT returns DESIGN."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "The architecture has a design flaw in the abstraction layer",
                }
            ],
            "synthesis_chain": [
                {"synthesis": "The interface mismatch and coupling issues stem from a design decision"}
            ],
        }

        result = suggest_return_stage(harvest, "IMPLEMENT")

        # "architecture", "design flaw", "abstraction", "coupling", "design decision",
        # "interface mismatch" are all DESIGN keywords. Multiple hits (>=2) -> DESIGN
        assert result == "DESIGN"

    def test_no_keyword_matches_returns_none(self):
        """Synthesis without stage-indicating keywords returns None."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "The code has some minor issues that need attention"}
            ],
        }

        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result is None

    def test_invalid_current_stage_returns_none(self):
        """Invalid current_stage returns None."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "architecture design flaw interface mismatch"}
            ],
        }

        result = suggest_return_stage(harvest, "INVALID_STAGE")

        assert result is None

    def test_current_at_discover_returns_none(self):
        """At DISCOVER there's no earlier stage to return to."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "requirements missing stakeholder use case missing",
                }
            ],
            "synthesis_chain": [
                {"synthesis": "requirements gap and undiscovered stakeholder needs"}
            ],
        }

        # DISCOVER keywords match, but can't go earlier than DISCOVER
        result = suggest_return_stage(harvest, "DISCOVER")

        assert result is None

    def test_single_keyword_hit_not_enough(self):
        """A single keyword hit (< 2) does not trigger a stage suggestion."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "There is an architecture problem in the system"}
            ],
        }

        # Only "architecture" matches for DESIGN -- that's 1 hit, needs >= 2
        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result is None

    def test_two_keyword_hits_is_enough(self):
        """Exactly 2 keyword hits triggers a stage suggestion."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "The architecture has coupling issues"}
            ],
        }

        # "architecture" + "coupling" = 2 hits for DESIGN
        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result == "DESIGN"

    def test_plan_keywords_return_plan(self):
        """PLAN keywords at IMPLEMENT return PLAN."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "The task breakdown has a dependency missing that affects ordering"}
            ],
        }

        # "task breakdown", "dependency missing", "ordering" = 3 hits for PLAN
        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result == "PLAN"

    def test_discover_keywords_return_discover(self):
        """DISCOVER keywords at IMPLEMENT return DISCOVER."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "requirements missing and stakeholder needs not gathered"}
            ],
        }

        # "requirements missing", "stakeholder", "not gathered" = 3 hits for DISCOVER
        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result == "DISCOVER"

    def test_multiple_candidate_stages_picks_highest_hits(self):
        """When multiple stages have keyword hits, returns the one with most hits."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "architecture design flaw abstraction coupling interface mismatch",
                }
            ],
            "synthesis_chain": [
                {"synthesis": "task breakdown has dependency missing"}
            ],
        }

        # DESIGN: "architecture", "design flaw", "abstraction", "coupling",
        #         "interface mismatch" = 5 hits
        # PLAN: "task breakdown", "dependency missing" = 2 hits
        # DESIGN wins with more hits
        result = suggest_return_stage(harvest, "COMPLETE")

        assert result == "DESIGN"

    def test_keywords_only_from_earlier_stages(self):
        """Keywords for stages at or after current are ignored."""
        harvest = {
            "findings": [],
            "synthesis_chain": [
                {"synthesis": "task breakdown dependency missing ordering estimation plan gap work sequence"}
            ],
        }

        # All PLAN keywords, but current is PLAN, so PLAN is not "earlier"
        # DISCOVER keywords don't match
        result = suggest_return_stage(harvest, "PLAN")

        assert result is None

    def test_empty_harvest_returns_none(self):
        """Empty harvest returns None."""
        result = suggest_return_stage({}, "IMPLEMENT")

        assert result is None

    def test_empty_synthesis_chain_returns_none(self):
        """Harvest with empty synthesis_chain returns None."""
        harvest = {
            "findings": [],
            "synthesis_chain": [],
        }

        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result is None

    def test_convergence_insights_contribute_to_keyword_search(self):
        """Convergence finding insights are included in the keyword search corpus."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "The coupling between modules is due to a design flaw",
                }
            ],
            "synthesis_chain": [
                {"synthesis": "General analysis with no stage keywords"}
            ],
        }

        # Keywords come from the convergence insight: "coupling" + "design flaw" = 2 DESIGN hits
        result = suggest_return_stage(harvest, "IMPLEMENT")

        assert result == "DESIGN"


class TestExtractRemediation:
    """Test _extract_remediation helper."""

    def test_uses_root_synthesis_when_available(self):
        """Returns root synthesis text as remediation."""
        harvest = {
            "synthesis_chain": [
                {"synthesis": "Apply dependency injection to decouple the modules"}
            ],
        }

        result = _extract_remediation("some insight", harvest)

        assert result == "Apply dependency injection to decouple the modules"

    def test_falls_back_to_insight_when_no_synthesis(self):
        """Returns insight-based message when no synthesis available."""
        harvest = {"synthesis_chain": []}

        result = _extract_remediation("Data flow bottleneck", harvest)

        assert result == "Address the root cause identified by fractal analysis: Data flow bottleneck"

    def test_falls_back_when_empty_synthesis_text(self):
        """Returns insight-based message when synthesis text is empty."""
        harvest = {"synthesis_chain": [{"synthesis": ""}]}

        result = _extract_remediation("Some issue", harvest)

        assert result == "Address the root cause identified by fractal analysis: Some issue"

    def test_truncates_long_synthesis(self):
        """Long synthesis is truncated to 800 chars."""
        long_synthesis = "X" * 1000
        harvest = {"synthesis_chain": [{"synthesis": long_synthesis}]}

        result = _extract_remediation("insight", harvest)

        assert result == "X" * 800

    def test_no_synthesis_chain_key(self):
        """Missing synthesis_chain key falls back to insight."""
        harvest = {}

        result = _extract_remediation("Missing feature", harvest)

        assert result == "Address the root cause identified by fractal analysis: Missing feature"


class TestFullHarvestMapping:
    """Test realistic full harvest JSON mapping."""

    def test_full_harvest_with_multiple_finding_types(self):
        """Realistic harvest with convergence, tension, gap, and boundary produces correct Feedback set."""
        harvest = {
            "findings": [
                {
                    "type": "convergence",
                    "insight": "Database schema mismatch causes data corruption",
                    "supporting_nodes": 5,
                },
                {
                    "type": "tension",
                    "status": "UNRESOLVED",
                    "description": "Sync vs async data access patterns",
                },
                {
                    "type": "tension",
                    "status": "RESOLVED",
                    "description": "This one is resolved and should be excluded",
                },
                {
                    "type": "gap",
                    "question": "What happens under high load?",
                    "reason": "budget_exhausted",
                },
                {
                    "type": "convergence",
                    "insight": "requirements missing from stakeholder input not gathered properly",
                    "supporting_nodes": 2,
                },
            ],
            "boundary_questions": [
                {
                    "question": "How do caching and persistence interact?",
                    "status": "answered",
                    "finding": "Cache invalidation is incomplete during writes",
                },
                {
                    "question": "Unresolved question",
                    "status": "open",
                    "finding": None,
                },
            ],
            "synthesis_chain": [
                {"synthesis": "The requirements missing and stakeholder needs not gathered are the fundamental issues"}
            ],
        }

        result = fractal_to_feedback(harvest, "IMPLEMENT", 3)

        # suggest_return_stage for convergence findings:
        # synthesis text: "the requirements missing and stakeholder needs not gathered are the fundamental issues"
        # convergence insights: "database schema mismatch causes data corruption" +
        #                       "requirements missing from stakeholder input not gathered properly"
        # DISCOVER keywords in corpus: "requirements missing" (in synthesis + insight), "not gathered" (in synthesis + insight), "stakeholder" (in insight)
        # That's 3+ hits for DISCOVER
        # DESIGN keywords: none match
        # So convergence return_to = DISCOVER

        assert len(result) == 5

        # All blocking first (2 convergences), then significant (tension + boundary), then minor (gap)
        assert result == [
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="DISCOVER",
                critique="Fractal convergence (5 branches): Database schema mismatch causes data corruption",
                evidence="Identified via fractal exploration with 5 independent branches converging on same conclusion",
                suggestion="The requirements missing and stakeholder needs not gathered are the fundamental issues",
                severity="blocking",
                iteration=3,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="DISCOVER",
                critique="Fractal convergence (2 branches): requirements missing from stakeholder input not gathered properly",
                evidence="Identified via fractal exploration with 2 independent branches converging on same conclusion",
                suggestion="The requirements missing and stakeholder needs not gathered are the fundamental issues",
                severity="blocking",
                iteration=3,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Unresolved tension: Sync vs async data access patterns",
                evidence="Fractal exploration found contradictory approaches that have not been reconciled",
                suggestion="Resolve the tension between the competing approaches before proceeding. Consider: Sync vs async data access patterns",
                severity="significant",
                iteration=3,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Cross-cutting insight: How do caching and persistence interact?",
                evidence="Boundary exploration between converging branches: Cache invalidation is incomplete during writes",
                suggestion="Cache invalidation is incomplete during writes",
                severity="significant",
                iteration=3,
            ),
            Feedback(
                source="fractal-analysis",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Unexplored area: What happens under high load?",
                evidence="Fractal exploration could not reach this area (reason: budget_exhausted)",
                suggestion="Consider investigating: What happens under high load?",
                severity="minor",
                iteration=3,
            ),
        ]
