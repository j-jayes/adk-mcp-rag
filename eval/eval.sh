#!/usr/bin/env bash
set -euo pipefail

# Ensure we run from the repo root (one level up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

adk eval agents ./eval/data/longer_evalset.evalset.json --config_file_path ./eval/data/test_config.json