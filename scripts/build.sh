#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
cargo test -p boot-core --locked
cargo run -p config-check --locked -- eutherboot.toml
cargo build -p eutherboot --release --features qemu-debug --target x86_64-unknown-uefi --locked
cargo build -p eutherboot-test-child --release --target x86_64-unknown-uefi --locked
mkdir -p artifacts
cp target/x86_64-unknown-uefi/release/eutherboot.efi artifacts/EutherBoot.efi
cp target/x86_64-unknown-uefi/release/eutherboot-test-child.efi artifacts/TestChild.efi
sha256sum artifacts/EutherBoot.efi artifacts/TestChild.efi > artifacts/SHA256SUMS
