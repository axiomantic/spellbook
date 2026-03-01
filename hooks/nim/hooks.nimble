# Package
version       = "0.1.0"
author        = "Spellbook"
description   = "Compiled Claude Code hooks for Spellbook"
license       = "MIT"
srcDir        = "src"
bin           = @[
  "tts_timer_start",
  "bash_gate",
  "spawn_guard",
  "state_sanitize",
  "audit_log",
  "canary_check",
  "tts_notify",
  "pre_compact_save",
  "post_compact_recover",
]
binDir        = "bin"

# Dependencies
requires "nim >= 1.6.0"
