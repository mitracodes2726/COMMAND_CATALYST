#!/usr/bin/env bash
# One-command demo. Extra flags are passed through, e.g. ./run_demo.sh --owner accept
set -euo pipefail
cd "$(dirname "$0")"
python3 -m proxytwin.demo "$@"
