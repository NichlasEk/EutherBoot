# Architecture

## Implemented boundaries

`boot-core` is no_std + alloc and contains the firmware-independent menu state
and TOML schema/parser, unvalidated Draft model, transaction engine and bounded
EFI-header/name classification. `config-check` is a small host CLI using the exact same
parser. There is no parallel Python schema to drift from firmware behavior.
`toml` 1.1.8 and Serde are compiled without std; only parsing/deserialization and
allocation features are enabled. The draft serializer emits a narrow, escaped
canonical TOML format; validation parses it again before persistence. Cargo.lock records exact dependency versions.
The TOML parser's unbounded-depth feature is deliberately not enabled.

`uefi-app` owns firmware initialization, read-only config loading, input/timer
policy, rendering and EFI image lifecycle. It uses maintained uefi-rs protocol
wrappers. The no_std parser is exercised both by host tests and the real EFI build.
`test-child` is an independent EFI executable, not a linked mock of the loader.

## Configuration and target identity

Read exactly `\EFI\EutherBoot\eutherboot.toml` using the application's own
LoadedImage filesystem. Open read-only, read at most 16385 bytes with partial-read
handling, reject more than 16384, require UTF-8, then parse and validate the entire
document. All file/protocol handles are dropped before child execution.

The typed Config and Entry have private fields and are only constructed by the
shared parser. Boot settings deny unknown fields; default is mandatory, timeout
is optional/zero, theme optional/system-regis (text is also supported). Entries require id, name, type and
path. EFI and explicit Linux EFI-stub entries are implemented. IDs are unique; case-insensitive EFI paths
are unique within a partition selector. The optional nonzero partition_guid is
normalized to lowercase; omission means the current volume. No arbitrary default
or partially accepted list is produced.
See README for input, display and path bounds. Error messages include TOML line
numbers where available, omit control characters and cap parser text length.

Firmware additionally compares every target to the loaded application's own
path and volume, rejecting direct self-reference. It also rejects implicit-own and
explicit-own-GUID duplicate targets. GUID-qualified launches and discovery exclude
exact binary copies through the shared `images` module. Legacy unqualified entries
retain their path-only check; different builds or modified binaries can still
recurse. Host validation cannot
verify this runtime identity or prove that any configured file exists.

A configuration error disables all configured entries and automatic boot. The
built-in read-only inspection and return-to-firmware actions remain available.
F4 explicitly enters discovery independently of configuration validity; discovered
entries never participate in the configured timeout. Configuration file writes
are exclusively behind the editor's explicit Save/Recovery confirmation; no
firmware-variable preferences are written.

## Menu, graphics and timing

The menu consists of validated EFI entries plus built-in inspection and return
actions. Navigation never activates an entry. The configured ID resolves to a
stable index. Both graphical and text menus page so every allowed entry remains
accessible; 16 entries plus the two built-ins are tested at 640×480.

Graphics use a bounded, fallibly allocated software buffer and GOP BLT, avoiding
pixel-format/stride assumptions. The current firmware mode is preserved; supported
dimensions are 640×480 through 3840×2160. Failed GOP/BLT/allocation or unsupported
dimensions fall back to firmware text output. F2 selects text explicitly, and `theme = "text"` requests it persistently. The
geometric emblem is original code, and font8x8 supplies bitmap glyphs.
GOP uses a short GET_PROTOCOL borrow, not Exclusive (which can disconnect the
firmware graphics-console driver). No console calls, driver removal or exit from
boot services happen while that unsafe borrow is alive.

Input currently polls at 10 ms; a positive timeout uses a firmware one-shot timer,
not a count of polling iterations. It is armed after the first frame. Input is
checked before expiry, so a queued key wins when both are ready. Any key closes
the timer. Expiry closes it before starting the default, and it is never rearmed.
Timer creation/check failures disable automatic boot. A saved or recovered configuration is reloaded without rearming automatic boot
in that session. The initial timeout is shown, but no live numeric countdown exists. Console failures remain
best-effort; simultaneous loss of both GOP and text output is unresolved.

## EFI image lifecycle

`loader` builds a full device path from an explicit volume handle and file path
(the application's own device for entries without partition_guid), in a bounded 4096-byte buffer. It calls LoadImage/ExactMatch
and StartImage with no borrowed protocols or graphics buffers held across transfer.
Ordinary EFI applications receive no external options. Explicit linux-efi entries
use the preparation described below; this is not arbitrary Linux-kernel loading.

Returning applications are unloaded by firmware. The loader checks whether the
child still exposes LoadedImage before attempting explicit unload, avoiding an
unconditional double unload. A still-loaded image refused before entry gets a
cleanup attempt. Device, path, load, start/exit and cleanup errors are distinguished.
After a returning attempt the menu is redrawn with its selection and text mode.
No automatic fallback to a different target or retry is permitted.

uefi-rs 0.40.0 start_image does not expose/free nonempty ExitData, and load_image
does not expose the optional loaded handle on SECURITY_VIOLATION. The narrow
image_services adapters use the existing uefi-raw ABI types to free ExitData and
unload a rejected image when firmware returns a handle. Three consecutive
nonempty-ExitData returns are exercised, including text mode. Secure Boot
rejection is exercised under OVMF: ACCESS_DENIED returns no loaded handle. The optional-handle SECURITY_VIOLATION cleanup branch remains untested.
Handle-release checks are not complete heap-leak audits. A child that hangs or
exits boot services cannot be recovered by this menu.

## Linux EFI-stub boundary

`boot-core::linux` validates printable ASCII command lines and the explicit
initrd path without adding a path to LoadOptions. `uefi-app::linux` checks PE32+
x86_64 application plus Linux HdrS, boot signature and protocol >= 2.11, and the
kernel's command-line capacity. If an initrd is configured, it separately checks
the PE ImageVersion capability: EFI-stub v1/v2, or bit 0 in v3+ per Linux pe.h.
This is independent of the x86 HdrS boot-protocol version. A pre-existing provider
on the Linux initrd device path blocks linux-efi preparation, including no-initrd
entries; EutherBoot never replaces or silently consumes someone else's provider.

The selected volume is opened read-only. The nonempty regular initrd file is
bounded to 128 MiB, allocated fallibly, and read fully in chunks, detecting early
EOF and growth. All file/protocol handles close before LoadImage. This snapshot
removes callback-time disk I/O; it is not cryptographic validation or protection
against replacement while reading. The kernel receives a separate copy, so the
snapshot adds to peak boot memory. UKIs remain ordinary EFI entries with embedded
resources and no EutherBoot initrd provider or LoadOptions overrides.

`initrd` uses uefi-rs installation/removal wrappers and the uefi-raw LoadFile2 ABI.
A stable owned context contains the callback, immutable bytes and a builder-created
vendor-media device path using LINUX_EFI_INITRD_MEDIA_GUID. DevicePath is installed
first and LoadFile2 last, after image authentication and before StartImage. The
callback accepts only the remaining EndEntire node and BootPolicy=false. It checks
null parameters, reports required size, preserves short buffers and copies only
the payload into a sufficiently large caller-owned buffer. It allocates nothing
and performs no firmware/file I/O. EFI callers must supply valid readable/writable
memory: a protocol is not a sandbox for malicious firmware or applications.

Context ownership is raw only while published, so no Rust mutable Context borrow
spans protocol notifications or child callbacks. A Drop guard removes LoadFile2
first, then DevicePath, before freeing data. Partial installation rolls back through
the same guard. Child release/unload precedes provider removal. If firmware refuses
removal, the guard retains memory and callback code and blocks returning to the
menu/firmware: R retries cleanup. A data leak alone would not keep EutherBoot's
code mapped after returning, so that unsafe fallback is deliberately forbidden.
Successful ExitBootServices never returns through these destructors; Linux owns
its destination copy and subsequent memory reclamation. No handoff/bootparams
structure or manual kernel relocation is implemented here.

The loader retains a stable CString16 until the child is released/unloaded. If
image cleanup fails or its lifetime cannot be established, the options allocation
is retained rather than freeing a pointer a live image might still use. Provider
cleanup still runs and cannot be bypassed by that error. No automatic retry of
StartImage or fallback to `initrd=` occurs.

A generated static PID 1 independently reports Linux uname and /proc/cmdline,
checks diagnostic arguments, then powers off. Tests use a fresh minimal initramfs,
not the host distribution's initramfs or root filesystem. The observed systemd
stub writes random-seed and boot-secret-mixin files when its virtual ESP is
writable. Child side effects are outside EutherBoot's configuration transaction;
there is no sandbox for EFI children. Writable-UKI tests account for those writes,
and read-only-UKI tests demonstrate Linux can reach PID 1 without them.

References: [Linux EFI stub](https://docs.kernel.org/admin-guide/efi-stub.html),
[x86 PE/COFF entry point](https://docs.kernel.org/arch/x86/boot.html#pe-coff-entry-point),
[UKI format](https://uapi-group.org/specifications/specs/unified_kernel_image/),
[systemd random seed](https://github.com/systemd/systemd/blob/main/src/boot/random-seed.c)
and [boot secret](https://github.com/systemd/systemd/blob/main/src/boot/boot-secret.c).
The stub capability convention is defined in [Linux pe.h](https://github.com/torvalds/linux/blob/master/include/linux/pe.h).
No source from those implementations was copied.

## Subsequent modules

- Broader image compatibility: more kernels/stubs and initrd memory limits,
  broader Secure Boot policies and cleanup fault injection.
- Preferences: optional vendor-GUID variables with bounded versioned data, written
  only by an explicit user action. Unsupported persistence remains nonfatal.
- Secure Boot: virtual owner-key acceptance/rejection is demonstrated; shim/MOK,
  production trust, hardware and optional rejected-handle cleanup remain gates.

## Virtual Secure Boot boundary

The harness uses existing sbsigntools for Authenticode and virt-firmware to enroll
fresh test certificates into copied OVMF vars, with a Secure Boot-capable firmware
image, q35 SMM and secure pflash. It never calls host efivarfs or enrolls host keys.
A temporary directory contains all private keys and signed binaries. Their public
fingerprints, input/payload hashes and test outcomes are the retained provenance.

EutherBoot delegates image authentication to firmware LoadImage. It does not
implement its own signature verifier, override rejections, or enroll trust during
boot. The independent EFI child reads SecureBoot and SetupMode, so a successful
signature-tool check or a Secure Boot-capable firmware filename alone cannot
satisfy the integration oracle. Unsigned, unknown-signer, authenticated-byte
mutation and dbx-revoked-certificate cases fail before StartImage. The signed child
still executes after refusals, including text mode and nonempty ExitData returns.
The revoked certificate is deliberately also enrolled in db to exercise dbx
precedence. OVMF's observed refusal is ACCESS_DENIED with no image handle, a valid
[LoadImage policy result](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html#efi-boot-services-loadimage).

An optional signed UKI proves one Linux kernel/stub can reach diagnostic PID 1
under this owner-key policy. The UKI disk is read-only to separate execution from
systemd-stub seed writes. This is not a claim that unsigned TOML or separate
initrd/command-line inputs become authenticated by signing the boot manager.
External EFI-stub resources, shim/MOK/SBAT, measured boot/TPM, production key
rotation, revocation updates and physical firmware remain outside these tests.
Test keys are not distribution credentials. Tool references:
[sbsigntools](https://git.kernel.org/pub/scm/linux/kernel/git/jejb/sbsigntools.git/)
and [virt-firmware](https://gitlab.com/kraxel/virt-firmware).

## Architectural references and licenses

No bootloader source code was copied.

- [uefi-rs 0.40](https://docs.rs/uefi/0.40.0/uefi/) (MIT/Apache-2.0): established
  firmware interfaces rather than locally recreated ABIs.
- [toml-rs](https://docs.rs/toml/1.1.8+spec-1.1.0/toml/) and
  [Serde no_std](https://serde.rs/no-std.html): shared parsing without a host OS.
- [systemd-boot](https://systemd.io/BOOT/): explicit entry and EFI execution
  boundaries. Consult per-file SPDX in [systemd licenses](https://github.com/systemd/systemd/blob/main/LICENSES/README.md)
  before code reuse; do not assume one license covers the entire repository.
- [rEFInd features](https://www.rodsbooks.com/refind/features.html): read-only
  discovery/exclusion ideas; GPLv3 code needs a deliberate compatible licensing
  decision before reuse.
- [Limine configuration](https://github.com/Limine-Bootloader/Limine/blob/v10.x/CONFIG.md):
  explicit search precedence motivates making configuration origin unambiguous.
  Its [BSD-2-Clause license](https://github.com/Limine-Bootloader/Limine/blob/v10.x/COPYING)
  requires preserving notices if code is reused.

font8x8 0.3.1 declares MIT. Retain dependency notices for future binary distribution.
The project is GPL-3.0-only, selected by the owner. Preserve dependency licenses
and provide corresponding source with distributed binaries.

## Hardware safety

No installer exists. After broader compatibility/recovery testing, separately
approve a copy to `EFI/EutherBoot/EutherBoot.efi` on a dedicated test machine,
preserving the existing loader and BootOrder. Start with a firmware one-time file
picker. Never overwrite physical `EFI/BOOT`, format, remove existing entries or
change Secure Boot keys. Record original paths and hashes before approval.
Rollback selects the unchanged known-good path and removes only approved files;
any optional firmware entry must be individually recorded and removed on request.

## Implemented editor and persistence

F3 opens inspection without acquiring writable file handles. E creates a Draft
independent of the active Config; field input is bounded ASCII and mutations stay
in memory. Default, timeout and appearance are editable, as are entry names/paths, kind,
Linux command line and initrd. F6 provides paginated full-field inspection.
Switching back to ordinary EFI requires confirmation before clearing Linux fields.
Entries can be added and removed. A removed default remains unresolved until D
explicitly picks a replacement. The current implementation requires an existing
valid live config to enter edit mode; it is not a raw TOML repair editor.

V and F5 validate before showing a draft or preview. Preview starts no timer or
EFI image. S validates, checks the loaded-image self-reference and then requires
Y at a separate disk-write confirmation. All other confirmation keys cancel.
The exact source bytes inspected at entry are retained; a save compares them with
the current file before mutation and again before rotation, rejecting stale drafts.

`boot-core::transaction::Store` isolates the save algorithm from UEFI I/O. It
writes only these names in the application's `EFI/EutherBoot` directory:

1. Create `eutherboot.toml.new`, flush, close and verify exact bytes.
2. Create and verify `eutherboot.toml.txn` to mark an incomplete transaction.
3. Verify the original again, remove the older backup, rename the live file to
   `eutherboot.toml.bak` and verify the exact original bytes.
4. Rename the staged file to `eutherboot.toml`, flush and verify new bytes.
5. Remove the transaction marker only after that final verification.

There is always a valid original at the live or backup path at the tested logical
operation boundaries. This statement is not a guarantee about torn writes, FAT
corruption, lying caches or physical power interruption. `.new` or `.txn` at startup
blocks configured targets and the boot timer. No startup repair writes occur.

Read-only recovery B validates and explicitly restores `.bak` via a new staged
copy while retaining the backup. C validates the current file and explicitly
removes pending data. Both require Y. Recovery also reloads without a timer.
If no valid live/backup candidate exists, manual external repair is needed.
Renamed copies of EutherBoot and malicious EFI children remain outside this model.

The UEFI adapter only permits fixed configuration-sidecar filenames, checks file
types, and refuses to overwrite a staging or rename destination. Reads are bounded
at 16 KiB. File flushes accompany writes/renames; directory flushes use a writable
handle acquired only during an explicit write action. Initial read-only directory
handles cannot be flushed on OVMF (ACCESS_DENIED), which was caught by the real-disk
save test. The adapter uses FileInfo/SetInfo wrappers from uefi-rs, not a custom
filesystem. Relevant protocol semantics are documented by the
[UEFI file services specification](https://uefi.org/specs/UEFI/2.11/13_Protocols_Media_Access.html).

The UEFI target has no C runtime. LLVM lowers some uefi-rs UCS-2 scans used by
FileInfo to `wcslen`, so `compiler_support` supplies the 16-bit Windows/UEFI ABI
helper. Volatile reads prevent it being optimized back into itself. End-to-end
rename tests exercise it; this is compiler compatibility, not a new firmware ABI.

`test-faults` adds a deliberately blocking checkpoint after staging, backup
rotation or candidate installation. Only the separate fault EFI artifact reads
the test-only `editor-fault` file; the normal artifact has no FAULT_WAIT hook.
Tests kill QEMU at those flushed boundaries, then boot the normal artifact on the
same GPT/FAT disk and verify explicit recovery. This simulates process loss, not
arbitrary physical sector tearing. Host tests also inject each failed mutation,
a corrupt staging readback and a stale source to verify original preservation.


## Implemented read-only discovery

F4 invokes a separate text browser, cancelling the menu timer through the existing
any-key rule. Discovery starts only on request or R rescan. Enumerate firmware
SimpleFileSystem handles; consult PartitionInfo for GPT ESP type, nonzero unique
partition GUID, and absence of the legacy-BIOS attribute. Do not infer ESP status
from FAT alone, partition position, a filename, or the current boot source.
Duplicate GUIDs exclude every matching handle, even if their paths differ.
Volumes sort by full GUID; candidates sort by volume then case-insensitive path.
Each candidate retains its specific volume index/handle and exact path. The same
path on two different ESPs remains two distinct choices.

Short synchronous GET_PROTOCOL borrows avoid disconnecting filesystem drivers.
All filesystem opens use FileMode::Read. No firmware variables are read or written
by this feature, and no ConnectController, partition writes, driver loading or
filesystem repair is attempted. FAT/partition enumeration is delegated to firmware.
A full device-path snapshot accompanies each GUID. At explicit Y launch, reread
the selected handle's identity/path, reclassify the file and exclude exact self
copies again; then drop every protocol/file borrow before calling the shared
LoadImage/StartImage implementation. A device cannot be silently substituted by a
first-match GUID search. Concurrent/hot-plug mutation and cryptographic identity
are not solved by these checks; this is ordinary firmware file loading.

Header classification checks DOS/PE signature, bounded e_lfanew, x86_64 machine,
PE32+ optional header, plausible section count/table extent and application
subsystem (10). The header must fit the 4096-byte prefix; e_lfanew is at most 3072,
files at most 128 MiB. This is intentionally not a PE loader, UKI detector or full
validator. LoadImage remains authoritative and can reject a classified candidate.
Do not interpret recognition as trust, OS compatibility or successful boot.

The current on-disk own image (at most 4 MiB) is read once. Same-size candidates
are compared byte-for-byte in bounded chunks, preventing exact renamed-copy
recursion without a new hashing dependency. Different builds/signatures or a
changed own file remain limitations. The scanner fails closed when that reference
cannot be read. Directory records use an aligned fixed 1024-byte buffer. Paths
are bounded printable ASCII without traversal/control characters; unsupported
names are skipped. Depth, record, target and 64 MiB read budgets limit scanning;
partial results are clearly labelled. Firmware calls themselves have no watchdog.
See README for all caps. Candidate promotion goes through an explicit unsaved
editor draft; the scanner itself never persists a selection.

Discovery tests use two ESPs and one non-ESP FAT partition on a temporary GPT disk.
The independent child reports its actual LoadedImage device's partition GUID,
proving which volume supplied identical paths. Read/write-enabled virtual disks
are hashed in full before/after the session to check absence of writes, rather
than merely relying on a read-only QEMU drive setting. Broader Secure Boot policies,
broader installed distributions and hardware remain separate gates.


## Persisted cross-volume targets

Entry.partition_guid is an optional validated canonical string, not a firmware
handle, partition number or device-path snapshot. Drafts keep its raw text until
validation; blank draft text serializes as omission, while explicitly empty TOML
is rejected. Serialization roundtrips GUIDs and retains omitted selectors.
The core duplicate key is (partition selector, case-insensitive path). Runtime
validation additionally recognizes aliases of the current ESP's own GUID. No
availability check is needed to edit or restore a structurally valid offline entry.

`volumes` centralizes the read-only protocol borrows and GPT ESP eligibility shared
with discovery. `resolve` enumerates at most 32 filesystem handles on each requested
qualified launch, examines all eligible identities, and returns a handle only for
one unique match. Enumeration/identity errors fail closed. There is no preference
for the current volume, disk order or first match. Unsupported non-ESP handles
are skipped. The default selector is preflighted before a positive timer is armed;
resolution failure disables that timer and shows the error in text mode. Other
entries remain selectable. The same resolver runs again at activation, so the
startup check is not a persistent handle cache.

`images` contains the bounded classifier and exact-copy check extracted from
discovery. GUID-qualified configured targets use the same checks before the shared
loader builds a full device path. File errors, rejected classification and firmware
LoadImage/StartImage failure do not select another target or rearm the timer.
This remains ordinary EFI chainloading; header recognition is not OS compatibility,
cryptographic identity or protection against hot-plug/concurrent filesystem changes.

Discovery A (or Enter in the editor's I picker) shows full GUID/path and asks Y
before returning an in-memory Selection. Import copies only the selector/path,
generates a collision-free entry ID and a reviewable name, and preserves default
and timeout. U edits/clears the selector on any draft entry. No discovery or picker
protocol handle survives the return to the editor. Import requires a valid live
config and no pending transaction, respects 16-entry/path bounds, and never writes
or launches. The existing S/Y transaction stores the draft and exact previous
backup on the own volume. Import cancellation/discard leaves all volumes unchanged.

## Installed Arch integration boundary

The optional Arch fixture extends the diagnostic PID 1 tests with an official,
signed, pinned preinstalled distribution. Preparation verifies the detached
signature using a pinned public key in a temporary GPG home, then extracts only
its own kernel/initramfs from sparse regular files using `btrfs restore`.
No privileged mounts, host partitions or host firmware interfaces are used.

EutherBoot runs on a separate read-only GPT ESP. A QCOW2 overlay of Arch's original
disk supplies the writable Btrfs root and its original ESP/GRUB. Root selection
uses the image's GPT PARTUUID. The image's existing loader is not overwritten.
The two boots share only the disposable root overlay; each gets fresh OVMF vars.
An independent serial-login oracle checks PID 1, OS identity, root filesystem,
packages, service state and a durable guest file, rather than trusting an EFI
launch marker. SHA-256 checks also verify that the original image and EutherBoot
ESP did not change. Socket output is continuously drained to avoid blocking QEMU.

The offline guest masks `systemd-time-wait-sync.service` through its kernel
command line because the official image otherwise holds first-boot keyring
initialization and multi-user.target waiting for network time. This is an explicit
fixture adjustment, not a loader default or a modification to the base image.
Arch Secure Boot and an ISO installation remain separate gates. Kernel upgrades
are covered by the additional guest update integration described below.

## Arch guest update integration

The optional `arch-update-qemu.py` runner adds a Linux-side prototype, isolated
under `tests/arch/update/`. It does not change the UEFI loader. The guest installs
a stock-linux mkinitcpio preset extension and post hook, and a pacman
pre-transaction guard. A full guest upgrade produces a UKI on the root filesystem,
then publishes it to one stable EFI path. The boot entry is unchanged on later
rebuilds. This uses mkinitcpio's normal post-hook API, not kernel-install; those
two orchestration paths must not be mixed without revisiting hook semantics.

Publication checks the intended ESP's PARTUUID, exact mount point, FAT type,
write access and minimum free space. A UKI identification check, exclusive lock,
temporary file, byte comparison and filesystem sync precede replacement. A saved
previous image is diagnostic only: its old kernel modules are not retained by
this prototype. FAT rename is not claimed to be power-loss atomic, and a failed
post hook cannot undo a completed pacman package transaction.

The integration oracle verifies a real package-version change and two subsequent
boots whose `uname -r` matches the new installed module directory. Negative cases
exercise missing/read-only/wrong ESPs and malformed UKIs. One explicitly staged
partial-file interruption is followed by QEMU process termination and another
boot. This establishes that the selected boot file survives that interruption;
it does not prove arbitrary interruption safety during filesystem metadata writes.
All disks and firmware variables are disposable files; only the upgrade boot has
QEMU user-mode NAT. No host sharing or forwarded services are configured.
