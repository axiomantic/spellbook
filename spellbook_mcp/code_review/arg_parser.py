"""Argument parser for code-review skill modes."""

from dataclasses import dataclass, field
import re


@dataclass
class CodeReviewArgs:
    """Parsed arguments for code-review skill.

    Mode flags (mutually exclusive):
        self_review: Pre-PR self-review mode (default)
        feedback: Process received review feedback mode
        give: Review someone else's code (value is the target)
        audit: Comprehensive multi-pass deep-dive mode

    Modifier flags:
        audit_scope: Scope for audit mode (file, directory, 'security', 'all')
        tarot: Enable tarot roundtable dialogue
        pr: PR number to use as diff source
    """

    self_review: bool = True
    feedback: bool = False
    give: str | None = None
    audit: bool = False
    audit_scope: str | None = None
    tarot: bool = False
    pr: int | None = None


def parse_args(args: str | None) -> CodeReviewArgs:
    """Parse argument string into CodeReviewArgs.

    Args:
        args: Space-separated argument string (e.g., "--feedback --pr 123")

    Returns:
        Parsed CodeReviewArgs instance

    Raises:
        ValueError: If invalid flag combinations or missing required values
    """
    if args is None or args.strip() == "":
        return CodeReviewArgs()

    # Normalize and tokenize
    tokens = args.strip().split()

    # Initialize state
    self_review = False
    feedback = False
    give: str | None = None
    audit = False
    audit_scope: str | None = None
    tarot = False
    pr: int | None = None

    # Track explicit mode flags
    explicit_self = False

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Handle --flag=value syntax
        if "=" in token:
            flag, value = token.split("=", 1)
            if flag == "--pr":
                try:
                    pr = int(value)
                except ValueError:
                    raise ValueError("--pr requires a number")
                i += 1
                continue
            elif flag == "--give":
                give = value
                i += 1
                continue
            elif flag == "--audit":
                audit = True
                audit_scope = value if value else None
                i += 1
                continue

        if token in ("--self", "-s"):
            self_review = True
            explicit_self = True
        elif token in ("--feedback", "-f"):
            feedback = True
        elif token == "--give":
            # Next token should be the target
            if i + 1 >= len(tokens) or tokens[i + 1].startswith("-"):
                raise ValueError("--give requires a target (PR number, URL, or branch)")
            give = tokens[i + 1]
            i += 1
        elif token == "--audit":
            audit = True
            # Check if next token is a scope (not a flag)
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                audit_scope = tokens[i + 1]
                i += 1
        elif token in ("--tarot", "-t"):
            tarot = True
        elif token == "--pr":
            # Next token should be the number
            if i + 1 >= len(tokens):
                raise ValueError("--pr requires a number")
            try:
                pr = int(tokens[i + 1])
            except ValueError:
                raise ValueError("--pr requires a number")
            i += 1
        # Unknown flags are ignored

        i += 1

    # Count mode flags
    mode_count = sum([
        explicit_self,
        feedback,
        give is not None,
        audit,
    ])

    if mode_count > 1:
        raise ValueError(
            "Choose one mode: --self, --feedback, --give, or --audit"
        )

    # Default to self if no mode specified
    if mode_count == 0:
        self_review = True
    elif not explicit_self:
        # A non-self mode was selected
        self_review = False

    return CodeReviewArgs(
        self_review=self_review,
        feedback=feedback,
        give=give,
        audit=audit,
        audit_scope=audit_scope,
        tarot=tarot,
        pr=pr,
    )
