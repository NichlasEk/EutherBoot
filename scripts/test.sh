#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
python3 scripts/validate-config.py
python3 scripts/test-config.py
bash scripts/build.sh
python3 scripts/qemu.py --test
python3 scripts/qemu.py --test --width 640 --height 480
