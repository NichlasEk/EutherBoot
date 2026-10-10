#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
cargo run -p config-check --locked -- "${1:-eutherboot.toml}"
