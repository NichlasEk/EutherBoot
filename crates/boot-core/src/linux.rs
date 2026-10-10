//! Conservative EFI-stub policy, not a Linux bzImage/ELF loader.
use crate::config;
use alloc::{format, string::String};

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
            // Precede user arguments, including any '--' terminator.
            Ok(format!("initrd={path} {cmdline}"))
        }
        None => Ok(cmdline.into()),
    }
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
    fn options_keep_initrd_explicit_before_kernel_arguments() {
        assert_eq!(
            load_options("console=ttyS0 -- test", Some("\\EFI\\Linux\\initrd.img")).unwrap(),
            "initrd=\\EFI\\Linux\\initrd.img console=ttyS0 -- test"
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
