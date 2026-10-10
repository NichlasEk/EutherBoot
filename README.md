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
launch or import into an unsaved configuration draft. Persisted targets can select
an ESP by its unique partition GUID. A separate EFI child demonstrates returning success and failure.
Linux EFI-stub and unsigned UKI boots reach a generated minimal initramfs PID 1 in
QEMU, including a second ESP. Disposable owner-key Secure Boot tests also cover
EFI authentication and a signed diagnostic UKI. The official installed Arch basic
image also boots through EutherBoot with its own initramfs, systemd and Btrfs root;
two cold boots verify a persistent guest write. Physical hardware remains untested.

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
./scripts/test.sh                       # 25 Rust tests + 48 OVMF cases
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

An entry may additionally select a specific GPT EFI System Partition:

```toml
[[entry]]
id = "other-esp"
name = "Boot application on another ESP"
type = "efi"
path = '\EFI\Tools\loader.efi'
partition_guid = "aabbccdd-1234-5678-9012-aabbccddeeff"
```

The GUID above is an example, not a host-machine value. Use the **unique partition
GUID** (PARTUUID), not the filesystem UUID, disk GUID or ESP type GUID. Omit
`partition_guid` to use EutherBoot's own volume, preserving previous behavior.
An explicit GUID must be nonzero hexadecimal in 8-4-4-4-12 form; uppercase is
accepted and normalized. An explicitly empty string is invalid.

On every launch, an explicit selector must resolve to exactly one eligible GPT
ESP. A missing/duplicate GUID or identity-enumeration error fails with a diagnostic;
there is no fallback to the own volume or another discovered target. If the
configured default's selector cannot resolve at startup, its automatic timer is
disabled. Other entries remain available for deliberate selection. File checks
and LoadImage errors retain the menu without retries or fallback.

Paths may repeat on different partition selectors. Repeating a case-insensitive
path on the same selector is rejected; firmware also rejects an implicit own-volume
entry and explicit own-GUID entry referring to the same file. Self-path checks
include the volume, so the same path on a different ESP remains valid. GUID-qualified
launches also apply discovery's image-header and exact-self-copy checks.

Validation can accept a well-formed GUID for an absent disk; availability is
checked at launch (and before arming a qualified default's timer). This allows
editing entries for temporarily disconnected media. Configuration and backups
are still written **only on EutherBoot's own volume**, never to the selected ESP.

`default` must match a unique entry ID. `timeout` is 0..3600 seconds; zero or
omission means wait indefinitely. Appearance is `system-regis` (the default) or `text`. A positive timeout starts the default once, after the initial
menu appears. **Any key cancels it**, including keys with no other action.
Load failures and returning children retain the menu and never restart the timer.

The entire configuration is rejected for unknown fields, invalid TOML/UTF-8,
unsupported types/themes, malformed partition GUIDs, missing/duplicate IDs,
duplicate case-insensitive paths on the same selector, an unresolved default or
a reference to EutherBoot's own loaded path on its own volume.
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

## Installed Arch in QEMU

```sh
python3 scripts/prepare-arch.py  # download and verify the pinned official basic image
python3 scripts/arch-qemu.py     # two cold boots and a persistent-write check
```

Additional tools: curl, GnuPG, qemu-img and btrfs-progs. No sudo, loop device or
host mount is needed. The signed download is about 513 MiB; preparation uses
sparse regular files for the 40 GiB virtual disk. Allow several GiB of free space.
The runner uses KVM when accessible, otherwise TCG (this Arch result used KVM).

EutherBoot receives a separate read-only 512 MiB virtual ESP containing the
image's own kernel and initramfs. Arch runs on a disposable QCOW2 overlay;
its original image and supplied GRUB remain intact. Firmware variables are
fresh temporary copies. The VM has no network. For this offline fixture only,
`systemd.mask=systemd-time-wait-sync.service` avoids waiting indefinitely for
network time during first-boot keyring initialization.

The test logs in with the image's public `arch` / `arch` credentials, checks real
systemd PID 1, the expected Btrfs root/PARTUUID, installed packages, active
multi-user.target and no failed units. It writes a guest marker, powers off,
and checks it after a second cold boot with a different boot ID. Both temporary
disks are removed after the run; the verified download and extracted payloads
remain cached. Logs, menu captures and `result.json` are under
`artifacts/arch-qemu/`. See [fixture provenance](tests/arch/README.md).
This tests an upstream preinstalled system, not installation from an Arch ISO
or installed Arch under Secure Boot.

## Arch kernel-update experiment

```sh
python3 scripts/prepare-arch.py
python3 scripts/arch-update-qemu.py
```

This optional online test installs the update integration **inside a disposable
Arch guest**, runs a full `pacman -Syu` with UKI build dependencies, and boots the
new kernel through EutherBoot. Arch's normal mkinitcpio hook generates the UKI;
a post hook publishes it to the fixed `\EFI\Linux\arch-linux.efi` path.
The guest's pre-transaction check refuses a missing, wrong or read-only ESP.

Only the first boot has QEMU user-mode NAT, without forwarded ports or shared
host directories. Subsequent boots are offline. No host package installation,
privileged host mount or firmware change is performed. The test also checks
refusal paths, replacement of an existing UKI, and reboot after a simulated power
cut with an abandoned partial staging file. Evidence is written under
`artifacts/arch-update-qemu/`.

This is a QEMU prototype, not a host installer. LTS recovery, retained old modules,
Secure Boot signing and comprehensive power-loss handling remain open. See the
[guest-only update workflow and limits](tests/arch/update/README.md).

## Linux EFI-stub and UKI

An x86_64 Linux kernel built with `CONFIG_EFI_STUB` can be copied under an `.efi`
filename and selected explicitly:

```toml
[[entry]]
id = "linux"
name = "Linux EFI-stub"
type = "linux-efi"
path = '\EFI\Linux\kernel.efi'
cmdline = "root=UUID=YOUR-ROOT-UUID ro"
initrd = '\EFI\Linux\initrd.img'
```

These are illustrative paths and parameters, not detected host values. The optional
`partition_guid` selects the ESP for both kernel and initrd. The command line is
optional, at most 1024 printable ASCII bytes. The optional single initrd requires
an absolute `\EFI\` path with the same path restrictions except the `.efi` suffix;
it must be a readable, nonempty regular file no larger than 128 MiB. Explicit
`initrd=` in cmdline is rejected; `noinitrd` is rejected when an initrd is selected.
The composed options must fit the kernel header's command-line capacity.

EutherBoot checks the PE application and Linux boot headers, then supplies UCS-2
LoadOptions containing only the configured command line. An initrd is read fully
from the selected ESP before launch and exposed through the Linux **LoadFile2**
device path. Linux chooses its destination buffer and handles ExitBootServices.
There is no generated `initrd=` argument and no silent path-based fallback.
An initrd requires EFI-stub v1/v2 or the LoadFile2 capability bit in v3+; kernels
without that capability are rejected before LoadImage. This is not support for
arbitrary ELF kernels or GRUB's Linux loading protocol.

A pre-existing Linux initrd provider blocks a linux-efi launch, even when the
entry has no initrd, to avoid consuming an unrelated source. Returning children
are unloaded/released before the temporary provider is removed. If firmware
refuses removal, boot/firmware return remains blocked: R explicitly retries
cleanup, or the user can power off. This prevents unloading live callback code.
The initrd snapshot requires up to 128 MiB of extra boot-manager memory, in addition
to the kernel's destination allocation; external initrd data is not authenticated.

A **UKI uses `type = "efi"`** and its embedded kernel, command line and initrd.
Ordinary EFI entries reject external `cmdline`/`initrd` fields. Discovery imports
always start as `efi`; K explicitly changes the type when appropriate.
Firmware authentication remains authoritative. The virtual owner-key tests below
cover one OVMF policy; they do not establish broad hardware or shim compatibility.

Run the additional nine Linux cases with a local EFI-stub kernel and systemd stub:

```sh
./scripts/test-linux.sh --kernel /path/to/vmlinuz
# Optional: --stub /path/to/linuxx64.efi.stub
```

This requires GCC with static libc, binutils (`objcopy`), `file` and the GPT/FAT
requirements above. It compiles a minimal diagnostic PID 1 and creates a fresh
initramfs and unsigned UKI under ignored `artifacts/linux/`, recording source and
artifact hashes. It does not use the host initramfs or invoke host initramfs tools.
Logs and screenshots are under `artifacts/linux-<case>-<width>x<height>/`.

An EFI child controls its own side effects. The tested systemd stub creates
`loader/random-seed` and `loader/boot-secret-mixin` on a writable ESP. A separate
case records those writes and verifies existing EFI files and the other partition
remain unchanged; normal UKI cases use a read-only virtual disk. This is not an
EutherBoot disk-write policy imposed on the child.

## LoadFile2 lifecycle tests

```sh
./scripts/build.sh
./scripts/build-faults.sh
python3 scripts/test-initrd.py
```

Eight additional QEMU cases use a synthetic EFI application with Linux-identifying
headers and unchanged test-child code. This is a returning protocol consumer,
not evidence of a Linux boot. It checks null/invalid arguments, boot policy,
size queries, undersized buffers, exact/repeated copies and trailing canaries.
Three repeated launches alternate with a plain EFI child that independently
confirms no initrd provider remains. Old-stub capability, empty/no-initrd cases,
partial registration failure and cleanup refusal/retry are exercised. The separate
fault artifact alone reads `initrd-fault`; normal firmware never reads that file.
Logs, screenshots and disk hashes are under `artifacts/initrd-*`.
The Linux matrix above independently proves actual kernel/userspace boot through
LoadFile2, including remote ESP selection and edited initrd paths after reboot.

## Secure Boot tests

The test harness signs EutherBoot and its child with fresh disposable RSA keys,
enrolls test certificates in a **temporary OVMF variable-store copy**, and enables
SMM and Secure Boot in QEMU. It does not enroll anything in the host firmware or
use existing signing keys. Private keys and signed fixture copies are deleted
with the temporary test directory; only logs, screenshots, hashes and public
certificate fingerprints remain under ignored `artifacts/secureboot-*`.

Additional tools: OpenSSL, `sbsign`/`sbverify` from sbsigntools and `virt-fw-vars`
from virt-firmware. Tested versions: sbsigntools 0.9.5 and virt-firmware 26.9.
Tools may be on PATH; the runner also recognizes isolated installs under
`.tools/sbsigntools/usr/bin/` and `.tools/secureboot/bin/`. For example:

```sh
python3 -m venv .tools/secureboot
.tools/secureboot/bin/pip install 'virt-firmware==26.9'
./scripts/build.sh
python3 scripts/test-secureboot.py
# After building the diagnostic Linux fixtures:
python3 scripts/test-secureboot.py --uki
```

`OVMF_SECURE_CODE` overrides the default
`/usr/share/edk2/x64/OVMF_CODE.secboot.4m.fd`; `OVMF_VARS` must be a matching blank
template. The script creates its own PK, KEK, db and dbx from test certificates.
One disposable certificate fills PK/KEK/db roles for this isolated test; it is
not a production key-management example. No Microsoft/shim trust is added.

Two resolution cases exercise a trusted image, unsigned image, unknown signer,
changed signed image and certificate present in both db and dbx. Each refusal
is repeated, followed by successful trusted-child execution. An untrusted default
also fails once without automatic fallback or rearming. The independent child
reads `SecureBoot=1` and `SetupMode=0` through firmware runtime services.
`--uki` adds a third VM that then boots a signed diagnostic UKI to Linux PID 1.
Its virtual disk is read-only; other cases hash their whole writable virtual disk.

This OVMF rejects unauthorized images with `ACCESS_DENIED` and no loaded handle.
Cleanup of an optional handle returned with `SECURITY_VIOLATION` remains untested.
The tests do not cover shim/MOK/SBAT, physical firmware, production trust stores,
or authentication of external TOML, command lines and initrds. Signing EutherBoot
alone does not authenticate those external inputs; a signed self-contained UKI
is the Linux integrity boundary tested here.

## Controls

- Up/Down: select, with wrapping and automatic page changes.
- Enter: start the selected EFI entry, inspect configuration or return to firmware.
- F2: use firmware text output for the current menu session.
- F3: open the configuration editor in read-only mode.
- F4: scan GPT EFI System Partitions and browse discovered applications.
- Escape: return to the firmware caller.
- In the test child: Enter returns SUCCESS; Escape returns ABORTED; D exits with error data.

The menu's configuration summary is read-only and switches to text mode. The
editor is opened with F3. No firmware-variable preferences or installer exist.

## Discover EFI applications

Press **F4** from the main menu. The read-only text browser lists eligible
applications by **partition GUID and full file path**, sorted independently of
firmware handle order. Long paths are abbreviated in the list; Enter displays
the complete path and GUID, and only **Y** starts that target. Escape returns to
the main menu; **R** rescans. F4 cancels any configured timeout, and leaving the
browser never rearms it. **A**, then Y, hands the selected target to a new editor
draft. Import does not write, change the default or adjust the timeout. The draft
requires a valid existing configuration and no unfinished save; choose **S**, then
Y to persist it. Generated IDs/names can be reviewed before saving. Duplicate
imports are rejected. Files unsupported by the TOML path schema cannot be imported.
No target becomes a default unless you explicitly select it with D in the editor.

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
| U | Edit partition GUID; clear the field to select the own volume |
| K | Switch EFI / Linux EFI-stub type; clearing Linux fields requires confirmation |
| C / J | Edit Linux command line / initrd path |
| F6 | Inspect complete entry details, including long command lines (also in read-only mode) |
| I | Browse EFI targets and import one into the current draft |
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
python3 scripts/cross-volume-qemu.py --case save
python3 scripts/cross-volume-qemu.py --case missing
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

## License

EutherBoot is licensed under [GNU GPL version 3](LICENSE), SPDX `GPL-3.0-only`.
Copyright (C) 2026 EutherBoot contributors. Dependencies retain their own licenses.
