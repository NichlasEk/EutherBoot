# Validation · 2026-10-10

Demonstrated on the host with QEMU TCG, q35, OVMF and a disposable FAT-backed
virtual ESP. This is not physical hardware evidence.

- Rust 1.99.0, uefi-rs 0.40.0; release x86_64-unknown-uefi build succeeded.
- Two Rust menu tests passed: wrap behavior and empty-menu navigation.
- Four Python schema tests passed, including unresolved default, unknown key,
  invalid timeout/theme, duplicate IDs and path traversal rejection.
- OVMF booted EutherBoot from EFI/BOOT/BOOTX64.EFI.
- 1024×768 and 640×480 GOP screenshots were captured and visually inspected.
- QMP-injected Up/Down wrapped selection. Enter on placeholders stayed in the
  application. F2 selected text output; selection and Enter still worked there.
- Enter on the return entry produced EXIT_FIRMWARE; the application returns
  EFI_SUCCESS. This is not a request to open firmware settings.

Reproduce with `./scripts/test.sh`. Generated logs/screenshots/binaries are
ignored by Git under `artifacts/`; the scripts regenerate them. Debugcon markers
come from the running EFI application, not from a mocked menu model.

Not demonstrated: absent/broken GOP automatic fallback, text-console failure,
allocation exhaustion, Escape under automation, physical firmware behavior,
chainloading, OS booting, configuration reads in UEFI, persistent preferences,
editor saves, Secure Boot or interrupted-save recovery.

The current virtual ESP uses QEMU's disposable directory-backed FAT device;
it does not test GPT partition enumeration. C/F will require actual disposable
GPT disk images and multiple ESPs. The input test does not prove every keyboard
or firmware implementation works.

Regression caught during development: opening GOP exclusively disconnected the
firmware graphics console, so text appeared on serial while the old GOP frame
remained on screen. A short-lived GET_PROTOCOL borrow preserves the driver.
The QEMU regression now rejects a navy graphical frame remaining after F2,
in addition to requiring text-console output and continued keyboard navigation.
