#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$ROOT/.tools/cargo/bin/cargo" ]]; then
  export CARGO_HOME="$ROOT/.tools/cargo" RUSTUP_HOME="$ROOT/.tools/rustup"
  export PATH="$CARGO_HOME/bin:$PATH"
fi
cd "$ROOT"
