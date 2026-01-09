#!/bin/bash
# Spellbook session initialization
# Checks fun-mode status and selects random persona/context/undertow if enabled

FUN_MODE_FILE="${HOME}/.config/spellbook/fun-mode"
FUN_DIR="${HOME}/.config/spellbook/fun"

# Check if fun mode is enabled
if [[ -f "$FUN_MODE_FILE" ]] && [[ "$(cat "$FUN_MODE_FILE" 2>/dev/null | head -1)" == "yes" ]]; then
    echo "fun_mode=yes"
    echo "persona=$(shuf -n 1 "$FUN_DIR/personas.txt" 2>/dev/null)"
    echo "context=$(shuf -n 1 "$FUN_DIR/contexts.txt" 2>/dev/null)"
    echo "undertow=$(shuf -n 1 "$FUN_DIR/undertows.txt" 2>/dev/null)"
elif [[ -f "$FUN_MODE_FILE" ]]; then
    echo "fun_mode=no"
else
    echo "fun_mode=unset"
fi
