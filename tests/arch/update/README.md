# Guest-only Arch update prototype

These files are copied to a disposable virtual ESP by
`python3 scripts/arch-update-qemu.py`. **Do not run setup.sh on the host.**
The installer additionally checks the known fixture root PARTUUID, root device
and virtualization. There is no physical installation mode.

The runner boots the signed Arch basic image through the existing EFI-stub
fixture, mounts the separate virtual ESP at `/eutherboot`, and installs:

- A `linux.preset` extension producing a UKI at
  `/var/lib/eutherboot/arch-linux.efi`, with an explicit guest kernel command line.
- An mkinitcpio post hook publishing that UKI to
  `/eutherboot/EFI/Linux/arch-linux.efi` after successful generation.
- A pacman pre-transaction hook checking the mounted ESP's PARTUUID, FAT type,
  read/write state and available space before selected boot-component upgrades.

Arch's existing pacman/mkinitcpio integration triggers generation; EutherBoot
keeps one ordinary `type='efi'` menu entry at the stable UKI path. No BootOrder,
BootNext, firmware keys or existing loader files are changed. The fixture initially
switches its menu from the old bootstrap entry to the UKI after the first upgrade;
subsequent publication does not rewrite TOML.

The publisher identifies the result as a UKI with `bootctl`, locks concurrent
publication, copies to a temporary file on the ESP, compares bytes and syncs
before renaming it to the active path. An existing image is retained as
`arch-linux.previous.efi` for diagnosis. This is **not** a complete rollback:
Arch may remove the matching old modules. The previous image is not added to the
menu. LTS integration and retained kernel/module generations remain future work.

The test runs an actual `pacman -Syu --noconfirm --needed binutils systemd-ukify`
inside the guest. These dependencies are installed only there. QEMU user-mode
NAT is enabled for the first boot only, with no port forwarding, host disk,
shared directory or bridged interface. Original image SHA-256 and the read-back
EutherBoot binary are checked after the test. Generated keys and guest data stay
in temporary disks, which are deleted on success or failure. Logs and the updated
UKI stay in ignored `artifacts/arch-update-qemu/`.

The online repositories are intentionally live. The test requires the installed
kernel package/version to change and the next `uname -r` to match the newly
installed module directory, not the original kernel. It does not silently pass
when no kernel upgrade occurred. The initial image provenance is pinned by
`prepare-arch.py`; complete package progress and versions are in the serial log.

The negative tests require the expected refusal reason, then check the active
UKI's hash: missing mount (an actual cached-package pacman transaction must abort),
read-only mount, wrong ESP, and malformed UKI. A successful cached-kernel reinstall
then exercises replacement and checks the saved previous image. Finally a partial
staging file is flushed, QEMU is killed without guest shutdown, and another boot
must reach the current kernel with the expected UKI hash. This tests one specific
interruption point; FAT rename and power-loss atomicity are not guaranteed.

This is currently scoped to the stock `linux` preset, ordinary OVMF, and this
fixture's unencrypted Btrfs root. It does not implement LTS/custom-kernel handling,
Secure Boot signing, rollback of a completed package transaction, detection of
all possible rebuild triggers before a transaction, or a hardware installer.
Post-transaction failures cannot roll back pacman's already-installed packages;
retain a separately proven recovery path before considering physical installation.

References:
[mkinitcpio presets and post hooks](https://man.archlinux.org/man/mkinitcpio.8.en),
[pacman pre-transaction hooks and AbortOnFail](https://man.archlinux.org/man/alpm-hooks.5.en).
