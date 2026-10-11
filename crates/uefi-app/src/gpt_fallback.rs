//! Read-only compatibility path when firmware omits PartitionInfo.
use crate::volumes::protocol;
use alloc::{format, vec, vec::Vec};
use boot_core::gpt;
use uefi::{
    Guid, Handle, Status, boot,
    proto::{device_path::DevicePath, media::block::BlockIO},
};
fn error(e: gpt::Error) -> Status {
    match e {
        gpt::Error::NotGpt | gpt::Error::NotEsp => Status::UNSUPPORTED,
        gpt::Error::Invalid => Status::VOLUME_CORRUPTED,
    }
}
fn read(io: &BlockIO, lba: u64, len: usize) -> Result<Vec<u8>, Status> {
    let m = io.media();
    let block = m.block_size() as usize;
    let align = (m.io_align() as usize).max(1);
    if !(512..=4096).contains(&block)
        || !block.is_power_of_two()
        || !align.is_power_of_two()
        || align > 1024 * 1024
        || len == 0
        || len > 1024 * 1024
    {
        return Err(Status::BAD_BUFFER_SIZE);
    }
    let size = len.div_ceil(block) * block;
    if lba
        .checked_add((size / block - 1) as u64)
        .ok_or(Status::VOLUME_CORRUPTED)?
        > m.last_block()
    {
        return Err(Status::VOLUME_CORRUPTED);
    }
    let mut buf = vec![0u8; size + align - 1];
    let offset = buf.as_ptr().align_offset(align);
    let bytes = &mut buf[offset..offset + size];
    io.read_blocks(m.media_id(), lba, bytes)
        .map_err(|e| e.status())?;
    Ok(bytes[..len].to_vec())
}
pub fn identity(handle: Handle) -> Result<Guid, Status> {
    let path = protocol::<DevicePath>(handle).map_err(|s| {
        if s == Status::UNSUPPORTED {
            Status::NOT_FOUND
        } else {
            s
        }
    })?;
    let p = gpt::partition_path(path.as_bytes()).map_err(error)?;
    drop(path); // GET_PROTOCOL opens are not reference-counted by all firmware.
    let handles = boot::find_handles::<BlockIO>().map_err(|e| e.status())?;
    if handles.len() > 128 {
        return Err(Status::OUT_OF_RESOURCES);
    }
    let mut parent = None;
    for h in handles {
        let Ok(path) = protocol::<DevicePath>(h) else {
            continue;
        };
        if path.as_bytes() != p.parent {
            continue;
        }
        let io = protocol::<BlockIO>(h)?;
        if io.media().is_logical_partition() {
            continue;
        }
        if parent.replace(h).is_some() {
            return Err(Status::VOLUME_CORRUPTED);
        }
    }
    let io = protocol::<BlockIO>(parent.ok_or(Status::NOT_FOUND)?)?;
    let block = io.media().block_size() as usize;
    let b = read(&io, 1, block)?;
    let h = gpt::header(&b, io.media().last_block()).map_err(error)?;
    let table = read(&io, h.table_lba, h.table_bytes)?;
    let guid = Guid::from_bytes(gpt::verify(&h, &table, &p).map_err(error)?);
    crate::trace(&format!("ESP_GPT_FALLBACK {guid}"));
    Ok(guid)
}
