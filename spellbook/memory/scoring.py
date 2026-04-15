"""Search scoring for the file-based memory system.

Implements BM25-inspired term frequency scoring, temporal decay,
and branch proximity multipliers for ranking memory search results.
"""

import math
from datetime import date

from spellbook.memory.models import MemoryFile, MemoryFrontmatter


# Temporal decay constant: exp(-0.0077 * days) gives ~90-day half-life
_DECAY_LAMBDA = 0.0077

# Confidence decay thresholds (days since last_verified or created).
_CONFIDENCE_HIGH_MAX_DAYS = 30
_CONFIDENCE_MEDIUM_MAX_DAYS = 90

# Score contribution per effective confidence level.
_CONFIDENCE_MULTIPLIERS = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.4,
}


def effective_confidence(
    frontmatter: MemoryFrontmatter,
    today: date | None = None,
) -> str:
    """Compute the effective confidence of a memory, applying lazy time decay.

    Decay is based on ``last_verified`` if present, otherwise ``created``.
    The stored frontmatter value is NOT rewritten; this is a pure function.

    Thresholds:
      - <= 30 days: "high"
      - 30 < days <= 90: "medium"
      - > 90 days: "low"

    A stored confidence of ``None`` is treated as "high" (safety net for
    memories that predate the field). A stored confidence value will never
    be upgraded by decay; decay can only downgrade below the stored level.

    Args:
        frontmatter: The memory's frontmatter.
        today: Optional date to use as "now" (default: today).

    Returns:
        One of "high", "medium", "low".
    """
    if today is None:
        today = date.today()

    stored = frontmatter.confidence if frontmatter.confidence is not None else "high"

    reference = frontmatter.last_verified
    if reference is None:
        reference = frontmatter.created

    if reference is None:
        # No timestamp to decay against; trust stored value.
        return stored

    days = (today - reference).days
    if days <= _CONFIDENCE_HIGH_MAX_DAYS:
        decayed = "high"
    elif days <= _CONFIDENCE_MEDIUM_MAX_DAYS:
        decayed = "medium"
    else:
        decayed = "low"

    # Decay can only downgrade, never upgrade below stored level.
    order = {"high": 2, "medium": 1, "low": 0}
    return decayed if order[decayed] < order[stored] else stored


def compute_confidence_multiplier(
    frontmatter: MemoryFrontmatter,
    today: date | None = None,
) -> float:
    """Return the score multiplier for a memory's effective confidence.

    Maps: high -> 1.0, medium -> 0.7, low -> 0.4.
    """
    return _CONFIDENCE_MULTIPLIERS[effective_confidence(frontmatter, today=today)]

# Branch relationship multipliers.
# "ancestor" and "descendant" are reserved for future Serena integration
# that will use git merge-base to detect branch ancestry relationships.
# Currently only "same" and "unrelated" are used by get_branch_multiplier().
_BRANCH_MULTIPLIERS = {
    "same": 2.0,
    "ancestor": 1.5,       # Reserved: requires git ancestry detection
    "descendant": 1.2,     # Reserved: requires git ancestry detection
    "unrelated": 1.0,
}


def compute_score(
    memory: MemoryFile,
    query_terms: list[str],
    current_branch: str | None,
) -> float:
    """Compute a relevance score for a memory against query terms.

    Combines:
    - Term frequency (BM25-inspired): how often query terms appear in content + tags
    - Temporal decay: exp(-0.0077 * days_since_created), ~90-day half-life
    - Branch multiplier: 2x for same branch, 1.5x ancestor, etc.

    Args:
        memory: The memory file to score.
        query_terms: Lowercased query terms to match against.
        current_branch: Current git branch for branch multiplier.

    Returns:
        A non-negative float score. Higher is more relevant.
    """
    if not query_terms:
        return 0.0

    # Term frequency in content
    content_lower = memory.content.lower()
    tf_content = sum(content_lower.count(term) for term in query_terms)

    # Term frequency in tags
    tags_text = " ".join(memory.frontmatter.tags).lower()
    tf_tags = sum(tags_text.count(term) for term in query_terms)

    # BM25-inspired: saturating tf with k1=1.5, b=0.75
    # Simplified: score = tf / (tf + 1.5) for content, plus tag bonus
    doc_len = len(content_lower.split())
    avg_doc_len = 50.0  # assumed average
    k1 = 1.5
    b = 0.75
    norm_len = 1.0 - b + b * (doc_len / avg_doc_len)
    bm25_content = tf_content / (tf_content + k1 * norm_len) if tf_content > 0 else 0.0

    # Tag matches get a flat bonus per matching term
    tag_bonus = 0.5 * tf_tags

    tf_score = bm25_content + tag_bonus

    # Temporal decay
    if memory.frontmatter.created is not None:
        days = (date.today() - memory.frontmatter.created).days
        decay = math.exp(-_DECAY_LAMBDA * max(days, 0))
    else:
        decay = 0.5  # Unknown age gets half weight

    # Branch multiplier
    branch_mult = get_branch_multiplier(
        memory.frontmatter.branch, current_branch, project_root=None
    )

    # Confidence multiplier (lazy time-based decay, no frontmatter rewrite).
    confidence_mult = compute_confidence_multiplier(memory.frontmatter)

    return tf_score * decay * confidence_mult * branch_mult


def get_branch_multiplier(
    memory_branch: str | None,
    current_branch: str | None,
    project_root: str | None,
) -> float:
    """Determine branch relationship multiplier.

    For now, only detects "same" vs "unrelated". Ancestor/descendant detection
    requires git operations and will be added when project_root is provided.

    Args:
        memory_branch: Branch where the memory was created.
        current_branch: Current git branch.
        project_root: Git repo root (unused for now, reserved for ancestry checks).

    Returns:
        Multiplier: 2.0 (same), 1.5 (ancestor), 1.2 (descendant), 1.0 (unrelated/unknown).
    """
    if memory_branch is None or current_branch is None:
        return _BRANCH_MULTIPLIERS["unrelated"]

    if memory_branch == current_branch:
        return _BRANCH_MULTIPLIERS["same"]

    # Ancestry detection would go here with git merge-base checks
    # For now, treat all non-matching as unrelated
    return _BRANCH_MULTIPLIERS["unrelated"]
