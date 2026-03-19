"""Verdict parsing for Forged roundtable responses.

This module provides parsing logic to extract structured verdicts
from LLM-generated roundtable dialogue. It handles the tarot archetype
format where each archetype provides their perspective and verdict.
"""

import re
from dataclasses import dataclass
from typing import Optional


# Valid verdicts for roundtable responses
VALID_ROUNDTABLE_VERDICTS = ["APPROVE", "ITERATE", "ABSTAIN"]

# Pattern to extract persona blocks from response
# Matches: **ArchetypeName**: followed by content until the next archetype or end
PERSONA_BLOCK_PATTERN = r"\*\*(\w+)\*\*:?\s*(.*?)(?=\*\*\w+\*\*:|$)"

# Pattern to extract verdict from a persona block
VERDICT_PATTERN = r"[Vv]erdict:?\s*(APPROVE|ITERATE|ABSTAIN)"

# Pattern to extract severity
SEVERITY_PATTERN = r"[Ss]everity:?\s*(blocking|significant|minor)"

# Pattern to extract concerns list
CONCERNS_PATTERN = r"[Cc]oncerns?:?\s*\n((?:\s*[-*]\s*.+\n?)+)"

# Pattern to extract suggestions list
SUGGESTIONS_PATTERN = r"[Ss]uggestions?:?\s*\n((?:\s*[-*]\s*.+\n?)+)"


@dataclass
class ParsedVerdict:
    """Structured verdict from a roundtable archetype.

    Represents the parsed output from a single archetype's contribution
    to the roundtable dialogue.

    Attributes:
        archetype: Name of the tarot archetype (e.g., "Magician", "Hermit")
        verdict: The archetype's decision - "APPROVE", "ITERATE", or "ABSTAIN"
        concerns: List of concerns raised by the archetype
        suggestions: List of suggestions for improvement
        severity: Impact level - "blocking", "significant", or "minor"
    """

    archetype: str
    verdict: str
    concerns: list[str]
    suggestions: list[str]
    severity: Optional[str]

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with all verdict fields
        """
        return {
            "archetype": self.archetype,
            "verdict": self.verdict,
            "concerns": self.concerns,
            "suggestions": self.suggestions,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ParsedVerdict":
        """Reconstruct ParsedVerdict from dictionary.

        Args:
            data: Dictionary containing verdict fields

        Returns:
            Reconstructed ParsedVerdict instance
        """
        return cls(
            archetype=data["archetype"],
            verdict=data["verdict"],
            concerns=data.get("concerns", []),
            suggestions=data.get("suggestions", []),
            severity=data.get("severity"),
        )


def _extract_list_items(text: str) -> list[str]:
    """Extract bullet point items from text.

    Args:
        text: Text containing bullet points (- or *)

    Returns:
        List of extracted items with leading markers removed
    """
    items = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("-") or line.startswith("*"):
            # Remove the bullet marker and leading whitespace
            item = line.lstrip("-* ").strip()
            if item:
                items.append(item)
    return items


def _parse_single_block(archetype: str, content: str) -> ParsedVerdict:
    """Parse a single archetype's response block.

    Args:
        archetype: Name of the archetype
        content: The archetype's response content

    Returns:
        ParsedVerdict with extracted information
    """
    # Extract verdict
    verdict_match = re.search(VERDICT_PATTERN, content, re.IGNORECASE)
    verdict = verdict_match.group(1).upper() if verdict_match else "ABSTAIN"

    # Normalize verdict
    if verdict not in VALID_ROUNDTABLE_VERDICTS:
        verdict = "ABSTAIN"

    # Extract severity
    severity_match = re.search(SEVERITY_PATTERN, content, re.IGNORECASE)
    severity = severity_match.group(1).lower() if severity_match else None

    # Extract concerns
    concerns: list[str] = []
    concerns_match = re.search(CONCERNS_PATTERN, content, re.IGNORECASE)
    if concerns_match:
        concerns = _extract_list_items(concerns_match.group(1))

    # Extract suggestions
    suggestions: list[str] = []
    suggestions_match = re.search(SUGGESTIONS_PATTERN, content, re.IGNORECASE)
    if suggestions_match:
        suggestions = _extract_list_items(suggestions_match.group(1))

    return ParsedVerdict(
        archetype=archetype,
        verdict=verdict,
        concerns=concerns,
        suggestions=suggestions,
        severity=severity,
    )


def parse_roundtable_response(response: str) -> list[ParsedVerdict]:
    """Parse LLM response into structured verdicts.

    Extracts individual archetype blocks from the response and parses
    each one into a ParsedVerdict structure.

    Args:
        response: Raw LLM response containing roundtable dialogue

    Returns:
        List of ParsedVerdict objects, one per archetype found
    """
    if not response or not response.strip():
        return []

    verdicts: list[ParsedVerdict] = []

    # Find all archetype blocks using regex
    matches = re.findall(PERSONA_BLOCK_PATTERN, response, re.DOTALL | re.IGNORECASE)

    for archetype, content in matches:
        # Normalize archetype name (capitalize first letter)
        archetype = archetype.capitalize()

        # Skip if not a known archetype name (prevents matching random bold text)
        known_archetypes = {
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
        }
        if archetype not in known_archetypes:
            continue

        parsed = _parse_single_block(archetype, content)
        verdicts.append(parsed)

    # If regex parsing found nothing, try fallback
    if not verdicts:
        verdicts = handle_parse_failure(response)

    return verdicts


def handle_parse_failure(response: str) -> list[ParsedVerdict]:
    """Fallback parsing when regex parsing fails.

    Attempts to extract any verdict-like content from unstructured text.
    This is a best-effort fallback for malformed responses.

    Args:
        response: Unstructured text that failed normal parsing

    Returns:
        List of ParsedVerdict objects (may be empty)
    """
    if not response or not response.strip():
        return []

    verdicts: list[ParsedVerdict] = []

    # Try to find any verdict mentions
    verdict_mentions = re.findall(
        r"(APPROVE|ITERATE|ABSTAIN)", response, re.IGNORECASE
    )

    if verdict_mentions:
        # If we found verdicts but no archetype structure,
        # create a generic "Unknown" archetype verdict
        # Use the first verdict found as a general signal
        first_verdict = verdict_mentions[0].upper()
        if first_verdict in VALID_ROUNDTABLE_VERDICTS:
            verdicts.append(
                ParsedVerdict(
                    archetype="Unknown",
                    verdict=first_verdict,
                    concerns=[],
                    suggestions=[],
                    severity=None,
                )
            )

    return verdicts
