# Roadmap

| Milestone | State | Required evidence |
| --- | --- | --- |
| A · First light | Demonstrated | EFI executable renders title/emblem in QEMU/OVMF; captures at 1024×768 and 640×480 |
| B · First choice | Started | Arrow-key selection, wrap, Enter, F2 and return demonstrated; configured EFI entries and pagination now work; event-driven input remains |
| C · First boot | Demonstrated in QEMU | Independent EFI child starts and returns; missing/invalid image and ABORTED cases preserve the menu |
| D · Configuration | Demonstrated in QEMU | Shared Rust TOML parser, own-volume config reads, optional GPT partition selectors, strict validation, default and cancellable one-shot timeout |
| E · Editor | Demonstrated in QEMU | Keyboard drafts, discovery import, partition selector editing, preview, confirmed save, backup and explicit recovery on GPT/FAT |
| F · Compatibility | Started in QEMU | Multiple GPT ESP discovery and explicit cross-volume EFI child launch demonstrated; Linux EFI-stub/UKI, initrd/command line and Secure Boot remain |
| G · Hardware | Not authorized or tested | Dedicated machine, separately approved installation, known-good boot path and rollback |

Read-only discovery is demonstrated: F4, stable partition GUIDs, full device paths,
exact self-copy exclusion, duplicate-GUID rejection and no automatic defaults.
Cross-volume selections now persist through TOML/editor and resolve again after
reboot, including reordered GPT partitions. Missing/ambiguous selectors never
fall back to another volume. Next: broader third-party chainloader cleanup and
Linux EFI-stub/UKI compatibility as separate gates.
Event-based input, richer editor styling and Unicode remain refinements.

C demonstrates a known unsigned application under ordinary OVMF, not arbitrary
OS compatibility. Firmware authentication rejection, child exit-data ownership
and resource-exhaustion behavior remain explicit compatibility gates before
third-party/Secure Boot support. No physical installation is implied.

Open questions: final project license, Unicode configuration/display policy,
removable-media policy, variable persistence contract, Secure Boot trust model,
initrd protocol strategy, localization, and physical power-loss behavior of configuration saves.
