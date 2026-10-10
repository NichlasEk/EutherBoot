//! x86_64 EFI-stub setup. Linux owns initrd loading and ExitBootServices.
use crate::volumes::protocol;
use boot_core::config::Entry;
use uefi::{
    CString16, Handle, Status,
    proto::media::{
        file::{File, FileAttribute, FileInfo, FileMode},
        fs::SimpleFileSystem,
    },
};

pub fn prepare(device: Handle, entry: &Entry) -> Result<CString16, Status> {
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
    if let Some(path) = entry.initrd() {
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
        // The EFI stub reads the payload itself; check readability before transferring control.
        if initrd.read(&mut [0u8; 1]).map_err(|e| e.status())? != 1 {
            return Err(Status::END_OF_FILE);
        }
    }
    crate::trace("LINUX_EFI_PREPARED");
    CString16::try_from(options.as_str()).map_err(|_| Status::INVALID_PARAMETER)
}
