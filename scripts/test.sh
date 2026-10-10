#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
python3 scripts/validate-config.py
python3 scripts/test-config.py
bash scripts/build.sh
python3 scripts/qemu.py --test
python3 scripts/qemu.py --test --width 640 --height 480
python3 scripts/qemu.py --test --scenario abort
python3 scripts/qemu.py --test --scenario missing
python3 scripts/qemu.py --test --scenario invalid
