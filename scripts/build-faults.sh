#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
cargo build -p eutherboot --release --features test-faults --target x86_64-unknown-uefi --locked
cp target/x86_64-unknown-uefi/release/eutherboot.efi artifacts/EutherBoot-faults.efi
