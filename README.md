# EutherBoot · System Regis

**The machine belongs to its owner.**

A Rust-first x86_64 UEFI boot environment. Local control, private by design,
freedom through understanding. No runtime network, telemetry or cloud services.

The current prototype reads TOML from its own EFI volume, validates it strictly,
displays configured EFI targets, and chainloads the selected application. It has
configurable default/timeout, keyboard navigation, paginated menus and firmware
text fallback. Its keyboard editor supports isolated drafts, validation, preview,
confirmed saves with backup, and explicit recovery after interrupted saves.
F4 discovers EFI applications on GPT EFI System Partitions for explicit manual
launch. A separate EFI child demonstrates returning success and failure.
No installed operating system, physical hardware or Secure Boot has been tested.

## Build and run

Requirements: Rust with `x86_64-unknown-uefi`, Python 3.11+, QEMU x86_64 and OVMF.
GPT/FAT runs additionally need `sgdisk`, `mkfs.fat` and mtools (`mcopy`, `mtype`).
Tested with Rust 1.99.0 and QEMU 11.1.2. Cargo.lock pins dependencies. Install the
target with `rustup target add x86_64-unknown-uefi`. Scripts also recognize the
isolated rustup installation under `.tools/` without changing the host compiler.

```sh
./scripts/build.sh
python3 scripts/qemu.py                 # interactive window
./scripts/validate-config.sh eutherboot.toml
./scripts/test.sh                       # 19 Rust tests + 36 OVMF cases
```

Override `OVMF_CODE` and `OVMF_VARS` if needed. Defaults are Arch Linux's
`/usr/share/edk2/x64/OVMF_{CODE,VARS}.4m.fd`; use a matching firmware pair.
Interactive QEMU runs copy the binary, config and child into a disposable
128 MiB GPT disk containing a 64 MiB FAT32 ESP, and copy the firmware variable
store. Configuration-only regression cases also use directory-backed FAT.
`--disk-image` selects the GPT/FAT image explicitly for a headless run. It attaches no host disk,
ESP or network interface. Exiting the runner removes the temporary storage, including edits made inside
the VM. The repository example is never modified by the guest.

Binaries: `artifacts/EutherBoot.efi`, `artifacts/TestChild.efi`.
Checksums: `artifacts/SHA256SUMS`.
Logs/screenshots: `artifacts/qemu-<width>x<height>-<scenario>-<config-case>/` (suffix `-disk` for
GPT runs); editor evidence is under `artifacts/editor-<case>-<width>x<height>/`.
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
omission means wait indefinitely. Appearance is `system-regis` (the default) or `text`. A positive timeout starts the default once, after the initial
menu appears. **Any key cancels it**, including keys with no other action.
Load failures and returning children retain the menu and never restart the timer.

The entire configuration is rejected for unknown fields, invalid TOML/UTF-8,
unsupported types/themes, missing/duplicate IDs, duplicate case-insensitive
paths, an unresolved default or a reference to EutherBoot's own loaded path.
Unfinished saves (`.new` or `.txn` present) also block automatic boot.
On error, no configured targets are enabled and no timer is armed; the error
appears in text mode with read-only inspection and return-to-firmware available.
The host checker cannot verify firmware-specific self-reference or file existence.

Current bounds: 16 KiB input, 1..16 EFI entries, IDs of 1..32 ASCII letters,
digits, `-` or `_`, printable ASCII names of 1..48 characters, and ASCII paths
up to 240 bytes. Paths must start with `\EFI\`, end in `.efi`, and cannot use
traversal, empty components, whitespace, wildcards or short-name `~` aliases.
These restrictions make the initial graphical renderer/path handling explicit.
Unicode entry names, additional themes and `type = "firmware"` are **not implemented**;
unsupported values produce errors. The built-in firmware-return action simply
returns to the caller; it does not open firmware settings or change BootOrder.

## Controls

- Up/Down: select, with wrapping and automatic page changes.
- Enter: start the selected EFI entry, inspect configuration or return to firmware.
- F2: use firmware text output for the current menu session.
- F3: open the configuration editor in read-only mode.
- F4: scan GPT EFI System Partitions and browse discovered applications.
- Escape: return to the firmware caller.
- In the test child: Enter returns SUCCESS; Escape returns ABORTED.

The menu's configuration summary is read-only and switches to text mode. The
editor is opened with F3. No firmware-variable preferences or installer exist.

## Discover EFI applications

Press **F4** from the main menu. The read-only text browser lists eligible
applications by **partition GUID and full file path**, sorted independently of
firmware handle order. Long paths are abbreviated in the list; Enter displays
the complete path and GUID, and only **Y** starts that target. Escape returns to
the main menu; **R** rescans. F4 cancels any configured timeout, and leaving the
browser never rearms it. No discovered target is added to TOML or made a default.

The initial scanner uses firmware filesystem and partition protocols. It accepts
GPT partitions explicitly typed as EFI System Partitions, searches `\EFI`, and
filters `.efi` files for PE32+ x86_64 application headers. This excludes drivers,
other architectures and obvious non-executables; firmware LoadImage still performs
full validation/authentication. The scanner excludes byte-identical copies of the
current on-disk EutherBoot executable, including renamed copies on another ESP.
Different builds or modified/signed copies are not recognized as self-copies.

Duplicate partition GUIDs exclude **all** affected volumes. Before launch, the
saved handle's GUID and full device path are checked again and the file is
reclassified. This is target identification, not a signature/trust check or a
hot-plug security guarantee. Failed loads and returning children keep the browser.
Discovery is available even when TOML is invalid, but still requires manual
selection and confirmation; it never repairs configuration automatically.

Bounds: at most 32 filesystem handles, 2048 directory records and 64 targets;
`\EFI` plus four nested directory levels; 240-byte paths; printable ASCII names.
Candidate header reads are limited to the first 4096 bytes and total candidate
reads to 64 MiB per scan. Self-copy comparison requires a readable own executable
of at most 4 MiB. Limits/read errors/duplicate GUIDs show a partial-scan notice;
inability to verify the own executable disables discovery. Only firmware-exposed
GPT ESPs are supported: no MBR/superfloppy, raw disk parsing, filesystem drivers,
network search or controller connection is attempted. These restrictions do not
change the existing same-volume configured-entry behavior.

## Configuration editor

Run `python3 scripts/qemu.py`, then press **F3**. Inspection does not write.
Press **E** to begin a separate draft. Up/Down selects the entry to edit.

| Key | Draft action |
| --- | --- |
| D | Make the selected entry the default |
| T | Enter timeout in seconds |
| G | Toggle System Regis graphics / text appearance |
| A | Add an entry by ID, name and EFI path |
| R | Remove the selected entry after confirmation |
| N / P | Change the selected entry's name / path |
| V | Validate the draft with the shared parser and self-reference check |
| F5 | Preview without booting or changing the live configuration |
| S | Validate and open a save confirmation; only Y writes |
| Escape | Confirm discarding the draft and return to the menu |

Field prompts accept Enter, Backspace, F4 to clear and Escape to cancel. Removing
the default does not silently select another entry: choose a replacement with D.
An invalid draft cannot be saved. Saving regenerates TOML formatting/comments;
the previous file is preserved byte-for-byte in `eutherboot.toml.bak`.

After save, settings are reloaded for the menu, but automatic boot remains disabled
for that session. A configured positive timeout takes effect on the next boot.
If a save fails, exit the draft with Escape and reopen F3 to inspect/recover; a
failure may leave staging files and does not imply the disk is unchanged.

Recovery is explicit in F3's read-only mode:

- **B**, then Y: restore the validated backup; the backup itself is retained.
- **C**, then Y: keep the validated current file and remove pending save data.

Both choices discard pending staged data. If neither the live file nor the backup
is valid, external repair is required. The editor starts from a valid existing
configuration; creating a first configuration or repairing raw malformed TOML
inside the editor is not implemented.

The save stages `.new`, verifies readback, creates `.txn`, moves the previous
valid file to `.bak`, installs the verified candidate and removes `.txn` after
final readback. Recovery is tested at three interruption boundaries. This is a
recoverable multi-file protocol, **not a guarantee of FAT power-loss atomicity**.
No automatic disk repair or NVRAM writes occur.

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
python3 scripts/editor-qemu.py --case save
python3 scripts/editor-qemu.py --case readonly
python3 scripts/discovery-qemu.py --case multiple
python3 scripts/discovery-qemu.py --case duplicate
python3 scripts/discovery-qemu.py --case multiple --width 640 --height 480
./scripts/build-faults.sh
python3 scripts/editor-qemu.py --case after-backup
```

See [architecture](ARCHITECTURE.md), [roadmap](ROADMAP.md) and
[validation evidence](docs/VALIDATION.md). This remains a virtual-development
prototype; physical installation requires separate approval and rollback planning.

Fault-injection tests use the separate `EutherBoot-faults.efi` artifact. Its
`test-faults` feature is excluded from the normal binary. Test scripts create
only temporary image files; they do not accept a physical disk destination.
