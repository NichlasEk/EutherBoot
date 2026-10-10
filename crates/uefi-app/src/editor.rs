//! Keyboard editor: inspection -> isolated draft -> preview -> confirmed save.
use crate::{config, graphics, storage::UefiStore, trace};
use alloc::{format, string::String, vec::Vec};
use boot_core::{
    config::MAX_ENTRIES,
    draft::{Draft, DraftEntry},
    transaction::{self, Store},
};
use uefi::{
    proto::console::text::{Key, ScanCode},
    system,
};

fn key() -> Option<Key> {
    crate::input::read_blocking()
}
fn clear() {
    system::with_stdout(|s| {
        let _ = s.clear();
    });
}
fn clipped(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}
fn confirm(title: &str, details: &str) -> bool {
    clear();
    uefi::println!(
        "EUTHERBOOT / CONFIRM\n\n{title}\n\n{details}\n\nY confirms. Any other key cancels."
    );
    trace("EDITOR_CONFIRM");
    matches!(key(),Some(Key::Printable(c)) if matches!(char::from(c),'y'|'Y'))
}
fn prompt(field: &str, initial: &str, max: usize) -> Option<String> {
    let mut value = String::from(initial);
    loop {
        clear();
        uefi::println!(
            "EUTHERBOOT / DRAFT FIELD\n\n{field}\n\n{}\n\n{} / {} characters\nEnter accepts | F4 clears | Esc cancels",
            value
                .chars()
                .rev()
                .take(65)
                .collect::<Vec<_>>()
                .into_iter()
                .rev()
                .collect::<String>(),
            value.len(),
            max
        );
        trace(&format!("PROMPT_READY {field}"));
        match key()? {
            Key::Special(ScanCode::ESCAPE) => return None,
            Key::Special(ScanCode::FUNCTION_4) => value.clear(),
            Key::Printable(c) => match char::from(c) {
                '\r' => return Some(value),
                '\u{8}' => {
                    value.pop();
                }
                c if c.is_ascii() && !c.is_control() && value.len() < max => value.push(c),
                _ => {}
            },
            _ => {}
        }
        trace("PROMPT_CHANGED");
    }
}
fn show(draft: Option<&Draft>, selected: usize, editing: bool, message: &str) {
    clear();
    uefi::println!(
        "EUTHERBOOT / CONFIGURATION\n{}\n",
        if editing {
            "DRAFT - edits require explicit Save"
        } else {
            "READ ONLY - E starts a separate draft"
        }
    );
    if let Some(d) = draft {
        uefi::println!(
            "Default: {}  Timeout: {}s  Appearance: {}\n",
            d.default,
            d.timeout,
            d.theme
        );
        let first = selected / 5 * 5;
        for (i, e) in d.entries.iter().enumerate().skip(first).take(5) {
            uefi::println!(
                "{} {:2} {} | {}",
                if i == selected { ">" } else { " " },
                i + 1,
                clipped(&e.id, 20),
                clipped(&e.name, 42)
            );
        }
        if let Some(e) = d.entries.get(selected) {
            uefi::println!(
                "\nPath: {}\nType: {} | Partition: {}",
                e.path,
                e.kind,
                if e.partition_guid.is_empty() {
                    "own volume"
                } else {
                    &e.partition_guid
                }
            );
        }
    } else {
        uefi::println!("No valid live configuration. Recovery or external repair required.");
    }
    if editing {
        uefi::println!(
            "\nD default | T timeout | G appearance | A add | R remove\nN name | P path | U partition | I import | V validate\nK type | C cmdline | J initrd | F6 details\nF5 preview | S save | Esc discard"
        );
    } else {
        uefi::println!(
            "\nE edit | B restore backup | C keep current / clear pending save\nF6 entry details | Esc returns to boot menu"
        );
    }
    uefi::println!("\n{}", clipped(message, 160));
    trace("EDITOR_READY");
}
fn details(e: &DraftEntry) {
    let content = format!(
        "Name: {}\nType: {}\nPartition: {}\nPath: {}\nCmdline: {}\nInitrd: {}",
        e.name,
        e.kind,
        if e.partition_guid.is_empty() {
            "own volume"
        } else {
            &e.partition_guid
        },
        e.path,
        e.cmdline,
        e.initrd
    );
    let mut lines = Vec::new();
    for line in content.lines() {
        for part in line.as_bytes().chunks(64) {
            lines.push(core::str::from_utf8(part).unwrap_or("?"));
        }
    }
    let mut page = 0;
    loop {
        clear();
        uefi::println!("EUTHERBOOT / ENTRY DETAILS (read-only)\n");
        for line in lines.iter().skip(page * 12).take(12) {
            uefi::println!("{line}");
        }
        uefi::println!(
            "\nPage {} / {}   Up/Down: page   Esc: back",
            page + 1,
            lines.len().div_ceil(12)
        );
        trace("EDITOR_DETAILS");
        match key() {
            Some(Key::Special(ScanCode::DOWN)) if (page + 1) * 12 < lines.len() => page += 1,
            Some(Key::Special(ScanCode::UP)) if page > 0 => page -= 1,
            None | Some(Key::Special(ScanCode::ESCAPE)) => return,
            _ => {}
        }
    }
}
fn preview(d: &Draft) -> Result<(), String> {
    let document = d.document()?;
    let c = config::validate(document.as_bytes())?;
    let mut labels: Vec<&str> = c.entries().iter().map(|e| e.name()).collect();
    labels.push("Configuration (read-only)");
    labels.push("Return to firmware");
    if c.theme() == "text"
        || graphics::draw(
            &labels,
            c.default_index(),
            "UNSAVED PREVIEW - any key returns; nothing will boot.",
        )
        .is_err()
    {
        clear();
        uefi::println!("EUTHERBOOT / UNSAVED PREVIEW\n");
        for (i, l) in labels.iter().enumerate() {
            uefi::println!("{} {}", if i == c.default_index() { ">" } else { " " }, l);
        }
        uefi::println!("\nAny key returns. No target is started.");
    }
    trace("EDITOR_PREVIEW");
    let _ = key();
    Ok(())
}
/// True means reload disk state without arming automatic boot.
pub fn run() -> bool {
    run_import(None)
}
pub fn run_import(import: Option<crate::discovery::Selection>) -> bool {
    trace("EDITOR_OPEN");
    let mut store = match UefiStore::open() {
        Ok(s) => s,
        Err(e) => {
            clear();
            uefi::println!("{e}\nPress any key to return.");
            let _ = key();
            return false;
        }
    };
    let original = store.read(transaction::LIVE).ok().flatten();
    let current = original.as_deref().and_then(|b| config::validate(b).ok());
    let mut draft = current.as_ref().map(Draft::from);
    let mut editing = false;
    let mut selected = 0;
    let mut reload = false;
    let mut message = String::from("Inspection does not write to disk.");
    if let Some(target) = import {
        if let Some(d) = draft
            .as_mut()
            .filter(|_| matches!(transaction::pending(&mut store), Ok(false)))
        {
            match d.import_target(&target.partition_guid, &target.path) {
                Ok(index) => {
                    selected = index;
                    editing = true;
                    message =
                        "Imported to draft only. Default/timeout unchanged; S asks to save.".into();
                    trace("EDITOR_IMPORTED");
                }
                Err(e) => message = e,
            }
        } else {
            message =
                "Import requires a valid live config and no unfinished save. Use recovery first."
                    .into();
        }
    }
    loop {
        show(draft.as_ref(), selected, editing, &message);
        let Some(k) = key() else { return false };
        match k {
            Key::Special(ScanCode::ESCAPE) => {
                if !editing
                    || confirm(
                        "Discard this draft?",
                        "Unsaved draft changes will be lost. Any earlier disk-write attempt is not undone.",
                    )
                {
                    trace("EDITOR_DISCARD");
                    return reload;
                }
            }
            Key::Special(ScanCode::UP) => {
                if let Some(d) = &draft {
                    if !d.entries.is_empty() {
                        selected = (selected + d.entries.len() - 1) % d.entries.len();
                    }
                }
            }
            Key::Special(ScanCode::DOWN) => {
                if let Some(d) = &draft {
                    if !d.entries.is_empty() {
                        selected = (selected + 1) % d.entries.len();
                    }
                }
            }
            Key::Special(ScanCode::FUNCTION_6) => {
                if let Some(e) = draft.as_ref().and_then(|d| d.entries.get(selected)) {
                    details(e);
                }
            }
            Key::Special(ScanCode::FUNCTION_5) if editing => {
                message = match preview(draft.as_ref().unwrap()) {
                    Ok(()) => "Preview closed; draft still unsaved.".into(),
                    Err(e) => {
                        trace("EDITOR_INVALID");
                        e
                    }
                };
            }
            Key::Printable(ch) => {
                let ch = char::from(ch).to_ascii_lowercase();
                if !editing {
                    match ch {
                        'e' if draft.is_some() => match transaction::pending(&mut store) {
                            Ok(false) => {
                                editing = true;
                                message =
                                    "Editing a draft. V validates; S asks before writing.".into();
                                trace("EDITOR_DRAFT");
                            }
                            _ => {
                                message =
                                    "Resolve the unfinished save with B or C before editing.".into()
                            }
                        },
                        'b' | 'c' => {
                            let name = if ch == 'b' {
                                transaction::BACKUP
                            } else {
                                transaction::LIVE
                            };
                            let candidate = store
                                .read(name)
                                .and_then(|b| b.ok_or_else(|| format!("Missing {name}")))
                                .and_then(|b| {
                                    config::validate(&b)?;
                                    Ok(b)
                                });
                            match candidate {
                                Err(e) => message = e,
                                Ok(bytes) => {
                                    let c = config::validate(&bytes).unwrap();
                                    let detail = format!(
                                        "Use {name}: {} entries, default {}, timeout {}s.\nPending staged data will be discarded. No EFI application is changed.",
                                        c.entries().len(),
                                        c.entries()[c.default_index()].id(),
                                        c.timeout()
                                    );
                                    if confirm(
                                        if ch == 'b' {
                                            "Restore the backup configuration?"
                                        } else {
                                            "Keep the current configuration?"
                                        },
                                        &detail,
                                    ) {
                                        reload = true;
                                        let result = if ch == 'b' {
                                            transaction::restore_backup(&mut store, &bytes)
                                        } else {
                                            transaction::keep_current(&mut store, &bytes)
                                        };
                                        match result {
                                            Ok(()) => {
                                                trace("EDITOR_RECOVERED");
                                                return true;
                                            }
                                            Err(e) => {
                                                trace(&format!("EDITOR_SAVE_ERROR {e}"));
                                                message = e
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        _ => {}
                    }
                    continue;
                }
                let d = draft.as_mut().unwrap();
                match ch {
                    'd' => {
                        if let Some(e) = d.entries.get(selected) {
                            d.default = e.id.clone();
                            message = "Draft default changed.".into();
                        }
                    }
                    't' => {
                        if let Some(v) = prompt("timeout", &d.timeout, 4) {
                            d.timeout = v;
                        }
                    }
                    'g' => {
                        d.theme = if d.theme == "text" {
                            "system-regis"
                        } else {
                            "text"
                        }
                        .into();
                    }
                    'a' => {
                        if d.entries.len() >= MAX_ENTRIES {
                            message = "At most 16 entries are allowed.".into();
                            continue;
                        }
                        if let Some(id) = prompt("id", "", 32) {
                            if let Some(name) = prompt("name", "", 48) {
                                if let Some(path) = prompt("path", "\\EFI\\", 240) {
                                    d.entries.push(DraftEntry {
                                        id,
                                        name,
                                        path,
                                        partition_guid: String::new(),
                                        kind: "efi".into(),
                                        cmdline: String::new(),
                                        initrd: String::new(),
                                    });
                                    selected = d.entries.len() - 1;
                                }
                            }
                        }
                    }
                    'r' => {
                        if let Some(e) = d.entries.get(selected) {
                            if confirm(
                                "Remove this entry from the draft?",
                                &format!(
                                    "{} | {}\nA removed default must be replaced explicitly with D.",
                                    e.id, e.name
                                ),
                            ) {
                                d.entries.remove(selected);
                                selected = selected.min(d.entries.len().saturating_sub(1));
                            }
                        }
                    }
                    'n' => {
                        if let Some(e) = d.entries.get_mut(selected) {
                            if let Some(v) = prompt("name", &e.name, 48) {
                                e.name = v;
                            }
                        }
                    }
                    'p' => {
                        if let Some(e) = d.entries.get_mut(selected) {
                            if let Some(v) = prompt("path", &e.path, 240) {
                                e.path = v;
                            }
                        }
                    }
                    'k' => {
                        if let Some(e) = d.entries.get_mut(selected) {
                            if e.kind == "efi" {
                                e.kind = "linux-efi".into();
                            } else if confirm(
                                "Change Linux EFI entry to plain EFI?",
                                "The draft's kernel command line and initrd path will be cleared.",
                            ) {
                                e.kind = "efi".into();
                                e.cmdline.clear();
                                e.initrd.clear();
                            }
                        }
                    }
                    'c' => {
                        if let Some(e) = d.entries.get_mut(selected) {
                            if e.kind == "linux-efi" {
                                if let Some(v) =
                                    prompt("cmdline", &e.cmdline, boot_core::linux::MAX_CMDLINE)
                                {
                                    e.cmdline = v;
                                }
                            } else {
                                message =
                                    "K selects linux-efi; plain EFI/UKI uses embedded resources."
                                        .into();
                            }
                        }
                    }
                    'j' => {
                        if let Some(e) = d.entries.get_mut(selected) {
                            if e.kind == "linux-efi" {
                                if let Some(v) = prompt("initrd (empty = none)", &e.initrd, 240) {
                                    e.initrd = v;
                                }
                            } else {
                                message =
                                    "K selects linux-efi before editing an initrd path.".into();
                            }
                        }
                    }
                    'u' => {
                        if let Some(e) = d.entries.get_mut(selected) {
                            if let Some(v) =
                                prompt("partition_guid (empty = own volume)", &e.partition_guid, 36)
                            {
                                e.partition_guid = v;
                            }
                        }
                    }
                    'i' => {
                        if let Some(target) = crate::discovery::pick() {
                            match d.import_target(&target.partition_guid, &target.path) {
                                Ok(index) => {
                                    selected = index;
                                    message =
                                        "Imported to draft only. Default and timeout unchanged."
                                            .into();
                                    trace("EDITOR_IMPORTED");
                                }
                                Err(e) => message = e,
                            }
                        }
                    }
                    'v' => {
                        message = match d.document().and_then(|s| config::validate(s.as_bytes())) {
                            Ok(_) => {
                                trace("EDITOR_VALID");
                                "Draft is valid. Nothing saved.".into()
                            }
                            Err(e) => {
                                trace("EDITOR_INVALID");
                                e
                            }
                        };
                    }
                    's' => {
                        let document = match d.document().and_then(|s| {
                            config::validate(s.as_bytes())?;
                            Ok(s)
                        }) {
                            Ok(s) => s,
                            Err(e) => {
                                message = e;
                                trace("EDITOR_INVALID");
                                continue;
                            }
                        };
                        if confirm(
                            "Save this draft to eutherboot.toml?",
                            "Previous valid file is kept in eutherboot.toml.bak.\nFormatting/comments will be regenerated. This writes to the EFI volume.",
                        ) {
                            reload = true;
                            let result = transaction::save(
                                &mut store,
                                original.as_deref().unwrap(),
                                document.as_bytes(),
                            );
                            match result {
                                Ok(()) => {
                                    trace("EDITOR_SAVED");
                                    return true;
                                }
                                Err(e) => {
                                    trace(&format!("EDITOR_SAVE_ERROR {e}"));
                                    message = e;
                                }
                            }
                        } else {
                            trace("EDITOR_SAVE_CANCELLED");
                            message = "Save cancelled. Draft still unsaved.".into();
                        }
                    }
                    _ => {}
                }
                trace("EDITOR_UPDATED");
            }
            _ => {}
        }
    }
}
