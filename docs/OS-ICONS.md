# Operating-system icons

EutherBoot identifies an icon from the boot entry's **display name**. For
example, `Debian GNU/Linux (reserv)` gets the Debian spiral, `Windows Boot
Manager` gets the window, and `Arch Linux LTS (reserv)` gets the Arch symbol.
Matching ignores ASCII case and punctuation and uses whole words: `Research`
and `Archived backup` do not accidentally select Arch. No boot target, disk
selection, kernel, command line or entry configuration is changed by an icon.

The 32 embedded icons cover Windows; Arch, Debian, Ubuntu, Linux Mint, Fedora,
openSUSE, Manjaro, EndeavourOS, Pop!_OS, elementary, Gentoo, Slackware, Alpine,
NixOS, Void, Kali, Parrot, Zorin, Rocky, AlmaLinux, CentOS, Red Hat, Artix,
Garuda, MX, Nobara, Kubuntu, Lubuntu, Xubuntu, Ubuntu MATE; and generic Linux.
Distribution variants take priority over parent names. Unknown entries retain
the terminal icon. Custom display names without a recognized OS name need
that name added to show a distribution-specific icon.

Icons use antialiased 64x64 masks embedded in the EFI binary, with no runtime
SVG parsing or external icon files. Colors are adjusted for the dark/light
card background; high contrast uses white silhouettes. Text mode continues
to use ordinary entry labels. The SVG sources, license metadata, pinned source
revision and rebuilding instructions are in
`crates/uefi-app/assets/icons/`. `scripts/build-os-icons.py` reproduces the masks
and writes a gallery to `artifacts/icons/icon-sheet.png`.

Most shapes come from [Simple Icons](https://github.com/simple-icons/simple-icons).
Its collection license and disclaimer are included, together with the upstream
metadata for each mark. The generated masks retain each source icon's license;
rasterization, padding and theme color adjustments are the local changes.
Source-specific Creative Commons terms are linked below:

- Debian: [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)
- Gentoo: [CC BY-SA 2.5](https://creativecommons.org/licenses/by-sa/2.5/)
- NixOS: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Rocky Linux: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Fedora: [brand guidelines](https://docs.fedoraproject.org/en-US/project/brand/)
- Garuda and MX: GPL-3.0-only; source SVGs are included.

This is **icon support**, not a claim that the Arch-specific package installer
or update hooks support Debian, Windows or the other listed systems.
