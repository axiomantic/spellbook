#!/usr/bin/env bash

# Install git hooks for spellbook development
# Run this after cloning the repo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "Installing git hooks..."

# Create pre-commit hook for TOC generation, linting, and formatting
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/usr/bin/env bash

# Pre-commit hook:
# 1. Auto-generate README TOC using doctoc
# 2. Run markdown linting and formatting

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"

# --- TOC Generation ---
if git diff --cached --name-only | grep -q "README.md"; then
    echo "README.md changed, regenerating TOC..."

    if command -v npx &> /dev/null; then
        npx doctoc@latest README.md --maxlevel 3 --github --notitle
        git add README.md
        echo "TOC updated and staged"
    else
        echo "Warning: npx not found, skipping TOC generation"
    fi
fi

# --- Markdown Linting ---
STAGED_MD=$(git diff --cached --name-only --diff-filter=ACM | grep '\.md$' || true)

if [ -n "$STAGED_MD" ]; then
    echo "Linting staged markdown files..."

    # Check if markdownlint is available
    if command -v npx &> /dev/null; then
        # Run markdownlint with fix flag, allow it to fail gracefully
        if [ -f "$REPO_ROOT/.markdownlint.json" ]; then
            echo "$STAGED_MD" | xargs npx markdownlint-cli@latest --fix --config "$REPO_ROOT/.markdownlint.json" 2>/dev/null || true
        else
            echo "$STAGED_MD" | xargs npx markdownlint-cli@latest --fix 2>/dev/null || true
        fi

        # Re-stage any fixed files
        echo "$STAGED_MD" | xargs git add 2>/dev/null || true
        echo "Markdown linting complete"
    else
        echo "Warning: npx not found, skipping markdown linting"
    fi
fi

echo "Pre-commit checks complete"
EOF

chmod +x "$HOOKS_DIR/pre-commit"

echo "Installed pre-commit hook:"
echo "  - Auto-generates README TOC"
echo "  - Runs markdown linting with auto-fix"
echo "Done!"
