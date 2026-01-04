#!/usr/bin/env bash
# SessionStart hook for spellbook plugin

set -euo pipefail

# Determine plugin root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Read using-skills content
using_skills_content=$(cat "${PLUGIN_ROOT}/skills/using-skills/SKILL.md" 2>&1 || echo "Error reading using-skills skill")

# Escape outputs for JSON using pure bash
escape_for_json() {
    local input="$1"
    local output=""
    local i char
    for (( i=0; i<${#input}; i++ )); do
        char="${input:$i:1}"
        case "$char" in
            $'\\') output+='\\' ;;
            '"') output+='\"' ;;
            $'\n') output+='\n' ;;
            $'\r') output+='\r' ;;
            $'\t') output+='\t' ;;
            *) output+="$char" ;;
        esac
    done
    printf '%s' "$output"
}

using_skills_escaped=$(escape_for_json "$using_skills_content")

# Output context injection as JSON
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "<EXTREMELY_IMPORTANT>\nYou have access to spellbook skills.\n\n**Below is the full content of your 'using-skills' skill - your introduction to using skills. For all other skills, use the 'Skill' tool:**\n\n${using_skills_escaped}\n</EXTREMELY_IMPORTANT>"
  }
}
EOF

exit 0
