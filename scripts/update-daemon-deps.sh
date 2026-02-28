#!/usr/bin/env bash
# Regenerate daemon lockfiles from .in files.
# Run this after editing daemon/requirements*.in
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Compiling daemon/requirements.txt..."
uv pip compile daemon/requirements.in -o daemon/requirements.txt --generate-hashes

echo "Compiling daemon/requirements-tts.txt..."
uv pip compile daemon/requirements-tts.in -o daemon/requirements-tts.txt --generate-hashes

echo "Done. Review changes and commit both .in and .txt files."
