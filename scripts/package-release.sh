#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
source "$(dirname "$0")/env.sh"
# Build in a separate tree so instrumented QEMU fixtures remain unchanged.
export CARGO_TARGET_DIR="$PWD/target/distribution"
cargo build --locked --release -p eutherboot --target x86_64-unknown-uefi
cargo build --locked --release -p config-check
release_dir="$PWD/artifacts/release"
mkdir -p "$release_dir/packaging" "$release_dir/tools"
cp "$CARGO_TARGET_DIR/x86_64-unknown-uefi/release/eutherboot.efi" "$release_dir/EutherBoot.efi"
cp "$CARGO_TARGET_DIR/release/config-check" "$release_dir/config-check"
cp LICENSE README.md ARCHITECTURE.md ROADMAP.md "$release_dir/"
cp packaging/arch/eutherboot.toml "$release_dir/eutherboot.toml"
cp -r docs "$release_dir/"
cp -r packaging/arch "$release_dir/packaging/"
cp tools/eutherbootctl.py "$release_dir/tools/"
# Include exact source (including reviewed working changes), offline dependencies,
# and their original license files with the binary package.
source_stage=$(mktemp -d "$PWD/artifacts/source.XXXXXXXX")
trap 'rm -rf "$source_stage"' EXIT
python3 - "$source_stage" <<'PYCODE'
import subprocess,shutil,sys
from pathlib import Path
out=Path(sys.argv[1])
for name in subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard']).split(b'\0'):
    if not name:continue
    source=Path(name.decode())
    if not source.is_file():continue
    target=out/source
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
PYCODE
mkdir -p "$source_stage/.cargo"
cargo vendor --locked --versioned-dirs "$source_stage/vendor" > "$source_stage/.cargo/config.toml"
# Cargo prints an absolute vendor path; the source bundle must be relocatable.
python3 - "$source_stage" <<'PYCODE'
import sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'.cargo/config.toml'
p.write_text(p.read_text().replace(str(root/'vendor'),'vendor'))
PYCODE
tar --sort=name --mtime="@$(git show -s --format=%ct HEAD)" --owner=0 --group=0 --numeric-owner \
    -czf "$release_dir/eutherboot-source.tar.gz" -C "$source_stage" .
python3 - "$release_dir" <<'PY'
import hashlib,json,subprocess,sys
from pathlib import Path
out=Path(sys.argv[1])
files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ('manifest.json','SHA256SUMS')}
manifest={'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          'dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
          'rustc':subprocess.check_output(['rustc','--version'],text=True).strip(),
          'target':'x86_64-unknown-uefi','qemu_debug':False,'license':'GPL-3.0-only','files':files}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(out/'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name,digest in files.items()))
PY
printf 'Release files: %s\n' "$release_dir"
printf 'Matching source, offline dependencies and dependency licenses included.\n'
