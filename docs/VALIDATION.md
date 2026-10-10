# Validation · 2026-10-10 · Multi-ESP discovery

Host: Rust 1.99.0, QEMU 11.1.2 TCG/q35, ordinary OVMF, x86_64 UEFI target.
This is virtual-development evidence, not physical hardware or OS boot evidence.

## Shared parser and builds

Nineteen Rust tests cover menu wrap/empty state, the example and safe defaults,
non-first defaults, positive timeouts, malformed TOML, unknown/duplicate fields,
bad types/ranges/themes, duplicate IDs and case-insensitive paths, unsupported
entry types, traversal/aliases, display controls/Unicode and resource bounds.
The host CLI validates the same example with the same no_std parser as firmware.
Draft tests cover isolation, serialization and validation. Transaction tests inject
failed mutations and corrupt readback, reject stale drafts, and preserve a valid
backup during interrupted recovery. Discovery tests reject unsafe names, truncated
headers, drivers and wrong architectures. Both real PE32+ EFI executables build with
Cargo.lock, including the parser. The normal firmware also passes a build check
without debug features.

## OVMF matrix

`./scripts/test.sh` builds/tests and runs **36 independent QEMU cases**. Each has
its own disposable FAT filesystem and firmware-variable copy, with no attached
host disks or networking. Editor tests use a real virtual GPT/FAT disk image. At most three VMs run concurrently. Test steps have
deadlines; an outer timeout interrupts the runner/VM process group.

| Cases | Count | Verified outcome |
| --- | --- | --- |
| Sample, successful child at 1024×768 and 640×480 | 2 | TOML-loaded EFI target starts and returns; menu restored |
| Child ABORTED, missing child, invalid child | 3 | Error retained on menu, no unintended target or retry |
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
| Multi-ESP discovery at both resolutions | 2 | Same path on two ESPs launches from the selected volume, proven by child-reported GUID; data partition and self-copies excluded |
| Duplicate GPT GUIDs | 1 | All ambiguous ESPs excluded; no targets promoted |
| Empty discovery | 1 | Only self/non-application files present; empty menu remains usable |
| Discovery candidate limit | 1 | 64-target cap is visible as partial; pagination reaches last entry |
| Classified but unloadable image | 1 | Firmware LoadImage rejects malformed section extent; browser retained and another target can start |
| Discovery after malformed TOML | 1 | Configured targets/timer remain disabled; separately confirmed discovered target boots |

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

The full 36-case suite is exercised by `./scripts/test.sh`; its combined run log
is `artifacts/discovery-regression.log`. Discovery uses two ESPs and one non-ESP
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

## Limits

No real OS, physical machine, Secure Boot rejection, nonempty child ExitData,
initrd/kernel command line, multiple physical disks or hot-plug behavior has been
demonstrated. Multiple ESPs on a virtual GPT disk are covered.
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
binary are excluded; different builds/signed copies are not. Persisting discovered
cross-volume choices in TOML is not implemented.
See ARCHITECTURE.md for loader cleanup and self-copy limitations.

Artifact SHA-256 for this build:

```text
02135ee849366b9fe572a5c873e85f9337786e5b4272dab5cef0afa9843cc119  artifacts/EutherBoot.efi
788bc2acd5f2bf3e228885be1f91a29e84df53b5843546d7987c72918989c1f8  artifacts/TestChild.efi
```
