"""Tests for Forged roundtable MCP tools.

Following TDD: these tests are written BEFORE implementation.

The roundtable system uses tarot archetypes to validate stage completion:
- Magician (technical precision)
- Priestess (hidden knowledge)
- Hermit (deep analysis)
- Fool (naive questions)
- Chariot (forward momentum)
- Justice (synthesis/resolution)
- Lovers (integration)
- Hierophant (standards)
- Emperor (constraints)
- Queen (user needs)
"""

import pytest
import json
from pathlib import Path


# =============================================================================
# Task 6.3: ParsedVerdict Dataclass Tests
# =============================================================================


class TestParsedVerdictDataclass:
    """Tests for ParsedVerdict dataclass."""

    def test_parsed_verdict_creation(self):
        """ParsedVerdict must be creatable with required fields."""
        from spellbook_mcp.forged.verdict_parsing import ParsedVerdict

        verdict = ParsedVerdict(
            archetype="Magician",
            verdict="APPROVE",
            concerns=[],
            suggestions=[],
            severity=None,
        )

        assert verdict.archetype == "Magician"
        assert verdict.verdict == "APPROVE"
        assert verdict.concerns == []
        assert verdict.suggestions == []
        assert verdict.severity is None

    def test_parsed_verdict_with_concerns(self):
        """ParsedVerdict can have concerns."""
        from spellbook_mcp.forged.verdict_parsing import ParsedVerdict

        verdict = ParsedVerdict(
            archetype="Hermit",
            verdict="ITERATE",
            concerns=["Missing error handling", "No test coverage"],
            suggestions=["Add try-catch blocks"],
            severity="blocking",
        )

        assert verdict.archetype == "Hermit"
        assert verdict.verdict == "ITERATE"
        assert len(verdict.concerns) == 2
        assert "Missing error handling" in verdict.concerns
        assert verdict.severity == "blocking"

    def test_parsed_verdict_to_dict(self):
        """ParsedVerdict.to_dict() must produce JSON-serializable dict."""
        from spellbook_mcp.forged.verdict_parsing import ParsedVerdict

        verdict = ParsedVerdict(
            archetype="Justice",
            verdict="ABSTAIN",
            concerns=["Not my domain"],
            suggestions=[],
            severity=None,
        )

        d = verdict.to_dict()
        json_str = json.dumps(d)
        assert json_str is not None

        assert d["archetype"] == "Justice"
        assert d["verdict"] == "ABSTAIN"
        assert d["concerns"] == ["Not my domain"]
        assert d["suggestions"] == []
        assert d["severity"] is None

    def test_parsed_verdict_from_dict(self):
        """ParsedVerdict.from_dict() must reconstruct from dict."""
        from spellbook_mcp.forged.verdict_parsing import ParsedVerdict

        data = {
            "archetype": "Fool",
            "verdict": "APPROVE",
            "concerns": [],
            "suggestions": ["Consider simplifying"],
            "severity": "minor",
        }

        verdict = ParsedVerdict.from_dict(data)

        assert verdict.archetype == "Fool"
        assert verdict.verdict == "APPROVE"
        assert verdict.suggestions == ["Consider simplifying"]
        assert verdict.severity == "minor"

    def test_parsed_verdict_roundtrip(self):
        """ParsedVerdict must survive to_dict() -> from_dict() roundtrip."""
        from spellbook_mcp.forged.verdict_parsing import ParsedVerdict

        original = ParsedVerdict(
            archetype="Emperor",
            verdict="ITERATE",
            concerns=["Exceeds scope", "Breaks constraints"],
            suggestions=["Reduce scope", "Add bounds checking"],
            severity="significant",
        )

        reconstructed = ParsedVerdict.from_dict(original.to_dict())

        assert reconstructed.archetype == original.archetype
        assert reconstructed.verdict == original.verdict
        assert reconstructed.concerns == original.concerns
        assert reconstructed.suggestions == original.suggestions
        assert reconstructed.severity == original.severity


# =============================================================================
# Task 6.3: Verdict Parsing Tests
# =============================================================================


class TestVerdictParsingConstants:
    """Tests for verdict parsing constants."""

    def test_persona_block_pattern_exists(self):
        """PERSONA_BLOCK_PATTERN must be defined."""
        from spellbook_mcp.forged.verdict_parsing import PERSONA_BLOCK_PATTERN

        assert PERSONA_BLOCK_PATTERN is not None
        assert isinstance(PERSONA_BLOCK_PATTERN, str)

    def test_valid_verdicts_constant_exists(self):
        """VALID_ROUNDTABLE_VERDICTS must be defined."""
        from spellbook_mcp.forged.verdict_parsing import VALID_ROUNDTABLE_VERDICTS

        assert "APPROVE" in VALID_ROUNDTABLE_VERDICTS
        assert "ITERATE" in VALID_ROUNDTABLE_VERDICTS
        assert "ABSTAIN" in VALID_ROUNDTABLE_VERDICTS


class TestParseRoundtableResponse:
    """Tests for parse_roundtable_response function."""

    def test_parse_single_archetype_approve(self):
        """parse_roundtable_response handles single archetype APPROVE."""
        from spellbook_mcp.forged.verdict_parsing import parse_roundtable_response

        response = """
**Magician**: I have reviewed the technical implementation.
The code is sound and follows best practices.

Verdict: APPROVE
"""
        verdicts = parse_roundtable_response(response)

        assert len(verdicts) >= 1
        magician = next((v for v in verdicts if v.archetype == "Magician"), None)
        assert magician is not None
        assert magician.verdict == "APPROVE"

    def test_parse_single_archetype_iterate(self):
        """parse_roundtable_response handles single archetype ITERATE."""
        from spellbook_mcp.forged.verdict_parsing import parse_roundtable_response

        response = """
**Hermit**: Upon deep reflection, I find issues.

Concerns:
- Missing validation
- No error handling

Verdict: ITERATE
Severity: blocking
"""
        verdicts = parse_roundtable_response(response)

        assert len(verdicts) >= 1
        hermit = next((v for v in verdicts if v.archetype == "Hermit"), None)
        assert hermit is not None
        assert hermit.verdict == "ITERATE"
        assert "Missing validation" in hermit.concerns or len(hermit.concerns) > 0

    def test_parse_multiple_archetypes(self):
        """parse_roundtable_response handles multiple archetypes."""
        from spellbook_mcp.forged.verdict_parsing import parse_roundtable_response

        response = """
**Magician**: Technical implementation is solid.
Verdict: APPROVE

**Fool**: Why is this so complicated?
Verdict: ITERATE
Concerns:
- Could be simpler

**Justice**: Balancing the perspectives, I synthesize.
Verdict: APPROVE
"""
        verdicts = parse_roundtable_response(response)

        assert len(verdicts) >= 3
        archetype_names = [v.archetype for v in verdicts]
        assert "Magician" in archetype_names
        assert "Fool" in archetype_names
        assert "Justice" in archetype_names

    def test_parse_abstain_verdict(self):
        """parse_roundtable_response handles ABSTAIN verdict."""
        from spellbook_mcp.forged.verdict_parsing import parse_roundtable_response

        response = """
**Priestess**: This matter is not within my domain of hidden knowledge.
Verdict: ABSTAIN
"""
        verdicts = parse_roundtable_response(response)

        priestess = next((v for v in verdicts if v.archetype == "Priestess"), None)
        assert priestess is not None
        assert priestess.verdict == "ABSTAIN"

    def test_parse_extracts_concerns(self):
        """parse_roundtable_response extracts concerns list."""
        from spellbook_mcp.forged.verdict_parsing import parse_roundtable_response

        response = """
**Emperor**: The constraints are violated.

Concerns:
- Budget exceeded
- Timeline unrealistic
- Resources insufficient

Verdict: ITERATE
Severity: blocking
"""
        verdicts = parse_roundtable_response(response)

        emperor = next((v for v in verdicts if v.archetype == "Emperor"), None)
        assert emperor is not None
        assert len(emperor.concerns) >= 1

    def test_parse_extracts_suggestions(self):
        """parse_roundtable_response extracts suggestions list."""
        from spellbook_mcp.forged.verdict_parsing import parse_roundtable_response

        response = """
**Chariot**: Moving forward requires action.

Suggestions:
- Start with MVP
- Iterate quickly
- Ship early

Verdict: APPROVE
"""
        verdicts = parse_roundtable_response(response)

        chariot = next((v for v in verdicts if v.archetype == "Chariot"), None)
        assert chariot is not None
        assert len(chariot.suggestions) >= 1

    def test_parse_extracts_severity(self):
        """parse_roundtable_response extracts severity level."""
        from spellbook_mcp.forged.verdict_parsing import parse_roundtable_response

        response = """
**Hierophant**: The standards are not met.

Verdict: ITERATE
Severity: significant
"""
        verdicts = parse_roundtable_response(response)

        hierophant = next((v for v in verdicts if v.archetype == "Hierophant"), None)
        assert hierophant is not None
        assert hierophant.severity == "significant"

    def test_parse_empty_response_returns_empty_list(self):
        """parse_roundtable_response returns empty list for empty input."""
        from spellbook_mcp.forged.verdict_parsing import parse_roundtable_response

        verdicts = parse_roundtable_response("")
        assert verdicts == []

    def test_parse_malformed_response_uses_fallback(self):
        """parse_roundtable_response uses fallback for malformed input."""
        from spellbook_mcp.forged.verdict_parsing import parse_roundtable_response

        # No clear verdict markers
        response = "This is just some text without structure."
        verdicts = parse_roundtable_response(response)

        # Should return empty list or fallback verdicts, not crash
        assert isinstance(verdicts, list)


class TestHandleParseFailure:
    """Tests for handle_parse_failure fallback function."""

    def test_handle_parse_failure_returns_list(self):
        """handle_parse_failure must return a list of ParsedVerdict."""
        from spellbook_mcp.forged.verdict_parsing import (
            handle_parse_failure,
            ParsedVerdict,
        )

        result = handle_parse_failure("Some unstructured text")

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, ParsedVerdict)

    def test_handle_parse_failure_extracts_any_verdicts(self):
        """handle_parse_failure tries to extract any verdict-like content."""
        from spellbook_mcp.forged.verdict_parsing import handle_parse_failure

        # Text that mentions a verdict but not in standard format
        response = "I think we should APPROVE this because it looks good."
        result = handle_parse_failure(response)

        # May find verdicts or return empty - should not crash
        assert isinstance(result, list)

    def test_handle_parse_failure_empty_input(self):
        """handle_parse_failure handles empty input gracefully."""
        from spellbook_mcp.forged.verdict_parsing import handle_parse_failure

        result = handle_parse_failure("")
        assert isinstance(result, list)


# =============================================================================
# Task 6.1: Roundtable Archetypes Constants Tests
# =============================================================================


class TestRoundtableArchetypes:
    """Tests for roundtable archetype constants."""

    def test_archetypes_constant_exists(self):
        """ROUNDTABLE_ARCHETYPES must be defined."""
        from spellbook_mcp.forged.roundtable import ROUNDTABLE_ARCHETYPES

        assert isinstance(ROUNDTABLE_ARCHETYPES, dict)
        assert len(ROUNDTABLE_ARCHETYPES) == 10

    def test_all_archetypes_present(self):
        """All 10 tarot archetypes must be present."""
        from spellbook_mcp.forged.roundtable import ROUNDTABLE_ARCHETYPES

        required_archetypes = [
            "Magician",
            "Priestess",
            "Hermit",
            "Fool",
            "Chariot",
            "Justice",
            "Lovers",
            "Hierophant",
            "Emperor",
            "Queen",
        ]

        for archetype in required_archetypes:
            assert archetype in ROUNDTABLE_ARCHETYPES, f"Missing archetype: {archetype}"

    def test_archetype_has_description(self):
        """Each archetype must have a description."""
        from spellbook_mcp.forged.roundtable import ROUNDTABLE_ARCHETYPES

        for name, info in ROUNDTABLE_ARCHETYPES.items():
            assert "description" in info, f"{name} missing description"
            assert len(info["description"]) > 0

    def test_archetype_has_focus(self):
        """Each archetype must have a focus area."""
        from spellbook_mcp.forged.roundtable import ROUNDTABLE_ARCHETYPES

        for name, info in ROUNDTABLE_ARCHETYPES.items():
            assert "focus" in info, f"{name} missing focus"
            assert len(info["focus"]) > 0

    def test_magician_is_technical_precision(self):
        """Magician archetype must focus on technical precision."""
        from spellbook_mcp.forged.roundtable import ROUNDTABLE_ARCHETYPES

        magician = ROUNDTABLE_ARCHETYPES["Magician"]
        assert "technical" in magician["focus"].lower()

    def test_justice_is_synthesis(self):
        """Justice archetype must focus on synthesis/resolution."""
        from spellbook_mcp.forged.roundtable import ROUNDTABLE_ARCHETYPES

        justice = ROUNDTABLE_ARCHETYPES["Justice"]
        assert (
            "synthesis" in justice["focus"].lower()
            or "resolution" in justice["focus"].lower()
        )


# =============================================================================
# Task 6.1: Prompt Template Tests
# =============================================================================


class TestRoundtablePromptTemplate:
    """Tests for roundtable prompt template generation."""

    def test_build_roundtable_prompt_exists(self):
        """build_roundtable_prompt function must exist."""
        from spellbook_mcp.forged.roundtable import build_roundtable_prompt

        assert callable(build_roundtable_prompt)

    def test_build_roundtable_prompt_includes_stage(self):
        """build_roundtable_prompt must include stage in prompt."""
        from spellbook_mcp.forged.roundtable import build_roundtable_prompt

        prompt = build_roundtable_prompt(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_content="# Design Document\nContent here.",
            archetypes=["Magician", "Hermit"],
        )

        assert "DESIGN" in prompt

    def test_build_roundtable_prompt_includes_feature_name(self):
        """build_roundtable_prompt must include feature name in prompt."""
        from spellbook_mcp.forged.roundtable import build_roundtable_prompt

        prompt = build_roundtable_prompt(
            feature_name="my-awesome-feature",
            stage="IMPLEMENT",
            artifact_content="Code here",
            archetypes=["Magician"],
        )

        assert "my-awesome-feature" in prompt

    def test_build_roundtable_prompt_includes_artifact_content(self):
        """build_roundtable_prompt must include artifact content."""
        from spellbook_mcp.forged.roundtable import build_roundtable_prompt

        artifact_content = "This is unique artifact content for testing."
        prompt = build_roundtable_prompt(
            feature_name="test-feature",
            stage="PLAN",
            artifact_content=artifact_content,
            archetypes=["Hermit"],
        )

        assert artifact_content in prompt

    def test_build_roundtable_prompt_includes_selected_archetypes(self):
        """build_roundtable_prompt must include selected archetype instructions."""
        from spellbook_mcp.forged.roundtable import build_roundtable_prompt

        prompt = build_roundtable_prompt(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_content="Content",
            archetypes=["Magician", "Fool", "Justice"],
        )

        # Should include archetype names and their focus areas
        assert "Magician" in prompt
        assert "Fool" in prompt
        assert "Justice" in prompt

    def test_build_roundtable_prompt_default_archetypes(self):
        """build_roundtable_prompt uses default archetypes when none specified."""
        from spellbook_mcp.forged.roundtable import build_roundtable_prompt

        prompt = build_roundtable_prompt(
            feature_name="test-feature",
            stage="IMPLEMENT",
            artifact_content="Content",
            archetypes=None,
        )

        # Should include at least some default archetypes
        assert len(prompt) > 100  # Should be substantial

    def test_build_roundtable_prompt_verdict_instructions(self):
        """build_roundtable_prompt must include verdict format instructions."""
        from spellbook_mcp.forged.roundtable import build_roundtable_prompt

        prompt = build_roundtable_prompt(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_content="Content",
            archetypes=["Magician"],
        )

        # Must explain expected output format
        assert "Verdict" in prompt or "verdict" in prompt
        assert "APPROVE" in prompt or "ITERATE" in prompt


# =============================================================================
# Task 6.2: roundtable_convene Tests
# =============================================================================


class TestRoundtableConvene:
    """Tests for roundtable_convene function."""

    def test_roundtable_convene_returns_dict(self, tmp_path):
        """roundtable_convene must return a dict."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        # Create test artifact
        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            archetypes=["Magician"],
        )

        assert isinstance(result, dict)

    def test_roundtable_convene_has_required_keys(self, tmp_path):
        """roundtable_convene result must have required keys."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            archetypes=["Magician"],
        )

        required_keys = ["consensus", "verdicts", "feedback", "return_to", "dialogue"]
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

    def test_roundtable_convene_consensus_is_bool(self, tmp_path):
        """roundtable_convene consensus must be boolean."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            archetypes=["Magician"],
        )

        assert isinstance(result["consensus"], bool)

    def test_roundtable_convene_verdicts_is_dict(self, tmp_path):
        """roundtable_convene verdicts must be dict[archetype, verdict]."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            archetypes=["Magician", "Hermit"],
        )

        assert isinstance(result["verdicts"], dict)

    def test_roundtable_convene_feedback_is_list(self, tmp_path):
        """roundtable_convene feedback must be a list."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            archetypes=["Magician"],
        )

        assert isinstance(result["feedback"], list)

    def test_roundtable_convene_return_to_is_stage_or_none(self, tmp_path):
        """roundtable_convene return_to must be valid stage or None."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact
        from spellbook_mcp.forged.models import VALID_STAGES

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            archetypes=["Magician"],
        )

        if result["return_to"] is not None:
            assert result["return_to"] in VALID_STAGES

    def test_roundtable_convene_dialogue_is_string(self, tmp_path):
        """roundtable_convene dialogue must be a string."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            archetypes=["Magician"],
        )

        assert isinstance(result["dialogue"], str)

    def test_roundtable_convene_nonexistent_artifact_error(self):
        """roundtable_convene with nonexistent artifact must error."""
        from spellbook_mcp.forged.roundtable import roundtable_convene

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path="/nonexistent/path/design.md",
            archetypes=["Magician"],
        )

        # Should indicate error state
        assert result["consensus"] is False
        assert "error" in result or len(result["feedback"]) > 0

    def test_roundtable_convene_invalid_stage_error(self, tmp_path):
        """roundtable_convene with invalid stage must error."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        with pytest.raises(ValueError) as exc_info:
            roundtable_convene(
                feature_name="test-feature",
                stage="INVALID_STAGE",
                artifact_path=str(artifact_path),
                archetypes=["Magician"],
            )

        assert "Invalid stage" in str(exc_info.value)

    def test_roundtable_convene_uses_default_archetypes(self, tmp_path):
        """roundtable_convene uses defaults when archetypes is None."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            archetypes=None,
        )

        # Should work and have verdicts
        assert isinstance(result["verdicts"], dict)


# =============================================================================
# Task 6.4: roundtable_debate Tests
# =============================================================================


class TestRoundtableDebate:
    """Tests for roundtable_debate function."""

    def test_roundtable_debate_returns_dict(self, tmp_path):
        """roundtable_debate must return a dict."""
        from spellbook_mcp.forged.roundtable import roundtable_debate
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        conflicting_verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ITERATE",
            "Fool": "APPROVE",
        }

        result = roundtable_debate(
            feature_name="test-feature",
            conflicting_verdicts=conflicting_verdicts,
            artifact_path=str(artifact_path),
        )

        assert isinstance(result, dict)

    def test_roundtable_debate_has_required_keys(self, tmp_path):
        """roundtable_debate result must have required keys."""
        from spellbook_mcp.forged.roundtable import roundtable_debate
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        conflicting_verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ITERATE",
        }

        result = roundtable_debate(
            feature_name="test-feature",
            conflicting_verdicts=conflicting_verdicts,
            artifact_path=str(artifact_path),
        )

        required_keys = ["binding_decision", "reasoning", "moderator", "dialogue"]
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

    def test_roundtable_debate_binding_decision_is_verdict(self, tmp_path):
        """roundtable_debate binding_decision must be valid verdict."""
        from spellbook_mcp.forged.roundtable import roundtable_debate
        from spellbook_mcp.forged.verdict_parsing import VALID_ROUNDTABLE_VERDICTS
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        conflicting_verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ITERATE",
        }

        result = roundtable_debate(
            feature_name="test-feature",
            conflicting_verdicts=conflicting_verdicts,
            artifact_path=str(artifact_path),
        )

        assert result["binding_decision"] in VALID_ROUNDTABLE_VERDICTS

    def test_roundtable_debate_moderator_is_justice(self, tmp_path):
        """roundtable_debate must use Justice as moderator."""
        from spellbook_mcp.forged.roundtable import roundtable_debate
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        conflicting_verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ITERATE",
        }

        result = roundtable_debate(
            feature_name="test-feature",
            conflicting_verdicts=conflicting_verdicts,
            artifact_path=str(artifact_path),
        )

        assert result["moderator"] == "Justice"

    def test_roundtable_debate_reasoning_is_string(self, tmp_path):
        """roundtable_debate reasoning must be a string (initially empty, filled after LLM)."""
        from spellbook_mcp.forged.roundtable import roundtable_debate
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "design.md"
        write_artifact(str(artifact_path), "# Design Document")

        conflicting_verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ITERATE",
        }

        result = roundtable_debate(
            feature_name="test-feature",
            conflicting_verdicts=conflicting_verdicts,
            artifact_path=str(artifact_path),
        )

        # The reasoning field is a string (initially empty, populated after LLM response)
        assert isinstance(result["reasoning"], str)
        # The dialogue field contains the prompt and should have content
        assert len(result["dialogue"]) > 0

    def test_roundtable_debate_nonexistent_artifact_error(self):
        """roundtable_debate with nonexistent artifact must error."""
        from spellbook_mcp.forged.roundtable import roundtable_debate

        conflicting_verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ITERATE",
        }

        result = roundtable_debate(
            feature_name="test-feature",
            conflicting_verdicts=conflicting_verdicts,
            artifact_path="/nonexistent/path/design.md",
        )

        # Should indicate error in some way
        assert "error" in result or result["binding_decision"] == "ABSTAIN"


# =============================================================================
# Task 6.5: Conflict Resolution Protocol Tests
# =============================================================================


class TestConflictResolution:
    """Tests for conflict resolution protocol."""

    def test_determine_consensus_all_approve(self):
        """determine_consensus returns True when all APPROVE."""
        from spellbook_mcp.forged.roundtable import determine_consensus

        verdicts = {
            "Magician": "APPROVE",
            "Hermit": "APPROVE",
            "Fool": "APPROVE",
        }

        consensus, return_to = determine_consensus(verdicts, "DESIGN")

        assert consensus is True
        assert return_to is None

    def test_determine_consensus_any_iterate(self):
        """determine_consensus returns False when any ITERATE."""
        from spellbook_mcp.forged.roundtable import determine_consensus

        verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ITERATE",
            "Fool": "APPROVE",
        }

        consensus, return_to = determine_consensus(verdicts, "DESIGN")

        assert consensus is False

    def test_determine_consensus_abstain_ignored(self):
        """determine_consensus ignores ABSTAIN verdicts."""
        from spellbook_mcp.forged.roundtable import determine_consensus

        verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ABSTAIN",
            "Fool": "APPROVE",
        }

        consensus, return_to = determine_consensus(verdicts, "DESIGN")

        # Should be True since ABSTAIN doesn't count against
        assert consensus is True

    def test_determine_consensus_returns_stage_on_iterate(self):
        """determine_consensus returns return_to stage on ITERATE."""
        from spellbook_mcp.forged.roundtable import determine_consensus
        from spellbook_mcp.forged.models import VALID_STAGES

        verdicts = {
            "Magician": "ITERATE",
            "Hermit": "APPROVE",
        }

        consensus, return_to = determine_consensus(verdicts, "IMPLEMENT")

        assert consensus is False
        assert return_to is not None
        assert return_to in VALID_STAGES

    def test_determine_consensus_empty_verdicts(self):
        """determine_consensus handles empty verdicts."""
        from spellbook_mcp.forged.roundtable import determine_consensus

        consensus, return_to = determine_consensus({}, "DESIGN")

        # Empty verdicts should be treated as no objections (consensus)
        assert consensus is True
        assert return_to is None

    def test_has_conflict_detects_disagreement(self):
        """has_conflict returns True when archetypes disagree."""
        from spellbook_mcp.forged.roundtable import has_conflict

        verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ITERATE",
            "Fool": "APPROVE",
        }

        assert has_conflict(verdicts) is True

    def test_has_conflict_no_disagreement(self):
        """has_conflict returns False when all agree."""
        from spellbook_mcp.forged.roundtable import has_conflict

        verdicts = {
            "Magician": "APPROVE",
            "Hermit": "APPROVE",
            "Fool": "APPROVE",
        }

        assert has_conflict(verdicts) is False

    def test_has_conflict_abstain_not_conflict(self):
        """has_conflict does not count ABSTAIN as conflict."""
        from spellbook_mcp.forged.roundtable import has_conflict

        verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ABSTAIN",
            "Fool": "APPROVE",
        }

        assert has_conflict(verdicts) is False


# =============================================================================
# Task 6.2: Default Archetypes by Stage Tests
# =============================================================================


class TestDefaultArchetypesByStage:
    """Tests for default archetype selection by stage."""

    def test_get_default_archetypes_exists(self):
        """get_default_archetypes function must exist."""
        from spellbook_mcp.forged.roundtable import get_default_archetypes

        assert callable(get_default_archetypes)

    def test_get_default_archetypes_discover(self):
        """DISCOVER stage should use discovery-focused archetypes."""
        from spellbook_mcp.forged.roundtable import get_default_archetypes

        archetypes = get_default_archetypes("DISCOVER")

        assert isinstance(archetypes, list)
        assert len(archetypes) >= 3
        # Fool (naive questions) and Queen (user needs) are good for discovery
        assert "Fool" in archetypes or "Queen" in archetypes

    def test_get_default_archetypes_design(self):
        """DESIGN stage should use design-focused archetypes."""
        from spellbook_mcp.forged.roundtable import get_default_archetypes

        archetypes = get_default_archetypes("DESIGN")

        assert isinstance(archetypes, list)
        assert len(archetypes) >= 3
        # Hermit (deep analysis) and Hierophant (standards) are good for design
        assert "Hermit" in archetypes or "Hierophant" in archetypes

    def test_get_default_archetypes_implement(self):
        """IMPLEMENT stage should use implementation-focused archetypes."""
        from spellbook_mcp.forged.roundtable import get_default_archetypes

        archetypes = get_default_archetypes("IMPLEMENT")

        assert isinstance(archetypes, list)
        assert len(archetypes) >= 3
        # Magician (technical) is critical for implementation
        assert "Magician" in archetypes

    def test_get_default_archetypes_always_includes_justice(self):
        """All stages should include Justice for synthesis."""
        from spellbook_mcp.forged.roundtable import get_default_archetypes
        from spellbook_mcp.forged.models import VALID_STAGES

        for stage in VALID_STAGES:
            if stage not in ["COMPLETE", "ESCALATED"]:
                archetypes = get_default_archetypes(stage)
                assert "Justice" in archetypes, f"Justice missing from {stage}"

    def test_get_default_archetypes_invalid_stage(self):
        """get_default_archetypes with invalid stage raises ValueError."""
        from spellbook_mcp.forged.roundtable import get_default_archetypes

        with pytest.raises(ValueError):
            get_default_archetypes("INVALID_STAGE")


# =============================================================================
# Integration Tests
# =============================================================================


class TestRoundtableIntegration:
    """Integration tests for roundtable workflow."""

    def test_full_approval_workflow(self, tmp_path):
        """Test complete workflow with unanimous approval."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        # Create a high-quality artifact
        artifact_path = tmp_path / "design.md"
        content = """# Feature Design: User Authentication

## Overview
Implement secure user authentication using industry-standard practices.

## Requirements
1. Password hashing with bcrypt
2. JWT tokens for session management
3. Rate limiting on login attempts

## Technical Approach
Use established libraries and follow OWASP guidelines.
"""
        write_artifact(str(artifact_path), content)

        result = roundtable_convene(
            feature_name="user-auth",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            archetypes=["Magician", "Hierophant", "Justice"],
        )

        # Should have all required keys
        assert "consensus" in result
        assert "verdicts" in result
        assert "feedback" in result
        assert "dialogue" in result

    def test_convene_then_debate_workflow(self, tmp_path):
        """Test workflow where convene leads to debate."""
        from spellbook_mcp.forged.roundtable import (
            roundtable_convene,
            roundtable_debate,
            has_conflict,
        )
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_path = tmp_path / "plan.md"
        write_artifact(str(artifact_path), "# Implementation Plan")

        convene_result = roundtable_convene(
            feature_name="test-feature",
            stage="PLAN",
            artifact_path=str(artifact_path),
            archetypes=["Magician", "Hermit", "Fool"],
        )

        # If there's conflict, debate should resolve it
        if has_conflict(convene_result["verdicts"]):
            debate_result = roundtable_debate(
                feature_name="test-feature",
                conflicting_verdicts=convene_result["verdicts"],
                artifact_path=str(artifact_path),
            )

            assert "binding_decision" in debate_result
            assert debate_result["moderator"] == "Justice"
