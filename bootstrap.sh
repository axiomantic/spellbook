#!/usr/bin/env bash
#
# Spellbook Bootstrap - Thin wrapper that curls and runs install.py
#
# One-line install:
#   curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
#
# This script just ensures Python 3 exists and runs install.py.
# All real work happens in install.py which is self-bootstrapping.
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_PY_URL="https://raw.githubusercontent.com/axiomantic/spellbook/main/install.py"

print_error() {
    echo -e "${RED}[error]${NC} $1" >&2
}

print_info() {
    echo -e "${CYAN}[info]${NC} $1"
}

# Find any Python 3 interpreter
find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &> /dev/null; then
            # Verify it's Python 3
            if "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

main() {
    # Find Python
    local python_cmd
    python_cmd=$(find_python) || {
        print_error "Python 3.8+ is required but not found."
        echo ""
        echo "Install Python first:"
        case "$(uname -s)" in
            Darwin*)
                echo "  brew install python3"
                echo "  # or: xcode-select --install"
                ;;
            Linux*)
                echo "  sudo apt install python3  # Debian/Ubuntu"
                echo "  sudo dnf install python3  # Fedora"
                echo "  sudo pacman -S python     # Arch"
                ;;
            *)
                echo "  Visit https://www.python.org/downloads/"
                ;;
        esac
        exit 1
    }

    print_info "Using $python_cmd ($(\"$python_cmd\" --version 2>&1))"

    # Download and run install.py
    # Pass through all arguments
    curl -fsSL "$INSTALL_PY_URL" | "$python_cmd" - "$@"
}

main "$@"
