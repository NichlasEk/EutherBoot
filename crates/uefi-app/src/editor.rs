//! Keyboard editor: inspection -> isolated draft -> preview -> confirmed save.
use crate::{config, graphics, storage::UefiStore, trace, ui};
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
    let title = ui::tr(title);
    let details = ui::tr(details);
    let lines: Vec<&str> = details.lines().collect();
    let footer = ui::choose(
        "Y confirms. Any other key cancels.",
        "Y bekräftar. Valfri annan tangent avbryter.",
    );
    if graphics::sheet(title, &lines, footer).is_err() {
        clear();
        uefi::println!("{title}\n\n{details}\n\n{footer}");
    }
    trace("EDITOR_CONFIRM");
    matches!(key(),Some(Key::Printable(c)) if matches!(char::from(c),'y'|'Y'))
}
fn prompt(field: &str, initial: &str, max: usize) -> Option<String> {
    let mut value = String::from(initial);
    loop {
        let display: String = value
            .chars()
            .rev()
            .take(100)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect();
        let count = format!(
            "{} / {} {}",
            value.chars().count(),
            max,
            ui::choose("characters", "tecken")
        );
        let footer = ui::choose(
            "Enter Accept   Backspace Delete   F4 Clear   Esc Cancel",
            "Enter Godkänn   Backsteg Radera   F4 Töm   Esc Avbryt",
        );
        if graphics::sheet(ui::tr(field), &[&display, "", &count], footer).is_err() {
            clear();
            uefi::println!("{}\n\n{display}\n\n{count}\n{footer}", ui::tr(field));
        }
        trace(&format!("PROMPT_READY {field}"));
        match key()? {
            Key::Special(ScanCode::ESCAPE) => return None,
            Key::Special(ScanCode::FUNCTION_4) => value.clear(),
            Key::Printable(c) => match char::from(c) {
                '\r' => return Some(value),
                '\u{8}' => {
                    value.pop();
                }
                c if (if field == "name" {
                    boot_core::presentation::display_char(c)
                } else {
                    c.is_ascii() && !c.is_control()
                }) && value.chars().count() < max =>
                {
                    value.push(c)
                }
                _ => {}
            },
            _ => {}
        }
        trace("PROMPT_CHANGED");
    }
}
fn show(draft: Option<&Draft>, selected: usize, editing: bool, message: &str) {
    if let Some(d) = draft {
        ui::configure(&d.theme, &d.language);
    }
    if graphics::editor(draft, selected, editing, message).is_ok() {
        trace("EDITOR_READY");
        return;
    }
    clear();
    uefi::println!(
        "EUTHERBOOT / {}\n{}\n",
        ui::choose("CONFIGURATION", "INSTÄLLNINGAR"),
        if editing {
            ui::choose(
                "DRAFT - edits require explicit Save",
                "UTKAST - ändringar kräver Spara",
            )
        } else {
            ui::choose(
                "READ ONLY - E starts a separate draft",
                "ENDAST LÄSNING - E skapar ett utkast",
            )
        }
    );
    if let Some(d) = draft {
        uefi::println!(
            "{}: {}  {}: {}s  {}: {}  {}: {}\n",
            ui::choose("Default", "Förval"),
            d.default,
            ui::choose("Timeout", "Väntetid"),
            d.timeout,
            ui::choose("Theme", "Tema"),
            d.theme,
            ui::choose("Language", "Språk"),
            d.language
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
                "\n{}: {}\n{}: {} | Partition: {}",
                ui::choose("Path", "Sökväg"),
                e.path,
                ui::choose("Type", "Typ"),
                e.kind,
                if e.partition_guid.is_empty() {
                    ui::choose("own volume", "egen volym")
                } else {
                    &e.partition_guid
                }
            );
        }
    } else {
        uefi::println!(
            "{}",
            ui::choose(
                "No valid live configuration. Recovery or external repair required.",
                "Ingen giltig konfiguration. Återställ eller reparera externt."
            )
        );
    }
    if editing {
        uefi::println!(
            "{}",
            ui::choose(
                "D default | T timeout | G theme | L language | A add | R remove\nN name | P path | U partition | I import | V validate\nK type | C cmdline | J initrd | F6 details\nF5 preview | S save | Esc discard | F2 graphics",
                "D förval | T väntetid | G tema | L språk | A lägg till | R ta bort\nN namn | P sökväg | U partition | I import | V kontrollera\nK typ | C kommandorad | J initrd | F6 detaljer\nF5 visa | S spara | Esc kasta | F2 grafik"
            )
        );
    } else {
        uefi::println!(
            "{}",
            ui::choose(
                "E edit | B restore backup | C keep current / clear pending save\nF6 entry details | F2 graphics | Esc boot menu",
                "E ändra | B återställ backup | C behåll nuvarande / rensa ofärdigt sparande\nF6 detaljer | F2 grafik | Esc startmeny"
            )
        );
    }
    uefi::println!("\n{}", clipped(ui::tr(message), 160));
    trace("EDITOR_READY");
}
fn details(e: &DraftEntry) {
    let content = format!(
        "{}: {}\n{}: {}\nPartition: {}\n{}: {}\n{}: {}\nInitrd: {}",
        ui::choose("Name", "Namn"),
        e.name,
        ui::choose("Type", "Typ"),
        e.kind,
        if e.partition_guid.is_empty() {
            ui::choose("own volume", "egen volym")
        } else {
            &e.partition_guid
        },
        ui::choose("Path", "Sökväg"),
        e.path,
        ui::choose("Cmdline", "Kommandorad"),
        e.cmdline,
        e.initrd
    );
    let mut lines = Vec::new();
    for line in content.lines() {
        for part in line.chars().collect::<Vec<_>>().chunks(58) {
            lines.push(part.iter().collect::<String>());
        }
    }
    let mut page = 0;
    loop {
        let page_lines: Vec<&str> = lines
            .iter()
            .skip(page * 10)
            .take(10)
            .map(|s| s.as_str())
            .collect();
        let footer = format!(
            "{} / {}   {}",
            page + 1,
            lines.len().div_ceil(10),
            ui::choose("Up/Down Page   Esc Back", "Upp/Ned Sida   Esc Tillbaka")
        );
        let title = ui::choose("Entry details", "Postens detaljer");
        if graphics::sheet(title, &page_lines, &footer).is_err() {
            clear();
            uefi::println!("{title}\n");
            for line in &page_lines {
                uefi::println!("{line}");
            }
            uefi::println!("{footer}");
        }
        trace("EDITOR_DETAILS");
        match key() {
            Some(Key::Special(ScanCode::DOWN)) if (page + 1) * 10 < lines.len() => page += 1,
            Some(Key::Special(ScanCode::UP)) if page > 0 => page -= 1,
            None | Some(Key::Special(ScanCode::ESCAPE)) => return,
            _ => {}
        }
    }
}
fn preview(d: &Draft) -> Result<(), String> {
    ui::configure(&d.theme, &d.language);
    let document = d.document()?;
    let c = config::validate(document.as_bytes())?;
    let mut labels: Vec<&str> = c.entries().iter().map(|e| e.name()).collect();
    labels.push("Configuration (read-only)");
    labels.push("Return to firmware");
    if c.theme() == "text"
        || graphics::draw(
            &labels,
            c.default_index(),
            ui::choose(
                "UNSAVED PREVIEW - any key returns; nothing will boot.",
                "OSPARAD VISNING - valfri tangent återgår; ingenting startas.",
            ),
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
            Key::Special(ScanCode::FUNCTION_2) => {
                ui::toggle_fallback();
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
                                        "{} {name}: {} {}, {} {}, {} {}s.\n{}",
                                        ui::choose("Use", "Använd"),
                                        c.entries().len(),
                                        ui::choose("entries", "poster"),
                                        ui::choose("default", "förval"),
                                        c.entries()[c.default_index()].id(),
                                        ui::choose("timeout", "väntetid"),
                                        c.timeout(),
                                        ui::choose(
                                            "Pending staged data will be discarded. No EFI application is changed.",
                                            "Ofärdigt sparande rensas. Inget EFI-program ändras."
                                        )
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
                        let themes = boot_core::presentation::THEMES;
                        let index = themes.iter().position(|t| *t == d.theme).unwrap_or(0);
                        d.theme = themes[(index + 1) % themes.len()].into();
                    }
                    'l' => {
                        d.language = if d.language == "sv" { "en" } else { "sv" }.into();
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
                                    "{} | {}\n{}",
                                    e.id,
                                    e.name,
                                    ui::choose(
                                        "A removed default must be replaced explicitly with D.",
                                        "Ett borttaget förval måste ersättas uttryckligen med D."
                                    )
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
