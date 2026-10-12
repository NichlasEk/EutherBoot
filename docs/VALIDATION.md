# Validation · 2026-10-10 · Arch kernel updates and LoadFile2

## Debian physical confirmation · 2026-10-12

Following the 0.1.2 delivery, the user reported “Nu fungerar debian”
(Debian now works), confirming Debian boots on the physical machine.
This is user-reported physical evidence in addition to the QEMU results.
The installed EFI hash and selected initrd size were not independently
read back from that machine.

## EutherBoot 0.1.2 large initrd · 2026-10-11

The production policy now allows 1 byte through 512 MiB of external initrd.
Debian QEMU tests pass with 128 MiB + 1 byte and exactly 512 MiB. Negative
tests reject 512 MiB + 1 byte, empty initrd and insufficient kernel cmdline
capacity with specific diagnostics; the independent recovery EFI child
starts and returns after each rejection. See `artifacts/debian/*/result.json`.
The earlier 128/256 MiB investigation is archived under
`artifacts/debian/investigation-011/` and does not describe the new policy.

The exact non-debug production EFI also booted the 512 MiB Debian case to
login (`production-maximum/result.json`), SHA-256
`7ecc51be45799dc07ae7dc80032f3898ca5d713673f6172bc487d4b70a57c91f`.
All 32 boot-core tests and eight LoadFile2 lifetime/error cases passed.

## Euther Rescue 0.1.2 · 2026-10-11

The final ISO and complete USB image each passed two QEMU cold boots,
embedded production EFI/source hashes, network access and persistent work
across reboot. The ISO's own Codex launchers reached onboarding without an
injected fix; an old `work/EutherBoot` sentinel remained unchanged and the
new `work/EutherBoot-0.1.2` snapshot contained the correct release version.
No credentials or host disks were attached to the guests.

The USB test exposed an intermittent Archiso UUID selection bug: a hybrid
ISO has the same filesystem UUID on the whole disk and its ISO partition.
In a failed run `/run/archiso/bootmnt` used `/dev/sda`, preventing `/dev/sda3`
from opening for ext4 mount. The assembler now binds `archisodevice` to the
exact ISO partition PARTUUID in the USB's FAT loader entry. It verifies that
entry after writing. Final USB tests assert the mounted source is a partition,
and verify data mounting and persistence across both boots. Optical ISO boot
retains its original UUID selection. Internal partitions need not be scanned.

One concurrent optical ISO run exceeded the test's 60-second shutdown bound;
the final retry used a 180-second allowance and both shutdowns completed in
3.9 seconds. This does not establish the cause of the earlier timeout.
The complete USB image's two shutdowns also completed normally.

Final ISO SHA-256:
`5a10ca0138d4a35f275e50fa9078af2fb9cdec4c76b38a1ce3e7ae80a7cf05e5`.
Complete USB image SHA-256:
`76e54df30b08fc6d701be9e6d057f586f5114b7322b367b478b3049c88ff9b75`.
See `artifacts/rescue/{build-result,test-result,usb-test-result,codex-start-fixed-result}.json`.
Physical USB readback/delivery is recorded separately in `usb-delivery.json`;
physical Debian boot was subsequently confirmed by the user on 2026-10-12
as recorded above.

Delivery completed: all 15,728,640,000 physical USB bytes were read back after
fsync and matched the complete image SHA-256 above. After that full check,
partitions were remounted; geometry, six ESP file hashes, embedded production
EFI/source hashes, the Debian guide and the explicit ISO PARTUUID boot entry
were verified from the physical USB. Data was left mounted at EUTHERDATA.
The ext4 mount can subsequently change filesystem metadata; the whole-device
hash records the verified pre-mount state. Host internal boot/NVRAM were not
modified. At delivery, physical boot had not yet been tested.

## Debian 13 initrd size investigation · 2026-10-11

Three QEMU/KVM cases passed: original Debian cloud kernel/initrd to login,
initrd padded to 128 MiB + 1 byte rejected with the photographed
`Linux EFI setup: BAD_BUFFER_SIZE` and working recovery child, and the same
padded initrd to login with an isolated 256 MiB-cap experiment build.
Production loader source is unchanged. See [DEBIAN-QEMU.md](DEBIAN-QEMU.md)
for hashes, commands, boot-oracle limits and the still-unconfirmed physical
diagnosis. Source image and test ESP hashes remained unchanged.

## OS icon gallery · 2026-10-11

32 embedded OS masks cover Windows, 30 Linux distributions/variants and generic
Linux. Host tests cover punctuation/case normalization, reserve suffixes,
derivative precedence and false Arch substring matches. `cargo test -p boot-core`
and the UEFI builds passed. SVG sources and per-icon provenance/license metadata
are vendored; rasterization is reproducible offline.

`scripts/test-os-icons-qemu.py` passed 160 silhouette checks across all icons:
1024x768 in dark, light and high-contrast themes; 640x480 and 1280x960 in dark.
The checker compares opaque/transparent mask pixels with actual framebuffer
pixels on every menu page, verifies white high-contrast icons, chainloads a
disposable EFI child and returns, and checks text fallback. Screenshots wait
for completed rendering rather than the earlier selection event.

The exact production EFI was separately tested with the host's two menu names
and EFI paths (timeout disabled, disposable test children substituted for UKIs).
Both targets chainloaded and returned with icons visible. No physical disks or
network were attached, and no bootloader debug trace was emitted by that build.
This is not a fresh physical normal/LTS boot test.

Evidence: `artifacts/icons/qemu/result.json`, gallery screenshots,
`artifacts/icons/production-qemu/result.json`, and `artifacts/icons/build.log`.
See `OS-ICONS.md` for supported names and attribution.

The production EFI and matching source archive were subsequently installed on
the host, backed up under `/var/lib/eutherboot-single/before-os-icons`, synced
and hash-verified. Menu, both UKI hashes and firmware entries remained unchanged.
Evidence: `artifacts/icons/installed-result.json` and `install.log`.
Physical boot with this updated EFI remains untested.

## Host LTS installation · 2026-10-11

LTS `6.18.55-1-lts`, matching `nvidia-open-lts` 615.78.08 and LTS headers
are installed. Both production UKIs were rebuilt by the deployed wrapper,
validated against package-owned kernels/cmdline and hash-compared to staging.
NVIDIA version/vermagic and all four early NVIDIA modules were checked for
both images; Btrfs support is built into both kernels. All four existing DKMS
modules are installed for both kernels, including VirtualBox. Missing-header
errors from the initial transaction were resolved by installing LTS headers.

Normal remains default with a 10-second timeout; LTS is a separate menu entry.
ESP free space is 449,863,680 bytes (429.0 MiB). The preflight check
passed. Bootloader hash and firmware entries are unchanged, and GRUB is absent.
The prior normal image and integration were backed up on root.

Evidence: `artifacts/internal-lts/installed-result.json` and `verify.log`.
The first ad-hoc content checker expected underscore NVIDIA filenames and a
loadable Btrfs module. It was corrected to accept actual hyphen filenames and
package-confirmed built-in Btrfs; the final checker passed without changing
boot payloads for those checks. No physical LTS boot or NVIDIA rendering test
has occurred yet. The host was not rebooted.

## Optional LTS integration · 2026-10-11

`scripts/test-lts-qemu.py` passed on a disposable 1 GiB FAT ESP and Btrfs `/@`
with the production release EFI, no network and no host disks attached.
The sequence installed the single profile, cold-booted normal Arch, added
real `linux-lts` 6.18.55, upgraded normal linux 7.2.7 to 7.2.9, cold-booted
LTS, reinstalled LTS through real pacman hooks, and cold-booted normal 7.2.9.
Module loading and absence of failed systemd units were checked on each boot.
The base image hash remained unchanged.

Both active UKIs were padded to 286,150,656 bytes to exercise host-sized
coexistence and sequential replacement. A corrupt staged LTS image and a
failed mkinitcpio build preserved both active hashes. A filled ESP caused
pacman's LTS pre-transaction hook to abort; managed LTS removal was also
refused. Four Python tests check copy/rename failures, validation-before-
publication, aggregate growth budgeting, and rejection of symlinked staging.

The initial run caught a regression: checking presets before the upstream
install hook rejected kernel upgrades because the upstream removal hook had
saved the preset as `.pacsave`. The wrapper now lets the upstream install hook
restore/build first, then verifies presets and images before publication.
The final run passed real normal upgrades and LTS reinstalls with this fix.

Evidence: `artifacts/lts-qemu/result.json`, four serial boot logs and
`artifacts/lts-qemu-run.log`. The virtual driver trigger is synthetic;
physical NVIDIA/LTS operation requires the separate host boot test.

## Physical internal normal boot · 2026-10-11

The user returned after the migration and reported successful startup with
GRUB absent and only Arch in the menu. Live checks verified
`eutherboot.internal=single-v1`, kernel `7.2.9-arch1-1`, Btrfs `/@`, internal
vfat ESP and BootCurrent 0001 pointing to the internal EFI path. No USB disk
was connected. This confirms physical internal normal boot; it does not
confirm the newly requested LTS path. Read-only evidence was saved in
`artifacts/internal-lts/before.json`.

## Single UKI with external rescue · 2026-10-11

`scripts/test-single-qemu.py` passed on a disposable 1 GiB FAT ESP and a
Btrfs `/@` root, without network or physical disks. The production release
EFI started installed Arch 7.2.7, a real pacman transaction upgraded linux
to 7.2.9, and a second cold boot reached that kernel with working module
loading and no failed systemd units. GRUB was removed by the tested installer.

Real pacman pre-transaction refusal with a filled ESP preserved both the
installed kernel package and the active UKI. Invalid PE input and a missing
mkinitcpio build hook preserved the active file. A synthetic `nvidia-open`
package exercised package-only rebuild/publication triggers; this is not a
real NVIDIA driver update test. A valid UKI padded to the host payload size
also passed publication. Separate injected copy and rename failures retained
the active bytes and cleaned temporary copies (`tests/test_single_publish.py`).

The initial mkinitcpio post-hook design failed the build-error oracle:
mkinitcpio ran it despite a missing build hook. The final integration wraps
the distribution's pacman build command and publishes only after successful
process exit. The final run passed that same negative test. Test-fixture
corrections included Python from the local package cache and explicit mounting
of the cloud image's separate swap subvolume after its root snapshot.

Evidence: `artifacts/single-qemu/result.json` and three serial boot logs.
The base image hash remained unchanged. Host installation and the subsequent
physical internal boot are separate gates; see `HANDOFF.md` for their status.

## Host single-UKI installation · 2026-10-11

The authorized migration completed: GRUB package and generated GRUB files were
removed, normal/fallback standalone initramfs images were replaced by one UKI,
and the production EutherBoot EFI replaced the existing fallback-path loader.
The prior ESP and preset were copied to root and hash-verified before changes.
The deployed rebuild wrapper built and published kernel 7.2.9 successfully;
ESP UKI and EFI hashes matched their sources. ESP free space is 748,019,712 bytes.
NVRAM/boot order remained byte-for-byte identical in `efibootmgr -v` output.
No reboot was performed. Physical internal boot remains pending.

Evidence: `artifacts/internal-layout/installed-result.json`, `install.log` and
`rebuild.log`; rescue/rollback instructions are in `INTERNAL-SINGLE-UKI.md`.

## Physical host return check · 2026-10-11

After the user returned, live read-only checks found
`eutherboot_probe=usb-direct-normal-v1` in `/proc/cmdline`, kernel
`7.2.9-arch1-1`, and root `/dev/nvme0n1p2[/@]` with Btrfs FSROOT `/@`.
The Kingston DataTraveler 3.0 was connected with its 1 GiB FAT partition
unmounted. The running host therefore carries the normal direct-test command
line. The user then replied “allt funkar fint” to the question about the direct
entry and working desktop/graphics, confirming physical normal direct boot.
This check does not validate the fallback entry or an internal
installation. No boot files, USB contents or EFI variables were changed.
The sections below retain their original virtual-test scope.

Host: Rust 1.99.0, QEMU 11.1.2 TCG/q35, ordinary OVMF, x86_64 UEFI target.
This is virtual-development evidence: Linux reaches a generated diagnostic PID 1,
including a locally signed UKI under an enforced OVMF owner-key policy.
The separate installed Arch test below additionally exercises a real root
filesystem and systemd through KVM. Physical hardware remains untested.

## Installed Arch: two cold boots

The official signed `Arch-Linux-x86_64-basic-20261001.604814.qcow2` was verified
against the public arch-boxes primary fingerprint
`1B9A16984A4E8CB448712D2AE0B78BF4326C6F8F` and published SHA-256
`f9fa16c40e6ac9c03fd28a9ba12fa6ab58b5648ac444a6d27b31ee5bd9913186`.
See [source/key provenance](../tests/arch/README.md).

`python3 scripts/prepare-arch.py` extracts the image's own kernel and initramfs
without host mounts. `python3 scripts/arch-qemu.py` runs ordinary OVMF/q35 with
KVM, 2 GiB RAM, a separate read-only 512 MiB EutherBoot ESP and a writable QCOW2
overlay of the original Arch disk. There is no network device. The original
Arch ESP and GRUB are left in the source image; no fallback boot is claimed.

Both cold boots passed the independent serial-login oracle:

- Linux `7.2.7-arch1-1`, package `linux 7.2.7.arch1-1`, `systemd 262-1`, `base 3-3`.
- PID 1 is systemd, `/etc/os-release` identifies Arch, and `/` is Btrfs on
  `/dev/vdb3` with the expected root PARTUUID.
- `multi-user.target` is active and there are no failed units at the check.
- A random marker written under `/var/lib` in boot 1 survives graceful power-off
  and boot 2; the kernel boot IDs differ.
- Both boots report LoadFile2 size query/copy and EFI-stub launch before the
  independent guest checks. Both guests shut down through systemd.
- The original QCOW2 and EutherBoot ESP retain their pre-test SHA-256 values.

The unadjusted offline image reached a usable login but held multi-user.target
behind `systemd-time-wait-sync.service`, `time-sync.target` and first-boot
`pacman-init.service`. The successful fixture explicitly adds
`systemd.mask=systemd-time-wait-sync.service` to its kernel command line; this
changes neither the base image nor EutherBoot's runtime defaults. The initial
waiting state is saved in `artifacts/arch/offline-time-wait.log`.

Evidence: `artifacts/arch/signature.txt`, `artifacts/arch/manifest.json`,
`artifacts/arch-qemu/result.json` and per-boot serial/debug logs and PPM screenshots.
Fresh extraction and the final two-boot runner were verified. The ordinary GPT
chainload/return, editor save/reboot and editor read-only cases were rerun after
extending the shared QEMU/disk helpers; all three passed. Firmware source and
validated EFI artifact are unchanged. The 68-case matrix recorded below is the
prior LoadFile2 run, not a claim that all 68 were repeated for this fixture change.
TCG fallback exists in the Arch runner but this installed-Arch result used KVM.
An ISO installation, installed-Arch Secure Boot and physical hardware remain
outside this result. The separate kernel-update experiment follows below.

## Arch kernel update and UKI publication

Command: `python3 scripts/arch-update-qemu.py` after preparing the pinned image.
This additional experiment uses QEMU/KVM, ordinary OVMF, 3 GiB RAM, a disposable
1 GiB ESP and an overlay of the same signed Arch basic image. Only the first boot
has user-mode NAT; there are no forwarded ports or shared host directories.
The host package manager, boot files, EFI variables and keys are not involved.

The guest executes a full
`pacman -Syu --noconfirm --needed binutils systemd-ukify`. It installs a stock-linux
mkinitcpio preset extension, a publication post hook, and a pre-transaction ESP
check. The actual observed change is Linux `7.2.7-arch1-1` to `7.2.9-arch1-1`
(package `linux 7.2.7.arch1-1` to `7.2.9.arch1-1`). The pacman log reports normal
initcpio rebuilding and `EUTHERBOOT_UKI_PUBLISHED kernel=7.2.9-arch1-1`.

The new UKI is placed at `\EFI\Linux\arch-linux.efi`. The next two cold boots
select that ordinary EFI entry and independently verify the new running kernel,
installed module version, Arch identity, systemd PID 1, expected root device,
active multi-user.target, no failed units, and the published UKI's SHA-256.
There is no external LoadFile2 initrd on these boots: the UKI embeds its initrd.

Between the two updated-kernel boots, the guest exercises:

| Case | Required outcome |
| --- | --- |
| ESP unmounted | Actual cached-kernel pacman transaction aborts with the expected missing-ESP reason; package state and UKI hash preserved |
| ESP read-only | Preflight rejects with the expected reason |
| Original Arch ESP mounted at the integration mount point | Wrong PARTUUID rejected |
| Malformed staged UKI | Publication rejected; active UKI unchanged |
| Successful cached-kernel reinstall | Standard hook republishes; previous image hash equals the formerly active image, new active file equals generated staging file |
| Abandoned partial staging file | File is synced, QEMU is killed without shutdown, subsequent cold boot still reaches the selected new kernel |

This does not claim general FAT power-loss atomicity: the abrupt termination
occurs after a partial staging file is flushed, not during active-file rename.
The previous UKI is diagnostic only, since old modules are not retained.
LTS recovery, build/I/O/full-disk fault injection, encrypted roots, signing and
physical installation remain open. A post-transaction failure cannot undo
pacman's completed package changes.

Evidence: `artifacts/arch-update-qemu/boot-{1,2,3}/` serial/debug/QEMU logs and menu
screenshots, `result.json`, and `updated-arch.efi` read back independently using
mtools. The original QCOW2 hash and unchanged EutherBoot binary read back from
the ESP are checked at the end. Disposable disks are removed after the test.
The final read-back UKI SHA-256 is
`aad348987236e34097f0e30bfc9c2d8822d2f3161dd59361f8416e8c785c6d02`.
The normal read-only editor QEMU case also passed after extending the shared VM
helper with opt-in networking. Python compilation, shell syntax and diff checks
passed. Firmware source and the previously validated EFI binary are unchanged;
the full earlier 68-case matrix was not rerun for this integration-only change.

## Shared parser and builds

Twenty-five Rust tests cover menu wrap/empty state, the example and safe defaults,
non-first defaults, positive timeouts, malformed TOML, unknown/duplicate fields,
bad types/ranges/themes, duplicate IDs and case-insensitive paths, unsupported
entry types, traversal/aliases, display controls/Unicode and resource bounds.
The host CLI validates the same example with the same no_std parser as firmware.
Draft tests cover isolation, serialization and validation. Transaction tests inject
failed mutations and corrupt readback, reject stale drafts, and preserve a valid
backup during interrupted recovery. Discovery tests reject unsafe names, truncated
headers, drivers and wrong architectures. Selector tests cover canonical GUID
syntax, zero/malformed/wrong-type rejection, case normalization and duplicate
paths scoped to a selector. Draft import preserves default/timeout and roundtrips
the selector, including clearing it back to omission. Linux tests cover typed fields, strict option bounds/conflicts, initrd path
validation, absence of generated initrd= options, EFI-stub version/capability
bounds and draft roundtrips. Both real PE32+ EFI executables build with
Cargo.lock, including the parser. The normal firmware also passes a build check
without debug features.

## OVMF matrix

`./scripts/test.sh` builds/tests and runs **48 independent QEMU cases**. Each has
its own disposable FAT filesystem and firmware-variable copy, with no attached
host disks or networking. Editor tests use a real virtual GPT/FAT disk image. At most three VMs run concurrently. Test steps have
deadlines; an outer timeout interrupts the runner/VM process group.

| Cases | Count | Verified outcome |
| --- | --- | --- |
| Sample, successful child at 1024×768 and 640×480 | 2 | TOML-loaded EFI target starts and returns; menu restored |
| Child ABORTED, missing child, invalid child | 3 | Error retained on menu, no unintended target or retry |
| Nonempty child ExitData | 1 | Three explicit ABORTED returns free 28-byte ExitData and retain menu, including text mode |
| Non-first configured default | 1 | Selection 1 loads a relocated child by its configured path |
| 3s timeout | 1 | Default starts once after the delay; return never rearms it |
| Any-key cancellation | 1 | Unhandled `x` cancels timeout; later explicit Enter works |
| Timeout into missing default | 1 | NOT_FOUND once; no automatic fallback/retry |
| Sixteen configured entries at both resolutions | 2 | Page navigation reaches entry 16, starts correct child and reaches built-ins |
| Missing configuration | 1 | Read error, no configured entries or timer |
| Malformed TOML, unknown field, duplicate ID, unresolved default, traversal | 5 | Entire config rejected; diagnostics and firmware return work |
| Invalid UTF-8, oversize input, direct self-reference | 3 | Entire config rejected before any child starts |
| Sample on virtual GPT/FAT disk | 1 | Same-volume chainloading from the disposable block device |
| Editor discard | 1 | Inspection, preview, cancelled save and discarded draft leave exact original bytes |
| Editor save at both resolutions | 2 | Add/remove entries, default, timeout and theme persist across reboot; added target starts; backup restores original |
| Invalid editor draft | 1 | Self-reference and missing default rejected; explicit default repair validates |
| Read-only disk | 1 | Save reports WRITE_PROTECTED; original unchanged |
| Interrupted save at three checkpoints | 3 | Kill after staging, backup or install; next boot blocks automatic selection; explicit recovery succeeds |
| Linux EFI-stub and UKI at both resolutions | 2 | Same path on two ESPs launches from the selected volume, proven by child-reported GUID; data partition and self-copies excluded |
| Duplicate GPT GUIDs | 1 | All ambiguous ESPs excluded; no targets promoted |
| Empty discovery | 1 | Only self/non-application files present; empty menu remains usable |
| Discovery candidate limit | 1 | 64-target cap is visible as partial; pagination reaches last entry |
| Classified but unloadable image | 1 | Firmware LoadImage rejects malformed section extent; browser retained and another target can start |
| Discovery after malformed TOML | 1 | Configured targets/timer remain disabled; separately confirmed discovered target boots |
| Persisted import at both resolutions | 2 | F4/A import, explicit save, exact backup, manual remote boot and timed reboot with reversed ESP positions |
| Editor picker / discard | 1 | F3/E/I import, duplicate rejection, GUID editing/clearing, preview, cancelled save and discard leave entire disk unchanged |
| Missing GUID, duplicate GUID, non-ESP selector | 3 | Default preflight disables timer; manual attempt fails without fallback; explicit own-volume entry remains usable |
| Implicit/explicit own-volume alias, qualified self-path | 2 | Entire config rejected; no target or timer enabled |
| Exact remote self-copy, missing remote file | 2 | Single automatic attempt fails before LoadImage; no fallback/retry; own entry can still be selected manually |
| Own boot path on another ESP | 1 | Same pathname as EutherBoot itself but a different GUID correctly starts the remote child |

The original five chainload cases each perform three explicit attempts in one
VM, including text mode. Positive configuration cases move the child away from
the original fixed path; the selected target log and actual child execution
prove the config path is used. The first non-default entry points to a missing
file, making accidental selection observable. Timeout tests check a 3-second
interval with host-observation tolerance and wait past the deadline again after
return/failure to reject unintended rearming. Invalid configs request a 1-second
timeout where syntactically possible; tests wait beyond it and require no load.

Screenshots confirm the configured default highlight, error diagnostics and the
last page at 640×480. Pixel comparisons verify the graphical menu is reconstructed
after the child clears the display. Text tests check new console output and
subsequent keyboard navigation, not just log markers. Returning child handles
no longer expose LoadedImage; this is not a complete memory-leak audit.

Reproduce individual cases through `scripts/qemu.py --help`. Evidence is ignored
under `artifacts/qemu-<width>x<height>-<scenario>-<config-case>/`: debug.log,
serial.log, qemu.log and PPM captures. `.efi` artifacts and SHA256SUMS are rebuilt
by scripts/build.sh. Editor evidence is under `artifacts/editor-<case>-<width>x<height>/`,
including logs, screenshots, configuration readback and SHA-256 results.

Editor saves require explicit Y confirmation. Tests verify exact backup bytes,
persistent values after reboot, and removal of transaction markers after recovery.
Reload after saving/recovery does not rearm the timer. Fault injection uses a
separate `EutherBoot-faults.efi`; the normal binary has no FAULT_WAIT hook. The
runner kills QEMU at flushed checkpoints, then boots the normal binary from the
same image. These are controlled interruption tests, not proof against torn
sectors or all physical power-loss behavior. No host boot configuration or
firmware variables were modified by EutherBoot.

The full 48-case suite is exercised by `./scripts/test.sh`; its combined run log
is `artifacts/efi-regression.log`. Discovery uses two ESPs and one non-ESP
FAT partition on one generated GPT disk. Fixtures include identical paths,
a renamed EutherBoot binary on the second ESP, invalid PE data, an AArch64 image,
and an EFI driver. Only eligible targets appear. Enter/cancel does not load an
image; Y starts the selected one. Child-reported LoadedImage GUIDs independently
confirm volume choice. Success and ABORTED return to the browser; R reconstructs
the same sorted target list. Entering discovery cancels the configured timer;
waiting past its deadline in the browser and after exit never triggers boot.

Discovery evidence lives under `artifacts/discovery-<case>-<width>x<height>/`:
debug/serial/QEMU logs, PPM screenshots and a result file with the identical
before/after SHA-256 of the entire writable virtual disk. No disk differences
were observed in these tests. The 640×480 browser and confirmation were visually
inspected for readable identity, path and keyboard controls.

Persisted-selector evidence lives under
`artifacts/cross-volume-<case>-<width>x<height>/`. Save cases export actual saved
TOML and exact backup bytes. After saving, the generated disk is rebuilt with
the exact saved configuration and reversed ESP partition positions; fresh OVMF
variables are used. The next boot resolves the GUID at its new device path and
automatically starts the correct child once. This proves resolution survives
changed virtual partition positions, not physical hot-plug behavior.

All cross-volume cases hash the other two complete FAT partitions before and
after the session. No differences are allowed, including when configuration is
saved on the own ESP. Cases that do not save additionally compare the whole
writable disk hash. Save verification includes default/timeout, omitted own-volume
selector, explicit remote GUID/path, exact old backup and absence of sidecars.
The reordered disk is also unchanged after booting/returning. Child-reported
GUIDs distinguish remote success from accidental own-volume fallback. Imported
drafts were visually inspected at 1024×768 and 640×480: full GUID, path, unchanged
boot policy and editing/saving controls remain readable.

## Linux matrix

`./scripts/test-linux.sh --kernel /usr/lib/modules/7.2.9-arch1-1/vmlinuz`
builds local fixtures and runs **9 additional QEMU cases**, at most two concurrently.
Tested kernel: Linux 7.2.9-arch1-1, CONFIG_EFI_STUB=y; installed systemd stub 262-1.
Each VM uses 768 MiB, TCG CPU max, a disposable two-ESP GPT disk and copied OVMF
variables. No host initramfs/root filesystem or physical disk is attached.

| Cases | Count | Verified outcome |
| --- | --- | --- |
| EFI-stub on own and selected remote ESP | 2 | Real kernel requests/copies LoadFile2 initrd, receives configured command line, reaches diagnostic PID 1 and powers off |
| UKI on own and selected remote ESP, read-only disk | 2 | Embedded kernel, command line and initrd reach diagnostic PID 1 without external options |
| UKI on writable disk | 1 | PID 1 reached; systemd stub creates two 32-byte seed files; existing EFI files and other partition retain exact hashes |
| Missing initrd, non-Linux EFI application as linux-efi | 2 | Rejected before LoadImage; menu retained; explicitly selected recovery child starts and returns |
| Linux editor at 1024×768 and 640×480 | 2 | Full details shown, type change can be cancelled or confirmed, command line and initrd edited and saved with exact backup, real Linux boots before and after reboot with persisted options |

The oracle is independent guest PID 1 output on the serial console: uname,
/proc/cmdline, the expected mode and owner-controlled diagnostic argument, then
poweroff. EFI-stub cases additionally require INITRD_INSTALLED, INITRD_SIZE_QUERY
and INITRD_COPIED, and reject any initrd= argument in serial output. A LoadImage
marker alone does not count as a Linux boot. Remote tests
put invalid payloads at identical paths on the own ESP and require the selected
remote kernel/UKI to reach PID 1 after timeout. Ordinary EFI/UKI entries have no
LoadOptions set by EutherBoot.

The editor fixture removes the original initrd path and saves the renamed path,
so reaching PID 1 requires the edited selection. EFI-stub and negative cases
compare the whole writable disk hash. Editor saves
verify exact TOML, original backup and an unchanged disk on the second boot.
Read-only UKI disks also retain their whole-disk hashes. The writable UKI exception
is explicit: systemd-stub creates `loader/random-seed` and
`loader/boot-secret-mixin`, each 32 bytes. The test retains file names/sizes only,
compares every EFI file hash and verifies bytes after the own ESP are unchanged.
It does not claim the child performs no firmware-variable writes; all variables
are disposable VM copies.

Fixtures, provenance and hashes: `artifacts/linux/manifest.json`.
Combined log: `artifacts/linux-regression.log`; extended editor reruns:
`artifacts/linux-editor-regression.log` and `artifacts/linux-editor-640-regression.log`.
Per-case serial/debug logs,
screenshots and results: `artifacts/linux-<case>-<width>x<height>/`.
The initramfs contains only a generated static /init, console node and directories.
The unsigned UKI embeds that archive and the copied local kernel; no host signing
keys or distribution initramfs content is consumed.

## Secure Boot matrix

`python3 scripts/test-secureboot.py --uki` runs three additional isolated VMs:
1024×768, 640×480, and 1024×768 followed by a signed diagnostic Linux UKI.
The first two disks are writable; the UKI disk is read-only. The entire disk hash
is unchanged in all three. Each VM uses Secure Boot OVMF, q35 SMM, secure pflash,
a fresh copied/enrolled variable store and independently generated RSA test keys.
The host firmware, key databases and source EFI files are unchanged.

Tools: sbsigntools 0.9.5 and virt-firmware 26.9. The sbsigntools Arch package was
extracted into ignored `.tools/`, and its detached package signature verified with
the distribution keyring. virt-firmware runs in a project-local Python venv.
Tools are used as separate executables; no signing/firmware parsing code was copied.

Every VM demonstrates:

- An unsigned configured default attempts once at timeout, is refused and does
  not restart or automatically select another target.
- A trusted signed child starts and independently reads `SecureBoot=1` and
  `SetupMode=0` using firmware runtime services.
- Unsigned, unknown-key, tampered-signature and dbx-revoked-certificate children
  each fail three manual attempts before StartImage. The revoked certificate is
  present in both db and dbx; tampering changes an authenticated DOS-stub byte.
- A trusted child starts after each category of refusal, then exits with 28 bytes
  of ExitData that EutherBoot frees. Later refusals and returns exercise text mode.
- Exactly 13 refusals and 5 trusted-child launches occur. This OVMF returns
  `ACCESS_DENIED` with no rejected handle in all 39 refusals across the matrix.
  `SECURITY_VIOLATION` with an optional loaded handle remains unexercised.

The third VM additionally starts the signed UKI and independently reaches Linux
7.2.9-arch1-1 diagnostic PID 1 with the embedded command line/initramfs, then powers
off. Linux EFI-stub with an external unsigned initrd is not a Secure Boot integrity
claim. No shim/MOK/SBAT, TPM, installed distribution or physical firmware is tested.

Evidence: `artifacts/secureboot-matrix.log`, plus per-case
`artifacts/secureboot-<width>x<height>[-uki]/result.json` and `boot-1/` logs/captures.
Results record source/payload hashes, public certificate fingerprints, refusal
counts and whole-disk hashes. Private keys, signed copies and firmware variable
stores remain temporary and are removed after each test. The 640×480 graphical
refusal and text-mode refusal were visually checked for legible diagnostics and
usable navigation.

## LoadFile2 protocol and lifetime matrix

`./scripts/build.sh`, `./scripts/build-faults.sh`, then
`python3 scripts/test-initrd.py` exercises **8 additional QEMU cases**:

| Cases | Count | Verified outcome |
| --- | --- | --- |
| Returning consumer, both resolutions | 2 | Null arguments, unsupported boot policy/path, size query, unchanged undersized buffer, exact/oversized copies with byte hashes and trailing canaries; three starts/returns |
| Partial protocol installation failure | 1 | Injected failure after DevicePath registration rolls back, unloads the unstarted child and retains the menu |
| Cleanup refusal, both resolutions | 2 | Injected removal error retains provider/code; Esc/Enter cannot leave; explicit R retries and restores menu |
| EFI-stub v0 capability | 1 | Rejected before LoadImage; no path-based fallback |
| Empty initrd | 1 | Rejected before registration/LoadImage |
| No initrd configured | 1 | Child starts without an installed initrd provider |

The consumer is TestChild code with moved PE headers/file offsets and synthetic
Linux HdrS/EFI-stub identification fields. It is an EFI protocol fixture, **not**
a Linux boot result. Its 4097-byte deterministic payload is checked independently
using byte count/FNV and canaries. Each case makes three explicit attempts and
alternates with an ordinary EFI child that independently locates the Linux initrd
path and requires it to be absent. Final attempts also exercise nonempty ExitData.
All eight writable GPT/FAT disks retain their complete pre-run SHA-256 hashes.

The fault artifact alone reads initrd-fault. `install` simulates a failed second
protocol registration; `cleanup` reports ACCESS_DENIED once per provider before
calling real removal on the explicit retry. These are controlled branch tests,
not evidence that OVMF naturally refuses these operations. Normal-OVMF kernel
boots use the production artifact, not fault hooks. Logs/screenshots/results:
`artifacts/initrd-<case>-<width>x<height>/`; combined log:
`artifacts/initrd-regression.log`. Cleanup-blocked and restored-menu captures at
640×480 were visually checked.

Current-build checks: 25 Rust tests, config validation, real EFI builds, formatting,
no-debug firmware check, all 48 normal OVMF cases, 9 real Linux cases, 3 Secure Boot
VMs and these 8 protocol cases (**68 QEMU cases total**). Logs are
`artifacts/efi-regression.log`, `artifacts/linux-regression.log`,
`artifacts/secureboot-matrix.log` and `artifacts/initrd-regression.log`.

## Limits

No physical machine, production Secure Boot trust store, multiple physical disks
or hot-plug behavior has been demonstrated. Installed-distribution coverage is
currently limited to the pinned Arch basic image and its upgraded normal/LTS
kernels under OVMF, including disposable owner-key Secure Boot. Diagnostic Linux
tests use a separate minimal initramfs and one systemd stub. Multiple
initrds and arbitrary non-EFI kernel loading are absent. LoadFile2 does not
authenticate external initrds or command lines. A pre-existing provider is rejected
by policy, but the foreign-provider collision branch is not yet integration-tested.
Initrd allocation exhaustion, mid-read I/O errors/file growth and genuine firmware
removal refusal are not injected; partial registration and synthetic removal
refusal are covered. An unrecoverable removal failure requires power-off. Multiple ESPs on a virtual GPT disk are covered.
Editor preferences persist in TOML; NVRAM preferences are not implemented.
The editor cannot create the first configuration or repair raw malformed TOML;
a valid backup can be restored explicitly. FAT rename is not power-loss atomic. Input waits on firmware events with a polling fallback; the timeout uses a
firmware timer. Timer creation/check failures and allocation exhaustion are
handled but not fault-injected. Automatic GOP failure fallback is not injected;
manual text fallback is tested. Only printable ASCII labels/paths are supported.
Directory-backed FAT, single-ESP GPT and multiple-ESP GPT are exercised. MBR,
superfloppy and firmware lacking PartitionInfo remain unsupported for discovery.
The target-count limit is exercised; exhaustive directory/depth/read-budget and
I/O fault injection is still outstanding. Exact copies of the current on-disk
binary are excluded for discovery/GUID-qualified launches; different builds/signed
copies are not. Legacy unqualified entries retain the path-only self check.
A valid but absent selector may be saved; validation is not availability or trust
verification. Import with an invalid live config or pending transaction is blocked;
these import-specific refusal branches have not been separately fault-injected.
See ARCHITECTURE.md for loader cleanup and self-copy limitations.

Historical pre-event-input artifact SHA-256 (PE timestamps change on relink).
The final source relink differs only in COFF/debug-directory timestamp fields;
`artifacts/loadfile2-relink-check.txt` records that comparison. The tested artifact
is retained:

```text
e5aeba5e876682fdc3648e09fbeb06eea260aae1ddac5b15c19fe0fbcfc38b63  artifacts/EutherBoot.efi
c8b2aa005a71407c6d9f805e9f19c83e5a47adf3d42f009d075744e1992f0b90  artifacts/TestChild.efi
```

## Event-driven input and GPL-3.0-only

The menu, editor and discovery now wait on firmware keyboard events. Timer
signals consumed by WaitForEvent are retained; a queued key still takes priority
over automatic boot. Broken event firmware falls back to polling with a diagnostic.
All 25 core tests and 48 ordinary OVMF cases passed after this change, including
timeout firing/cancellation, return paths, editors and cross-volume discovery.
The owner selected GPL-3.0-only; Cargo metadata and LICENSE now declare it.

## Managed Arch installation and recovery

The initial complete run of `scripts/arch-release-qemu.py` passed side-by-side
installation, normal Linux 7.2.9-arch1-1, LTS, current-kernel package reinstall,
recovery after an intentionally damaged active UKI and missing module directory,
LTS-assisted repair, original Linux 7.2.7-arch1-1 recovery, and uninstall. The
original fallback EFI child then started successfully and matched its initial
hash; the pinned original Arch image also remained unchanged. All installed
normal/LTS/recovery starts used Secure Boot with a disposable OVMF owner key.
Each Linux oracle checked expected uname, systemd/root identity, multi-user.target,
no failed services, and loading the real `dummy` module with matching vermagic.
Evidence for that run is retained under `artifacts/arch-release-initial-pass/`.

The original 7.2.7 archive is captured by the fixture before installing integration
prerequisites; it proves old-kernel/module recovery, not that the installer existed
before that bootstrap upgrade. Automatic pre-transaction capture is exercised by
the later installed-kernel reinstall. The older update fixture independently
proved an actual 7.2.7 to 7.2.9 pacman upgrade. No result implies userspace rollback.

Generation-pruning tests exercise read-only plans, actual deletion in temporary
files, and refusals for selected/pending/configured generations, wrong identities,
symlinks and path escapes. They mock ESP identity and redirect the process lock;
they do not claim physical storage or firmware coverage.

The expanded final run additionally passed a signed upgrade from the diagnostic
manager to the non-instrumented release EFI, automatic timeout boot into LTS,
and an empty debug-port trace. Wrong ESP identity, duplicate installation and
removal with a locally modified integration file were refused. After restoring
that test edit, removal succeeded and the original fallback child booted again.
This run's complete evidence is `artifacts/arch-release/result.json` and its nine
boot directories. Tested kernels were 7.2.9-arch1-1, 6.18.55-1-lts and retained
7.2.7-arch1-1. The host boot configuration was not touched.

The current event-driven EFI also passed all 68 ordinary/Linux/LoadFile2/Secure
Boot cases; logs are `artifacts/release-{core,linux,initrd,secureboot}-tests.log`.
Eight installer generation-policy tests passed. The packaged source archive was
extracted to a separate directory and passed its 25 Rust tests and a real release
UEFI build with `--offline --locked` using the bundled dependencies. GitHub's
Rust/EFI workflow passed for commit `5fd4b47`.

Validated EFI hashes (the release package manifest includes all distribution files):

```text
3b1d1026a7de035537df5da12e5fb83f6fcd931601bc816effe968b5332bc5eb  artifacts/EutherBoot.efi
c674a24b4b5fc15793fd6775bd0a725599a4cbde753708b66e9c76cd18e6d823  artifacts/release/EutherBoot.efi
```

## Host inventory and Arch update guards

Read-only inventory identified FAT `/boot`, Btrfs `@`, udev initramfs, explicit
NVIDIA modules, multiple retained `pkgbase=linux` trees and insufficient free ESP
space for the managed UKI/recovery layout. Machine-specific details and a read-only
plan for chainloading the existing loader are kept under ignored `artifacts/`.
No host packages, boot files, hooks or firmware variables were changed.

Twelve installer tests now pass, including payload-based sizing for a 257 MiB
synthetic initramfs and preserving the active EFI file when actual staging space
is insufficient. These use temporary sparse files and controlled capacity/image
oracles. Installed-module selection now uses pacman's ownership list and checks
that its kernel matches `/boot`.

`artifacts/arch-hooks/result.json` records a passing offline Arch test with actual
pacman/libalpm: an external-module path triggers pre and post hooks, and a failing
pre-hook prevents the second package transaction from replacing the installed
version/payload. The hooks' Exec commands are assertion oracles in this fixture;
real NVIDIA/DKMS operation remains untested. The signed base image and read-only
virtual ESP were unchanged.

The additional 1 GiB shared-`/boot` run rejected installation with approximately
419 MiB free before creating an EFI installation, integration file or journal.
After removing its temporary filler, it installed and booted the Btrfs `@` root
with udev initramfs, active swap and no failed services. The later real pacman
transaction was then correctly refused: the generation budget required
616,449,828 bytes but only 528,293,888 were free. Pacman reported that no packages
were upgraded. These partial-run logs are retained under
`artifacts/arch-host-layout-capacity-refusal/`; they establish the refusal and
first boot, not a completed recovery matrix on 1 GiB.

Preparing the `@` fixture first exposed its separately nested swap subvolume,
and then the cloud image's lack of an explicit root fstab entry. The fixture now
adds explicit root and swap mounts. The failed runs remain distinct from passing
evidence and are not attributed to a firmware or bootloader defect.

The prepared USB-image file also passed an independent QEMU test using the exact
non-instrumented release EFI. Framebuffer observations establish that the System
Regis menu is displayed before input; Enter starts a test child on the explicitly
selected second ESP, and returning restores the menu. Both disk-image hashes are
unchanged. Evidence: `artifacts/host-probe/usb-result.json` and PNG captures under
`boot-1/`. The second ESP is a disposable stand-in with the requested partition
identity; this is not a physical GRUB boot. No image was flashed to physical media.

The complete `btrfs-at-udev` matrix subsequently passed with a **2 GiB virtual
ESP**. `artifacts/arch-host-layout/result.json` records the actual size and all
seven managed Linux boots, plus bootstrap and the original fallback child.
Every managed boot verified FSROOT `/@`, FAT `/boot`, the expected kernel, working
module loading and no failed services, including swap. Installation refusal at
approximately 419 MiB free was exercised before the positive run. Current/LTS,
missing-module recovery, original-kernel recovery, repair, signed release upgrade,
automatic boot and uninstall passed with disposable owner-key Secure Boot.
The original Arch image and fallback loader hashes were unchanged.

This is not evidence that the complete generation store fits the inventoried
1 GiB host ESP, nor that NVIDIA hardware or the physical firmware has passed.
The large-initramfs capacity case is synthetic, and the guest uses virtio/Btrfs
modules instead of NVIDIA. Hardware testing remains a separate gate.

## Physical USB chainload — 0.1.1, 2026-10-11

User-supplied photo shows EutherBoot 0.1.1 discovery with two firmware
filesystems, two verified ESPs, one application at `\EFI\BOOT\BOOTX64.EFI`
and one skipped candidate. The user reports Escape returned to the graphical
menu, selecting the existing loader opened GRUB, and choosing Arch reached
the running desktop. The subsequent host inventory reports 7.2.9-arch1-1,
matching the installed linux package. Evidence: `artifacts/physical-0.1.1/`.

This establishes the configured physical chainload path on this machine. It
does not establish the precise cause of the 0.1.0 failure, direct discovery
launch, physical editor/save recovery, Secure Boot or managed UKI installation.
The unchanged internal path without USB has no separate reported control test.

## System Regis main-menu revision — 2026-10-11

The local development renderer embeds antialiased Liberation-derived glyphs
(OFL license included), rounded gradient cards, supersampled geometry and a
three-crown emblem. Left/right joins existing up/down navigation. Entry-name
icon hints are decorative and do not change the configured boot target.

Validation on the final renderer: 29 boot-core tests, configuration validation
and release-profile UEFI build passed. Eight QEMU cases passed: sample
start/return at 1024×768 and 640×480, 16-entry pagination at 640×480 and
1920×1080, missing target, aborted child, timeout and cancellation. Sample
cases also exercise left/right, text mode and repeated child start/return.
The discovery multiple-volume case passed at 640×480 during UI development
with the complete virtual GPT/FAT disk unchanged. Main-menu screenshots were
visually inspected; manifests and captures remain in ignored artifacts.

Evidence: `artifacts/regis-ui-result.json`, `artifacts/qemu-*/first-light.png`,
`artifacts/qemu-*-return-many/` and `artifacts/discovery-*`.
This is a local QEMU-debug development binary, still labeled 0.1.1, not a new
physical USB delivery. F4 and editor retain their text UI. No physical test of
the revised graphics or release deployment has occurred.

## Approved emblem and live countdown — 2026-10-11

The approved transparent steel-sword/gold-crown artwork is now embedded as a
bounded 144×144 RGBA asset; the compact layout renders it at 96×96. The original
PNG and conversion script are retained in the source tree. The Arch installation
example now specifies 10 seconds; explicit zero and omitted timeout retain their
existing wait semantics, and no saved or physical USB configuration was modified.

The final build passed 29 core tests and six QEMU cases recorded in
`artifacts/regis-emblem-countdown-result.json`: zero-timeout sample start/return
at 1024×768 and 640×480, 10-second countdown, 3-second countdown at 640×480,
cancellation after a displayed tick, and timeout to a missing target. The tests
observe changed framebuffer pixels after a completed countdown redraw, bound
the actual boot time, and check that cancellation stops further ticks and that
return/failure does not rearm automatic boot.

The first countdown capture exposed a test synchronization race: the trace was
emitted before GOP redraw completed. The completion trace now follows rendering;
the assertion still requires an actual framebuffer change. Screenshots of the
final countdown and embedded emblem were visually inspected at both resolutions.
The independent deadline remains authoritative if display ticks are delayed.
No physical UI or autoboot test, USB write, or internal installation occurred.

## Grafisk editor och rescue-leverans 2026-10-11

- 31 boot-core-tester godkända; normal- och felinjektionsbygge godkända.
- Tio editorfall godkända i QEMU: appearance och save vid 1024×768/640×480,
  discard, readonly, invalid samt avbrott efter stage/backup/install.
- Appearance provar språk/teman, svenska namn, förhandsvisning, avbrytning och
  beständig konfiguration efter omstart. Bildkontrollen väntar på färdigrenderad
  palett; ett första 1024-test läste föregående bild för tidigt och kördes om.
- Huvudmenyns sample (640×480), countdown och cancel (1024×768) godkända.
- Evidens: `artifacts/editor-validation/{result,menu-result}.json`, fallens
  loggar och EFI-hash i respektive result.txt. Lågupplöst editor granskad visuellt.
- Fysiskt UEFI-tangentbord med svenska tecken och ny grafik återstår.
- Rescue-USB skrivet och fsync slutförd. Full återläsning uttryckligen bortvald
  av användaren; GPT jämförd och partitioner monterade. Fysisk start återstår.
  Rescue innehåller den äldre källsnapshoten 17e20d9, inte den nya editorn.

## Rescue: fysisk start och korrigerad Codex-launcher

2026-10-11: användarfoto bekräftar fysisk rescue-start till autologin. Codex
misslyckades med saknad state-katalog och därefter ENOSPC. Den levererade ISO:n
reproducerade ENOSPC vid riktig terminalstart i QEMU; `--no-daemon` nådde
inloggningsvyn. Version/help-testerna från första leveransen var otillräckliga.

Aktuella launchers injicerades i en disponibel gästs RAM med oförändrad ISO.
`scripts/test-rescue-start-qemu.py` passerade: rescue-start från tomt state,
inloggningsvy, katalogläge 700, --version vidarebefordrat, login status visar
Not logged in, ingen auth-fil eller daemoninstallation. Resultat och
launcherhashar: `artifacts/rescue/codex-start-fixed-result.json`.
Detta verifierar inte en ombyggd ISO, uppdaterad sticka eller autentiserad
AI-session. Den fysiska stickans workaround finns i rescue/README.md.

## Rescue 0.1.1: ombyggd avbild

ISO SHA-256: `958f0a2614c80c6da17124743a4a613e9519e6c8aeaaa11038ed174c6c18e44b`.
Källsnapshot: `e89ed0b`, inklusive grafisk editor och korrigerad Codex-launcher.
Bygggästen slutförde mkarchiso och explicit sync; avstängningen överskred
60 sekunder. Avbilden hämtades från transferdisken efter att gästen stoppats.
Nästa byggning tillåter 180 sekunder för gästens avstängning.

Verifierat på den färdiga avbilden: Codex inloggningsvy från tomt state med
`--installed-launchers` (hashkontrollerade inbyggda skript, ingen injicerad fix),
katalogläge 700, ingen auth eller daemoninstallation och argumentvidarebefordran.
Komplett USB-avbild klarade två UEFI-starter, nätverk, bootkopians checksummor,
återkopiering till tom FAT och arbetsfil som överlevde omstart. Inga interna
diskar eller värdens inloggning anslöts till testgästerna. Autentiserad session
är fortfarande inte verifierad. Fysisk leverans dokumenteras i HANDOFF.md.

Fysisk USB-leverans av rescue 0.1.1 slutförd efter Polkit-autentisering.
Blockjämförelse följd av skrivning av avvikande block och fsync; båda GPT-
kopiorna matchar, sex EFI-partitionsfiler (inklusive kärna och initramfs)
hashmatchar avbilden och datapartitionen monteras. Separat full
återläsning hoppades över enligt uttryckligt tidigare önskemål. Fysisk start
av denna nya utgåva återstår. Se lokal `artifacts/rescue/usb-delivery.json`.

## Separat direktstart-USB för installerat Arch

`scripts/prepare-direct-probe.py` byggde två UKI:er av aktuella kernel-/initramfs-
kopior. Tillagda PE-sektioner extraherades och hashmatchades med originalen.
Release-menyns normal- och fallback-val nådde faktisk initramfs i QEMU med rätt
kärnmarkör; saknad fysisk root bekräftades via skärmbild/OCR. GRUB-reservposten
valde rätt virtuell ESP och testapplikationen återvände till menyn. Inga interna
diskar var anslutna. Detta är inte fysisk NVIDIA-/Arch-inloggningsverifiering.

Kingston DataTraveler-leveransen är fsync:ad, GPT-kopior kontrollerade och sex
filhashar (båda UKI:er, manager, konfiguration, källarkiv, licens) verifierade.
Alla 366 värdbootfiler är oförändrade. Lokal evidens finns i `artifacts/direct-probe/`
och `artifacts/direct-delivery/`. Instruktion och begränsningar finns i
[DIRECT-ARCH-USB.md](DIRECT-ARCH-USB.md). Rescue/Codex har separat fysisk
användarbekräftelse; direkt Arch-start från den nya stickan återstår.
