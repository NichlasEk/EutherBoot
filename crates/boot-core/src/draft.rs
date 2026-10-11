//! Explicitly unvalidated editing state, separate from the live Config.
use crate::config::{self, Config};
use alloc::{format, string::String, vec::Vec};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DraftEntry {
    pub id: String,
    pub name: String,
    pub path: String,
    /// Empty selects EutherBoot's own volume. Nonempty remains unvalidated draft text.
    pub partition_guid: String,
    pub kind: String,
    pub cmdline: String,
    pub initrd: String,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Draft {
    pub entries: Vec<DraftEntry>,
    pub default: String,
    pub timeout: String,
    pub theme: String,
    pub language: String,
}
impl From<&Config> for Draft {
    fn from(c: &Config) -> Self {
        Self {
            entries: c
                .entries()
                .iter()
                .map(|e| DraftEntry {
                    id: e.id().into(),
                    name: e.name().into(),
                    path: e.path().into(),
                    partition_guid: e.partition_guid().unwrap_or("").into(),
                    kind: e.kind().as_str().into(),
                    cmdline: e.cmdline().unwrap_or("").into(),
                    initrd: e.initrd().unwrap_or("").into(),
                })
                .collect(),
            default: c.entries()[c.default_index()].id().into(),
            timeout: format!("{}", c.timeout()),
            theme: c.theme().into(),
            language: c.language().into(),
        }
    }
}
fn quote(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
impl Draft {
    /// Import only target identity; preserve the user's default and timeout.
    pub fn import_target(&mut self, guid: &str, path: &str) -> Result<usize, String> {
        if self.entries.len() >= config::MAX_ENTRIES {
            return Err("At most 16 entries are allowed".into());
        }
        if !config::valid_partition_guid(guid) || !config::valid_path(path) {
            return Err("Target cannot be represented by the current GUID/path schema".into());
        }
        if self.entries.iter().any(|e| {
            e.partition_guid.eq_ignore_ascii_case(guid) && e.path.eq_ignore_ascii_case(path)
        }) {
            return Err("Target is already present in the draft".into());
        }
        let mut number = 1;
        let id = loop {
            let id = format!("efi-{number}");
            if !self.entries.iter().any(|e| e.id == id) {
                break id;
            }
            number += 1;
        };
        let file = path.rsplit('\\').next().unwrap_or("EFI application");
        let short: String = file.chars().take(32).collect();
        self.entries.push(DraftEntry {
            id,
            name: format!("{short} [{}]", &guid[..8]),
            path: path.into(),
            partition_guid: guid.to_ascii_lowercase(),
            kind: "efi".into(),
            cmdline: String::new(),
            initrd: String::new(),
        });
        Ok(self.entries.len() - 1)
    }
    pub fn document(&self) -> Result<String, String> {
        // Never interpolate user-entered TOML syntax as a numeric value.
        let timeout: u16 = self
            .timeout
            .parse()
            .map_err(|_| String::from("Timeout must be an integer in 0..3600"))?;
        let mut s = format!(
            "# Saved by EutherBoot. Previous file is preserved in .bak.\n[boot]\ndefault = {}\ntimeout = {timeout}\ntheme = {}\nlanguage = {}\n",
            quote(&self.default),
            quote(&self.theme),
            quote(&self.language)
        );
        for e in &self.entries {
            s.push_str(&format!(
                "\n[[entry]]\nid = {}\nname = {}\ntype = {}\npath = {}\n",
                quote(&e.id),
                quote(&e.name),
                quote(&e.kind),
                quote(&e.path)
            ));
            if !e.cmdline.is_empty() {
                s.push_str(&format!("cmdline = {}\n", quote(&e.cmdline)));
            }
            if !e.initrd.is_empty() {
                s.push_str(&format!("initrd = {}\n", quote(&e.initrd)));
            }
            if !e.partition_guid.is_empty() {
                s.push_str(&format!("partition_guid = {}\n", quote(&e.partition_guid)));
            }
        }
        config::parse(&s)?;
        Ok(s)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn base() -> Config {
        config::parse(include_str!("../../../eutherboot.toml")).unwrap()
    }
    #[test]
    fn draft_isolated_and_roundtrips_escaped_text() {
        let c = base();
        let mut d = Draft::from(&c);
        d.entries[0].name = "Owner's \"boot\" \\ test".into();
        d.timeout = "7".into();
        d.theme = "text".into();
        let parsed = config::parse(&d.document().unwrap()).unwrap();
        assert_eq!(parsed.entries()[0].name(), d.entries[0].name);
        assert_eq!(parsed.timeout(), 7);
        assert_eq!(parsed.theme(), "text");
        assert_eq!(c.timeout(), 0);
    }
    #[test]
    fn removing_default_does_not_silently_choose_another() {
        let mut d = Draft::from(&base());
        d.entries.push(DraftEntry {
            id: "second".into(),
            name: "Other".into(),
            path: "\\EFI\\Other.efi".into(),
            partition_guid: String::new(),
            kind: "efi".into(),
            cmdline: String::new(),
            initrd: String::new(),
        });
        d.entries.remove(0);
        assert!(d.document().is_err());
        d.default = "second".into();
        assert!(d.document().is_ok());
    }
    #[test]
    fn imported_target_roundtrips_without_changing_boot_policy() {
        let mut d = Draft::from(&base());
        let guid = "aabbccdd-1234-5678-9012-aabbccddeeff";
        let path = "\\EFI\\Tools\\shared.efi";
        assert_eq!(d.import_target(guid, path).unwrap(), 1);
        assert_eq!(d.default, "test");
        assert_eq!(d.timeout, "0");
        assert!(d.import_target(&guid.to_ascii_uppercase(), path).is_err());
        let parsed = config::parse(&d.document().unwrap()).unwrap();
        assert_eq!(parsed.entries()[1].partition_guid(), Some(guid));
        d.entries[1].partition_guid.clear();
        assert_eq!(
            config::parse(&d.document().unwrap()).unwrap().entries()[1].partition_guid(),
            None
        );
        d.entries[1].partition_guid = "bad".into();
        assert!(d.document().is_err());
    }
    #[test]
    fn linux_draft_preserves_kind_resources_and_quoted_cmdline() {
        let mut d = Draft::from(&base());
        d.entries[0].kind = "linux-efi".into();
        d.entries[0].cmdline = "console=ttyS0 test=\"hello world\"".into();
        d.entries[0].initrd = "\\EFI\\Linux\\initrd.cpio".into();
        let c = config::parse(&d.document().unwrap()).unwrap();
        assert_eq!(Draft::from(&c), d);
        d.entries[0].kind = "efi".into();
        assert!(d.document().is_err());
    }
    #[test]
    fn invalid_draft_cannot_serialize_as_valid_config() {
        let mut d = Draft::from(&base());
        d.timeout = "0\nunknown=true".into();
        assert!(d.document().is_err());
        d.timeout = "0".into();
        d.entries[0].path = "\\EFI\\..\\bad.efi".into();
        assert!(d.document().is_err());
    }
}
