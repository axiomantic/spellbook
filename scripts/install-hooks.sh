#!/usr/bin/env bash

# Install git hooks for spellbook development
# Run this after cloning the repo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "Installing git hooks..."

# Create pre-commit hook for TOC generation
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/usr/bin/env bash

# Pre-commit hook to auto-generate README TOC using doctoc
# Includes entries for each command and skill

set -e

# Check if README.md is staged
if git diff --cached --name-only | grep -q "README.md"; then
    echo "README.md changed, regenerating TOC..."

    # Check if npx is available
    if ! command -v npx &> /dev/null; then
        echo "Warning: npx not found, skipping TOC generation"
        exit 0
    fi

    # Run doctoc with maxlevel 3 to include command/skill subsections
    npx doctoc@latest README.md --maxlevel 3 --github --notitle

    # Re-stage README.md if doctoc modified it
    git add README.md

    echo "TOC updated and staged"
fi
EOF

chmod +x "$HOOKS_DIR/pre-commit"

echo "Installed pre-commit hook (auto-generates README TOC)"
echo "Done!"
