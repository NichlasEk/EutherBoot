# Validation · 2026-10-10 · Linux EFI-stub and UKI

Host: Rust 1.99.0, QEMU 11.1.2 TCG/q35, ordinary OVMF, x86_64 UEFI target.
This is virtual-development evidence: Linux reaches a generated diagnostic PID 1.
It is not evidence of an installed distribution or physical hardware boot.

## Shared parser and builds

Twenty-four Rust tests cover menu wrap/empty state, the example and safe defaults,
non-first defaults, positive timeouts, malformed TOML, unknown/duplicate fields,
bad types/ranges/themes, duplicate IDs and case-insensitive paths, unsupported
entry types, traversal/aliases, display controls/Unicode and resource bounds.
The host CLI validates the same example with the same no_std parser as firmware.
Draft tests cover isolation, serialization and validation. Transaction tests inject
failed mutations and corrupt readback, reject stale drafts, and preserve a valid
backup during interrupted recovery. Discovery tests reject unsafe names, truncated
headers, drivers and wrong architectures. Selector tests cover canonical GUID
syntax, zero/malformed/wrong-type rejection, case normalization and duplicate
paths scoped to a selector. Draft import preserves default/timeout and roundtrips
the selector, including clearing it back to omission. Linux tests cover typed fields, strict option bounds/conflicts, managed initrd
composition and draft roundtrips. Both real PE32+ EFI executables build with
Cargo.lock, including the parser. The normal firmware also passes a build check
without debug features.

## OVMF matrix

`./scripts/test.sh` builds/tests and runs **48 independent QEMU cases**. Each has
its own disposable FAT filesystem and firmware-variable copy, with no attached
host disks or networking. Editor tests use a real virtual GPT/FAT disk image. At most three VMs run concurrently. Test steps have
deadlines; an outer timeout interrupts the runner/VM process group.

| Cases | Count | Verified outcome |
| --- | --- | --- |
| Sample, successful child at 1024×768 and 640×480 | 2 | TOML-loaded EFI target starts and returns; menu restored |
| Child ABORTED, missing child, invalid child | 3 | Error retained on menu, no unintended target or retry |
| Nonempty child ExitData | 1 | Three explicit ABORTED returns free 28-byte ExitData and retain menu, including text mode |
| Non-first configured default | 1 | Selection 1 loads a relocated child by its configured path |
| 3s timeout | 1 | Default starts once after the delay; return never rearms it |
| Any-key cancellation | 1 | Unhandled `x` cancels timeout; later explicit Enter works |
| Timeout into missing default | 1 | NOT_FOUND once; no automatic fallback/retry |
| Sixteen configured entries at both resolutions | 2 | Page navigation reaches entry 16, starts correct child and reaches built-ins |
| Missing configuration | 1 | Read error, no configured entries or timer |
| Malformed TOML, unknown field, duplicate ID, unresolved default, traversal | 5 | Entire config rejected; diagnostics and firmware return work |
| Invalid UTF-8, oversize input, direct self-reference | 3 | Entire config rejected before any child starts |
| Sample on virtual GPT/FAT disk | 1 | Same-volume chainloading from the disposable block device |
| Editor discard | 1 | Inspection, preview, cancelled save and discarded draft leave exact original bytes |
| Editor save at both resolutions | 2 | Add/remove entries, default, timeout and theme persist across reboot; added target starts; backup restores original |
| Invalid editor draft | 1 | Self-reference and missing default rejected; explicit default repair validates |
| Read-only disk | 1 | Save reports WRITE_PROTECTED; original unchanged |
| Interrupted save at three checkpoints | 3 | Kill after staging, backup or install; next boot blocks automatic selection; explicit recovery succeeds |
| Linux EFI-stub and UKI at both resolutions | 2 | Same path on two ESPs launches from the selected volume, proven by child-reported GUID; data partition and self-copies excluded |
| Duplicate GPT GUIDs | 1 | All ambiguous ESPs excluded; no targets promoted |
| Empty discovery | 1 | Only self/non-application files present; empty menu remains usable |
| Discovery candidate limit | 1 | 64-target cap is visible as partial; pagination reaches last entry |
| Classified but unloadable image | 1 | Firmware LoadImage rejects malformed section extent; browser retained and another target can start |
| Discovery after malformed TOML | 1 | Configured targets/timer remain disabled; separately confirmed discovered target boots |
| Persisted import at both resolutions | 2 | F4/A import, explicit save, exact backup, manual remote boot and timed reboot with reversed ESP positions |
| Editor picker / discard | 1 | F3/E/I import, duplicate rejection, GUID editing/clearing, preview, cancelled save and discard leave entire disk unchanged |
| Missing GUID, duplicate GUID, non-ESP selector | 3 | Default preflight disables timer; manual attempt fails without fallback; explicit own-volume entry remains usable |
| Implicit/explicit own-volume alias, qualified self-path | 2 | Entire config rejected; no target or timer enabled |
| Exact remote self-copy, missing remote file | 2 | Single automatic attempt fails before LoadImage; no fallback/retry; own entry can still be selected manually |
| Own boot path on another ESP | 1 | Same pathname as EutherBoot itself but a different GUID correctly starts the remote child |

The original five chainload cases each perform three explicit attempts in one
VM, including text mode. Positive configuration cases move the child away from
the original fixed path; the selected target log and actual child execution
prove the config path is used. The first non-default entry points to a missing
file, making accidental selection observable. Timeout tests check a 3-second
interval with host-observation tolerance and wait past the deadline again after
return/failure to reject unintended rearming. Invalid configs request a 1-second
timeout where syntactically possible; tests wait beyond it and require no load.

Screenshots confirm the configured default highlight, error diagnostics and the
last page at 640×480. Pixel comparisons verify the graphical menu is reconstructed
after the child clears the display. Text tests check new console output and
subsequent keyboard navigation, not just log markers. Returning child handles
no longer expose LoadedImage; this is not a complete memory-leak audit.

Reproduce individual cases through `scripts/qemu.py --help`. Evidence is ignored
under `artifacts/qemu-<width>x<height>-<scenario>-<config-case>/`: debug.log,
serial.log, qemu.log and PPM captures. `.efi` artifacts and SHA256SUMS are rebuilt
by scripts/build.sh. Editor evidence is under `artifacts/editor-<case>-<width>x<height>/`,
including logs, screenshots, configuration readback and SHA-256 results.

Editor saves require explicit Y confirmation. Tests verify exact backup bytes,
persistent values after reboot, and removal of transaction markers after recovery.
Reload after saving/recovery does not rearm the timer. Fault injection uses a
separate `EutherBoot-faults.efi`; the normal binary has no FAULT_WAIT hook. The
runner kills QEMU at flushed checkpoints, then boots the normal binary from the
same image. These are controlled interruption tests, not proof against torn
sectors or all physical power-loss behavior. No host boot configuration or
firmware variables were modified by EutherBoot.

The full 48-case suite is exercised by `./scripts/test.sh`; its combined run log
is `artifacts/efi-regression.log`. Discovery uses two ESPs and one non-ESP
FAT partition on one generated GPT disk. Fixtures include identical paths,
a renamed EutherBoot binary on the second ESP, invalid PE data, an AArch64 image,
and an EFI driver. Only eligible targets appear. Enter/cancel does not load an
image; Y starts the selected one. Child-reported LoadedImage GUIDs independently
confirm volume choice. Success and ABORTED return to the browser; R reconstructs
the same sorted target list. Entering discovery cancels the configured timer;
waiting past its deadline in the browser and after exit never triggers boot.

Discovery evidence lives under `artifacts/discovery-<case>-<width>x<height>/`:
debug/serial/QEMU logs, PPM screenshots and a result file with the identical
before/after SHA-256 of the entire writable virtual disk. No disk differences
were observed in these tests. The 640×480 browser and confirmation were visually
inspected for readable identity, path and keyboard controls.

Persisted-selector evidence lives under
`artifacts/cross-volume-<case>-<width>x<height>/`. Save cases export actual saved
TOML and exact backup bytes. After saving, the generated disk is rebuilt with
the exact saved configuration and reversed ESP partition positions; fresh OVMF
variables are used. The next boot resolves the GUID at its new device path and
automatically starts the correct child once. This proves resolution survives
changed virtual partition positions, not physical hot-plug behavior.

All cross-volume cases hash the other two complete FAT partitions before and
after the session. No differences are allowed, including when configuration is
saved on the own ESP. Cases that do not save additionally compare the whole
writable disk hash. Save verification includes default/timeout, omitted own-volume
selector, explicit remote GUID/path, exact old backup and absence of sidecars.
The reordered disk is also unchanged after booting/returning. Child-reported
GUIDs distinguish remote success from accidental own-volume fallback. Imported
drafts were visually inspected at 1024×768 and 640×480: full GUID, path, unchanged
boot policy and editing/saving controls remain readable.

## Linux matrix

`./scripts/test-linux.sh --kernel /usr/lib/modules/7.2.9-arch1-1/vmlinuz`
builds local fixtures and runs **9 additional QEMU cases**, at most two concurrently.
Tested kernel: Linux 7.2.9-arch1-1, CONFIG_EFI_STUB=y; installed systemd stub 262-1.
Each VM uses 768 MiB, TCG CPU max, a disposable two-ESP GPT disk and copied OVMF
variables. No host initramfs/root filesystem or physical disk is attached.

| Cases | Count | Verified outcome |
| --- | --- | --- |
| EFI-stub on own and selected remote ESP | 2 | Real kernel receives managed initrd path and command line, reaches diagnostic PID 1 and powers off |
| UKI on own and selected remote ESP, read-only disk | 2 | Embedded kernel, command line and initrd reach diagnostic PID 1 without external options |
| UKI on writable disk | 1 | PID 1 reached; systemd stub creates two 32-byte seed files; existing EFI files and other partition retain exact hashes |
| Missing initrd, non-Linux EFI application as linux-efi | 2 | Rejected before LoadImage; menu retained; explicitly selected recovery child starts and returns |
| Linux editor at 1024×768 and 640×480 | 2 | Full details shown, type change can be cancelled or confirmed, command line and initrd edited and saved with exact backup, real Linux boots before and after reboot with persisted options |

The oracle is independent guest PID 1 output on the serial console: uname,
/proc/cmdline, the expected mode and owner-controlled diagnostic argument, then
poweroff. A LoadImage marker alone does not count as a Linux boot. Remote tests
put invalid payloads at identical paths on the own ESP and require the selected
remote kernel/UKI to reach PID 1 after timeout. Ordinary EFI/UKI entries have no
LoadOptions set by EutherBoot.

EFI-stub and negative cases compare the whole writable disk hash. Editor saves
verify exact TOML, original backup and an unchanged disk on the second boot.
Read-only UKI disks also retain their whole-disk hashes. The writable UKI exception
is explicit: systemd-stub creates `loader/random-seed` and
`loader/boot-secret-mixin`, each 32 bytes. The test retains file names/sizes only,
compares every EFI file hash and verifies bytes after the own ESP are unchanged.
It does not claim the child performs no firmware-variable writes; all variables
are disposable VM copies.

Fixtures, provenance and hashes: `artifacts/linux/manifest.json`.
Combined log: `artifacts/linux-regression.log`; extended editor reruns:
`artifacts/linux-editor-regression.log` and `artifacts/linux-editor-640-regression.log`.
Per-case serial/debug logs,
screenshots and results: `artifacts/linux-<case>-<width>x<height>/`.
The initramfs contains only a generated static /init, console node and directories.
The unsigned UKI embeds that archive and the copied local kernel; no host signing
keys or distribution initramfs content is consumed.

## Limits

No installed distribution, physical machine, Secure Boot acceptance/rejection,
multiple physical disks or hot-plug behavior has been demonstrated. Linux tests
use one kernel version, one systemd stub and a diagnostic initramfs. A LoadFile2
initrd provider, multiple initrds and arbitrary non-EFI kernel loading are absent. Multiple ESPs on a virtual GPT disk are covered.
Editor preferences persist in TOML; NVRAM preferences are not implemented.
The editor cannot create the first configuration or repair raw malformed TOML;
a valid backup can be restored explicitly. FAT rename is not power-loss atomic. Input is polled; the timeout itself uses a
firmware timer. Timer creation/check failures and allocation exhaustion are
handled but not fault-injected. Automatic GOP failure fallback is not injected;
manual text fallback is tested. Only printable ASCII labels/paths are supported.
Directory-backed FAT, single-ESP GPT and multiple-ESP GPT are exercised. MBR,
superfloppy and firmware lacking PartitionInfo remain unsupported for discovery.
The target-count limit is exercised; exhaustive directory/depth/read-budget and
I/O fault injection is still outstanding. Exact copies of the current on-disk
binary are excluded for discovery/GUID-qualified launches; different builds/signed
copies are not. Legacy unqualified entries retain the path-only self check.
A valid but absent selector may be saved; validation is not availability or trust
verification. Import with an invalid live config or pending transaction is blocked;
these import-specific refusal branches have not been separately fault-injected.
See ARCHITECTURE.md for loader cleanup and self-copy limitations.

Artifact SHA-256 for this build:

```text
358d8c2b650f7b4825d9d18ff4d935af4e5c5b1a51342477e105c5f494052c4b  artifacts/EutherBoot.efi
89f068ad22f0e8a303975866f6f95974552e140a34f6a7f94e7b82973cc310f4  artifacts/TestChild.efi
```
