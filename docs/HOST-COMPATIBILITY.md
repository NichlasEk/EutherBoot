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
physical USB → existing GRUB → Arch boot is now confirmed by the user. See `../HANDOFF.md` for the test and rollback steps.

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

## Physical boot and refreshed inventory — 2026-10-11

The user confirmed EutherBoot 0.1.1 → F4 → Escape → main menu → existing
loader → GRUB → Arch login. The photo shows two firmware filesystems, two
verified ESPs, one application and one skipped candidate. Direct launch from
the discovery browser was not tested. A separate boot without USB remains open.

Read-only inventory after this boot found:

| Item | Current observation |
| --- | --- |
| Running / installed kernel | 7.2.9-arch1-1 / linux 7.2.9.arch1-1 |
| ESP capacity / free | 1,071,624,192 / 438,767,616 bytes (418.4 MiB free) |
| Current kernel | 17,236,480 bytes |
| Normal initramfs | 268,792,835 bytes (256.3 MiB) |
| Fallback initramfs | 316,676,253 bytes (302.0 MiB) |
| Intel microcode image | 15,265,792 bytes |
| GRUB directory | Approximately 15 MiB |
| Old module directories on root | 174,166,016 allocated bytes (166.1 MiB), 110 files/symlinks; no pacman ownership found |

No old kernel images were found on the ESP. The fallback image is a current
recovery image, not an old kernel. Old module remnants are on the Btrfs root;
removing them would not increase ESP free space. Lack of package ownership alone
does not establish that every remnant is safe to remove. No files were deleted.

`lsinitcpio -a` identifies the normal image as kernel 7.2.9-arch1-1, with
166.14 MiB early CPIO plus a 90.2 MiB zstd payload. It includes explicit NVIDIA
modules and many other graphics modules. The current hook order places `kms`
before `autodetect`; image-size optimization deserves a separate validated
experiment, not deletion of the working fallback. LTS and systemd-ukify remain
absent; the managed-generation capacity gate remains unresolved.

Evidence is local and ignored under `artifacts/physical-0.1.1/`: discovery photo,
`host-audit.json` and per-file ownership results in `old-modules.json`. The audit
script's generic unverified list is not aware of the separately reported physical
boot; its package, mount and size observations are the refreshed inventory.

## Isolated initramfs size experiment — 2026-10-11

Two unprivileged builds used copied configuration, explicit kernel 7.2.9-arch1-1,
`mkinitcpio --nopost`, and output only under ignored `artifacts/initramfs-size/`.
No preset was invoked and no installed configuration or boot image was changed.

| Variant | Bytes | MiB |
| --- | --- | --- |
| Installed normal image | 268,792,835 | 256.34 |
| Move autodetect before kms | 217,429,499 | 207.36 |
| Omit kms, retain all four explicit NVIDIA modules | 105,433,302 | 100.55 |

The machine uses an RTX 4090 with the NVIDIA driver. The installed hook order
collects broad DRM drivers before hardware filtering. Moving autodetect earlier
reduces that collection but still includes nouveau and its firmware, despite
the installed nouveau blacklist. Four nouveau GSP firmware files alone account
for about 100.4 MiB. Early CPIO is not just CPU microcode: the installed
mkinitcpio moves already-compressed modules/firmware there to avoid recompression.

The smallest candidate retains explicit nvidia, nvidia-modeset, nvidia-uvm and
nvidia-drm modules, NVIDIA GSP firmware, NVMe, Btrfs content and Intel microcode.
Both builds succeeded; listing checks establish inclusion, not physical boot
compatibility. The candidate has not been installed or booted. Replacing only
the normal image would save about 155.8 MiB, leaving about 574.2 MiB free; the
current fallback would remain available. This alone does not establish capacity
for managed UKI/LTS generations. SHA-256 comparison of all files under `/boot`
confirmed no changes. Logs, image lists, configurations and `result.json` are
retained with the experiment.
