//! Explicitly unvalidated editing state, separate from the live Config.
use crate::config::{self, Config};
use alloc::{format, string::String, vec::Vec};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DraftEntry {
    pub id: String,
    pub name: String,
    pub path: String,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Draft {
    pub entries: Vec<DraftEntry>,
    pub default: String,
    pub timeout: String,
    pub theme: String,
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
                })
                .collect(),
            default: c.entries()[c.default_index()].id().into(),
            timeout: format!("{}", c.timeout()),
            theme: c.theme().into(),
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
    pub fn document(&self) -> Result<String, String> {
        // Never interpolate user-entered TOML syntax as a numeric value.
        let timeout: u16 = self
            .timeout
            .parse()
            .map_err(|_| String::from("Timeout must be an integer in 0..3600"))?;
        let mut s = format!(
            "# Saved by EutherBoot. Previous file is preserved in .bak.\n[boot]\ndefault = {}\ntimeout = {timeout}\ntheme = {}\n",
            quote(&self.default),
            quote(&self.theme)
        );
        for e in &self.entries {
            s.push_str(&format!(
                "\n[[entry]]\nid = {}\nname = {}\ntype = \"efi\"\npath = {}\n",
                quote(&e.id),
                quote(&e.name),
                quote(&e.path)
            ));
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
        });
        d.entries.remove(0);
        assert!(d.document().is_err());
        d.default = "second".into();
        assert!(d.document().is_ok());
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
