#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
bash scripts/build.sh
python3 scripts/test-qemu.py
