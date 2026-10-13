//! Optional, read-only metadata; errors never disable a boot entry.
use alloc::{string::String, vec::Vec};
use boot_core::config::Entry;
use uefi::{
    CString16,
    proto::media::{
        file::{File, FileAttribute, FileInfo, FileMode},
        fs::SimpleFileSystem,
    },
};

pub fn collect(entries: &[Entry]) -> Vec<Option<String>> {
    entries
        .iter()
        .map(|entry| {
            let value = inspect(entry);
            if let Some(version) = &value {
                crate::trace(&alloc::format!("KERNEL_VERSION {} {version}", entry.id()));
            }
            value
        })
        .collect()
}
fn inspect(entry: &Entry) -> Option<String> {
    let device = crate::loader::entry_device(entry).ok()?;
    let mut fs = crate::volumes::protocol::<SimpleFileSystem>(device).ok()?;
    let mut root = fs.open_volume().ok()?;
    let path = CString16::try_from(entry.path()).ok()?;
    let mut file = root
        .open(&path, FileMode::Read, FileAttribute::empty())
        .ok()?
        .into_regular_file()?;
    let size = file.get_boxed_info::<FileInfo>().ok()?.file_size();
    boot_core::kernel_version::read(size, |offset, mut out| {
        if offset.checked_add(out.len() as u64)? > size {
            return None;
        }
        file.set_position(offset).ok()?;
        while !out.is_empty() {
            let n = file.read(out).ok()?;
            if n == 0 {
                return None;
            }
            out = &mut out[n..];
        }
        Some(())
    })
}
