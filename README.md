# EutherBoot · System Regis

**The machine belongs to its owner.**

An independent Rust-first UEFI boot environment for x86_64. Local control,
private by design, freedom through understanding. No network, telemetry or services.

This is a working **UEFI chainloading prototype**, not yet an OS bootloader.
It displays a restrained navy/gold interface with an original geometric
three-crowns-and-sword emblem, accepts keyboard input, and chainloads an
independent EFI test application. Returned children and load errors restore
the menu. It can also return to firmware.
It does not discover or launch installed operating systems yet.

## Run locally

Requirements: Rust with `x86_64-unknown-uefi`, Python 3.11+, QEMU x86_64 and OVMF.
The initial build was tested with Rust 1.99.0, uefi-rs 0.40.0 and the committed
Cargo.lock. Install the target with `rustup target add x86_64-unknown-uefi`.
The scripts also recognize an isolated rustup installation under `.tools/`.

```sh
./scripts/build.sh
python3 scripts/qemu.py          # interactive QEMU window
./scripts/test.sh                # host checks + five headless OVMF runs
```

Override `OVMF_CODE` and `OVMF_VARS` if needed. Defaults are Arch Linux's
`/usr/share/edk2/x64/OVMF_{CODE,VARS}.4m.fd`; use a matching firmware pair.
All VM storage is generated inside a unique temporary directory. The runner
copies the EFI executable to a disposable FAT volume's `EFI/BOOT/BOOTX64.EFI`
and the independent child to `EFI/EutherBoot/TestChild.efi`, then copies OVMF variables. No host disk, ESP, firmware variables or network
interface is exposed. Temporary storage is removed when QEMU exits.

Binaries: `artifacts/EutherBoot.efi` and `artifacts/TestChild.efi`; checksums:
`artifacts/SHA256SUMS`. The child is a QEMU-only fixture, not an OS or installer.
Screenshots and logs: `artifacts/qemu-<width>x<height>-<scenario>/`.
The test build enables the `qemu-debug` feature (debugcon port 0xe9).
A normal EutherBoot Cargo build without that feature contains no debug-port writes.
The QEMU-only test child always emits debugcon markers.

## Controls

- Up/Down: select, wrapping at either end.
- Enter: start the EFI test application, inspect the editor placeholder, or return to firmware.
- Inside the child: Enter returns SUCCESS; Escape returns ABORTED to EutherBoot.
- F2: switch to firmware text output for the remainder of this run.
- Escape: return to the firmware caller.

“Return to firmware” returns EFI_SUCCESS; it does not request firmware settings
or change BootOrder. What appears next is decided by the caller.
There is no timeout or automatic activation in this prototype.

`eutherboot.toml` is a **proposed schema**, validated on the host by
`python3 scripts/validate-config.py`. The EFI application does not read it yet.
There is no configuration editor or persistent write operation yet.

See [architecture](ARCHITECTURE.md), [roadmap](ROADMAP.md), and
[validation evidence](docs/VALIDATION.md). Physical installation is not provided;
this binary is for the disposable virtual environment only at this stage.

## Chainloading regression cases

```sh
python3 scripts/qemu.py --test --scenario return
python3 scripts/qemu.py --test --scenario abort
python3 scripts/qemu.py --test --scenario missing
python3 scripts/qemu.py --test --scenario invalid
```

Each run makes three explicit attempts in one VM, including one in text mode.
The child displays its own screen and waits for a key. Tests verify its execution
markers, return status, released image handle, reconstructed menu pixels and
continued input. Missing/corrupt fixtures must never execute a child. Full test
coverage also runs the successful case at 640×480. No automatic retries occur
in EutherBoot itself; every attempt comes from an injected Enter key.
