#!/usr/bin/env bash
#
# Spellbook Bootstrap Installer
#
# One-line install:
#   curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
#
# Or with options:
#   curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash -s -- --help
#
# This script:
#   1. Installs prerequisites (uv, git, Python via uv if needed)
#   2. Clones spellbook to ~/.local/share/spellbook
#   3. Runs the Python installer via uv
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Default install location
INSTALL_DIR="${SPELLBOOK_DIR:-$HOME/.local/share/spellbook}"

# GitHub repo
REPO_URL="https://github.com/axiomantic/spellbook.git"

# Minimum Python version
MIN_PYTHON_VERSION="3.10"

# Whether to prompt (can be disabled with --yes)
INTERACTIVE=true

# Track what we installed
INSTALLED_UV=false
INSTALLED_PYTHON=false

print_header() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}            ${BOLD}Spellbook Bootstrap Installer${NC}                   ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_info() {
    echo -e "  $1"
}

# Prompt for yes/no, returns 0 for yes, 1 for no
prompt_yn() {
    local prompt="$1"
    local default="${2:-y}"

    if [ "$INTERACTIVE" = false ]; then
        return 0
    fi

    local yn_prompt
    if [ "$default" = "y" ]; then
        yn_prompt="[Y/n]"
    else
        yn_prompt="[y/N]"
    fi

    echo ""
    read -r -p "$(echo -e "${BOLD}$prompt${NC} $yn_prompt ") " response
    response=${response:-$default}

    case "$response" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) return 1 ;;
    esac
}

# Prompt for input with default
prompt_input() {
    local prompt="$1"
    local default="$2"
    local result

    if [ "$INTERACTIVE" = false ]; then
        echo "$default"
        return
    fi

    echo ""
    if [ -n "$default" ]; then
        read -r -p "$(echo -e "${BOLD}$prompt${NC} [$default]: ") " result
        echo "${result:-$default}"
    else
        read -r -p "$(echo -e "${BOLD}$prompt${NC}: ") " result
        echo "$result"
    fi
}

detect_os() {
    case "$(uname -s)" in
        Darwin*)  echo "macos" ;;
        Linux*)   echo "linux" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)        echo "unknown" ;;
    esac
}

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    else
        echo "unknown"
    fi
}

# Check if running in a terminal (for interactive prompts)
check_terminal() {
    if [ ! -t 0 ]; then
        print_warning "Not running in interactive terminal. Using defaults."
        INTERACTIVE=false
    fi
}

#
# Git Installation
#
check_git() {
    if command -v git &> /dev/null; then
        return 0
    fi
    return 1
}

install_git() {
    local os=$(detect_os)
    local distro=$(detect_distro)

    print_step "Git is required but not installed."
    echo ""

    case "$os" in
        macos)
            print_info "On macOS, git comes with Xcode Command Line Tools."
            echo ""
            if prompt_yn "Install Xcode Command Line Tools (includes git)?"; then
                print_step "Installing Xcode Command Line Tools..."
                xcode-select --install 2>/dev/null || true
                echo ""
                print_warning "A dialog should appear. After installation completes, run this script again."
                exit 0
            fi
            ;;
        linux)
            print_info "Install git using your package manager:"
            echo ""
            case "$distro" in
                ubuntu|debian|pop)
                    print_info "  sudo apt update && sudo apt install -y git"
                    ;;
                fedora)
                    print_info "  sudo dnf install -y git"
                    ;;
                arch|manjaro)
                    print_info "  sudo pacman -S git"
                    ;;
                opensuse*)
                    print_info "  sudo zypper install git"
                    ;;
                *)
                    print_info "  Use your distribution's package manager to install git"
                    ;;
            esac
            echo ""
            if prompt_yn "Attempt automatic installation?"; then
                case "$distro" in
                    ubuntu|debian|pop)
                        sudo apt update && sudo apt install -y git
                        ;;
                    fedora)
                        sudo dnf install -y git
                        ;;
                    arch|manjaro)
                        sudo pacman -S --noconfirm git
                        ;;
                    *)
                        print_error "Automatic installation not supported for $distro"
                        print_info "Please install git manually and run this script again."
                        exit 1
                        ;;
                esac
            fi
            ;;
        *)
            print_error "Please install git manually and run this script again."
            exit 1
            ;;
    esac
}

#
# uv Installation
#
check_uv() {
    # Check if uv is in PATH
    if command -v uv &> /dev/null; then
        return 0
    fi

    # Check common install locations
    for path in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$path" ]; then
            export PATH="$(dirname "$path"):$PATH"
            return 0
        fi
    done

    return 1
}

install_uv() {
    print_step "uv (Python package manager) is required but not installed."
    echo ""
    print_info "uv is a fast Python package manager from Astral."
    print_info "Learn more: https://docs.astral.sh/uv/"
    echo ""

    if ! prompt_yn "Install uv?"; then
        print_error "uv is required. Install it manually:"
        print_info "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    print_step "Installing uv..."
    echo ""

    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        INSTALLED_UV=true
        print_success "uv installed successfully"

        # Add to PATH for this session
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

        # Source shell config if available
        for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
            if [ -f "$rc" ]; then
                source "$rc" 2>/dev/null || true
            fi
        done

        if ! check_uv; then
            print_warning "uv installed but not in PATH for this session."
            print_info "Using direct path: $HOME/.local/bin/uv"
            export PATH="$HOME/.local/bin:$PATH"
        fi
    else
        print_error "Failed to install uv."
        exit 1
    fi
}

#
# Python Installation (via uv)
#
check_python() {
    # First check if uv can find a suitable Python
    if command -v uv &> /dev/null; then
        # uv python find returns 0 if it finds a suitable Python
        if uv python find --quiet 2>/dev/null; then
            return 0
        fi
    fi

    # Fallback: check system Python
    local python_cmd=""
    for cmd in python3 python; do
        if command -v "$cmd" &> /dev/null; then
            local version=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
            if [ -n "$version" ]; then
                local major=$(echo "$version" | cut -d. -f1)
                local minor=$(echo "$version" | cut -d. -f2)
                local req_major=$(echo "$MIN_PYTHON_VERSION" | cut -d. -f1)
                local req_minor=$(echo "$MIN_PYTHON_VERSION" | cut -d. -f2)

                if [ "$major" -gt "$req_major" ] || ([ "$major" -eq "$req_major" ] && [ "$minor" -ge "$req_minor" ]); then
                    return 0
                fi
            fi
        fi
    done

    return 1
}

install_python() {
    print_step "Python $MIN_PYTHON_VERSION+ is required but not found."
    echo ""
    print_info "uv can install a standalone Python for you."
    print_info "This doesn't affect your system Python installation."
    echo ""

    # Ask which version to install
    local python_version
    python_version=$(prompt_input "Python version to install" "3.12")

    if [ -z "$python_version" ]; then
        print_error "No Python version specified."
        exit 1
    fi

    print_step "Installing Python $python_version via uv..."
    echo ""
    print_info "Press Ctrl+C to cancel"
    echo ""

    if uv python install "$python_version"; then
        INSTALLED_PYTHON=true
        print_success "Python $python_version installed successfully"
    else
        print_error "Failed to install Python $python_version"
        print_info "You can install Python manually and run this script again."
        exit 1
    fi
}

#
# System Dependencies (optional)
#
check_build_deps() {
    local os=$(detect_os)

    # Most uv-managed packages don't need build deps, but some might
    # This is informational only
    case "$os" in
        linux)
            if ! command -v gcc &> /dev/null; then
                return 1
            fi
            ;;
    esac
    return 0
}

suggest_build_deps() {
    local os=$(detect_os)
    local distro=$(detect_distro)

    print_warning "Build tools not found (optional, needed for some packages)."
    echo ""
    print_info "If you encounter build errors, install development tools:"
    echo ""

    case "$os" in
        macos)
            print_info "  xcode-select --install"
            ;;
        linux)
            case "$distro" in
                ubuntu|debian|pop)
                    print_info "  sudo apt install -y build-essential python3-dev"
                    ;;
                fedora)
                    print_info "  sudo dnf groupinstall -y 'Development Tools'"
                    print_info "  sudo dnf install -y python3-devel"
                    ;;
                arch|manjaro)
                    print_info "  sudo pacman -S base-devel"
                    ;;
                *)
                    print_info "  Install your distribution's development tools package"
                    ;;
            esac
            ;;
    esac
    echo ""
}

#
# Repository Management
#
clone_or_update_repo() {
    print_step "Setting up spellbook repository..."

    if [ -d "$INSTALL_DIR/.git" ]; then
        print_info "Found existing installation at $INSTALL_DIR"

        if prompt_yn "Update existing installation?"; then
            cd "$INSTALL_DIR"
            if git pull --ff-only 2>/dev/null; then
                print_success "Updated to latest version"
            else
                print_warning "Could not fast-forward. Using existing version."
            fi
        fi
    else
        if [ -d "$INSTALL_DIR" ]; then
            print_warning "Directory $INSTALL_DIR exists but is not a git repository."
            if prompt_yn "Back up and replace?"; then
                local backup="${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
                mv "$INSTALL_DIR" "$backup"
                print_info "Backed up to $backup"
            else
                print_error "Cannot continue without a clean install directory."
                exit 1
            fi
        fi

        print_step "Cloning spellbook to $INSTALL_DIR..."
        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone "$REPO_URL" "$INSTALL_DIR"
        print_success "Repository cloned"
    fi
}

#
# Run Installer
#
run_installer() {
    print_step "Running spellbook installer..."
    echo ""

    cd "$INSTALL_DIR"
    uv run install.py "$@"
}

#
# Summary
#
print_summary() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""

    if [ "$INSTALLED_UV" = true ] || [ "$INSTALLED_PYTHON" = true ]; then
        print_info "Installed during bootstrap:"
        [ "$INSTALLED_UV" = true ] && print_info "  • uv (Python package manager)"
        [ "$INSTALLED_PYTHON" = true ] && print_info "  • Python (via uv)"
        echo ""
    fi

    print_info "Spellbook location: $INSTALL_DIR"
    echo ""
    print_info "Common commands:"
    print_info "  Upgrade:    cd $INSTALL_DIR && git pull && uv run install.py"
    print_info "  Uninstall:  uv run $INSTALL_DIR/uninstall.py"
    print_info "  Serve docs: cd $INSTALL_DIR && uvx mkdocs serve"
    echo ""

    if [ "$INSTALLED_UV" = true ]; then
        print_warning "Restart your shell or run: source ~/.bashrc (or ~/.zshrc)"
    fi
}

#
# Help
#
show_help() {
    cat << 'EOF'
Spellbook Bootstrap Installer

Usage:
  curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
  curl -fsSL ... | bash -s -- [OPTIONS]

Options:
  --help, -h          Show this help message
  --yes, -y           Skip confirmation prompts (accept defaults)
  --install-dir DIR   Install to DIR instead of ~/.local/share/spellbook

  Options passed to install.py:
  --platforms LIST    Comma-separated platforms (claude_code,opencode,codex,gemini)
  --force             Force reinstall even if version matches
  --dry-run           Show what would be done without changes
  --no-interactive    Skip platform selection UI

Environment Variables:
  SPELLBOOK_DIR       Override install directory

Prerequisites (installed automatically if missing):
  • uv    - Fast Python package manager (https://docs.astral.sh/uv/)
  • git   - Version control (prompted for system install)
  • Python 3.10+ - Installed via uv if not found

Examples:
  # Interactive install (recommended)
  curl -fsSL .../bootstrap.sh | bash

  # Non-interactive with defaults
  curl -fsSL .../bootstrap.sh | bash -s -- --yes

  # Custom location
  curl -fsSL .../bootstrap.sh | bash -s -- --install-dir ~/my-spellbook

  # Specific platforms only
  curl -fsSL .../bootstrap.sh | bash -s -- --platforms claude_code,codex

EOF
}

#
# Main
#
main() {
    local installer_args=()

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --yes|-y)
                INTERACTIVE=false
                shift
                ;;
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            *)
                # Pass through to installer
                installer_args+=("$1")
                shift
                ;;
        esac
    done

    print_header
    check_terminal

    # Step 1: Check/install git
    print_step "Checking prerequisites..."
    echo ""

    if check_git; then
        print_success "git $(git --version | cut -d' ' -f3)"
    else
        install_git
        if ! check_git; then
            print_error "git still not available. Please install it and try again."
            exit 1
        fi
        print_success "git installed"
    fi

    # Step 2: Check/install uv
    if check_uv; then
        print_success "$(uv --version)"
    else
        install_uv
    fi

    # Step 3: Check/install Python
    if check_python; then
        local py_version=$(uv python find 2>/dev/null || python3 --version 2>/dev/null || python --version 2>/dev/null)
        print_success "Python available ($py_version)"
    else
        install_python
    fi

    # Step 4: Optional build deps check
    if ! check_build_deps; then
        suggest_build_deps
    fi

    echo ""

    # Step 5: Clone/update repo
    clone_or_update_repo

    echo ""

    # Step 6: Run installer
    run_installer "${installer_args[@]}"

    # Summary
    print_summary
}

main "$@"
