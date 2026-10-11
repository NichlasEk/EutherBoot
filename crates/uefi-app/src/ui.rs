//! Session presentation only. Persisted preferences live in the validated draft.
use core::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
static SWEDISH: AtomicBool = AtomicBool::new(false);
static THEME: AtomicUsize = AtomicUsize::new(0);
static TEXT: AtomicBool = AtomicBool::new(false);
pub fn configure(theme: &str, language: &str) {
    THEME.store(
        boot_core::presentation::THEMES
            .iter()
            .position(|s| *s == theme)
            .unwrap_or(0),
        Ordering::Relaxed,
    );
    SWEDISH.store(language == "sv", Ordering::Relaxed);
}
pub fn theme() -> usize {
    THEME.load(Ordering::Relaxed)
}
pub fn text() -> bool {
    theme() == 1 || TEXT.load(Ordering::Relaxed)
}
pub fn reset_fallback() {
    TEXT.store(false, Ordering::Relaxed);
}
pub fn toggle_fallback() {
    TEXT.fetch_xor(true, Ordering::Relaxed);
}
pub fn choose<'a>(en: &'a str, sv: &'a str) -> &'a str {
    if SWEDISH.load(Ordering::Relaxed) {
        sv
    } else {
        en
    }
}
pub fn tr(s: &str) -> &str {
    if !SWEDISH.load(Ordering::Relaxed) {
        return s;
    }
    match s {
        "name" => "Visningsnamn",
        "path" => "Startfil",
        "id" => "Tekniskt ID",
        "timeout" => "Automatisk start (sekunder, 0 = av)",
        "cmdline" => "Kärnans kommandorad",
        "initrd (empty = none)" => "Initrd (tomt = ingen)",
        "partition_guid (empty = own volume)" => "Partitionens GUID (tomt = egen volym)",
        "Inspection does not write to disk." => "Inspektion skriver ingenting till disk.",
        "Editing a draft. V validates; S asks before writing." => {
            "Du ändrar ett utkast. V kontrollerar; S frågar innan det sparas."
        }
        "Draft default changed." => "Förvald start ändrad i utkastet.",
        "Draft is valid. Nothing saved." => "Utkastet är giltigt. Ingenting har sparats.",
        "Preview closed; draft still unsaved." => {
            "Förhandsvisningen stängd. Utkastet är inte sparat."
        }
        "Save cancelled. Draft still unsaved." => "Sparandet avbröts. Utkastet är inte sparat.",
        "Discard this draft?" => "Kasta detta utkast?",
        "Unsaved draft changes will be lost. Any earlier disk-write attempt is not undone." => {
            "Osparade ändringar försvinner. Tidigare skrivförsök till disk ångras inte."
        }
        "Save this draft to eutherboot.toml?" => "Spara utkastet till eutherboot.toml?",
        "Previous valid file is kept in eutherboot.toml.bak.\nFormatting/comments will be regenerated. This writes to the EFI volume." => {
            "Tidigare fil behålls i eutherboot.toml.bak.\nFormatering och kommentarer återskapas. Detta skriver till EFI-volymen."
        }
        "Restore the backup configuration?" => "Återställ konfigurationen från backup?",
        "Keep the current configuration?" => "Behåll den nuvarande konfigurationen?",
        "Remove this entry from the draft?" => "Ta bort posten från utkastet?",
        "Change Linux EFI entry to plain EFI?" => "Ändra Linux EFI-posten till vanlig EFI?",
        "The draft's kernel command line and initrd path will be cleared." => {
            "Utkastets kommandorad och initrd-sökväg töms."
        }
        "At most 16 entries are allowed." => "Högst 16 poster är tillåtna.",
        "Resolve the unfinished save with B or C before editing." => {
            "Hantera det ofärdiga sparandet med B eller C först."
        }
        "Imported to draft only. Default and timeout unchanged." => {
            "Importerad till utkastet. Förval och väntetid är oförändrade."
        }
        "Imported to draft only. Default/timeout unchanged; S asks to save." => {
            "Importerad till utkastet. Förval och väntetid är oförändrade; S sparar."
        }
        "Import requires a valid live config and no unfinished save. Use recovery first." => {
            "Import kräver giltig konfiguration utan ofärdigt sparande. Återställ först."
        }
        "K selects linux-efi; plain EFI/UKI uses embedded resources." => {
            "K väljer linux-efi; vanlig EFI/UKI använder inbyggda resurser."
        }
        "K selects linux-efi before editing an initrd path." => {
            "Välj linux-efi med K innan du ändrar initrd."
        }
        _ => s, // Technical parser/storage diagnostics retain their exact meaning.
    }
}
