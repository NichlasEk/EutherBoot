#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
cargo test -p boot-core --locked
cargo build -p eutherboot --release --features qemu-debug --target x86_64-unknown-uefi --locked
mkdir -p artifacts
cp target/x86_64-unknown-uefi/release/eutherboot.efi artifacts/EutherBoot.efi
sha256sum artifacts/EutherBoot.efi > artifacts/SHA256SUMS
