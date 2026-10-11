# Debian 13 boot investigation · 2026-10-11

## Follow-up: release 0.1.2

The release now supports initrd through **512 MiB** and prints actual size
and maximum on rejection. Current `debian-qemu.py` cases are `normal`, `large`
(128 MiB + 1), `maximum` (512 MiB), `limit` (512 MiB + 1), `empty` and
`cmdline` (synthetically reduced kernel command-line capacity). The latter
three must retain the menu and allow recovery. `--production --firmware PATH`
uses autoboot and the real Debian serial oracle without requiring debug traces.

The original investigation below remains historical; its three result
directories were moved into `artifacts/debian/investigation-011/`. The
experimental 256 MiB build is not the delivered production release.

The user reported Debian 13 failing with `Linux EFI setup: BAD_BUFFER_SIZE.
Menu retained.` on a physical machine. Windows recovery and Pop!_OS started
through F4 on that machine. Its configuration, kernel and initrd have not been
collected; further physical testing was deferred.

## Original 0.1.1 results

QEMU/KVM, OVMF, 2 GiB RAM, no guest network, disposable ESP and Debian root
overlay. The source was the [official Debian 13 generic AMD64 cloud image](https://cloud.debian.org/images/cloud/trixie/latest/),
verified against SHA512SUMS downloaded over HTTPS from the same directory.
The image reports Debian 13.7 and kernel `6.12.111+deb13-amd64`. This is a
cloud image, not a reproduction of the user's desktop installation.

| Test | Initrd bytes | EutherBoot cap | Observed outcome |
| --- | ---: | ---: | --- |
| Original Debian kernel and initrd | 36,847,801 | 128 MiB | Debian serial login reached |
| Same initrd with trailing zero padding | 134,217,729 | 128 MiB | Exact photographed error; recovery EFI child still starts and returns |
| Same padded initrd, isolated experimental build | 134,217,729 | 256 MiB | Debian serial login reached |

The experiment changes only `size > 128 * 1024 * 1024` to
`size > 256 * 1024 * 1024` in a separate source copy under
`artifacts/debian/experiment`. At that stage production loader source and installed boot
files were not modified. This is evidence for the size-limit mechanism,
not a validated production policy change or a confirmed physical diagnosis.

Successful tests first boot with `init=/bin/bash`, verify `/etc/os-release`,
the exact kernel version and EFI presence, then execute `/sbin/init` and wait
for the Debian login prompt. Both reach multi-user.target. Both also report
an SSH service failure; full service health and graphical desktop behavior
are outside this boot test. The original QCOW2 and each test ESP retained
their full SHA-256 hashes. Only disposable root overlays were writable.

The tested kernel advertises a 2,047-byte command-line capacity, above
EutherBoot's 1,024-byte configuration maximum. The command-line length check
therefore cannot explain BAD_BUFFER_SIZE for this particular kernel and a
valid configuration. Empty initrd and propagated firmware errors remain other
possible paths; the physical files are still needed.

## Evidence

All local artifacts are ignored by Git under `artifacts/debian/`:

- `manifest.json`: source image hash, partition identities, kernel/initrd hashes.
- `normal/result.json`, `limit/result.json`, `large/result.json`: test outcomes.
- Each case's `boot-1/`: debug log, serial log, QEMU log and screenshots.
- `build.log`, `experiment-build.log`: build results.
- `experiment/CHANGE.txt`: single experimental change.

Source QCOW2 SHA-256:
`07f9fe05fe7cb1702047034830150baddd66c8be06e233bb226c84aa8a275263`.
Baseline debug EFI SHA-256:
`c1c324917ff697a0e8bf162cccc2cfbd980b06576c024621dc98554b5d488c23`.
Experimental debug EFI SHA-256:
`9ad6908cc4aed09f287f05e1f3027bf0b1fde764b37840a378c1573e6cf4d6a5`.

## Reproduction

Download `debian-13-generic-amd64.qcow2` and `SHA512SUMS` from the linked
directory into `artifacts/debian/download/`. Keep the verified cached files
together: `latest` changes over time. Then run:

```sh
bash scripts/build.sh
python3 scripts/prepare-debian.py
python3 scripts/debian-qemu.py --case normal
python3 scripts/debian-qemu.py --case limit
```

For the current 0.1.2 release, run the additional boundary/error cases and
the production EFI without debug traces:

```sh
python3 scripts/debian-qemu.py --case large
python3 scripts/debian-qemu.py --case maximum
python3 scripts/debian-qemu.py --case empty
python3 scripts/debian-qemu.py --case cmdline
bash scripts/package-release.sh
python3 scripts/debian-qemu.py --case maximum --production --firmware artifacts/release/EutherBoot.efi
```

The earlier isolated 256 MiB experiment's source and binary remain in
`artifacts/debian/experiment/`; do not use them for a new production delivery.

Next physical investigation: read the selected Debian entry and its actual
initrd byte size, kernel header capacity and EFI identity. Do not infer that
the photographed 0.1.1 build is byte-identical to this local debug build.
No physical test or boot-media update was performed during that initial
investigation. The subsequent 0.1.2 rescue delivery is recorded in HANDOFF.md.
