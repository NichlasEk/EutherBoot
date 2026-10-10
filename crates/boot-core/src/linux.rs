//! Conservative EFI-stub policy, not a Linux bzImage/ELF loader.
use crate::config;
use alloc::string::String;

pub const MAX_CMDLINE: usize = 1024;
pub fn valid_cmdline(value: &str) -> bool {
    value.len() <= MAX_CMDLINE
        && value.bytes().all(|b| (32..=126).contains(&b))
        // Keep the initrd source explicit and tied to the selected volume.
        && !value.contains("initrd=")
}
pub fn load_options(cmdline: &str, initrd: Option<&str>) -> Result<String, String> {
    if !valid_cmdline(cmdline) {
        return Err("cmdline must be <=1024 printable ASCII bytes without initrd=".into());
    }
    match initrd {
        Some(path) => {
            if !config::valid_esp_path(path) || cmdline.contains("noinitrd") {
                return Err(
                    "initrd requires an absolute EFI path and cannot be combined with noinitrd"
                        .into(),
                );
            }
            // Initrd bytes travel through LoadFile2, never via command-line paths.
            Ok(cmdline.into())
        }
        None => Ok(cmdline.into()),
    }
}
/// Linux EFI stub v1/v2 support LoadFile2; v3+ uses a feature bitmask.
/// See Linux include/linux/pe.h. This is independent of the x86 HdrS version.
pub fn supports_load_file2(prefix: &[u8]) -> bool {
    let check = || -> Option<bool> {
        let pe = u32::from_le_bytes(prefix.get(0x3c..0x40)?.try_into().ok()?) as usize;
        let version = u16::from_le_bytes(prefix.get(pe + 68..pe + 70)?.try_into().ok()?);
        Some(matches!(version, 1 | 2) || (version >= 3 && version & 1 != 0))
    };
    check().unwrap_or(false)
}
pub fn is_linux_efi(prefix: &[u8], size: u64) -> bool {
    crate::discovery::is_x64_application(prefix, size)
        && prefix.get(0x1fe..0x200) == Some(&[0x55, 0xaa])
        && prefix.get(0x202..0x206) == Some(b"HdrS")
        && prefix
            .get(0x206..0x208)
            .is_some_and(|b| u16::from_le_bytes([b[0], b[1]]) >= 0x20b)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn initrd_capability_uses_efi_stub_version_not_x86_boot_version() {
        let mut prefix = [0u8; 256];
        prefix[0x3c] = 64;
        for (version, supported) in [
            (0u16, false),
            (1, true),
            (2, true),
            (3, true),
            (4, false),
            (5, true),
        ] {
            prefix[132..134].copy_from_slice(&version.to_le_bytes());
            assert_eq!(supports_load_file2(&prefix), supported);
        }
        assert!(!supports_load_file2(&prefix[..133]));
    }
    #[test]
    fn options_keep_initrd_out_of_kernel_arguments() {
        assert_eq!(
            load_options("console=ttyS0 -- test", Some("\\EFI\\Linux\\initrd.img")).unwrap(),
            "console=ttyS0 -- test"
        );
        for command in [
            "bad\nvalue",
            "x\0y",
            "å",
            "initrd=\\wrong",
            "\"initrd=\\wrong\"",
        ] {
            assert!(load_options(command, None).is_err());
        }
        assert!(load_options(&"x".repeat(MAX_CMDLINE + 1), None).is_err());
        assert!(load_options("noinitrd", Some("\\EFI\\Linux\\initrd.img")).is_err());
        assert!(load_options("", Some("\\EFI\\..\\initrd.img")).is_err());
        assert!(!is_linux_efi(b"ELF kernel", 4096));
    }
}
