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
#[cfg(test)]
mod tests {
    use super::*;
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
