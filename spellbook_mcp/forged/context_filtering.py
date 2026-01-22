"""Context filtering algorithms for the Forged autonomous development system.

These functions select and prioritize content for inclusion in constrained
context windows, ensuring the most relevant information fits within token budgets.
"""

import math
from dataclasses import dataclass

from spellbook_mcp.forged.models import Feedback, IterationState

# Common English stop words for filtering in similarity calculations
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
    }
)

# Characters per token (conservative estimate)
CHARS_PER_TOKEN = 4


def estimate_tokens(content: str) -> int:
    """Estimate token count from character count.

    Uses a conservative estimate of 4 characters per token.

    Args:
        content: Text content to estimate tokens for

    Returns:
        Estimated token count (rounded up)
    """
    if not content:
        return 0
    return math.ceil(len(content) / CHARS_PER_TOKEN)


def truncate_smart(
    content: str, max_tokens: int, preserve_structure: bool = True
) -> str:
    """Truncate content to fit token budget while preserving structure.

    Algorithm:
    1. If content fits, return as-is
    2. If markdown/code, preserve:
       - First N lines (intro, ~20%)
       - Section headers
       - Last M lines (conclusion, ~10%)
       - Truncation marker in middle
    3. If prose, truncate at sentence boundaries

    Args:
        content: Text content to truncate
        max_tokens: Maximum token budget
        preserve_structure: If True, preserve structural elements like headers

    Returns:
        Truncated content fitting within budget
    """
    if max_tokens <= 0:
        return ""

    max_chars = max_tokens * CHARS_PER_TOKEN

    if len(content) <= max_chars:
        return content

    if not preserve_structure:
        # Truncate prose at sentence boundary
        return _truncate_prose(content, max_chars)

    # Preserve structure for markdown/code
    return _truncate_structured(content, max_chars)


def _truncate_prose(content: str, max_chars: int) -> str:
    """Truncate prose at sentence boundaries.

    Args:
        content: Prose text to truncate
        max_chars: Maximum characters allowed

    Returns:
        Truncated text ending at a sentence boundary
    """
    marker = " [...]"
    available = max_chars - len(marker)

    if available <= 0:
        return "[...]"

    # Find the last sentence boundary before the limit
    truncated = content[:available]

    # Look for sentence-ending punctuation
    last_period = truncated.rfind(". ")
    last_exclaim = truncated.rfind("! ")
    last_question = truncated.rfind("? ")

    # Find the best cut point
    cut_point = max(last_period, last_exclaim, last_question)

    if cut_point > 0:
        return truncated[: cut_point + 1] + marker
    else:
        # No sentence boundary found, just cut and add marker
        return truncated.rstrip() + marker


def _truncate_structured(content: str, max_chars: int) -> str:
    """Truncate structured content (markdown/code) preserving key elements.

    Preserves:
    - First 20% of lines (introduction)
    - Section headers (lines starting with #)
    - Last 10% of lines (conclusion)

    Args:
        content: Structured text content
        max_chars: Maximum characters allowed

    Returns:
        Truncated content with structure preserved
    """
    marker = "\n\n[...]\n\n"
    lines = content.split("\n")

    if len(lines) <= 3:
        # Very short, just truncate directly
        if len(content) > max_chars:
            return content[: max_chars - len(marker)] + marker
        return content

    # Calculate line budgets
    intro_lines = max(2, len(lines) // 5)  # 20%
    conclusion_lines = max(1, len(lines) // 10)  # 10%

    # Collect intro
    intro = lines[:intro_lines]

    # Collect conclusion
    conclusion = lines[-conclusion_lines:] if conclusion_lines > 0 else []

    # Collect headers from the middle (lines starting with #)
    middle_start = intro_lines
    middle_end = len(lines) - conclusion_lines if conclusion_lines > 0 else len(lines)
    headers = [line for line in lines[middle_start:middle_end] if line.startswith("#")]

    # Build result
    result_lines = intro + headers + [marker.strip()] + conclusion

    result = "\n".join(result_lines)

    # If still too long, progressively reduce
    while len(result) > max_chars and len(result_lines) > 3:
        # Remove headers first, keeping intro and conclusion
        if headers:
            headers = headers[:-1]
            result_lines = intro + headers + [marker.strip()] + conclusion
            result = "\n".join(result_lines)
        else:
            # Reduce intro
            if len(intro) > 2:
                intro = intro[:-1]
                result_lines = intro + [marker.strip()] + conclusion
                result = "\n".join(result_lines)
            else:
                # Just truncate
                return content[: max_chars - len(marker)] + marker

    return result


def select_relevant_knowledge(
    accumulated_knowledge: dict,
    max_tokens: int,
    current_stage: str = None,
    current_issue: str = None,
) -> dict:
    """Select most relevant accumulated knowledge for current context.

    Priority order:
    1. User decisions (always included, summarized)
    2. Stage-specific learnings (if current_stage provided)
    3. Recent learnings (last 3 iterations)
    4. Keyword-matched learnings (if current_issue provided)

    Args:
        accumulated_knowledge: Dictionary of accumulated knowledge
        max_tokens: Maximum token budget
        current_stage: Current workflow stage for prioritization
        current_issue: Current issue text for keyword matching

    Returns:
        Filtered knowledge dictionary within budget
    """
    if not accumulated_knowledge:
        return {}

    max_chars = max_tokens * CHARS_PER_TOKEN
    result = {}
    used_chars = 0

    # Priority 1: User decisions (always included)
    if "user_decisions" in accumulated_knowledge:
        decisions = accumulated_knowledge["user_decisions"]
        decisions_str = str(decisions)
        if used_chars + len(decisions_str) <= max_chars:
            result["user_decisions"] = decisions
            used_chars += len(decisions_str)
        else:
            # Summarize/truncate user decisions
            truncated = _truncate_list_to_fit(
                decisions, max_chars - used_chars - 50
            )
            if truncated:
                result["user_decisions"] = truncated
                used_chars += len(str(truncated))

    # Priority 2: Stage-specific learnings
    if current_stage and "stage_learnings" in accumulated_knowledge:
        stage_learnings = accumulated_knowledge["stage_learnings"]
        if current_stage in stage_learnings:
            learnings = stage_learnings[current_stage]
            learnings_str = str(learnings)
            if used_chars + len(learnings_str) <= max_chars:
                if "stage_learnings" not in result:
                    result["stage_learnings"] = {}
                result["stage_learnings"][current_stage] = learnings
                used_chars += len(learnings_str)

    # Priority 3: Recent iteration learnings (last 3)
    if "iteration_learnings" in accumulated_knowledge:
        iter_learnings = accumulated_knowledge["iteration_learnings"]
        # Sort by iteration number (descending) and take last 3
        sorted_iters = sorted(iter_learnings.keys(), key=lambda x: int(x), reverse=True)
        recent = sorted_iters[:3]

        selected = {}
        for iter_key in recent:
            iter_content = iter_learnings[iter_key]
            iter_str = str(iter_content)
            if used_chars + len(iter_str) <= max_chars:
                selected[iter_key] = iter_content
                used_chars += len(iter_str)

        if selected:
            result["iteration_learnings"] = selected

    # Priority 4: General learnings (keyword-matched if issue provided, otherwise all)
    if "learnings" in accumulated_knowledge:
        learnings = accumulated_knowledge["learnings"]
        if isinstance(learnings, list):
            if current_issue:
                # Extract keywords from current issue for prioritization
                issue_words = _extract_keywords(current_issue)

                # Score learnings by keyword overlap
                scored = []
                for learning in learnings:
                    learning_words = _extract_keywords(learning)
                    overlap = len(issue_words & learning_words)
                    scored.append((overlap, learning))

                # Sort by score descending
                scored.sort(key=lambda x: x[0], reverse=True)
                learnings_to_add = [learning for _, learning in scored]
            else:
                # No issue, just use all learnings in order
                learnings_to_add = learnings

            # Add learnings that fit
            selected = []
            for learning in learnings_to_add:
                learning_str = str(learning)
                if used_chars + len(learning_str) <= max_chars:
                    selected.append(learning)
                    used_chars += len(learning_str)

            if selected:
                result["learnings"] = selected

    return result


def _truncate_list_to_fit(items: list, max_chars: int) -> list:
    """Truncate a list of items to fit within character budget.

    Args:
        items: List of items (strings or other)
        max_chars: Maximum characters for serialized output

    Returns:
        Truncated list fitting within budget
    """
    if max_chars <= 0:
        return []

    result = []
    used = 0

    for item in items:
        item_str = str(item)
        if used + len(item_str) <= max_chars:
            result.append(item)
            used += len(item_str)
        else:
            break

    return result


def _extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text, filtering stop words.

    Args:
        text: Text to extract keywords from

    Returns:
        Set of lowercase keywords
    """
    words = text.lower().split()
    # Filter stop words and short words
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


def similarity(text1: str, text2: str, threshold: float = 0.8) -> float:
    """Compute semantic similarity between two texts.

    Uses Jaccard similarity on normalized word sets with stop word filtering.

    Args:
        text1: First text
        text2: Second text
        threshold: Similarity threshold (for context, doesn't affect calculation)

    Returns:
        Similarity score between 0.0 and 1.0
    """
    # Handle empty strings
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0

    # Normalize and extract words
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    # Filter stop words
    words1 = {w for w in words1 if w not in STOP_WORDS}
    words2 = {w for w in words2 if w not in STOP_WORDS}

    # Handle case where all words were stop words
    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0

    # Jaccard similarity: intersection / union
    intersection = len(words1 & words2)
    union = len(words1 | words2)

    if union == 0:
        return 1.0

    return intersection / union


def filter_feedback(
    history: list,
    stage: str,
    limit: int,
    dedup_threshold: float = 0.8,
) -> list:
    """Filter feedback history to most relevant items for current stage.

    Algorithm:
    1. Prioritize: same stage > blocking severity > recent
    2. Deduplicate similar feedback (similarity > threshold)
    3. Return top `limit` items

    Args:
        history: List of Feedback objects
        stage: Current workflow stage
        limit: Maximum number of items to return
        dedup_threshold: Similarity threshold for deduplication

    Returns:
        Filtered and deduplicated list of Feedback objects
    """
    if not history:
        return []

    # Score each feedback item
    def score_feedback(fb: Feedback) -> tuple:
        """Return scoring tuple (higher is better priority)."""
        stage_match = 1 if fb.stage == stage else 0
        severity_score = {"blocking": 2, "significant": 1, "minor": 0}.get(
            fb.severity, 0
        )
        recency = fb.iteration  # Higher iteration = more recent

        return (stage_match, severity_score, recency)

    # Sort by score (descending)
    sorted_feedback = sorted(history, key=score_feedback, reverse=True)

    # Deduplicate similar feedback
    result = []
    for fb in sorted_feedback:
        # Check if this is too similar to any already selected
        is_duplicate = False
        for selected in result:
            sim = similarity(fb.critique, selected.critique)
            if sim >= dedup_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            result.append(fb)
            if len(result) >= limit:
                break

    return result


@dataclass
class ContextBudget:
    """Token budget allocation for context window building.

    Attributes:
        total_tokens: Total context budget (~6% of 128K)
        artifact_budget: Budget for current artifact (~500 lines of code)
        knowledge_budget: Budget for accumulated knowledge (capped to prevent domination)
        reflections_budget: Budget for reflections (~3 reflections * ~300 tokens)
        feedback_budget: Budget for feedback items (~5-7 items)
    """

    total_tokens: int = 8000
    artifact_budget: int = 3000
    knowledge_budget: int = 2000
    reflections_budget: int = 1000
    feedback_budget: int = 1500


@dataclass
class ContextWindow:
    """Built context window with prioritized content.

    Attributes:
        artifact_content: Truncated current artifact
        knowledge_items: Selected knowledge items
        reflections: Selected reflections
        feedback_items: Filtered feedback items
        total_tokens: Estimated total tokens used
    """

    artifact_content: str
    knowledge_items: dict
    reflections: list
    feedback_items: list
    total_tokens: int


def prioritize_for_context(
    state: IterationState, budget: ContextBudget
) -> ContextWindow:
    """Build context window within budget.

    Allocates the budget across different content types and uses
    the filtering functions to select the most relevant content.

    Args:
        state: Current iteration state with all accumulated data
        budget: Token budget allocation

    Returns:
        ContextWindow with prioritized content within budget
    """
    # Extract artifact content if present
    artifact_content = ""
    if "current_artifact" in state.accumulated_knowledge:
        raw_artifact = state.accumulated_knowledge["current_artifact"]
        artifact_content = truncate_smart(
            raw_artifact, max_tokens=budget.artifact_budget, preserve_structure=True
        )

    # Select knowledge (excluding artifact which we handle separately)
    knowledge_to_filter = {
        k: v for k, v in state.accumulated_knowledge.items() if k != "current_artifact"
    }
    knowledge_items = select_relevant_knowledge(
        knowledge_to_filter,
        max_tokens=budget.knowledge_budget,
        current_stage=state.current_stage,
    )

    # Extract reflections
    reflections = []
    if "reflections" in state.accumulated_knowledge:
        raw_reflections = state.accumulated_knowledge["reflections"]
        if isinstance(raw_reflections, list):
            # Truncate to fit budget
            max_reflection_chars = budget.reflections_budget * CHARS_PER_TOKEN
            used = 0
            for reflection in raw_reflections:
                reflection_str = str(reflection)
                if used + len(reflection_str) <= max_reflection_chars:
                    reflections.append(reflection)
                    used += len(reflection_str)
                else:
                    break

    # Filter feedback
    # Estimate items based on budget (rough: ~200-300 tokens per feedback item)
    estimated_items = max(1, budget.feedback_budget // 250)
    feedback_items = filter_feedback(
        state.feedback_history,
        stage=state.current_stage,
        limit=estimated_items,
    )

    # Estimate total tokens
    total_chars = (
        len(artifact_content)
        + len(str(knowledge_items))
        + len(str(reflections))
        + sum(len(str(fb.to_dict())) for fb in feedback_items)
    )
    total_tokens = math.ceil(total_chars / CHARS_PER_TOKEN)

    return ContextWindow(
        artifact_content=artifact_content,
        knowledge_items=knowledge_items,
        reflections=reflections,
        feedback_items=feedback_items,
        total_tokens=total_tokens,
    )
