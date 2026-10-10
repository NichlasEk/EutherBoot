# Roadmap

| Milestone | State | Required evidence |
| --- | --- | --- |
| A · First light | Demonstrated | EFI executable renders title/emblem in QEMU/OVMF; captures at 1024×768 and 640×480 |
| B · First choice | Started | Arrow-key selection, wrap, Enter, F2 and return demonstrated; real boot entries and event-driven input remain |
| C · First boot | Not implemented | Chainload a known test EFI child, observe child marker, exercise return/error path |
| D · Configuration | Schema proposal only | Rust firmware TOML parsing, strict validation, default/timeout, virtual ESP read tests |
| E · Editor | Not implemented | Read-only inspection, drafts, preview, explicit transactional save and interrupted-save recovery |
| F · Compatibility | Not implemented | Linux EFI-stub/UKI, initrd/command line, multiple ESPs, signed/rejected images and recovery matrix |
| G · Hardware | Not authorized or tested | Dedicated machine, separately approved installation, known-good boot path and rollback |

Next: implement a tiny independent EFI test child and explicit chainloading in
QEMU before adding real OS discovery. Discovery must retain volume identity,
exclude EutherBoot itself and never promote an unknown file into an automatic
default. Add missing-image, malformed-image, rejected-image and returning-child
cases before declaring C complete.

Open questions: final project license, no_std TOML parser choice and limits,
removable-media policy, variable persistence contract, Secure Boot trust model,
initrd protocol strategy, localization, and power-loss-safe configuration saves.
