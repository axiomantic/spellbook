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
    mkdir -p "$CLAUDE_CONFIG_DIR/scripts"
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

install_scripts() {
    print_step "Installing scripts..."

    local count=0
    for script_file in "$SCRIPT_DIR/scripts"/*.py "$SCRIPT_DIR/scripts"/*.sh; do
        if [ -f "$script_file" ]; then
            local script_name=$(basename "$script_file")
            local target="$CLAUDE_CONFIG_DIR/scripts/$script_name"

            # Remove existing
            rm -f "$target"

            # Create symlink
            ln -s "$script_file" "$target"
            count=$((count + 1))
        fi
    done

    if [ $count -gt 0 ]; then
        print_success "Installed $count scripts"
    else
        print_info "No scripts to install"
    fi
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

install_docs() {
    print_step "Installing docs..."

    local source="$SCRIPT_DIR/docs"
    local target="$CLAUDE_CONFIG_DIR/docs"

    if [ -d "$source" ]; then
        # Remove existing (file, dir, or symlink)
        rm -rf "$target"

        # Create symlink
        ln -s "$source" "$target"
        print_success "Installed docs directory"
    else
        print_info "No docs directory found in spellbook"
    fi
}

install_patterns() {
    print_step "Setting up shared patterns..."

    local patterns_dir="$SCRIPT_DIR/patterns"
    local claude_patterns_dir="$CLAUDE_CONFIG_DIR/patterns"

    # Verify SCRIPT_DIR is set
    if [ -z "$SCRIPT_DIR" ]; then
        print_error "SCRIPT_DIR not set. Cannot create patterns directory."
        exit 1
    fi

    # Create patterns directory if it doesn't exist
    if ! mkdir -p "$patterns_dir"; then
        print_error "Failed to create patterns directory: $patterns_dir"
        print_error "Check permissions and try again."
        exit 1
    fi

    # Create .claude directory if it doesn't exist
    if ! mkdir -p "$CLAUDE_CONFIG_DIR"; then
        print_error "Failed to create .claude directory: $CLAUDE_CONFIG_DIR"
        print_error "Check permissions and try again."
        exit 1
    fi

    # Handle existing patterns location (including broken symlinks)
    if [ -L "$claude_patterns_dir" ]; then
        # Symlink exists - check if it's broken or points to wrong location
        if [ ! -e "$claude_patterns_dir" ]; then
            print_warning "Broken symlink detected at $claude_patterns_dir"
            print_info "Removing broken symlink and recreating..."
            rm "$claude_patterns_dir"
        else
            # Symlink is valid - verify it points to correct location
            local current_target
            current_target=$(readlink "$claude_patterns_dir")
            if [ "$current_target" != "$patterns_dir" ]; then
                print_warning "Existing symlink points to different location"
                print_info "  Current: $current_target"
                print_info "  Expected: $patterns_dir"
                print_info "Removing old symlink and recreating..."
                rm "$claude_patterns_dir"
            else
                print_success "Patterns symlink already exists and is correct"
            fi
        fi
    fi

    # Create symlink if it doesn't exist (or was just removed)
    if [ ! -L "$claude_patterns_dir" ]; then
        # Check for non-symlink obstruction
        if [ -e "$claude_patterns_dir" ]; then
            print_warning "$claude_patterns_dir exists but is not a symlink"
            print_error "Backup existing directory and re-run install.sh"
            print_error "  mv $claude_patterns_dir ${claude_patterns_dir}.backup"
            exit 1
        fi

        # Create new symlink
        if ! ln -s "$patterns_dir" "$claude_patterns_dir"; then
            print_error "Failed to create symlink"
            print_error "  Source: $patterns_dir"
            print_error "  Target: $claude_patterns_dir"
            exit 1
        fi

        print_success "Created symlink: $claude_patterns_dir -> $patterns_dir"
    fi

    # Verify adaptive-response-handler.md exists (REQUIRED)
    if [ ! -f "$patterns_dir/adaptive-response-handler.md" ]; then
        print_error "adaptive-response-handler.md not found in patterns/"
        print_error "  Expected: $patterns_dir/adaptive-response-handler.md"
        print_error "This file is REQUIRED for implement-feature and other skills."
        exit 1
    fi

    print_success "adaptive-response-handler.md found"
}

validate_doc_references() {
    print_step "Validating doc references in skills..."

    local broken_count=0
    local checked_count=0

    for skill_dir in "$SCRIPT_DIR/skills"/*/; do
        if [ -f "$skill_dir/SKILL.md" ]; then
            # Extract doc references (docs/*.md patterns)
            while IFS= read -r doc_ref; do
                if [ -n "$doc_ref" ]; then
                    checked_count=$((checked_count + 1))
                    # Check if the referenced doc exists relative to spellbook root
                    if [ ! -f "$SCRIPT_DIR/$doc_ref" ]; then
                        local skill_name=$(basename "$skill_dir")
                        print_warning "Broken reference in $skill_name: $doc_ref"
                        broken_count=$((broken_count + 1))
                    fi
                fi
            done < <(grep -oE 'docs/[a-zA-Z0-9_-]+\.md' "$skill_dir/SKILL.md" 2>/dev/null | sort -u)
        fi
    done

    if [ $checked_count -eq 0 ]; then
        print_info "No doc references found in skills"
    elif [ $broken_count -eq 0 ]; then
        print_success "All $checked_count doc references valid"
    else
        print_warning "$broken_count of $checked_count doc references are broken"
    fi
}

setup_claude_code_bootstrap() {
    print_step "Setting up Claude Code bootstrap..."

    local bootstrap_file="$SCRIPT_DIR/.claude-plugin/bootstrap.md"

    if [ ! -f "$bootstrap_file" ]; then
        print_warning "Claude Code bootstrap.md not found"
        return
    fi

    print_success "Claude Code bootstrap ready at .claude-plugin/bootstrap.md"
}

setup_codex_integration() {
    print_step "Setting up Codex integration..."

    local codex_dir="$HOME/.codex"
    local spellbook_link="$codex_dir/spellbook"

    if [ ! -d "$codex_dir" ]; then
        print_info "Codex config directory not found (skipping)"
        return
    fi

    # Create symlink to spellbook root for easy access from Codex
    if [ -L "$spellbook_link" ]; then
        rm -f "$spellbook_link"
    fi

    ln -s "$SCRIPT_DIR" "$spellbook_link"
    print_success "Created Codex symlink at ~/.codex/spellbook"

    # Verify CLI script exists and is executable
    local cli_script="$SCRIPT_DIR/.codex/spellbook-codex"
    if [ -f "$cli_script" ] && [ -x "$cli_script" ]; then
        print_success "Codex CLI script ready and executable"
    else
        print_warning "Codex CLI script not found or not executable"
    fi
}

setup_opencode_integration() {
    print_step "Setting up OpenCode integration..."

    # Check if OpenCode plugin exists (placeholder for future implementation)
    local opencode_plugin="$SCRIPT_DIR/.opencode-plugin"

    if [ -d "$opencode_plugin" ]; then
        print_success "OpenCode plugin directory found"
    else
        print_info "OpenCode plugin not yet implemented (skipping)"
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
    install_scripts
    install_agents
    install_claude_md
    install_docs
    install_patterns
    validate_doc_references
    setup_claude_code_bootstrap
    setup_codex_integration
    setup_opencode_integration
    print_completion
}

main "$@"
