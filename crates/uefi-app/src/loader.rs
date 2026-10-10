//! Chainload an explicit path on an explicit volume.
use core::mem::MaybeUninit;
use uefi::{
    CString16, Handle, Status,
    boot::{self, LoadImageSource, OpenProtocolParams},
    proto::{
        BootPolicy,
        device_path::{
            DevicePath,
            build::{DevicePathBuilder, media::FilePath},
        },
        loaded_image::LoadedImage,
    },
};

#[derive(Debug)]
pub enum LoadError {
    Device(Status),
    Target(alloc::string::String),
    PathTooLong,
    Load(Status),
    Start(Status),
    Cleanup(Status),
}

/// Every explicit partition selector is resolved anew. No fallback to our own volume.
pub fn entry_device(entry: &boot_core::config::Entry) -> Result<Handle, LoadError> {
    match entry.partition_guid() {
        Some(guid) => crate::volumes::resolve(guid).map_err(LoadError::Target),
        None => crate::volumes::own_device().map_err(LoadError::Device),
    }
}
pub fn chainload(entry: &boot_core::config::Entry) -> Result<(), LoadError> {
    let device = entry_device(entry)?;
    if entry.partition_guid().is_some() {
        crate::images::verify(device, entry.path())
            .map_err(|s| LoadError::Target(alloc::format!("EFI target check: {s:?}")))?;
    }
    chainload_path(device, entry.path())
}

pub fn chainload_path(device: Handle, filename: &str) -> Result<(), LoadError> {
    let filename =
        CString16::try_from(filename).map_err(|_| LoadError::Device(Status::INVALID_PARAMETER))?;
    let mut buffer = [MaybeUninit::uninit(); 4096];
    let path = {
        let volume = boot::open_protocol_exclusive::<DevicePath>(device)
            .map_err(|e| LoadError::Device(e.status()))?;
        let mut builder = DevicePathBuilder::with_buf(&mut buffer);
        for node in volume.node_iter() {
            builder = builder.push(&node).map_err(|_| LoadError::PathTooLong)?;
        }
        builder
            .push(&FilePath {
                path_name: &filename,
            })
            .and_then(|b| b.finalize())
            .map_err(|_| LoadError::PathTooLong)?
    };
    // Protocol borrows are dropped before control can pass to the child.
    let child = boot::load_image(
        boot::image_handle(),
        LoadImageSource::FromDevicePath {
            device_path: path,
            boot_policy: BootPolicy::ExactMatch,
        },
    )
    .map_err(|e| LoadError::Load(e.status()))?;
    crate::trace("CHAINLOAD_LOADED");
    let result = boot::start_image(child).map_err(|e| LoadError::Start(e.status()));
    // UEFI unloads applications on return/Exit. Do not blindly unload a stale
    // handle. A pre-entry refusal may leave the loaded image alive instead.
    match boot::test_protocol::<LoadedImage>(OpenProtocolParams {
        handle: child,
        agent: boot::image_handle(),
        controller: None,
    }) {
        Ok(true) => {
            boot::unload_image(child).map_err(|e| LoadError::Cleanup(e.status()))?;
            crate::trace("CHAINLOAD_UNLOADED");
        }
        Ok(false) => crate::trace("CHAINLOAD_RELEASED"),
        Err(e) if e.status() == Status::INVALID_PARAMETER || e.status() == Status::UNSUPPORTED => {
            crate::trace("CHAINLOAD_RELEASED");
        }
        Err(e) => return Err(LoadError::Cleanup(e.status())),
    }
    result
}

impl LoadError {
    pub fn notice(&self) -> alloc::string::String {
        let (stage, status) = match self {
            Self::Target(message) => return alloc::format!("{message}. Menu retained."),
            Self::Device(s) => ("Device", *s),
            Self::PathTooLong => ("Device path", Status::BAD_BUFFER_SIZE),
            Self::Load(s) => ("LoadImage", *s),
            Self::Start(s) => ("StartImage / child exit", *s),
            Self::Cleanup(s) => ("Cleanup", *s),
        };
        alloc::format!("{stage}: {status:?}. Menu retained.")
    }
}
