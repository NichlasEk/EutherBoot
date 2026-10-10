//! Conservative discovery filters, not an executable validator or trust decision.

/// Paths from directory records must not contain separators, traversal or console controls.
pub fn safe_component(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 128
        && name != "."
        && name != ".."
        && !name.ends_with([' ', '.'])
        && name.bytes().all(|b| b.is_ascii_graphic() || b == b' ')
        && !name.contains(['\\', '/', ':', '*', '?', '"', '<', '>', '|'])
}

/// Only classify bounded PE32+ x86_64 EFI applications. Firmware LoadImage is
/// still responsible for full validation and Secure Boot authentication.
pub fn is_x64_application(prefix: &[u8], file_size: u64) -> bool {
    fn u16_at(b: &[u8], n: usize) -> Option<u16> {
        Some(u16::from_le_bytes(b.get(n..n + 2)?.try_into().ok()?))
    }
    fn u32_at(b: &[u8], n: usize) -> Option<u32> {
        Some(u32::from_le_bytes(b.get(n..n + 4)?.try_into().ok()?))
    }
    let check = || -> Option<bool> {
        if prefix.get(..2)? != b"MZ" || file_size > 128 * 1024 * 1024 {
            return Some(false);
        }
        let pe = u32_at(prefix, 0x3c)? as usize;
        if !(64..=3072).contains(&pe) || prefix.get(pe..pe + 4)? != b"PE\0\0" {
            return Some(false);
        }
        let sections = u16_at(prefix, pe + 6)?;
        let optional_size = u16_at(prefix, pe + 20)? as usize;
        let optional = pe + 24;
        Some(
            u16_at(prefix, pe + 4)? == 0x8664
                && (1..=96).contains(&sections)
                && optional_size >= 112
                && optional + optional_size <= prefix.len()
                && (optional + optional_size + usize::from(sections) * 40) as u64 <= file_size
                && u16_at(prefix, optional)? == 0x20b
                && u16_at(prefix, optional + 68)? == 10,
        )
    };
    check().unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn file_names_cannot_escape_or_control_display() {
        for bad in [
            "", ".", "..", "foo/efi", "foo\\efi", "x:", "x\n", "x\u{1b}", "x.", "x ", "å.efi",
        ] {
            assert!(!safe_component(bad), "{bad:?}");
        }
        assert!(safe_component("bootx64.EFI"));
        assert!(safe_component("Boot Tools"));
    }
    #[test]
    fn classification_rejects_truncation_wrong_architecture_and_drivers() {
        let mut image = [0u8; 512];
        image[..2].copy_from_slice(b"MZ");
        image[0x3c] = 64;
        image[64..68].copy_from_slice(b"PE\0\0");
        image[68..70].copy_from_slice(&0x8664u16.to_le_bytes());
        image[70] = 1;
        image[84] = 112;
        image[88..90].copy_from_slice(&0x20bu16.to_le_bytes());
        image[156] = 10;
        assert!(is_x64_application(&image, 512));
        for n in 0..200 {
            assert!(!is_x64_application(&image[..n], n as u64));
        }
        for (offset, value) in [
            (68, 0x4c),
            (88, 0x0b),
            (156, 11),
            (156, 12),
            (70, 0),
            (84, 80),
        ] {
            let mut bad = image;
            bad[offset] = value;
            // PE32 magic must actually differ from PE32+ (low byte is shared).
            if offset == 88 {
                bad[89] = 1;
            }
            assert!(!is_x64_application(&bad, 512));
        }
        image[0x3c..0x40].copy_from_slice(&u32::MAX.to_le_bytes());
        assert!(!is_x64_application(&image, u64::MAX));
    }
}
