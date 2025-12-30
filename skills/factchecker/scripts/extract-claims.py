#!/usr/bin/env python3
"""
Extract claims from code files for factchecker verification.

Usage:
    python extract-claims.py <file_or_directory> [--output json|text] [--category <category>]
    python extract-claims.py --from-diff <diff_file>
    python extract-claims.py --git-scope branch|uncommitted

Output: JSON array of claims with metadata.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class Claim:
    id: str
    text: str
    file: str
    line: int
    source_type: str  # comment, docstring, markdown, commit, naming
    category: str  # security, correctness, performance, etc.
    confidence: float
    keywords: list[str]
    context: dict


# Claim indicator keywords by category
CLAIM_KEYWORDS = {
    "behavior": [
        r"\breturns?\b", r"\bthrows?\b", r"\braises?\b", r"\berrors?\s+when\b",
        r"\bfails?\s+if\b", r"\bensures?\b", r"\bguarantees?\b", r"\bpromises?\b",
        r"\bnever\b", r"\balways\b", r"\bmust\b", r"\bshall\b", r"\bwill\b",
    ],
    "security": [
        r"\bsanitiz", r"\bescape[ds]?\b", r"\bvalidat", r"\bsecure\b", r"\bsafe\b",
        r"\bxss\b", r"\binjection\b", r"\bhash(?:ed|ing)?\b", r"\bencrypt",
        r"\bauthenticat", r"\bauthoriz", r"\bpassword\b", r"\btoken\b", r"\bsecret\b",
    ],
    "performance": [
        r"\bO\s*\(", r"\bcomplexity\b", r"\bcached?\b", r"\bmemoiz", r"\blazy\b",
        r"\boptimiz", r"\bfast\b", r"\befficient\b", r"\bbatch", r"\bparallel\b",
        r"\b\d+\s*(?:ms|seconds?|s|minutes?)\b", r"\b\d+\s*(?:KB|MB|GB)\b",
    ],
    "concurrency": [
        r"\bthread[- ]?safe\b", r"\batomic\b", r"\block[- ]?free\b", r"\bwait[- ]?free\b",
        r"\breentrant\b", r"\bsynchroniz", r"\bmutex\b", r"\block(?:ing|ed)?\b",
        r"\bconcurrent\b", r"\brace\s+condition\b",
    ],
    "correctness": [
        r"\bpure\s+function\b", r"\bidempotent\b", r"\bside[- ]?effect", r"\bimmutable\b",
        r"\breadonly\b", r"\bconst(?:ant)?\b", r"\binvariant\b", r"\bnull\b",
        r"\bvalid(?:ation|ates?)?\b",
    ],
    "historical": [
        r"\bTODO\b", r"\bFIXME\b", r"\bHACK\b", r"\bXXX\b", r"\bBUG\b",
        r"\bworkaround\b", r"\btemporary\b", r"\blegacy\b", r"\bdeprecated\b",
        r"#\d+", r"\bfixes?\b", r"\bcloses?\b", r"\bresolves?\b",
    ],
    "configuration": [
        r"\bdefaults?\s+to\b", r"\benv(?:ironment)?\s+var", r"\bconfig(?:uration)?\b",
        r"\brequires?\b", r"\bneeds?\b", r"\bdepends?\s+on\b", r"\bcompatible\b",
        r"\bversion\b", r"\bv\d+",
    ],
    "documentation": [
        r"\bsee\s+(?:also\s+)?(?:tests?|docs?|readme)\b", r"\bcovered\s+by\b",
        r"\bexample\b", r"\bfor\s+more\s+info",
    ],
}

# Comment patterns by file extension
COMMENT_PATTERNS = {
    ".py": [
        (r'#\s*(.+)$', "comment"),
        (r'"""([\s\S]*?)"""', "docstring"),
        (r"'''([\s\S]*?)'''", "docstring"),
    ],
    ".js": [
        (r'//\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".ts": [
        (r'//\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".jsx": [
        (r'//\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".tsx": [
        (r'//\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".go": [
        (r'//\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".rs": [
        (r'//\s*(.+)$', "comment"),
        (r'///\s*(.+)$', "docstring"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".rb": [
        (r'#\s*(.+)$', "comment"),
        (r'=begin([\s\S]*?)=end', "comment"),
    ],
    ".java": [
        (r'//\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".c": [
        (r'//\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".cpp": [
        (r'//\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".h": [
        (r'//\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".sh": [
        (r'#\s*(.+)$', "comment"),
    ],
    ".bash": [
        (r'#\s*(.+)$', "comment"),
    ],
    ".sql": [
        (r'--\s*(.+)$', "comment"),
        (r'/\*\s*([\s\S]*?)\s*\*/', "comment"),
    ],
    ".md": [
        (r'<!--\s*([\s\S]*?)\s*-->', "comment"),
        (r'^(.+)$', "markdown"),  # All non-code content
    ],
}

# Naming patterns that imply claims
NAMING_PATTERNS = [
    (r'\b(validate|verify|check|assert|ensure|confirm)[A-Z_]\w*', "behavior"),
    (r'\bis[A-Z]\w*', "behavior"),
    (r'\bhas[A-Z]\w*', "behavior"),
    (r'\bcan[A-Z]\w*', "behavior"),
    (r'\bsafe[A-Z]\w*', "security"),
    (r'\bsanitize[A-Z]\w*', "security"),
    (r'\bescape[A-Z]\w*', "security"),
    (r'\b(get|compute|calculate|derive)[A-Z]\w*', "correctness"),
    (r'\b(async|await|promise)[A-Z_]\w*', "concurrency"),
    (r'\b(atomic|sync|synchronized)[A-Z_]\w*', "concurrency"),
]

# False positive filters
FALSE_POSITIVE_PATTERNS = [
    r'(?:Author|Copyright|License|Created by|Maintained by)',
    r'(?:TODO|FIXME):\s*(?:format|style|cleanup)',
    r'\?$',  # Questions
    r'^(?:if|for|while|return|const|let|var|function|def|class)\s',  # Commented code
]


def classify_claim(text: str) -> tuple[str, float, list[str]]:
    """Classify claim by category and return confidence + matched keywords."""
    text_lower = text.lower()
    matches = {}

    for category, patterns in CLAIM_KEYWORDS.items():
        keywords_found = []
        for pattern in patterns:
            if re.search(pattern, text_lower):
                keywords_found.append(pattern.replace(r'\b', '').replace('\\', ''))
        if keywords_found:
            matches[category] = keywords_found

    if not matches:
        return "unknown", 0.3, []

    # Return category with most keyword matches
    best_category = max(matches, key=lambda k: len(matches[k]))
    confidence = min(0.5 + len(matches[best_category]) * 0.1, 0.95)

    return best_category, confidence, matches[best_category]


def is_false_positive(text: str) -> bool:
    """Check if text matches false positive patterns."""
    for pattern in FALSE_POSITIVE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def extract_from_file(filepath: Path, claim_counter: Iterator[int]) -> list[Claim]:
    """Extract claims from a single file."""
    claims = []
    suffix = filepath.suffix.lower()

    if suffix not in COMMENT_PATTERNS:
        return claims

    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return claims

    lines = content.split('\n')
    patterns = COMMENT_PATTERNS[suffix]

    for pattern, source_type in patterns:
        for match in re.finditer(pattern, content, re.MULTILINE):
            text = match.group(1).strip() if match.lastindex else match.group(0).strip()

            # Skip empty or very short
            if len(text) < 10:
                continue

            # Skip false positives
            if is_false_positive(text):
                continue

            # Find line number
            line_num = content[:match.start()].count('\n') + 1

            # Classify
            category, confidence, keywords = classify_claim(text)

            # Only include if has claim indicators
            if confidence < 0.4:
                continue

            # Get context
            context = {
                "surrounding_lines": lines[max(0, line_num-3):min(len(lines), line_num+2)],
            }

            claims.append(Claim(
                id=f"claim-{next(claim_counter):04d}",
                text=text[:500],  # Truncate long claims
                file=str(filepath),
                line=line_num,
                source_type=source_type,
                category=category,
                confidence=confidence,
                keywords=keywords,
                context=context,
            ))

    # Also check for naming convention claims
    for pattern, category in NAMING_PATTERNS:
        for match in re.finditer(pattern, content):
            name = match.group(0)
            line_num = content[:match.start()].count('\n') + 1

            claims.append(Claim(
                id=f"claim-{next(claim_counter):04d}",
                text=f"Function/variable '{name}' implies {category} behavior",
                file=str(filepath),
                line=line_num,
                source_type="naming",
                category=category,
                confidence=0.6,
                keywords=[name],
                context={"name": name},
            ))

    return claims


def extract_from_directory(dirpath: Path, claim_counter: Iterator[int]) -> list[Claim]:
    """Recursively extract claims from a directory."""
    claims = []

    for filepath in dirpath.rglob('*'):
        if filepath.is_file() and filepath.suffix.lower() in COMMENT_PATTERNS:
            # Skip common non-source directories
            if any(part.startswith('.') or part in ['node_modules', 'venv', '__pycache__', 'dist', 'build']
                   for part in filepath.parts):
                continue
            claims.extend(extract_from_file(filepath, claim_counter))

    return claims


def get_git_files(scope: str) -> list[str]:
    """Get files based on git scope."""
    if scope == "branch":
        # Get merge base with main/master
        for base in ['main', 'master', 'devel', 'develop']:
            try:
                result = subprocess.run(
                    ['git', 'merge-base', 'HEAD', base],
                    capture_output=True, text=True, check=True
                )
                merge_base = result.stdout.strip()
                break
            except subprocess.CalledProcessError:
                continue
        else:
            print("Could not find base branch", file=sys.stderr)
            return []

        # Get files changed since merge base
        result = subprocess.run(
            ['git', 'diff', '--name-only', f'{merge_base}...HEAD'],
            capture_output=True, text=True
        )
        files = result.stdout.strip().split('\n')

        # Also include uncommitted
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            capture_output=True, text=True
        )
        files.extend(result.stdout.strip().split('\n'))

        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True, text=True
        )
        files.extend(result.stdout.strip().split('\n'))

    elif scope == "uncommitted":
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            capture_output=True, text=True
        )
        files = result.stdout.strip().split('\n')

        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True, text=True
        )
        files.extend(result.stdout.strip().split('\n'))
    else:
        print(f"Unknown scope: {scope}", file=sys.stderr)
        return []

    return [f for f in set(files) if f and Path(f).exists()]


def main():
    parser = argparse.ArgumentParser(description='Extract claims from code files')
    parser.add_argument('path', nargs='?', help='File or directory to scan')
    parser.add_argument('--output', choices=['json', 'text'], default='json')
    parser.add_argument('--category', help='Filter by category')
    parser.add_argument('--git-scope', choices=['branch', 'uncommitted'])
    parser.add_argument('--min-confidence', type=float, default=0.4)

    args = parser.parse_args()

    claim_counter = iter(range(1, 100000))
    claims = []

    if args.git_scope:
        files = get_git_files(args.git_scope)
        for filepath in files:
            p = Path(filepath)
            if p.exists() and p.is_file():
                claims.extend(extract_from_file(p, claim_counter))
    elif args.path:
        p = Path(args.path)
        if p.is_file():
            claims = extract_from_file(p, claim_counter)
        elif p.is_dir():
            claims = extract_from_directory(p, claim_counter)
        else:
            print(f"Path not found: {args.path}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    # Filter by category if specified
    if args.category:
        claims = [c for c in claims if c.category == args.category]

    # Filter by confidence
    claims = [c for c in claims if c.confidence >= args.min_confidence]

    # Sort by category, then by file, then by line
    claims.sort(key=lambda c: (c.category, c.file, c.line))

    if args.output == 'json':
        print(json.dumps([asdict(c) for c in claims], indent=2))
    else:
        for claim in claims:
            print(f"[{claim.category.upper()}] {claim.file}:{claim.line}")
            print(f"  {claim.text[:100]}...")
            print()


if __name__ == '__main__':
    main()
