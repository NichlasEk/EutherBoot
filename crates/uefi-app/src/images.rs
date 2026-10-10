//! Bounded read-only image classification and exact self-copy exclusion.
use crate::volumes::protocol;
use alloc::vec::Vec;
use boot_core::discovery::is_x64_application;
use uefi::{
    CString16, Handle, Status, boot,
    proto::{
        loaded_image::LoadedImage,
        media::{
            file::{Directory, File, FileAttribute, FileInfo, FileMode, RegularFile},
            fs::SimpleFileSystem,
        },
    },
};
fn read_prefix(file: &mut RegularFile, bytes: &mut [u8]) -> Result<usize, Status> {
    let mut used = 0;
    while used < bytes.len() {
        let n = file.read(&mut bytes[used..]).map_err(|e| e.status())?;
        if n == 0 {
            break;
        }
        used += n;
    }
    Ok(used)
}
pub(crate) fn own_bytes() -> Result<Vec<u8>, Status> {
    let name = CString16::try_from(crate::config::own_path()?.as_str())
        .map_err(|_| Status::UNSUPPORTED)?;
    let device = protocol::<LoadedImage>(boot::image_handle())?
        .device()
        .ok_or(Status::NOT_FOUND)?;
    let mut fs = protocol::<SimpleFileSystem>(device)?;
    let mut root = fs.open_volume().map_err(|e| e.status())?;
    let mut file = root
        .open(&name, FileMode::Read, FileAttribute::empty())
        .map_err(|e| e.status())?
        .into_regular_file()
        .ok_or(Status::UNSUPPORTED)?;
    let size = file
        .get_boxed_info::<FileInfo>()
        .map_err(|e| e.status())?
        .file_size();
    if size == 0 || size > 4 * 1024 * 1024 {
        return Err(Status::BAD_BUFFER_SIZE);
    }
    let mut bytes = Vec::new();
    bytes
        .try_reserve_exact(size as usize)
        .map_err(|_| Status::OUT_OF_RESOURCES)?;
    bytes.resize(size as usize, 0);
    if read_prefix(&mut file, &mut bytes)? != bytes.len() {
        return Err(Status::END_OF_FILE);
    }
    Ok(bytes)
}
/// Header classification and exact current-binary exclusion, including renamed copies.
pub(crate) fn candidate(
    root: &mut Directory,
    path: &str,
    own: &[u8],
    budget: &mut usize,
) -> Result<bool, Status> {
    // Charge the maximum requested bytes before each read, including self-copy comparisons.
    fn read(file: &mut RegularFile, bytes: &mut [u8], budget: &mut usize) -> Result<usize, Status> {
        *budget = budget
            .checked_sub(bytes.len())
            .ok_or(Status::OUT_OF_RESOURCES)?;
        read_prefix(file, bytes)
    }
    let name = CString16::try_from(path).map_err(|_| Status::UNSUPPORTED)?;
    let mut file = root
        .open(&name, FileMode::Read, FileAttribute::empty())
        .map_err(|e| e.status())?
        .into_regular_file()
        .ok_or(Status::UNSUPPORTED)?;
    let size = file
        .get_boxed_info::<FileInfo>()
        .map_err(|e| e.status())?
        .file_size();
    let mut prefix = [0u8; 4096];
    let n = read(&mut file, &mut prefix, budget)?;
    if !is_x64_application(&prefix[..n], size) {
        return Ok(false);
    }
    if size == own.len() as u64 {
        file.set_position(0).map_err(|e| e.status())?;
        let mut offset = 0;
        while offset < own.len() {
            let end = (offset + prefix.len()).min(own.len());
            let len = end - offset;
            if read(&mut file, &mut prefix[..len], budget)? != len {
                return Err(Status::END_OF_FILE);
            }
            if prefix[..len] != own[offset..end] {
                return Ok(true);
            }
            offset = end;
        }
        return Ok(false);
    }
    Ok(true)
}

pub fn verify(device: Handle, path: &str) -> Result<(), Status> {
    let own = own_bytes()?;
    let mut fs = protocol::<SimpleFileSystem>(device)?;
    let mut root = fs.open_volume().map_err(|e| e.status())?;
    if candidate(&mut root, path, &own, &mut (4 * 1024 * 1024 + 4096))? {
        Ok(())
    } else {
        Err(Status::UNSUPPORTED)
    }
}
