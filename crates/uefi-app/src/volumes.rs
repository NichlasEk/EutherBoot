//! Explicit GPT ESP identity. Never choose the first of ambiguous matches.
use alloc::{format, string::String};
use uefi::{
    Guid, Handle, Status, boot,
    proto::{
        ProtocolPointer,
        loaded_image::LoadedImage,
        media::{
            fs::SimpleFileSystem,
            partition::{GptPartitionAttributes, GptPartitionType, PartitionInfo},
        },
    },
};
pub const MAX_VOLUMES: usize = 32;
// SAFETY: callers are synchronous and never disconnect, uninstall protocols or
// run another image while a borrow is held. GET_PROTOCOL preserves drivers.
pub(crate) fn protocol<P: ProtocolPointer + ?Sized>(
    handle: Handle,
) -> Result<boot::ScopedProtocol<P>, Status> {
    unsafe {
        boot::open_protocol::<P>(
            boot::OpenProtocolParams {
                handle,
                agent: boot::image_handle(),
                controller: None,
            },
            boot::OpenProtocolAttributes::GetProtocol,
        )
    }
    .map_err(|e| e.status())
}
pub(crate) fn identity(handle: Handle) -> Result<Guid, Status> {
    // Absence of the protocol is not evidence that this is a non-ESP.
    // Keep it distinct from the deliberate exclusions below.
    let partition = partition_info(handle).map_err(|s| {
        if s == Status::UNSUPPORTED {
            Status::NOT_FOUND
        } else {
            s
        }
    })?;
    let entry = partition.gpt_partition_entry().ok_or(Status::UNSUPPORTED)?;
    let kind = entry.partition_type_guid;
    let attributes = entry.attributes;
    let id = entry.unique_partition_guid;
    if kind != GptPartitionType::EFI_SYSTEM_PARTITION
        || attributes.contains(GptPartitionAttributes::LEGACY_BIOS_BOOTABLE)
        || id == uefi::guid!("00000000-0000-0000-0000-000000000000")
    {
        return Err(Status::UNSUPPORTED);
    }
    Ok(id)
}

pub fn own_device() -> Result<Handle, Status> {
    protocol::<LoadedImage>(boot::image_handle())?
        .device()
        .ok_or(Status::NOT_FOUND)
}
pub fn own_guid() -> Option<String> {
    identity(own_device().ok()?).ok().map(|id| format!("{id}"))
}
pub fn resolve(guid: &str) -> Result<Handle, String> {
    if !boot_core::config::valid_partition_guid(guid) {
        return Err("Invalid partition GUID".into());
    }
    let handles = boot::find_handles::<SimpleFileSystem>()
        .map_err(|s| format!("ESP enumeration: {:?}", s.status()))?;
    if handles.len() > MAX_VOLUMES {
        return Err("ESP enumeration exceeds 32 filesystem handles".into());
    }
    let mut found = None;
    for handle in handles {
        match identity(handle) {
            Ok(id) if format!("{id}").eq_ignore_ascii_case(guid) => {
                if found.is_some() {
                    return Err(format!("Ambiguous ESP GUID {guid}"));
                }
                found = Some(handle);
            }
            Ok(_) | Err(Status::UNSUPPORTED) => {}
            Err(Status::NOT_FOUND) => {
                return Err("Firmware lacks PartitionInfo; cannot verify ESP identities".into());
            }
            Err(s) => return Err(format!("Cannot verify all ESP identities: {s:?}")),
        }
    }
    found.ok_or_else(|| format!("Missing ESP GUID {guid}"))
}

// Test-only firmware compatibility injection. Production never reads the marker.
fn partition_info(handle: Handle) -> Result<boot::ScopedProtocol<PartitionInfo>, Status> {
    #[cfg(feature = "test-faults")]
    {
        use boot_core::transaction::Store;
        if own_device().ok() != Some(handle)
            && crate::storage::UefiStore::open()
                .ok()
                .and_then(|mut s| s.read("volume-fault").ok().flatten())
                .as_deref()
                == Some(b"missing-partition-info")
        {
            return Err(Status::UNSUPPORTED);
        }
    }
    protocol::<PartitionInfo>(handle)
}
