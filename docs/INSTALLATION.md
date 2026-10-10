# Side-by-side installation and rollback

The installer is for a dedicated test system. Physical firmware, storage failure
and machine-specific initramfs configurations remain separate validation gates.
All automated installation tests operate on disposable QEMU disks.

## Build and inspect

Run `bash scripts/package-release.sh`. The non-instrumented EFI application,
native configuration validator, installer and Arch integration are placed in
`artifacts/release/`. `manifest.json` records compiler, Git revision, dirty state
and file hashes. The native validator requires a compatible Linux userspace.

Identify the intended **already mounted** FAT ESP using `findmnt` and `lsblk`.
Record its PARTUUID and preserve the current boot manager and bootable recovery
media. The installer neither mounts nor formats disks and never edits BootOrder,
BootNext, boot entries or Secure Boot keys. It refuses an existing EutherBoot
installation instead of overwriting it. `/EFI/BOOT/BOOTX64.EFI` is never replaced.

Prepare and validate a TOML configuration with real paths on the intended ESP.
An installation plan is read-only:

```sh
python3 tools/eutherbootctl.py install \
  --esp /your/mounted/esp --esp-guid YOUR-ESP-PARTUUID \
  --image artifacts/release/EutherBoot.efi --config your-config.toml \
  --validator artifacts/release/config-check
```

These are placeholders, not detected destinations. Only after reviewing the plan,
run the same command as root with `--apply`. EutherBoot is placed at
`\EFI\EutherBoot\EutherBoot.efi`; configuration is in the same directory.
Use firmware **Boot From File** for the first boot. Leave the established boot
path available until repeated cold boots and recovery have passed on that machine.

## Optional Arch integration

The supported initial integration uses stock `linux` and `linux-lts` packages,
mkinitcpio presets retaining `/boot/initramfs-linux.img` and
`/boot/initramfs-linux-lts.img`, systemd and systemd-ukify. Install the prerequisites
through the system's normal full-upgrade process before requesting integration.
Separate `/usr` and `/var` filesystems are refused. Encrypted roots, custom
presets, other kernel package names and other distributions are not established
compatibility claims. Keep ample root and ESP free space; a 1 GiB ESP is used in
the automated test, and saved generations continue consuming space.

Add `--arch --cmdline your-kernel-command-line.txt` to the installation command.
The file must contain one explicit line appropriate for this root filesystem.
Do not copy the QEMU fixture's root PARTUUID or diagnostic arguments.
The generated UKI paths for TOML entries of `type = "efi"` are:

| Entry | Path |
| --- | --- |
| Current | `\EFI\EutherBoot\kernels\linux.efi` |
| LTS | `\EFI\EutherBoot\kernels\linux-lts.efi` |
| Previous current | `\EFI\EutherBoot\kernels\linux-previous.efi` |
| Previous LTS | `\EFI\EutherBoot\kernels\linux-lts-previous.efi` |

With the integration explicitly installed, ordinary `pacman -Syu` (including
pacman transactions invoked through yay) performs the following:

1. A pre-transaction hook validates the mounted ESP and available space. It saves
   the installed kernel, its initramfs and matching modules on the root filesystem,
   verifies the archive, and publishes a recovery UKI before package changes.
2. mkinitcpio builds the replacement UKI in root-owned staging. The post hook
   validates it, optionally signs it, verifies the copied candidate and replaces
   the stable ESP path. TOML needs no edit for each kernel version.
3. A successful normal boot records the published kernel hash. An unbooted update
   cannot silently displace the previously confirmed recovery selection.
4. Recovery boot binds the archived matching modules into the running kernel's
   module path before normal module loading. Kernel updates are refused while
   using recovery; boot LTS or another normal kernel to perform repairs.

This is **kernel and module recovery**, not rollback of the entire userspace or
package database. Generations are intentionally retained rather than automatically
deleted; the free-space guard can stop subsequent updates. Use `status` to list generation IDs, then review a read-only pruning plan:

```sh
python3 tools/eutherbootctl.py prune --esp /your/mounted/esp \
  --esp-guid YOUR-ESP-PARTUUID --generation GENERATION-ID
```

Repeat with `--apply` only for an unwanted generation. Pruning refuses running,
selected, pending and TOML-referenced recovery generations, including editor
backups. It removes the corresponding immutable UKI and module archive. Do not
manually delete archives referenced by recovery images you intend to retain.

## Secure Boot

For managed Arch installation, optionally supply `--signing-key` and
`--signing-cert`. The private key must be root-owned, mode 0600 or stricter and
outside the ESP. The integration signs the manager and generated UKIs using
`sbsign`, and verifies signatures using `sbverify`. The corresponding certificate
must already be trusted by the intended firmware. The installer does not enroll
keys, change trust stores or implement shim/MOK/SBAT. Disposable OVMF owner keys
are only test material. External configuration is not authenticated by signing
EutherBoot; self-contained signed UKIs are the tested Linux integrity boundary.

## Upgrade and uninstall

`eutherbootctl.py status` inspects the recorded installation. `upgrade` takes
`--esp`, `--esp-guid` and `--image`; it defaults to a read-only plan, requires
`--apply` to write and retains `EutherBoot.previous.efi`. A signed installation
requires signing material for the replacement. Configuration remains unchanged.
An interrupted upgrade is recorded in the installation journal; inspect both
image hashes before retrying or selecting the retained EFI application manually.

To remove the managed installation, boot a normal or LTS kernel first:

```sh
python3 tools/eutherbootctl.py remove --esp /your/mounted/esp --esp-guid YOUR-ESP-PARTUUID
# Review the plan, then repeat as root with --apply.
```

Removal verifies ownership, refuses locally modified integration files, archives
EutherBoot's EFI directory under `/var/lib/eutherboot/removed-<id>`, restores the
original mkinitcpio presets and removes its hooks/services. Recovery generations
remain available for deliberate inspection. The existing boot manager and its
normal initramfs were retained throughout. Select that existing loader through
firmware if needed. No firmware entry needs removal because none was created.

If installation fails, its journal is marked incomplete. Inspect the reported
error, then use the same removal workflow to undo recorded integration changes.
Renames and flushes improve recoverability but do not guarantee atomic survival
of arbitrary physical FAT power loss. Always retain a separate known-good path.
