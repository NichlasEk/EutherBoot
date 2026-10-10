# Roadmap

| Milestone | State | Required evidence |
| --- | --- | --- |
| A · First light | Demonstrated | EFI executable renders title/emblem in QEMU/OVMF; captures at 1024×768 and 640×480 |
| B · First choice | Started | Arrow-key selection, wrap, Enter, F2 and return demonstrated; real boot entries and event-driven input remain |
| C · First boot | Demonstrated in QEMU | Independent EFI child starts and returns; missing/invalid image and ABORTED cases preserve the menu |
| D · Configuration | Schema proposal only | Rust firmware TOML parsing, strict validation, default/timeout, virtual ESP read tests |
| E · Editor | Not implemented | Read-only inspection, drafts, preview, explicit transactional save and interrupted-save recovery |
| F · Compatibility | Not implemented | Linux EFI-stub/UKI, initrd/command line, multiple ESPs, signed/rejected images and recovery matrix |
| G · Hardware | Not authorized or tested | Dedicated machine, separately approved installation, known-good boot path and rollback |

Next: read and validate TOML from the application's own virtual volume, replacing
the fixed test entry with explicit configured EFI entries. Add read-only discovery
with stable volume identity, self-exclusion and no automatic target guessing.

C demonstrates a known unsigned application under ordinary OVMF, not arbitrary
OS compatibility. Firmware authentication rejection, child exit-data ownership
and resource-exhaustion behavior remain explicit compatibility gates before
third-party/Secure Boot support. No physical installation is implied.

Open questions: final project license, no_std TOML parser choice and limits,
removable-media policy, variable persistence contract, Secure Boot trust model,
initrd protocol strategy, localization, and power-loss-safe configuration saves.
