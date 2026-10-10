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
path. Only EFI entries are implemented. IDs are unique; case-insensitive EFI paths
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
This is EFI chainloading, not arbitrary Linux-kernel loading. No command lines,
initrds or ExitBootServices handoff are implemented.

Returning applications are unloaded by firmware. The loader checks whether the
child still exposes LoadedImage before attempting explicit unload, avoiding an
unconditional double unload. A still-loaded image refused before entry gets a
cleanup attempt. Device, path, load, start/exit and cleanup errors are distinguished.
After a returning attempt the menu is redrawn with its selection and text mode.
No automatic fallback to a different target or retry is permitted.

Dependency limitations found in uefi-rs 0.40.0 source: start_image does not expose
or free nonempty ExitData; load_image does not return an optional loaded handle on
SECURITY_VIOLATION. The test child returns without ExitData and tests use ordinary
non-Secure-Boot OVMF. These paths require a maintained crate fix/update or a narrowly
justified wrapper before general third-party/authentication-rejection support.
Handle-release checks are not complete heap-leak audits. A child that hangs or
exits boot services cannot be recovered by this menu.

## Subsequent modules

- Broader image compatibility: Linux EFI-stub/UKI tests, command-line/initrd
  handling and maintained-crate fixes for image lifecycle limitations.
- Preferences: optional vendor-GUID variables with bounded versioned data, written
  only by an explicit user action. Unsupported persistence remains nonfatal.
- Linux/UKI: separate command-line, initrd, memory-map and handoff logic, tested
  independently from ordinary EFI chainloading. Secure Boot trust/signing and
  rejection behavior are compatibility gates, not current claims.

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
The project's own distribution license remains an owner decision.

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
in memory. Default, timeout and appearance are editable, as are entry names/paths.
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
than merely relying on a read-only QEMU drive setting. Secure Boot, real operating
systems and hardware remain separate gates.


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
