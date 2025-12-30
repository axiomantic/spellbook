#!/usr/bin/env bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Unicode symbols
CHECK="${GREEN}✓${NC}"
CROSS="${RED}✗${NC}"
ARROW="${BLUE}→${NC}"
INFO="${CYAN}ℹ${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_CONFIG_DIR="$HOME/.claude"

print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  Spellbook - Installation Script                         ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${ARROW} $1"
}

print_success() {
    echo -e "${CHECK} $1"
}

print_error() {
    echo -e "${CROSS} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

print_info() {
    echo -e "${INFO} $1"
}

create_directories() {
    print_step "Ensuring directories exist..."

    mkdir -p "$CLAUDE_CONFIG_DIR/skills"
    mkdir -p "$CLAUDE_CONFIG_DIR/commands"
    mkdir -p "$CLAUDE_CONFIG_DIR/agents"
    mkdir -p "$CLAUDE_CONFIG_DIR/plans"

    print_success "Directories ready"
}

install_skills() {
    print_step "Installing skills..."

    local count=0
    for skill_dir in "$SCRIPT_DIR/skills"/*/; do
        if [ -d "$skill_dir" ]; then
            local skill_name=$(basename "$skill_dir")
            local target="$CLAUDE_CONFIG_DIR/skills/$skill_name"

            # Remove existing (file, dir, or symlink)
            rm -rf "$target"

            # Create symlink
            ln -s "$skill_dir" "$target"
            count=$((count + 1))
        fi
    done

    print_success "Installed $count skills"
}

install_commands() {
    print_step "Installing commands..."

    local count=0
    for cmd_file in "$SCRIPT_DIR/commands"/*.md; do
        if [ -f "$cmd_file" ]; then
            local cmd_name=$(basename "$cmd_file")
            local target="$CLAUDE_CONFIG_DIR/commands/$cmd_name"

            # Remove existing
            rm -f "$target"

            # Create symlink
            ln -s "$cmd_file" "$target"
            count=$((count + 1))
        fi
    done

    print_success "Installed $count commands"
}

install_agents() {
    print_step "Installing agents..."

    local count=0
    for agent_file in "$SCRIPT_DIR/agents"/*.md; do
        if [ -f "$agent_file" ]; then
            local agent_name=$(basename "$agent_file")
            local target="$CLAUDE_CONFIG_DIR/agents/$agent_name"

            # Remove existing
            rm -f "$target"

            # Create symlink
            ln -s "$agent_file" "$target"
            count=$((count + 1))
        fi
    done

    if [ $count -gt 0 ]; then
        print_success "Installed $count agents"
    else
        print_info "No agents to install"
    fi
}

install_claude_md() {
    print_step "Installing CLAUDE.md..."

    local source="$SCRIPT_DIR/CLAUDE.md"
    local target="$CLAUDE_CONFIG_DIR/CLAUDE.md"

    if [ -f "$source" ]; then
        # Backup existing if it's not a symlink
        if [ -f "$target" ] && [ ! -L "$target" ]; then
            local backup="$target.backup.$(date +%Y%m%d_%H%M%S)"
            mv "$target" "$backup"
            print_warning "Backed up existing CLAUDE.md to $(basename "$backup")"
        fi

        # Remove existing symlink
        rm -f "$target"

        # Create symlink
        ln -s "$source" "$target"
        print_success "Installed CLAUDE.md"
    else
        print_info "No CLAUDE.md found in spellbook"
    fi
}

print_completion() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  Installation Complete!                                  ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    print_success "Spellbook installed to $CLAUDE_CONFIG_DIR"
    echo ""
    print_info "Skills, commands, and CLAUDE.md are now symlinked"
    print_info "Edit files in $SCRIPT_DIR to update"
    echo ""
}

main() {
    print_header

    # Check if spellbook has content
    if [ ! -d "$SCRIPT_DIR/skills" ] && [ ! -d "$SCRIPT_DIR/commands" ]; then
        print_error "No skills or commands found in $SCRIPT_DIR"
        exit 1
    fi

    create_directories
    install_skills
    install_commands
    install_agents
    install_claude_md
    print_completion
}

main "$@"
