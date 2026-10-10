# Validation · 2026-10-10

Demonstrated on the host with QEMU 11.1.2 TCG, q35, OVMF and disposable FAT-backed
virtual storage. This is not physical hardware or OS-boot evidence.

## First light and menu

- Rust 1.99.0, uefi-rs 0.40.0; release x86_64-unknown-uefi build succeeded.
- Two Rust menu tests passed: wrap behavior and empty-menu navigation.
- Four Python schema tests cover the proposal, unresolved default, unknown keys,
  invalid timeout/theme, duplicate IDs and path traversal rejection.
- OVMF booted EutherBoot from EFI/BOOT/BOOTX64.EFI.
- GOP rendering and manual text fallback work at 1024×768 and 640×480.
- Up/Down wrap selection. The configuration placeholder stays in the menu.
- Enter on the return entry returns EFI_SUCCESS to firmware, not firmware settings.

## Chainloading

The child is a separately linked PE32+ EFI application at
`EFI/EutherBoot/TestChild.efi` on the temporary volume. Each scenario is attempted
three times in one VM (twice graphical, once text), using actual QMP keyboard
input. The runner verifies that no child executes before Enter.

| Scenario | Resolution | Observed outcome |
| --- | --- | --- |
| Valid child, Enter | 1024×768 | CHILD_STARTED, context present, SUCCESS, image released, menu redrawn |
| Valid child, Enter | 640×480 | Same success and recovery checks |
| Valid child, Escape | 1024×768 | Child returns ABORTED; status displayed; menu usable |
| Missing file | 1024×768 | LoadImage NOT_FOUND; no child execution; menu usable |
| Invalid file | 1024×768 | LoadImage UNSUPPORTED for non-PE data; no child execution; menu usable |

All five scenarios passed (15 explicit chainload attempts). The runner accepts
LOAD_ERROR or UNSUPPORTED for invalid images, since firmware may classify these
differently. Inspect debug.log for the exact firmware result.

Image checks compare the restored menu region with the initial frame after the
child clears the screen. Text recovery checks console output, disappearance of
the graphics canvas and working subsequent input. The child and restored graphical
menu were also visually inspected. Handle-release markers confirm that the
returning application no longer exposes LoadedImage; this is not a memory-leak audit.

Reproduce with `./scripts/test.sh`. Generated binaries, checksums, logs and PPM
screenshots remain ignored under `artifacts/`. Each VM run uses
`artifacts/qemu-<width>x<height>-<scenario>/`. The runner prepares a unique temporary
FAT directory and writable OVMF-variable copy; none survives into another run.
No host disks, ESP or network interface are attached.

Not demonstrated: absent/broken GOP automatic fallback, text-console failure,
allocation exhaustion, authentication-rejected images, nonempty child ExitData,
OS booting, UEFI configuration reads, editor saves, preferences or hardware.
The directory-backed FAT device does not test GPT enumeration or multiple ESPs.
See ARCHITECTURE.md for the dependency cleanup limitations before Secure Boot work.

Regression retained from A: opening GOP exclusively disconnected the firmware
console, leaving the old graphical frame after F2 while text only reached serial.
GET_PROTOCOL preserves the console driver. A pixel check now rejects stale
navy graphics after F2 as well as requiring console output and continued input.

Artifact SHA-256 from this validated build:

```text
294d5371be595025eb9a4fa6e03664b749e0050c6ed1c0411ea81229d21667b1  artifacts/EutherBoot.efi
3528b88ea4cc535bd68693a3d5e315069facae07a895aba3ae9d8c87222f970e  artifacts/TestChild.efi
```
