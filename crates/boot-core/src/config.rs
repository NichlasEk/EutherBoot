//! Shared no_std TOML parser and fail-closed schema. No firmware or I/O here.
use alloc::{
    format,
    string::{String, ToString},
    vec::Vec,
};
use serde::Deserialize;

pub const MAX_BYTES: usize = 16 * 1024;
pub const MAX_ENTRIES: usize = 16;

#[derive(Debug, Clone)]
pub struct Config {
    entries: Vec<Entry>,
    default_index: usize,
    timeout: u16,
    theme: String,
}
#[derive(Debug, Clone)]
pub struct Entry {
    id: String,
    name: String,
    path: String,
    partition_guid: Option<String>,
}
impl Entry {
    pub fn id(&self) -> &str {
        &self.id
    }
    pub fn name(&self) -> &str {
        &self.name
    }
    pub fn partition_guid(&self) -> Option<&str> {
        self.partition_guid.as_deref()
    }
    pub fn path(&self) -> &str {
        &self.path
    }
}
impl Config {
    pub fn entries(&self) -> &[Entry] {
        &self.entries
    }
    pub fn default_index(&self) -> usize {
        self.default_index
    }
    pub fn theme(&self) -> &str {
        &self.theme
    }
    pub fn timeout(&self) -> u16 {
        self.timeout
    }
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawConfig {
    boot: RawBoot,
    entry: Vec<RawEntry>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawBoot {
    default: String,
    #[serde(default)]
    timeout: u16,
    #[serde(default = "theme")]
    theme: String,
}
fn theme() -> String {
    "system-regis".into()
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawEntry {
    id: String,
    name: String,
    #[serde(rename = "type")]
    kind: String,
    path: Option<String>,
    partition_guid: Option<String>,
}

/// Canonical GPT unique-partition GUID syntax; not a filesystem UUID or type GUID.
pub fn valid_partition_guid(value: &str) -> bool {
    value.len() == 36
        && value.bytes().enumerate().all(|(i, b)| {
            if [8, 13, 18, 23].contains(&i) {
                b == b'-'
            } else {
                b.is_ascii_hexdigit()
            }
        })
        && value.bytes().any(|b| b.is_ascii_hexdigit() && b != b'0')
}

/// Deliberately restricted to unambiguous ASCII FAT paths in this milestone.
pub fn valid_path(path: &str) -> bool {
    path.is_ascii()
        && path.len() <= 240
        && path.len() > 9
        && path[..5.min(path.len())].eq_ignore_ascii_case("\\EFI\\")
        && path.to_ascii_lowercase().ends_with(".efi")
        && path
            .bytes()
            .all(|b| b.is_ascii_graphic() && !b"/:*?\"<>|~".contains(&b))
        && path[1..]
            .split('\\')
            .all(|p| !p.is_empty() && p != "." && p != ".." && !p.ends_with('.'))
}

pub fn parse(source: &str) -> Result<Config, String> {
    if source.len() > MAX_BYTES {
        return Err("Configuration exceeds 16384 bytes".into());
    }
    let raw: RawConfig = toml::from_str(source).map_err(|e: toml::de::Error| {
        let line = e
            .span()
            .map(|s| {
                source.as_bytes()[..s.start.min(source.len())]
                    .iter()
                    .copied()
                    .filter(|b| *b == b'\n')
                    .count()
                    + 1
            })
            .unwrap_or(1);
        let message: String = e
            .message()
            .chars()
            .take(160)
            .map(|c| {
                if c.is_ascii_graphic() || c == ' ' {
                    c
                } else {
                    ' '
                }
            })
            .collect();
        format!("TOML line {line}: {message}")
    })?;
    if raw.boot.timeout > 3600 {
        return Err("boot.timeout must be 0..3600 seconds".into());
    }
    if !matches!(raw.boot.theme.as_str(), "system-regis" | "text") {
        return Err("boot.theme: expected system-regis or text".into());
    }
    if raw.entry.is_empty() || raw.entry.len() > MAX_ENTRIES {
        return Err("Expected 1..16 EFI entries".into());
    }
    let mut entries: Vec<Entry> = Vec::new();
    for (index, e) in raw.entry.into_iter().enumerate() {
        let fail = |s: &str| format!("entry {}: {s}", index + 1);
        if e.id.is_empty()
            || e.id.len() > 32
            || !e
                .id
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"-_".contains(&b))
        {
            return Err(fail("id must be 1..32 ASCII letters, digits, '-' or '_'"));
        }
        if e.name.trim().is_empty()
            || e.name.len() > 48
            || !e.name.bytes().all(|b| (32..=126).contains(&b))
        {
            return Err(fail("name must be 1..48 printable ASCII characters"));
        }
        if e.kind != "efi" {
            return Err(fail("unsupported type; only efi is implemented"));
        }
        let path = e.path.ok_or_else(|| fail("efi entry requires path"))?;
        if !path.is_ascii() || !valid_path(&path) {
            return Err(fail(
                "expected absolute \\EFI\\...efi path without traversal or aliases",
            ));
        }
        if entries.iter().any(|v| v.id == e.id) {
            return Err(fail("duplicate id"));
        }
        let partition_guid = match e.partition_guid {
            Some(guid) if valid_partition_guid(&guid) => Some(guid.to_ascii_lowercase()),
            Some(_) => {
                return Err(fail(
                    "partition_guid must be a nonzero 8-4-4-4-12 hexadecimal GUID",
                ));
            }
            None => None,
        };
        if entries
            .iter()
            .any(|v| v.partition_guid == partition_guid && v.path.eq_ignore_ascii_case(&path))
        {
            return Err(fail("duplicate EFI path on the same partition selector"));
        }
        entries.push(Entry {
            id: e.id,
            name: e.name,
            path,
            partition_guid,
        });
    }
    let default_index = entries
        .iter()
        .position(|e| e.id == raw.boot.default)
        .ok_or_else(|| "boot.default does not identify an entry".to_string())?;
    Ok(Config {
        entries,
        default_index,
        timeout: raw.boot.timeout,
        theme: raw.boot.theme,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    const BASE: &str = include_str!("../../../eutherboot.toml");
    #[test]
    fn example_and_safe_defaults() {
        let c = parse(BASE).unwrap();
        assert_eq!(c.default_index(), 0);
        assert_eq!(c.timeout(), 0);
        let c = parse(
            &BASE
                .replace("timeout = 0", "")
                .replace("theme = \"system-regis\"", ""),
        )
        .unwrap();
        assert_eq!(c.timeout(), 0);
    }
    #[test]
    fn typed_default_and_timeout() {
        let s = BASE
            .replace("default = \"test\"", "default = \"second\"")
            .replace("timeout = 0", "timeout = 5");
        let s = format!(
            "{s}\n[[entry]]\nid='second'\nname='Second'\ntype='efi'\npath='\\EFI\\Other\\second.efi'\n"
        );
        let c = parse(&s).unwrap();
        assert_eq!(c.default_index(), 1);
        assert_eq!(c.timeout(), 5);
    }
    #[test]
    fn malformed_and_unknown_fields_fail_closed() {
        for s in [
            String::from("[boot"),
            BASE.replace("timeout = 0", "timeout = true"),
            BASE.replace("timeout = 0", "timeout = -1"),
            BASE.replace("timeout = 0", "timeout = 3601"),
            BASE.replace("timeout = 0", "timeuot = 5"),
            BASE.replace("type = \"efi\"", "typo = 'efi'"),
            BASE.replace("[boot]", "unknown = 1\n[boot]"),
            BASE.replace("default = \"test\"", "default = 'missing'"),
            BASE.replace("system-regis", "other"),
            BASE.replace("type = \"efi\"", "type = 'firmware'"),
            BASE.replace("timeout = 0", "timeout = 0\ntimeout = 2"),
        ] {
            assert!(parse(&s).is_err(), "accepted {s}");
        }
    }
    #[test]
    fn duplicate_ids_and_case_insensitive_paths_rejected() {
        let extra =
            "\n[[entry]]\nid='test'\nname='Other'\ntype='efi'\npath='\\EFI\\Other\\other.efi'\n";
        assert!(parse(&format!("{BASE}{extra}")).is_err());
        let extra = extra.replace("id='test'", "id='other'").replace(
            "\\EFI\\Other\\other.efi",
            "\\efi\\eutherboot\\testchild.EFI",
        );
        assert!(parse(&format!("{BASE}{extra}")).is_err());
    }
    #[test]
    fn partition_identity_is_strict_and_paths_are_volume_scoped() {
        let guid = "aabbccdd-1234-5678-9012-aabbccddeeff";
        let extra = format!(
            "\n[[entry]]\nid='other'\nname='Other'\ntype='efi'\npath='\\EFI\\EutherBoot\\TestChild.efi'\npartition_guid='{guid}'\n"
        );
        let parsed = parse(&format!("{BASE}{extra}")).unwrap();
        assert_eq!(parsed.entries()[0].partition_guid(), None);
        assert_eq!(parsed.entries()[1].partition_guid(), Some(guid));
        let qualified = format!("{BASE}\npartition_guid='{}'\n", guid.to_ascii_uppercase());
        assert_eq!(
            parse(&qualified).unwrap().entries()[0].partition_guid(),
            Some(guid)
        );
        assert!(parse(&format!("{qualified}{extra}")).is_err());
        for value in [
            "",
            "00000000-0000-0000-0000-000000000000",
            "aabbccdd123456789012aabbccddeeff",
            "aabbccdd-1234-5678-9012-aabbccddeefg",
            " aabbccdd-1234-5678-9012-aabbccddeeff",
        ] {
            assert!(parse(&format!("{BASE}\npartition_guid='{value}'")).is_err());
        }
        assert!(parse(&format!("{BASE}\npartition_guid=123")).is_err());
    }
    #[test]
    fn paths_never_escape_volume_or_use_ambiguous_aliases() {
        for p in [
            "\\EFI\\..\\bad.efi",
            "\\EFI\\.\\bad.efi",
            "EFI\\bad.efi",
            "\\EFI\\\\bad.efi",
            "\\EFI\\dir.\\bad.efi",
            "\\EFI\\TESTCH~1.EFI",
            "\\EFI\\bad.exe",
            "\\EFI\\bad name.efi",
            "\\EFI\\x:bad.efi",
            "\\EFI\\bad\u{1b}.efi",
            "\\EFI\\å.efi",
        ] {
            assert!(!valid_path(p), "accepted {p}");
        }
        assert!(valid_path("\\efi\\Linux\\arch-linux.EFI"));
    }
    #[test]
    fn bound_input_and_entry_count() {
        assert!(parse(&" ".repeat(MAX_BYTES + 1)).is_err());
        assert!(parse("[boot]\ndefault='x'\nentry=[]").is_err());
        let mut source = String::from("[boot]\ndefault='e0'\n");
        for i in 0..17 {
            source.push_str(&format!(
                "\n[[entry]]\nid='e{i}'\nname='Entry'\ntype='efi'\npath='\\EFI\\E{i}.efi'\n"
            ));
        }
        assert!(parse(&source).is_err());
    }
    #[test]
    fn display_controls_and_unicode_rejected() {
        for name in ["", "å", "\\u001b[2J", "\\n", &"x".repeat(49)] {
            assert!(parse(&BASE.replace("EFI test application", name)).is_err());
        }
    }
}
