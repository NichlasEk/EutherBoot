//! Chainload an explicit path on an explicit volume.
use core::mem::MaybeUninit;
use uefi::{
    CString16, Handle, Status,
    boot::{self, OpenProtocolParams},
    proto::{
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
    if entry.partition_guid().is_some() || entry.kind() == boot_core::config::EntryKind::LinuxEfi {
        crate::images::verify(device, entry.path())
            .map_err(|s| LoadError::Target(alloc::format!("EFI target check: {s:?}")))?;
    }
    let prepared = if entry.kind() == boot_core::config::EntryKind::LinuxEfi {
        Some(
            crate::linux::prepare(device, entry)
                .map_err(|s| LoadError::Target(alloc::format!("Linux EFI setup: {s:?}")))?,
        )
    } else {
        None
    };
    launch(device, entry.path(), prepared)
}

pub fn chainload_path(device: Handle, filename: &str) -> Result<(), LoadError> {
    launch(device, filename, None)
}
fn launch(
    device: Handle,
    filename: &str,
    prepared: Option<crate::linux::Prepared>,
) -> Result<(), LoadError> {
    let (mut options, payload) = match prepared {
        Some(p) => (Some(p.options), p.initrd),
        None => (None, None),
    };
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
    let child = crate::image_services::load(path)?;
    if let Some(options) = &options {
        let mut image = match boot::open_protocol_exclusive::<LoadedImage>(child) {
            Ok(image) => image,
            Err(e) => {
                boot::unload_image(child).map_err(|e| LoadError::Cleanup(e.status()))?;
                return Err(LoadError::Device(e.status()));
            }
        };
        // SAFETY: CString16 owns stable, NUL-terminated UCS-2 storage. It remains
        // live until StartImage returns and the child is released/unloaded.
        unsafe {
            image.set_load_options(options.as_ptr().cast(), options.num_bytes() as u32);
        }
        crate::trace(&alloc::format!(
            "LOAD_OPTIONS_SET bytes={}",
            options.num_bytes()
        ));
    }
    // Register after successful image authentication, before child execution.
    let provider = payload.map(crate::initrd::Provider::install).transpose();
    let result = match &provider {
        Ok(_) => {
            crate::trace("CHAINLOAD_LOADED");
            crate::image_services::start(child)
        }
        Err(s) => Err(LoadError::Target(alloc::format!("Initrd provider: {s:?}"))),
    };
    // Provider is dropped after the child's release/unload check, even on errors.

    // UEFI unloads applications on return/Exit. Do not blindly unload a stale
    // handle. A pre-entry refusal may leave the loaded image alive instead.
    match boot::test_protocol::<LoadedImage>(OpenProtocolParams {
        handle: child,
        agent: boot::image_handle(),
        controller: None,
    }) {
        Ok(true) => {
            if let Err(e) = boot::unload_image(child) {
                // A live image may still retain the pointer. Leak only on failed cleanup,
                // rather than freeing referenced storage. Provider Drop still runs.
                core::mem::forget(options.take());
                return Err(LoadError::Cleanup(e.status()));
            }
            crate::trace("CHAINLOAD_UNLOADED");
        }
        Ok(false) => crate::trace("CHAINLOAD_RELEASED"),
        Err(e) if e.status() == Status::INVALID_PARAMETER || e.status() == Status::UNSUPPORTED => {
            crate::trace("CHAINLOAD_RELEASED");
        }
        Err(e) => {
            core::mem::forget(options.take());
            return Err(LoadError::Cleanup(e.status()));
        }
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
