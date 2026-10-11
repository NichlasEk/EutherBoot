//! Shared, bounded presentation vocabulary. Technical paths remain ASCII.
pub const THEMES: &[&str] = &[
    "system-regis",
    "text",
    "system-regis-light",
    "high-contrast",
];
pub const EXTRA_GLYPHS: &str = "ÅÄÖåäöÉé";
pub fn display_char(c: char) -> bool {
    (' '..='~').contains(&c) || EXTRA_GLYPHS.contains(c)
}
pub fn glyph_index(c: char) -> usize {
    if (' '..='~').contains(&c) {
        c as usize - 32
    } else {
        EXTRA_GLYPHS
            .chars()
            .position(|v| v == c)
            .map(|n| n + 95)
            .unwrap_or(31)
    }
}
/// Visual identification only: this does not probe disks or change boot targets.
/// Match whole words so "research" and "archived" do not look like Arch.
pub fn os_icon(label: &str) -> Option<&'static str> {
    let lower = label.to_ascii_lowercase();
    let words: alloc::vec::Vec<_> = lower
        .split(|c: char| !c.is_ascii_alphanumeric())
        .filter(|s| !s.is_empty())
        .collect();
    // Derivatives precede their parent distribution; generic Linux comes last.
    const ICONS: &[(&str, &[&str])] = &[
        ("windows", &["windows"]),
        ("ubuntumate", &["ubuntu mate"]),
        ("kubuntu", &["kubuntu"]),
        ("lubuntu", &["lubuntu"]),
        ("xubuntu", &["xubuntu"]),
        ("linuxmint", &["linux mint", "linuxmint", "mint", "lmde"]),
        ("endeavouros", &["endeavouros", "endeavour os", "endeavour"]),
        ("manjaro", &["manjaro"]),
        ("artixlinux", &["artix"]),
        ("garudalinux", &["garuda"]),
        ("nobaralinux", &["nobara"]),
        ("popos", &["pop os", "popos"]),
        ("elementary", &["elementary"]),
        ("kalilinux", &["kali"]),
        ("parrotsecurity", &["parrot"]),
        ("zorin", &["zorin"]),
        ("mxlinux", &["mx linux", "mxlinux", "mx"]),
        ("rockylinux", &["rocky"]),
        ("almalinux", &["almalinux", "alma linux"]),
        ("centos", &["centos", "cent os"]),
        ("archlinux", &["arch", "archlinux"]),
        ("debian", &["debian"]),
        ("ubuntu", &["ubuntu"]),
        ("fedora", &["fedora", "silverblue", "kinoite"]),
        ("opensuse", &["opensuse", "open suse", "suse", "tumbleweed"]),
        ("gentoo", &["gentoo"]),
        ("slackware", &["slackware"]),
        ("alpinelinux", &["alpine"]),
        ("nixos", &["nixos", "nix os"]),
        ("voidlinux", &["void"]),
        ("redhat", &["red hat", "redhat", "rhel"]),
        ("linux", &["linux", "gnu linux"]),
    ];
    for &(slug, aliases) in ICONS {
        for alias in aliases {
            let count = alias.split_ascii_whitespace().count();
            if words
                .windows(count)
                .any(|w| w.iter().copied().eq(alias.split_ascii_whitespace()))
            {
                return Some(slug);
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn os_icons_handle_suffixes_aliases_and_parent_names() {
        assert_eq!(os_icon("Debian GNU/Linux (reserv)"), Some("debian"));
        assert_eq!(os_icon("ARCH Linux LTS (reserv)"), Some("archlinux"));
        assert_eq!(os_icon("Windows Boot Manager"), Some("windows"));
        assert_eq!(os_icon("Pop!_OS recovery"), Some("popos"));
        assert_eq!(os_icon("Ubuntu MATE 24.04"), Some("ubuntumate"));
        assert_eq!(os_icon("Linux Mint Debian Edition"), Some("linuxmint"));
        assert_eq!(os_icon("Unknown Linux"), Some("linux"));
        for label in [
            "",
            "Research tools",
            "Archived backup",
            "Darwin",
            "UEFI Shell",
            "Euther Rescue",
        ] {
            assert_eq!(os_icon(label), None, "{label}");
        }
    }
    #[test]
    fn glyphs_and_validation_agree() {
        for (i, c) in (' '..='~').chain(EXTRA_GLYPHS.chars()).enumerate() {
            assert!(display_char(c));
            assert_eq!(glyph_index(c), i);
        }
        for c in ['\n', '\u{1b}', '\u{202e}', '\u{200b}', '\u{301}', '中'] {
            assert!(!display_char(c));
            assert_eq!(glyph_index(c), glyph_index('?'));
        }
    }
}
