"""Unified diff parsing for PR distillation.

Parses git unified diff format into structured FileDiff objects.
Ported from lib/pr-distill/parse.js.
"""

import re
from typing import Optional

from .errors import ErrorCode, PRDistillError
from .types import DiffLine, FileDiff, Hunk


# Regex to parse the diff header line "diff --git a/path b/path"
# Handles paths with spaces by extracting from a/ and b/ prefixes
DIFF_HEADER_REGEX = re.compile(r"^diff --git a/(.+) b/(.+)$", re.MULTILINE)

# Regex to parse hunk headers like "@@ -1,3 +1,5 @@"
# Captures old_start, old_count, new_start, new_count
HUNK_HEADER_REGEX = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_file_chunk(chunk: str) -> FileDiff:
    """Parse a single file's diff chunk into a FileDiff structure.

    Args:
        chunk: Single file's diff content starting with "diff --git"

    Returns:
        FileDiff object with parsed diff information

    Raises:
        PRDistillError: If diff header cannot be parsed
    """
    lines = chunk.split("\n")

    # Parse file paths from header
    header_match = DIFF_HEADER_REGEX.match(lines[0])
    if not header_match:
        raise PRDistillError(
            ErrorCode.DIFF_PARSE_ERROR,
            f"Could not parse diff header: {lines[0]}",
            recoverable=False,
            context={"chunk": chunk[:200]},
        )

    old_path = header_match.group(1)
    new_path = header_match.group(2)

    # Detect file status
    status = "modified"
    is_binary = False

    for line in lines[1:10]:
        if line.startswith("new file mode"):
            status = "added"
        elif line.startswith("deleted file mode"):
            status = "deleted"
        elif line.startswith("rename from "):
            status = "renamed"
            old_path = line[len("rename from "):]
        elif line.startswith("rename to "):
            new_path = line[len("rename to "):]
        elif "Binary files" in line:
            is_binary = True

    # For renamed files, keep the old_path, otherwise set it to None
    final_old_path: Optional[str] = old_path if status == "renamed" else None

    # Binary files have no hunks to parse
    if is_binary:
        return FileDiff(
            path=new_path,
            old_path=final_old_path,
            status=status,
            hunks=[],
            additions=0,
            deletions=0,
        )

    # Parse hunks
    hunks: list[Hunk] = []
    current_hunk: Optional[Hunk] = None
    old_line_num = 0
    new_line_num = 0
    additions = 0
    deletions = 0

    for i in range(1, len(lines)):
        line = lines[i]

        # Check for hunk header
        hunk_match = HUNK_HEADER_REGEX.match(line)
        if hunk_match:
            if current_hunk is not None:
                hunks.append(current_hunk)

            hunk_old_start = int(hunk_match.group(1))
            hunk_old_count = int(hunk_match.group(2)) if hunk_match.group(2) is not None else 1
            hunk_new_start = int(hunk_match.group(3))
            hunk_new_count = int(hunk_match.group(4)) if hunk_match.group(4) is not None else 1

            current_hunk = Hunk(
                old_start=hunk_old_start,
                old_count=hunk_old_count,
                new_start=hunk_new_start,
                new_count=hunk_new_count,
                lines=[],
            )
            old_line_num = hunk_old_start
            new_line_num = hunk_new_start
            continue

        # Parse diff lines within a hunk
        if current_hunk is not None and len(line) > 0:
            prefix = line[0]
            content = line[1:]

            if prefix == "+":
                current_hunk["lines"].append(
                    DiffLine(
                        type="add",
                        content=content,
                        old_line_num=None,
                        new_line_num=new_line_num,
                    )
                )
                new_line_num += 1
                additions += 1
            elif prefix == "-":
                current_hunk["lines"].append(
                    DiffLine(
                        type="remove",
                        content=content,
                        old_line_num=old_line_num,
                        new_line_num=None,
                    )
                )
                old_line_num += 1
                deletions += 1
            elif prefix == " ":
                current_hunk["lines"].append(
                    DiffLine(
                        type="context",
                        content=content,
                        old_line_num=old_line_num,
                        new_line_num=new_line_num,
                    )
                )
                old_line_num += 1
                new_line_num += 1
            # Ignore other prefixes like '\' for "No newline at end of file"

    # Don't forget the last hunk
    if current_hunk is not None:
        hunks.append(current_hunk)

    return FileDiff(
        path=new_path,
        old_path=final_old_path,
        status=status,
        hunks=hunks,
        additions=additions,
        deletions=deletions,
    )


def parse_diff(diff: str) -> dict:
    """Parse a unified diff into an array of FileDiff objects.

    Args:
        diff: Complete unified diff output

    Returns:
        Dict with "files" (list of FileDiff) and "warnings" (list of strings)
    """
    if not diff or diff.strip() == "":
        return {"files": [], "warnings": []}

    # Split by "diff --git" but keep the delimiter
    chunks = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)

    files: list[FileDiff] = []
    warnings: list[str] = []

    for chunk in chunks:
        if not chunk.strip():
            continue

        # Each chunk should start with "diff --git"
        if not chunk.startswith("diff --git"):
            continue

        try:
            file_diff = parse_file_chunk(chunk)
            files.append(file_diff)
        except PRDistillError as error:
            # If we fail to parse one file, continue with others
            # but collect the warning for the caller
            warnings.append(str(error))

    return {"files": files, "warnings": warnings}
