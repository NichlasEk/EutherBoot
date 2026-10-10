# Roadmap

| Milestone | State | Required evidence |
| --- | --- | --- |
| A · First light | Demonstrated | EFI executable renders title/emblem in QEMU/OVMF; captures at 1024×768 and 640×480 |
| B · First choice | Demonstrated in QEMU | Keyboard-event-driven menu/editor/discovery, arrow-key selection, wrap, Enter, F2, return and pagination; timer/key ordering verified |
| C · First boot | Demonstrated in QEMU | Independent EFI child starts and returns; missing/invalid image and ABORTED cases preserve the menu |
| D · Configuration | Demonstrated in QEMU | Shared Rust TOML parser, own-volume config reads, optional GPT partition selectors, strict validation, default and cancellable one-shot timeout |
| E · Editor | Demonstrated in QEMU | Keyboard drafts, discovery import, partition selector editing, preview, confirmed save, backup and explicit recovery on GPT/FAT |
| F · Compatibility | Started in QEMU | Multiple GPT ESPs, Linux EFI-stub with LoadFile2 initrd/command line and UKI reach diagnostic Linux PID 1; virtual owner-key Secure Boot tested; installed Arch reaches systemd/Btrfs root across two cold boots; broader distributions and firmware remain |
| G · Hardware | Not authorized or tested | Dedicated machine, separately approved installation, known-good boot path and rollback |

Read-only discovery is demonstrated: F4, stable partition GUIDs, full device paths,
exact self-copy exclusion, duplicate-GUID rejection and no automatic defaults.
Cross-volume selections now persist through TOML/editor and resolve again after
reboot, including reordered GPT partitions. Missing/ambiguous selectors never
fall back to another volume. LoadFile2 delivery now reaches Linux PID 1; returning protocol consumers verify
copy semantics and cleanup. Installed Arch now boots its own kernel/initramfs from
a separate virtual ESP with persistent root writes across two cold boots. Next:
broader kernel/stub compatibility and initrd memory/failure limits.
The optional Arch update fixture now exercises a guest pacman upgrade, automatic
UKI publication and boot into the updated kernel, plus selected refusal and
interruption cases. The separate managed installer now includes LTS, retained kernel/module
generations, optional signing, binary upgrades and removal. Its expanded
installation/recovery matrix is tracked separately in validation evidence.
Secure Boot acceptance/rejection is demonstrated with disposable owner keys in
OVMF, including a signed diagnostic UKI; production/hardware trust remains open.
Richer editor styling and Unicode remain refinements.

C demonstrates a known unsigned application under ordinary OVMF, not arbitrary
OS compatibility. Nonempty child ExitData is now freed and tested across repeated returns.
Optional rejected-handle cleanup and resource-exhaustion behavior remain
explicit compatibility gates. No physical installation is implied.

Open questions: Unicode configuration/display policy,
removable-media policy, variable persistence contract, Secure Boot trust model,
initrd authentication policy, localization, and physical power-loss behavior of configuration saves.
