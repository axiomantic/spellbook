#!/usr/bin/env python3
"""
Validate URLs found in code comments and documentation.

Usage:
    python check-urls.py <file_or_directory>
    python check-urls.py --urls-file urls.txt
    python check-urls.py --from-json claims.json

Output: JSON with URL validation results.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


@dataclass
class URLCheck:
    url: str
    file: Optional[str]
    line: Optional[int]
    status: str  # valid, invalid, redirect, timeout, error
    status_code: Optional[int]
    final_url: Optional[str]
    error: Optional[str]
    title: Optional[str]


# URL pattern
URL_PATTERN = re.compile(
    r'https?://[^\s<>\"\'\)\]\}]+',
    re.IGNORECASE
)

# Patterns to exclude (not real URLs)
EXCLUDE_PATTERNS = [
    r'example\.com',
    r'localhost',
    r'127\.0\.0\.1',
    r'\$\{',  # Template variables
    r'\{\{',  # Template variables
    r'<[^>]+>',  # Placeholders like <URL>
]

# User agent for requests
USER_AGENT = 'Mozilla/5.0 (compatible; FactChecker/1.0; +https://github.com/factchecker)'

# Timeout in seconds
TIMEOUT = 10


def should_exclude(url: str) -> bool:
    """Check if URL should be excluded from validation."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def clean_url(url: str) -> str:
    """Clean URL by removing trailing punctuation."""
    # Remove trailing punctuation that's likely not part of URL
    while url and url[-1] in '.,;:!?)]\'"':
        url = url[:-1]
    return url


def extract_title(html: str) -> Optional[str]:
    """Extract title from HTML content."""
    match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:200]
    return None


def check_url(url: str, file: Optional[str] = None, line: Optional[int] = None) -> URLCheck:
    """Check if a URL is accessible."""
    url = clean_url(url)

    if should_exclude(url):
        return URLCheck(
            url=url,
            file=file,
            line=line,
            status="excluded",
            status_code=None,
            final_url=None,
            error="URL matches exclusion pattern",
            title=None,
        )

    # Validate URL format
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return URLCheck(
                url=url,
                file=file,
                line=line,
                status="invalid",
                status_code=None,
                final_url=None,
                error="Invalid URL format",
                title=None,
            )
    except Exception as e:
        return URLCheck(
            url=url,
            file=file,
            line=line,
            status="invalid",
            status_code=None,
            final_url=None,
            error=str(e),
            title=None,
        )

    # Make request
    try:
        request = urllib.request.Request(
            url,
            headers={'User-Agent': USER_AGENT},
            method='GET'
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            status_code = response.getcode()
            final_url = response.geturl()

            # Try to get title for HTML pages
            title = None
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                try:
                    content = response.read(10000).decode('utf-8', errors='ignore')
                    title = extract_title(content)
                except Exception:
                    pass

            status = "valid"
            if final_url != url:
                status = "redirect"

            return URLCheck(
                url=url,
                file=file,
                line=line,
                status=status,
                status_code=status_code,
                final_url=final_url if final_url != url else None,
                error=None,
                title=title,
            )

    except urllib.error.HTTPError as e:
        return URLCheck(
            url=url,
            file=file,
            line=line,
            status="error",
            status_code=e.code,
            final_url=None,
            error=f"HTTP {e.code}: {e.reason}",
            title=None,
        )

    except urllib.error.URLError as e:
        return URLCheck(
            url=url,
            file=file,
            line=line,
            status="error",
            status_code=None,
            final_url=None,
            error=str(e.reason),
            title=None,
        )

    except TimeoutError:
        return URLCheck(
            url=url,
            file=file,
            line=line,
            status="timeout",
            status_code=None,
            final_url=None,
            error=f"Request timed out after {TIMEOUT}s",
            title=None,
        )

    except Exception as e:
        return URLCheck(
            url=url,
            file=file,
            line=line,
            status="error",
            status_code=None,
            final_url=None,
            error=str(e),
            title=None,
        )


def extract_urls_from_file(filepath: Path) -> list[tuple[str, int]]:
    """Extract URLs from a file with line numbers."""
    urls = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            for match in URL_PATTERN.finditer(line):
                url = clean_url(match.group(0))
                urls.append((url, line_num))

    except Exception:
        pass

    return urls


def extract_urls_from_directory(dirpath: Path) -> list[tuple[str, str, int]]:
    """Extract URLs from all files in a directory."""
    urls = []

    for filepath in dirpath.rglob('*'):
        if filepath.is_file():
            # Skip binary files and common non-doc directories
            if any(part.startswith('.') or part in ['node_modules', 'venv', '__pycache__', 'dist', 'build']
                   for part in filepath.parts):
                continue

            # Only check text-like files
            if filepath.suffix.lower() in [
                '.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.rb', '.java',
                '.c', '.cpp', '.h', '.sh', '.bash', '.sql', '.md', '.txt', '.rst',
                '.html', '.css', '.json', '.yaml', '.yml', '.toml', '.xml',
            ]:
                for url, line in extract_urls_from_file(filepath):
                    urls.append((url, str(filepath), line))

    return urls


def check_urls_parallel(
    urls: list[tuple[str, Optional[str], Optional[int]]],
    max_workers: int = 10
) -> list[URLCheck]:
    """Check multiple URLs in parallel."""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_url, url, file, line): (url, file, line)
            for url, file, line in urls
        }

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                url, file, line = futures[future]
                results.append(URLCheck(
                    url=url,
                    file=file,
                    line=line,
                    status="error",
                    status_code=None,
                    final_url=None,
                    error=str(e),
                    title=None,
                ))

    return results


def main():
    parser = argparse.ArgumentParser(description='Validate URLs in code and documentation')
    parser.add_argument('path', nargs='?', help='File or directory to scan')
    parser.add_argument('--urls-file', help='File containing URLs (one per line)')
    parser.add_argument('--from-json', help='JSON file with claims containing URLs')
    parser.add_argument('--output', '-o', choices=['json', 'text'], default='json')
    parser.add_argument('--parallel', '-p', type=int, default=10, help='Max parallel requests')
    parser.add_argument('--include-valid', action='store_true', help='Include valid URLs in output')

    args = parser.parse_args()

    urls_to_check = []

    if args.urls_file:
        # Read URLs from file
        with open(args.urls_file) as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith('#'):
                    urls_to_check.append((url, args.urls_file, None))

    elif args.from_json:
        # Extract URLs from claims JSON
        with open(args.from_json) as f:
            claims = json.load(f)

        for claim in claims:
            text = claim.get('text', '')
            for match in URL_PATTERN.finditer(text):
                url = clean_url(match.group(0))
                urls_to_check.append((url, claim.get('file'), claim.get('line')))

    elif args.path:
        p = Path(args.path)
        if p.is_file():
            for url, line in extract_urls_from_file(p):
                urls_to_check.append((url, str(p), line))
        elif p.is_dir():
            urls_to_check = extract_urls_from_directory(p)
        else:
            print(f"Path not found: {args.path}", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)

    # Deduplicate URLs (keep first occurrence)
    seen = set()
    unique_urls = []
    for url, file, line in urls_to_check:
        if url not in seen:
            seen.add(url)
            unique_urls.append((url, file, line))

    print(f"Checking {len(unique_urls)} unique URLs...", file=sys.stderr)

    # Check URLs
    results = check_urls_parallel(unique_urls, max_workers=args.parallel)

    # Filter results
    if not args.include_valid:
        results = [r for r in results if r.status not in ('valid', 'excluded')]

    # Sort by status (errors first)
    status_order = {'error': 0, 'timeout': 1, 'invalid': 2, 'redirect': 3, 'valid': 4, 'excluded': 5}
    results.sort(key=lambda r: status_order.get(r.status, 99))

    # Output
    if args.output == 'json':
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        for r in results:
            status_icon = {'valid': '✅', 'redirect': '↪️', 'error': '❌', 'timeout': '⏱️', 'invalid': '⚠️', 'excluded': '⏭️'}.get(r.status, '?')
            print(f"{status_icon} [{r.status.upper()}] {r.url}")
            if r.file:
                print(f"   Location: {r.file}:{r.line or '?'}")
            if r.error:
                print(f"   Error: {r.error}")
            if r.final_url:
                print(f"   Redirects to: {r.final_url}")
            if r.title:
                print(f"   Title: {r.title}")
            print()

    # Summary
    status_counts = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    print(f"\nSummary: {len(unique_urls)} URLs checked", file=sys.stderr)
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}", file=sys.stderr)


if __name__ == '__main__':
    main()
