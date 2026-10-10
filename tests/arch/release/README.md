# Managed installation fixture

Run `scripts/prepare-arch.py`, the normal EFI build, and
`bash scripts/package-release.sh`, then `python3 scripts/arch-release-qemu.py`.
The release script also builds the native configuration validator used by the
guest installer.

The runner creates a disposable Arch QCOW2 overlay, bootstrap ESP, destination
ESP with an existing fallback application, and temporary owner-key OVMF variables.
Only bootstrap has user-mode NAT. No host mount, physical disk, EFI variable,
production signing key or shared host directory is used. It requires the same
QEMU, GPT/FAT and signing tools as the existing test matrix. Downloads use current
Arch repositories, so exact upgraded versions are recorded rather than assumed.

The serial oracle checks current Linux, LTS, current recovery without its installed
module directory, original-image recovery, and a signed non-instrumented manager
upgrade followed by normal timeout boot. Each checks uname, systemd/root identity,
service state and loading a real kernel module. The original-image module archive
is captured before bootstrap installs prerequisites; subsequent managed capture
is exercised through a real cached kernel-package reinstall.

Plans must leave installation absent. Wrong ESP identity and duplicate installation
must fail. Removal must refuse changed integration files, then restore original
presets and retain the original fallback. Its hash and the base image hash are
checked after the final boot. A complete successful run writes
`artifacts/arch-release/result.json`; partial logs are not a passing result.
All guest storage and private test keys are deleted on exit. Artifacts retain logs,
screenshots, the original fallback readback and result metadata, not private keys.

The fixture does not prove arbitrary physical power-loss atomicity, all Arch
storage/encryption layouts, userspace rollback or production Secure Boot trust.
Generation prune protections are tested separately in `tests/installer/`.

`--layout btrfs-at-udev` selects the additional layout described in
[the compatibility gate](../../../docs/HOST-COMPATIBILITY.md): FAT `/boot`, Btrfs
`@`, separately mounted swap subvolume and udev default/fallback initramfs images.
A temporary filler leaves approximately 419 MiB free before an installation
attempt; the payload-based budget must refuse before creating any integration
file, EFI installation or journal. The filler is then removed for the positive
installation/recovery tests. No host files are used as kernel/initramfs inputs.

`python3 scripts/test-arch-hooks.py` is a separate offline libalpm test. It installs
a synthetic package containing an external-module directory and records real
pre/post hook invocation. A refused second transaction must retain the original
package/version/payload. Exec commands are replaced with assertion oracles and
upstream mkinitcpio generation is disabled only inside that disposable guest;
this validates trigger/AbortOnFail semantics, not NVIDIA driver operation.
