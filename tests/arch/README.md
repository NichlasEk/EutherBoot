# Arch installed-system fixture

`arch-boxes.asc` is the **public** arch-boxes signing key published in the
[official Arch project README](https://github.com/archlinux/arch-boxes#readme),
retrieved on 2026-10-10. Primary fingerprint:
`1B9A16984A4E8CB448712D2AE0B78BF4326C6F8F`.
The preparation script checks this fingerprint in GPG's machine-readable
`VALIDSIG` result, in an isolated temporary keyring.

The pinned official `basic` image is version `20261001.604814`:
[versioned mirror directory](https://geo.mirror.pkgbuild.com/images/v20261001.604814/).
Its SHA-256 is `f9fa16c40e6ac9c03fd28a9ba12fa6ab58b5648ac444a6d27b31ee5bd9913186`.
Downloads and extracted guest payloads stay in ignored `artifacts/`.
This image contains an existing Arch installation; we do not claim an ISO install.
The image's public test credentials are `arch` / `arch`. No guest network is attached.

Use `python3 scripts/prepare-arch.py`, then `python3 scripts/arch-qemu.py`.
Preparation requires curl, GnuPG, qemu-img and btrfs-progs in addition to the
normal QEMU/GPT tools. It reads the signed QCOW2, uses sparse regular files to
extract its kernel and initramfs, and never mounts a host filesystem or uses sudo.
Keep several GiB available for temporary data; the sparse virtual disk is 40 GiB.
The versioned download may eventually disappear from upstream mirrors; preserve
the verified cache for offline reproduction. Never silently substitute `latest`.
