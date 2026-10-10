//! x86_64 EFI-stub setup. Preload initrd; Linux chooses its final location.
use crate::volumes::protocol;
use alloc::vec::Vec;
use boot_core::config::Entry;
use uefi::{
    CString16, Handle, Status,
    proto::media::{
        file::{File, FileAttribute, FileInfo, FileMode},
        fs::SimpleFileSystem,
    },
};

pub struct Prepared {
    pub options: CString16,
    pub initrd: Option<Vec<u8>>,
}
pub fn prepare(device: Handle, entry: &Entry) -> Result<Prepared, Status> {
    crate::initrd::ensure_absent()?;
    let options = boot_core::linux::load_options(entry.cmdline().unwrap_or(""), entry.initrd())
        .map_err(|_| Status::INVALID_PARAMETER)?;
    let mut fs = protocol::<SimpleFileSystem>(device)?;
    let mut root = fs.open_volume().map_err(|e| e.status())?;
    let path = CString16::try_from(entry.path()).map_err(|_| Status::INVALID_PARAMETER)?;
    let mut kernel = root
        .open(&path, FileMode::Read, FileAttribute::empty())
        .map_err(|e| e.status())?
        .into_regular_file()
        .ok_or(Status::UNSUPPORTED)?;
    let size = kernel
        .get_boxed_info::<FileInfo>()
        .map_err(|e| e.status())?
        .file_size();
    let mut header = [0u8; 4096];
    let mut n = 0;
    while n < header.len() {
        let read = kernel.read(&mut header[n..]).map_err(|e| e.status())?;
        if read == 0 {
            break;
        }
        n += read;
    }
    if !boot_core::linux::is_linux_efi(&header[..n], size) || n < 0x23c {
        return Err(Status::UNSUPPORTED);
    }
    let capacity = u32::from_le_bytes(header[0x238..0x23c].try_into().unwrap());
    if options.len() > capacity as usize {
        return Err(Status::BAD_BUFFER_SIZE);
    }
    let mut payload = None;
    if let Some(path) = entry.initrd() {
        if !boot_core::linux::supports_load_file2(&header[..n]) {
            return Err(Status::UNSUPPORTED);
        }
        let path = CString16::try_from(path).map_err(|_| Status::INVALID_PARAMETER)?;
        let mut initrd = root
            .open(&path, FileMode::Read, FileAttribute::empty())
            .map_err(|e| e.status())?
            .into_regular_file()
            .ok_or(Status::UNSUPPORTED)?;
        let size = initrd
            .get_boxed_info::<FileInfo>()
            .map_err(|e| e.status())?
            .file_size();
        if size == 0 || size > 128 * 1024 * 1024 {
            return Err(Status::BAD_BUFFER_SIZE);
        }
        let mut bytes = Vec::new();
        bytes
            .try_reserve_exact(size as usize)
            .map_err(|_| Status::OUT_OF_RESOURCES)?;
        bytes.resize(size as usize, 0);
        let mut offset = 0;
        while offset < bytes.len() {
            let end = (offset + 1024 * 1024).min(bytes.len());
            let read = initrd
                .read(&mut bytes[offset..end])
                .map_err(|e| e.status())?;
            if read == 0 {
                return Err(Status::END_OF_FILE);
            }
            offset += read;
        }
        // Detect growth during the read; never silently truncate the selected file.
        if initrd.read(&mut [0u8; 1]).map_err(|e| e.status())? != 0 {
            return Err(Status::BAD_BUFFER_SIZE);
        }
        crate::trace("INITRD_PRELOADED");
        payload = Some(bytes);
    }
    crate::trace("LINUX_EFI_PREPARED");
    Ok(Prepared {
        options: CString16::try_from(options.as_str()).map_err(|_| Status::INVALID_PARAMETER)?,
        initrd: payload,
    })
}
