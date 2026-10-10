# Roadmap

| Milestone | State | Required evidence |
| --- | --- | --- |
| A · First light | Demonstrated | EFI executable renders title/emblem in QEMU/OVMF; captures at 1024×768 and 640×480 |
| B · First choice | Started | Arrow-key selection, wrap, Enter, F2 and return demonstrated; configured EFI entries and pagination now work; event-driven input remains |
| C · First boot | Demonstrated in QEMU | Independent EFI child starts and returns; missing/invalid image and ABORTED cases preserve the menu |
| D · Configuration | Demonstrated in QEMU | Shared Rust TOML parser, same-volume reads, dynamic targets, strict validation, default and cancellable one-shot timeout |
| E · Editor | Not implemented | Read-only inspection, drafts, preview, explicit transactional save and interrupted-save recovery |
| F · Compatibility | Not implemented | Linux EFI-stub/UKI, initrd/command line, multiple ESPs, signed/rejected images and recovery matrix |
| G · Hardware | Not authorized or tested | Dedicated machine, separately approved installation, known-good boot path and rollback |

Next: milestone E, a keyboard-driven editor with an explicit unsaved draft,
validation/preview and safe save with recovery. The current configuration view
is read-only. Read-only discovery across ESPs is still outstanding; preserve
stable volume identity and avoid guessing an automatic default.

C demonstrates a known unsigned application under ordinary OVMF, not arbitrary
OS compatibility. Firmware authentication rejection, child exit-data ownership
and resource-exhaustion behavior remain explicit compatibility gates before
third-party/Secure Boot support. No physical installation is implied.

Open questions: final project license, Unicode configuration/display policy,
removable-media policy, variable persistence contract, Secure Boot trust model,
initrd protocol strategy, localization, and power-loss-safe configuration saves.
