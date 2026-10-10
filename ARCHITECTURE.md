# Architecture

## Implemented boundary

`boot-core` is a no_std, firmware-independent menu state machine. Navigation
never activates an entry. Its tests run on the host.

`uefi-app` owns firmware initialization, console input and the event loop.
`graphics` renders into a bounded, fallibly allocated software buffer, then
uses GOP BLT, avoiding assumptions about framebuffer pixel layout or stride.
The interface retains the firmware's current mode and supports 640×480 through
3840×2160. Unsupported dimensions, unavailable GOP, allocation failure or BLT
failure select firmware text output. F2 provides manual text fallback.
No desktop graphics stack, raster reference image or network is involved.
The emblem is original geometry; font8x8 supplies the bitmap glyphs.

Input currently polls at 10 ms intervals; event-based input and timeout events
belong in B/D. Errors initializing UEFI or reading keys return an explicit EFI
status. A panic is not a recovery strategy: future discovery/loading code must
surface recoverable errors in the menu. Console operations currently have only
best-effort error handling; simultaneous GOP and text-console failure remains
unresolved. No attempt is made to call ExitBootServices in this prototype.

## Planned module contracts

- Discovery: enumerate SimpleFileSystem handles and identify ESP/device paths;
  associate each entry with a specific volume, avoid duplicate/self entries.
  Discovery is read-only and never activates a target.
- Configuration: no_std-compatible TOML parser producing validated typed data;
  reject unknown fields, duplicate IDs, bad paths and unresolved defaults.
  Missing/invalid configuration cancels automatic boot and opens diagnostics.
  Initial paths resolve only against the application's own volume; future
  explicit volume selectors must reject ambiguity rather than pick a disk.
- EFI loader: LoadImage/StartImage with explicit device paths; retain the menu
  when loading fails or a child returns, and release child resources. Never
  fall through to another OS without an explicit, visible user policy.
- Linux: separate EFI-stub/UKI handling from generic EFI chainloading.
  Kernel command lines, initrd delivery, memory-map lifetime and handoff require
  dedicated tests. Arbitrary kernel images are not assumed to be EFI images.
- Editor: inspection and unsaved draft first, validation and preview second,
  explicit save last. Preserve last valid configuration. Stage a new file,
  flush, validate readback, then replace while retaining a backup. FAT/UEFI
  rename and flush do not guarantee power-loss atomicity; recovery must detect
  interrupted saves. No disk or NVRAM writes without explicit action.
- Preferences: optional vendor GUID variables, bounded data and versioning;
  writes only through an explicit save action. Unsupported NVRAM is nonfatal.

## Configuration proposal

The example deliberately contains no guessed host OS paths. Timeout zero means
wait indefinitely. Unknown themes/types/keys are errors. IDs are unique and the
default must exist. The host Python validator is an early schema contract,
not a replacement for the future Rust parser. Firmware settings require later
capability checks; the present menu merely returns to its caller.

## Architectural references and licenses

No source code was copied from these bootloaders.

- [uefi-rs 0.40](https://docs.rs/uefi/0.40.0/uefi/): established Rust firmware
  interfaces (MIT/Apache-2.0). Use its protocol wrappers instead of recreating
  firmware ABI declarations. Version pinned by Cargo.lock.
- [systemd-boot](https://systemd.io/BOOT/): small EFI execution boundary and
  explicit loader entries. Its documented EFI-stub distinction informs the
  separation of chainloading and Linux loading here. Consult per-file SPDX
  terms in [systemd licenses](https://github.com/systemd/systemd/blob/main/LICENSES/README.md)
  before reusing code; do not assume the entire repository has one license.
- [rEFInd features](https://www.rodsbooks.com/refind/features.html): volume/file
  discovery and exclusion controls are useful design references. GPLv3 code
  must not be copied without a deliberate compatible licensing decision.
- [Limine configuration](https://github.com/Limine-Bootloader/Limine/blob/v10.x/CONFIG.md):
  explicit configuration search precedence demonstrates why config origin must
  be visible and unambiguous. Its [BSD-2-Clause license](https://github.com/Limine-Bootloader/Limine/blob/v10.x/COPYING)
  requires retaining notices if code is reused.

font8x8 0.3.1 declares MIT; retain dependency license notices for future
binary distribution. The project's own distribution license remains an owner
decision; no compatibility or Secure Boot claim is implied by this prototype.

## Hardware safety and future installation

No installer exists. After virtual chainloading and recovery have passed,
prepare an explicit approved copy to `EFI/EutherBoot/EutherBoot.efi` on a
**dedicated test machine**, preserving its existing loader and boot order.
Use a firmware one-time file picker first. Do not overwrite `EFI/BOOT` on a
physical ESP. Record hashes and the original known-good path before approval.
Rollback should select that unchanged path and remove only approved EutherBoot
files. Any optional new firmware entry must be individually recorded and
removed only on request. Never format, delete existing entries, change Secure
Boot keys or automatically reorder boot targets. Secure Boot signing, trust
and rejection behavior are future tests, not demonstrated compatibility.

GOP is borrowed with GET_PROTOCOL rather than Exclusive: exclusive access can
disconnect the firmware graphics-console driver and destroy visible fallback.
The unsafe borrow is scoped to rendering, with no driver removal, console use
or boot-services exit while it is alive.
