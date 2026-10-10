# EutherBoot · System Regis

**The machine belongs to its owner.**

A Rust-first x86_64 UEFI boot environment. Local control, private by design,
freedom through understanding. No runtime network, telemetry or cloud services.

The current prototype reads TOML from its own EFI volume, validates it strictly,
displays configured EFI targets, and chainloads the selected application. It has
configurable default/timeout, keyboard navigation, paginated menus and firmware
text fallback. A separate EFI child demonstrates returning success and failure.
No installed operating system, physical hardware or Secure Boot has been tested.

## Build and run

Requirements: Rust with `x86_64-unknown-uefi`, Python 3.11+, QEMU x86_64 and OVMF.
Tested with Rust 1.99.0 and QEMU 11.1.2. Cargo.lock pins dependencies. Install the
target with `rustup target add x86_64-unknown-uefi`. Scripts also recognize the
isolated rustup installation under `.tools/` without changing the host compiler.

```sh
./scripts/build.sh
python3 scripts/qemu.py                 # interactive window
./scripts/validate-config.sh eutherboot.toml
./scripts/test.sh                       # shared Rust tests + 20 OVMF cases
```

Override `OVMF_CODE` and `OVMF_VARS` if needed. Defaults are Arch Linux's
`/usr/share/edk2/x64/OVMF_{CODE,VARS}.4m.fd`; use a matching firmware pair.
The QEMU runner copies the binary, config and test child into a unique disposable
FAT directory, and copies the firmware variable store. It attaches no host disk,
ESP or network interface. Exiting the runner removes the temporary storage.

Binaries: `artifacts/EutherBoot.efi`, `artifacts/TestChild.efi`.
Checksums: `artifacts/SHA256SUMS`.
Logs/screenshots: `artifacts/qemu-<width>x<height>-<scenario>-<config-case>/`.
Artifacts, target output and local tools are intentionally ignored by Git.
The supplied build enables EutherBoot's `qemu-debug` feature (port 0xe9).
Normal builds without this feature have no debug-port writes. The independent
test child is QEMU-only and always emits diagnostic markers.

## Configuration

Firmware reads **only** `\EFI\EutherBoot\eutherboot.toml` from the volume that
contains EutherBoot. No search across disks or fallback to another config occurs.
The QEMU runner copies the repository's `eutherboot.toml` there for normal runs.
The host validator and firmware use the same no_std Rust parser and schema.

```toml
[boot]
default = "test"
timeout = 0
theme = "system-regis"

[[entry]]
id = "test"
name = "EFI test application"
type = "efi"
path = '\EFI\EutherBoot\TestChild.efi'
```

`default` must match a unique entry ID. `timeout` is 0..3600 seconds; zero or
omission means wait indefinitely. The only supported theme is `system-regis`
(the default). A positive timeout starts the default once, after the initial
menu appears. **Any key cancels it**, including keys with no other action.
Load failures and returning children retain the menu and never restart the timer.

The entire configuration is rejected for unknown fields, invalid TOML/UTF-8,
unsupported types/themes, missing/duplicate IDs, duplicate case-insensitive
paths, an unresolved default or a reference to EutherBoot's own loaded path.
On error, no configured targets are enabled and no timer is armed; the error
appears in text mode with read-only inspection and return-to-firmware available.
The host checker cannot verify firmware-specific self-reference or file existence.

Current bounds: 16 KiB input, 1..16 EFI entries, IDs of 1..32 ASCII letters,
digits, `-` or `_`, printable ASCII names of 1..48 characters, and ASCII paths
up to 240 bytes. Paths must start with `\EFI\`, end in `.efi`, and cannot use
traversal, empty components, whitespace, wildcards or short-name `~` aliases.
These restrictions make the initial graphical renderer/path handling explicit.
Unicode entry names, other themes and `type = "firmware"` are **not implemented**;
unsupported values produce errors. The built-in firmware-return action simply
returns to the caller; it does not open firmware settings or change BootOrder.

## Controls

- Up/Down: select, with wrapping and automatic page changes.
- Enter: start the selected EFI entry, inspect configuration or return to firmware.
- F2: use firmware text output for the remainder of the run.
- Escape: return to the firmware caller.
- In the test child: Enter returns SUCCESS; Escape returns ABORTED.

Configuration inspection is read-only and also switches to text mode. There is
no configuration editor, persistent preference save or installer yet.

## Focused virtual tests

```sh
python3 scripts/qemu.py --test --scenario missing
python3 scripts/qemu.py --test --scenario invalid
python3 scripts/qemu.py --test --scenario abort
python3 scripts/qemu.py --test --config-case default
python3 scripts/qemu.py --test --config-case timeout
python3 scripts/qemu.py --test --config-case cancel
python3 scripts/qemu.py --test --config-case unknown
python3 scripts/qemu.py --test --config-case many --width 640 --height 480
```

See [architecture](ARCHITECTURE.md), [roadmap](ROADMAP.md) and
[validation evidence](docs/VALIDATION.md). This remains a virtual-development
prototype; physical installation requires separate approval and rollback planning.
