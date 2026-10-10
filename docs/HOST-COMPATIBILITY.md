# Arch compatibility gate

`python3 scripts/audit-host.py` prints a read-only JSON inventory. It reads mount
metadata, package versions, EFI SecureBoot state, boot-file sizes and selected
mkinitcpio settings. It never sources a preset, invokes an installer, mounts a
filesystem or writes to the ESP/NVRAM. Redirect output to ignored `artifacts/`
when retaining machine-specific evidence. No machine identifiers are required in
committed documentation.

The first inventory exposed these differences from the original cloud fixture:

- Btrfs root is the `@` subvolume; `/usr/lib/modules` and `/var/lib` remain on that
  root mount. Other mounted subvolumes do not by themselves violate the recovery
  service's early-boot requirements.
- The FAT ESP is mounted at `/boot` and already contains the existing kernel,
  normal initramfs and fallback initramfs.
- The udev/busybox initramfs includes NVIDIA modules; its normal image is about
  257 MiB. The installed NVIDIA package targets the regular kernel; matching
  LTS modules also need validation before an LTS initramfs can be relied on. An external `linux-efi` initrd exceeds the current 128 MiB loader limit.
  A self-contained UKI uses ordinary EFI chainloading and does not use that
  external-initrd path, but needs adequate ESP space.
- About 419 MiB is free on the 1 GiB ESP. The old fixed 384 MiB check was inadequate
  for these payloads. Even the present non-LTS payload requires a conservative
  initial budget of about 1.47 GiB **free** with current/recovery copies and staging;
  missing LTS payloads increase the full budget. This is an estimate with headroom,
  not a prediction of exact future UKI size.
- `linux-lts` and `systemd-ukify` were absent. The running kernel was older than
  the installed kernel, with multiple module trees retaining `pkgbase=linux`.
  Selecting directories by package-name scans alone was therefore unsafe.

The installer now budgets initial generations from actual kernel/initramfs sizes.
The pre-transaction hook budgets retained generations and replacement staging;
publication independently checks the completed UKI size before creating its
adjacent temporary copy. Firmware/kernel growth and other writers can still
invalidate estimates; failures preserve the active target and require repair.

Pre/post hooks also match initramfs-affecting payload paths, following the
installed mkinitcpio hook: external modules, DKMS definitions, firmware, udev and
related early-boot components. A driver-only update must not bypass capture merely
because the kernel package version stays unchanged. Real NVIDIA/DKMS updates remain
a separate validation gate; kernel recovery does not restore NVIDIA userspace libraries.

Recovery capture selects the unique module tree owned by the installed pacman
package. Unowned stale trees are ignored; ambiguity/missing identity is refused.
The kernel under `/boot` must match that tree's kernel before capture.

## Virtual layout test

```sh
python3 scripts/arch-release-qemu.py --layout btrfs-at-udev
```

This variant uses disposable disks and temporary OVMF keys. Its positive recovery
matrix uses a 2 GiB virtual ESP, explicitly larger than the inventoried host ESP.
The 1 GiB run booted the `@` root with no failed units, then correctly refused
the package transaction when retained-generation headroom was insufficient. It mounts the guest
ESP at `/boot`, builds udev-based default/fallback initramfs images, snapshots the
guest root into `@` before the first managed boot and uses explicit `rootflags`.
Every subsequent Linux oracle requires root FSROOT `/@` and FAT `/boot`. A stale,
unowned `pkgbase=linux` module directory challenges generation selection.
The normal/LTS/recovery/upgrade/uninstall matrix is otherwise retained. Evidence
is isolated under `artifacts/arch-host-layout/`; only `result.json` proves completion.
The NVIDIA driver, GPU, physical firmware and production keys are not emulated.

## Before physical installation

The managed UKI/recovery installation is **not ready to apply to the inventoried
host** with its current free space and missing prerequisites. No partition resize,
boot-file removal, package install or host hook installation has been performed.
Space must be resolved through a separately reviewed storage/boot plan; do not
remove the working fallback merely to force installation through a capacity check.

A first hardware probe could instead run EutherBoot from separately prepared test
media and chainload the established loader. That tests firmware/menu integration
without requiring the managed UKI layout to fit the existing ESP. Preparing media
or writing a host ESP is a separate explicit action with a concrete destination
and rollback plan. The first USB delivery is now written and readback-verified;
physical boot remains untested. See `../HANDOFF.md` for the test and rollback steps.

Before interpreting any hardware-probe failure, establish a cold-boot baseline
through the unchanged GRUB path: the inventoried running and installed kernel
versions differ. The next ordinary reboot already exercises a pending Arch kernel
update independently of EutherBoot. No reboot was requested or performed by the
inventory tooling.

## Prepared USB image file

```sh
python3 scripts/prepare-host-probe.py --target-guid YOUR-EXISTING-ESP-PARTUUID
```

This creates `artifacts/host-probe/usb.img`, a 128 MiB GPT disk image with a
64 MiB FAT ESP, the non-instrumented EFI release, its GPL license and matching
source archive. The configuration has timeout zero and explicitly selects the
existing loader's partition GUID and EFI path. The default path is
`\EFI\BOOT\BOOTX64.EFI`; it must be confirmed on the intended machine.
The image contains no copy of the existing loader and does not install Arch hooks.

Before publishing the local file, the script boots those exact image bytes in
QEMU, observes the System Regis framebuffer, selects a disposable EFI child on a
second virtual ESP with the requested identity and verifies return to the menu.
Both virtual disk hashes must remain unchanged. No host disk is attached. This
proves the image/menu/partition-selection route, not physical GRUB compatibility.
Result metadata and PNG captures are under `artifacts/host-probe/`.

Creating the file does not flash a USB stick. A physical test still requires an
explicitly identified disposable destination and use of the firmware's one-time
boot selector. Boot order and installed loaders need not be changed for that test.
The currently prepared image is unsigned, matching the inventoried disabled
Secure Boot state; do not change firmware trust settings merely to run it.
