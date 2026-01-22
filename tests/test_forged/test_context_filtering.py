"""Tests for forged context filtering algorithms.

These tests verify the context filtering functions that select and prioritize
content for inclusion in constrained context windows.
"""

import pytest

from spellbook_mcp.forged.models import Feedback, IterationState


class TestTruncateSmart:
    """Tests for smart truncation that preserves structure."""

    def test_content_under_budget_returns_unchanged(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        content = "Short content"
        result = truncate_smart(content, max_tokens=100)
        assert result == content

    def test_exact_budget_returns_unchanged(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        # 40 chars ~ 10 tokens at 4 chars/token
        content = "x" * 40
        result = truncate_smart(content, max_tokens=10)
        assert result == content

    def test_over_budget_gets_truncated(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        # 400 chars ~ 100 tokens, budget is 50
        content = "x" * 400
        result = truncate_smart(content, max_tokens=50)
        assert len(result) < len(content)

    def test_truncation_preserves_intro_lines(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        lines = [f"Line {i}" for i in range(100)]
        content = "\n".join(lines)
        result = truncate_smart(content, max_tokens=50, preserve_structure=True)
        # Should preserve intro lines
        assert "Line 0" in result
        assert "Line 1" in result

    def test_truncation_preserves_conclusion(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        lines = [f"Line {i}" for i in range(100)]
        content = "\n".join(lines)
        result = truncate_smart(content, max_tokens=50, preserve_structure=True)
        # Should preserve last line(s)
        assert "Line 99" in result

    def test_truncation_includes_marker(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        content = "x\n" * 200
        result = truncate_smart(content, max_tokens=50, preserve_structure=True)
        # Should include truncation marker
        assert "[...]" in result or "..." in result

    def test_markdown_preserves_headers(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        content = """# Header 1
Some content here.

## Header 2
More content here that goes on for a while.

### Header 3
Even more content.

## Header 4
Final section with content.
"""
        # Make it longer
        content = content + ("Additional content. " * 100)
        result = truncate_smart(content, max_tokens=100, preserve_structure=True)
        # Should preserve at least some headers
        assert "# Header 1" in result

    def test_prose_truncates_at_sentence_boundary(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        content = "First sentence. Second sentence. Third sentence. " * 50
        result = truncate_smart(content, max_tokens=30, preserve_structure=False)
        # Should end at a sentence boundary (period followed by space or end)
        stripped = result.rstrip()
        assert stripped.endswith(".") or stripped.endswith("[...]")

    def test_zero_budget_returns_empty_or_marker(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        content = "Some content"
        result = truncate_smart(content, max_tokens=0)
        # Should return empty or minimal marker
        assert len(result) <= 10  # Allow for truncation marker

    def test_code_block_preservation(self):
        from spellbook_mcp.forged.context_filtering import truncate_smart

        content = """# Introduction

Here's some code:

```python
def hello():
    return "world"
```

More text here.
""" + ("Extra content. " * 100)

        result = truncate_smart(content, max_tokens=80, preserve_structure=True)
        # Should preserve at least the header and intro
        assert "# Introduction" in result


class TestSelectRelevantKnowledge:
    """Tests for knowledge selection with priority ordering."""

    def test_empty_knowledge_returns_empty(self):
        from spellbook_mcp.forged.context_filtering import select_relevant_knowledge

        result = select_relevant_knowledge({}, max_tokens=1000)
        assert result == {}

    def test_under_budget_returns_all(self):
        from spellbook_mcp.forged.context_filtering import select_relevant_knowledge

        knowledge = {
            "user_decisions": ["Use pytest", "Prefer explicit imports"],
            "learnings": ["Pattern A works well"],
        }
        result = select_relevant_knowledge(knowledge, max_tokens=1000)
        assert "user_decisions" in result
        assert "learnings" in result

    def test_user_decisions_always_included(self):
        from spellbook_mcp.forged.context_filtering import select_relevant_knowledge

        knowledge = {
            "user_decisions": ["Critical decision 1", "Critical decision 2"],
            "learnings": ["Learning " * 100],  # Large learning to exceed budget
        }
        result = select_relevant_knowledge(knowledge, max_tokens=50)
        # User decisions should always be present
        assert "user_decisions" in result
        assert len(result["user_decisions"]) > 0

    def test_stage_specific_prioritized(self):
        from spellbook_mcp.forged.context_filtering import select_relevant_knowledge

        knowledge = {
            "user_decisions": ["Decision"],
            "stage_learnings": {
                "DESIGN": ["Design learning 1", "Design learning 2"],
                "IMPLEMENT": ["Implement learning 1"],
                "PLAN": ["Plan learning"],
            },
        }
        result = select_relevant_knowledge(
            knowledge, max_tokens=100, current_stage="DESIGN"
        )
        # Should include DESIGN learnings when in DESIGN stage
        if "stage_learnings" in result:
            assert "DESIGN" in result["stage_learnings"]

    def test_recent_learnings_included(self):
        from spellbook_mcp.forged.context_filtering import select_relevant_knowledge

        knowledge = {
            "iteration_learnings": {
                "1": ["Old learning"],
                "2": ["Less old learning"],
                "3": ["Recent learning"],
                "4": ["Most recent"],
            }
        }
        result = select_relevant_knowledge(knowledge, max_tokens=100)
        # Should include recent iterations (last 3)
        if "iteration_learnings" in result:
            assert "4" in result["iteration_learnings"]
            assert "3" in result["iteration_learnings"]

    def test_keyword_matching(self):
        from spellbook_mcp.forged.context_filtering import select_relevant_knowledge

        knowledge = {
            "learnings": [
                "The authentication flow has issues",
                "Database connections are slow",
                "Error handling in auth is incomplete",
            ]
        }
        result = select_relevant_knowledge(
            knowledge, max_tokens=100, current_issue="authentication error"
        )
        # Should prioritize auth-related learnings
        if "learnings" in result and result["learnings"]:
            # At least one auth-related learning should be included
            auth_related = [
                l for l in result["learnings"] if "auth" in l.lower()
            ]
            assert len(auth_related) > 0

    def test_budget_respected(self):
        from spellbook_mcp.forged.context_filtering import select_relevant_knowledge

        # Create knowledge that exceeds budget
        knowledge = {
            "user_decisions": ["Short decision"],
            "learnings": ["Very long learning content " * 50 for _ in range(10)],
        }
        result = select_relevant_knowledge(knowledge, max_tokens=50)
        # Result should fit within budget (rough estimate)
        total_chars = sum(
            len(str(v)) for v in result.values()
        )
        # 50 tokens * 4 chars/token = 200 chars max (with some slack)
        assert total_chars < 300


class TestSimilarity:
    """Tests for text similarity computation."""

    def test_identical_texts_return_one(self):
        from spellbook_mcp.forged.context_filtering import similarity

        text = "The quick brown fox"
        result = similarity(text, text)
        assert result == 1.0

    def test_completely_different_texts_return_zero(self):
        from spellbook_mcp.forged.context_filtering import similarity

        text1 = "alpha beta gamma"
        text2 = "one two three"
        result = similarity(text1, text2)
        assert result == 0.0

    def test_partial_overlap_returns_intermediate(self):
        from spellbook_mcp.forged.context_filtering import similarity

        text1 = "the quick brown fox jumps"
        text2 = "the quick brown dog runs"
        result = similarity(text1, text2)
        # Should be between 0 and 1, with some overlap
        assert 0 < result < 1

    def test_case_insensitive(self):
        from spellbook_mcp.forged.context_filtering import similarity

        text1 = "THE QUICK BROWN"
        text2 = "the quick brown"
        result = similarity(text1, text2)
        assert result == 1.0

    def test_stop_words_filtered(self):
        from spellbook_mcp.forged.context_filtering import similarity

        # These differ only in stop words
        text1 = "error in the authentication"
        text2 = "error with an authentication"
        result = similarity(text1, text2)
        # Should be very similar after stop word filtering
        assert result > 0.8

    def test_empty_texts(self):
        from spellbook_mcp.forged.context_filtering import similarity

        result = similarity("", "")
        # Empty texts should either return 1.0 (both same) or 0.0 (no content)
        assert result in [0.0, 1.0]

    def test_one_empty_text(self):
        from spellbook_mcp.forged.context_filtering import similarity

        result = similarity("some content", "")
        assert result == 0.0

    def test_threshold_parameter(self):
        from spellbook_mcp.forged.context_filtering import similarity

        text1 = "quick brown fox"
        text2 = "quick brown dog"
        # Threshold doesn't change the similarity value, just provides context
        result = similarity(text1, text2, threshold=0.5)
        assert isinstance(result, float)


class TestFilterFeedback:
    """Tests for feedback history filtering."""

    def test_empty_history_returns_empty(self):
        from spellbook_mcp.forged.context_filtering import filter_feedback

        result = filter_feedback([], stage="DESIGN", limit=5)
        assert result == []

    def test_respects_limit(self):
        from spellbook_mcp.forged.context_filtering import filter_feedback

        history = [
            Feedback(
                source=f"validator{i}",
                stage="DESIGN",
                return_to="DESIGN",
                critique=f"Issue {i}",
                evidence="evidence",
                suggestion="fix it",
                severity="minor",
                iteration=i,
            )
            for i in range(10)
        ]
        result = filter_feedback(history, stage="DESIGN", limit=3)
        assert len(result) == 3

    def test_prioritizes_same_stage(self):
        from spellbook_mcp.forged.context_filtering import filter_feedback

        history = [
            Feedback(
                source="validator1",
                stage="IMPLEMENT",
                return_to="IMPLEMENT",
                critique="Implement issue",
                evidence="evidence",
                suggestion="fix",
                severity="minor",
                iteration=1,
            ),
            Feedback(
                source="validator2",
                stage="DESIGN",
                return_to="DESIGN",
                critique="Design issue",
                evidence="evidence",
                suggestion="fix",
                severity="minor",
                iteration=2,
            ),
        ]
        result = filter_feedback(history, stage="DESIGN", limit=1)
        assert result[0].stage == "DESIGN"

    def test_prioritizes_blocking_severity(self):
        from spellbook_mcp.forged.context_filtering import filter_feedback

        history = [
            Feedback(
                source="v1",
                stage="DESIGN",
                return_to="DESIGN",
                critique="Minor issue",
                evidence="e",
                suggestion="s",
                severity="minor",
                iteration=1,
            ),
            Feedback(
                source="v2",
                stage="DESIGN",
                return_to="DESIGN",
                critique="Blocking issue",
                evidence="e",
                suggestion="s",
                severity="blocking",
                iteration=1,
            ),
        ]
        result = filter_feedback(history, stage="DESIGN", limit=1)
        assert result[0].severity == "blocking"

    def test_prioritizes_recent(self):
        from spellbook_mcp.forged.context_filtering import filter_feedback

        history = [
            Feedback(
                source="v1",
                stage="OTHER",
                return_to="OTHER",
                critique="Old issue",
                evidence="e",
                suggestion="s",
                severity="minor",
                iteration=1,
            ),
            Feedback(
                source="v2",
                stage="OTHER",
                return_to="OTHER",
                critique="New issue",
                evidence="e",
                suggestion="s",
                severity="minor",
                iteration=5,
            ),
        ]
        result = filter_feedback(history, stage="DESIGN", limit=1)
        # Should prefer more recent when other factors equal
        assert result[0].iteration == 5

    def test_deduplication_removes_similar(self):
        from spellbook_mcp.forged.context_filtering import filter_feedback

        # Use texts that will be similar after stop word filtering
        # Jaccard similarity = intersection / union
        # "authentication login validation error" vs "authentication login validation problem"
        # Intersection: {authentication, login, validation} = 3
        # Union: {authentication, login, validation, error, problem} = 5
        # Similarity: 3/5 = 0.6
        history = [
            Feedback(
                source="v1",
                stage="DESIGN",
                return_to="DESIGN",
                critique="authentication login validation error",
                evidence="e",
                suggestion="s",
                severity="minor",
                iteration=1,
            ),
            Feedback(
                source="v2",
                stage="DESIGN",
                return_to="DESIGN",
                critique="authentication login validation problem",
                evidence="e",
                suggestion="s",
                severity="minor",
                iteration=2,
            ),
            Feedback(
                source="v3",
                stage="DESIGN",
                return_to="DESIGN",
                critique="database connection pooling slow",
                evidence="e",
                suggestion="s",
                severity="minor",
                iteration=3,
            ),
        ]
        # With threshold=0.5, the two auth feedbacks (similarity=0.6) will be deduped
        result = filter_feedback(history, stage="DESIGN", limit=3, dedup_threshold=0.5)
        # Should have removed one of the similar auth issues
        assert len(result) <= 2

    def test_dedup_threshold_respected(self):
        from spellbook_mcp.forged.context_filtering import filter_feedback

        history = [
            Feedback(
                source="v1",
                stage="DESIGN",
                return_to="DESIGN",
                critique="auth issue one",
                evidence="e",
                suggestion="s",
                severity="minor",
                iteration=1,
            ),
            Feedback(
                source="v2",
                stage="DESIGN",
                return_to="DESIGN",
                critique="auth issue two",
                evidence="e",
                suggestion="s",
                severity="minor",
                iteration=2,
            ),
        ]
        # With high threshold, should keep both (not similar enough)
        result_high = filter_feedback(history, stage="DESIGN", limit=5, dedup_threshold=0.95)
        # With low threshold, may deduplicate
        result_low = filter_feedback(history, stage="DESIGN", limit=5, dedup_threshold=0.3)
        # Lower threshold = more aggressive dedup
        assert len(result_high) >= len(result_low)


class TestContextBudget:
    """Tests for ContextBudget dataclass."""

    def test_default_values(self):
        from spellbook_mcp.forged.context_filtering import ContextBudget

        budget = ContextBudget()
        assert budget.total_tokens == 8000
        assert budget.artifact_budget == 3000
        assert budget.knowledge_budget == 2000
        assert budget.reflections_budget == 1000
        assert budget.feedback_budget == 1500

    def test_custom_values(self):
        from spellbook_mcp.forged.context_filtering import ContextBudget

        budget = ContextBudget(
            total_tokens=5000,
            artifact_budget=2000,
            knowledge_budget=1000,
            reflections_budget=500,
            feedback_budget=1000,
        )
        assert budget.total_tokens == 5000
        assert budget.artifact_budget == 2000


class TestContextWindow:
    """Tests for ContextWindow dataclass."""

    def test_fields_present(self):
        from spellbook_mcp.forged.context_filtering import ContextWindow

        window = ContextWindow(
            artifact_content="code here",
            knowledge_items={"decisions": ["d1"]},
            reflections=["reflection 1"],
            feedback_items=[],
            total_tokens=100,
        )
        assert window.artifact_content == "code here"
        assert window.knowledge_items == {"decisions": ["d1"]}
        assert window.reflections == ["reflection 1"]
        assert window.feedback_items == []
        assert window.total_tokens == 100


class TestPrioritizeForContext:
    """Tests for context window building within budget."""

    def test_returns_context_window(self):
        from spellbook_mcp.forged.context_filtering import (
            ContextBudget,
            ContextWindow,
            prioritize_for_context,
        )

        state = IterationState(
            iteration_number=1,
            current_stage="DESIGN",
            feedback_history=[],
            accumulated_knowledge={},
            artifacts_produced=[],
            preferences={},
        )
        budget = ContextBudget()
        result = prioritize_for_context(state, budget)
        assert isinstance(result, ContextWindow)

    def test_respects_artifact_budget(self):
        from spellbook_mcp.forged.context_filtering import (
            ContextBudget,
            prioritize_for_context,
        )

        state = IterationState(
            iteration_number=1,
            current_stage="DESIGN",
            feedback_history=[],
            accumulated_knowledge={"current_artifact": "x" * 20000},  # Large artifact
            artifacts_produced=[],
            preferences={},
        )
        budget = ContextBudget(artifact_budget=100)
        result = prioritize_for_context(state, budget)
        # Artifact should be truncated to fit budget (100 tokens * 4 chars = 400)
        assert len(result.artifact_content) <= 500  # Some slack for truncation marker

    def test_respects_knowledge_budget(self):
        from spellbook_mcp.forged.context_filtering import (
            ContextBudget,
            prioritize_for_context,
        )

        state = IterationState(
            iteration_number=1,
            current_stage="DESIGN",
            feedback_history=[],
            accumulated_knowledge={
                "user_decisions": ["Decision " * 100 for _ in range(10)],
                "learnings": ["Learning " * 100 for _ in range(10)],
            },
            artifacts_produced=[],
            preferences={},
        )
        budget = ContextBudget(knowledge_budget=50)
        result = prioritize_for_context(state, budget)
        # Knowledge should be filtered to fit budget
        total_chars = sum(len(str(v)) for v in result.knowledge_items.values())
        assert total_chars < 500  # 50 tokens * 4 chars + slack

    def test_respects_feedback_budget(self):
        from spellbook_mcp.forged.context_filtering import (
            ContextBudget,
            prioritize_for_context,
        )

        history = [
            Feedback(
                source=f"v{i}",
                stage="DESIGN",
                return_to="DESIGN",
                critique="Issue " * 50,
                evidence="evidence " * 50,
                suggestion="fix " * 50,
                severity="minor",
                iteration=i,
            )
            for i in range(20)
        ]
        state = IterationState(
            iteration_number=10,
            current_stage="DESIGN",
            feedback_history=history,
            accumulated_knowledge={},
            artifacts_produced=[],
            preferences={},
        )
        budget = ContextBudget(feedback_budget=100)
        result = prioritize_for_context(state, budget)
        # Should limit feedback items
        assert len(result.feedback_items) < 20

    def test_includes_reflections(self):
        from spellbook_mcp.forged.context_filtering import (
            ContextBudget,
            prioritize_for_context,
        )

        state = IterationState(
            iteration_number=5,
            current_stage="IMPLEMENT",
            feedback_history=[],
            accumulated_knowledge={
                "reflections": [
                    "Reflection 1: learned about X",
                    "Reflection 2: learned about Y",
                    "Reflection 3: learned about Z",
                ]
            },
            artifacts_produced=[],
            preferences={},
        )
        budget = ContextBudget(reflections_budget=500)
        result = prioritize_for_context(state, budget)
        # Should include some reflections
        assert len(result.reflections) > 0

    def test_total_tokens_estimated(self):
        from spellbook_mcp.forged.context_filtering import (
            ContextBudget,
            prioritize_for_context,
        )

        state = IterationState(
            iteration_number=1,
            current_stage="DESIGN",
            feedback_history=[],
            accumulated_knowledge={"current_artifact": "test content"},
            artifacts_produced=[],
            preferences={},
        )
        budget = ContextBudget()
        result = prioritize_for_context(state, budget)
        # Should have a non-negative token count
        assert result.total_tokens >= 0

    def test_empty_state_produces_valid_window(self):
        from spellbook_mcp.forged.context_filtering import (
            ContextBudget,
            ContextWindow,
            prioritize_for_context,
        )

        state = IterationState(
            iteration_number=1,
            current_stage="DISCOVER",
            feedback_history=[],
            accumulated_knowledge={},
            artifacts_produced=[],
            preferences={},
        )
        budget = ContextBudget()
        result = prioritize_for_context(state, budget)
        assert isinstance(result, ContextWindow)
        assert result.artifact_content == ""
        assert result.knowledge_items == {}
        assert result.reflections == []
        assert result.feedback_items == []


class TestTokenEstimation:
    """Tests for token estimation utility."""

    def test_estimate_tokens_basic(self):
        from spellbook_mcp.forged.context_filtering import estimate_tokens

        # 40 chars / 4 chars per token = 10 tokens
        result = estimate_tokens("x" * 40)
        assert result == 10

    def test_estimate_tokens_empty(self):
        from spellbook_mcp.forged.context_filtering import estimate_tokens

        result = estimate_tokens("")
        assert result == 0

    def test_estimate_tokens_rounds_up(self):
        from spellbook_mcp.forged.context_filtering import estimate_tokens

        # 5 chars / 4 = 1.25, should round up to 2
        result = estimate_tokens("hello")
        assert result == 2
