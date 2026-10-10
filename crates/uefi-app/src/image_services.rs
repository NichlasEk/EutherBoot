//! Narrow adapters for uefi-rs 0.40 ownership gaps: rejected handles and ExitData.
//! ABI types come from uefi-raw; no local firmware-table layout is invented.
use crate::loader::LoadError;
use core::ptr;
use uefi::{Handle, Status, boot, proto::device_path::DevicePath, table};

pub fn load(path: &DevicePath) -> Result<Handle, LoadError> {
    let table = table::system_table_raw().ok_or(LoadError::Device(Status::NOT_READY))?;
    // SAFETY: helpers initialized the table; these calls occur only in boot services.
    // Copy the function pointer so no table/protocol borrow survives child execution.
    let load = unsafe { (*table.as_ref().boot_services).load_image };
    let mut raw = ptr::null_mut();
    // SAFETY: full path is valid through this call; output points to a writable handle.
    let status = unsafe {
        load(
            uefi_raw::Boolean::FALSE,
            boot::image_handle().as_ptr(),
            path.as_ffi_ptr().cast(),
            ptr::null(),
            0,
            &mut raw,
        )
    };
    // SAFETY: UEFI returns an image handle, or null. It may be set on security rejection.
    let child = unsafe { Handle::from_ptr(raw) };
    if status.is_error() {
        if let Some(child) = child {
            crate::trace(&alloc::format!("LOAD_REJECTED_HANDLE {status:?}"));
            boot::unload_image(child).map_err(|e| LoadError::Cleanup(e.status()))?;
        }
        return Err(LoadError::Load(status));
    }
    child.ok_or(LoadError::Load(Status::LOAD_ERROR))
}
pub fn start(child: Handle) -> Result<(), LoadError> {
    let table = table::system_table_raw().ok_or(LoadError::Device(Status::NOT_READY))?;
    // SAFETY: valid initialized boot services, as in load().
    let start = unsafe { (*table.as_ref().boot_services).start_image };
    let mut size = 0;
    let mut data = ptr::null_mut();
    // SAFETY: live loaded handle and writable output fields; no protocol borrows held.
    let status = unsafe { start(child.as_ptr(), &mut size, &mut data) };
    if let Some(data) = ptr::NonNull::new(data.cast::<u8>()) {
        // SAFETY: StartImage allocates ExitData from pool; caller owns it after return.
        // Never interpret or print untrusted child-provided bytes.
        unsafe { boot::free_pool(data) }.map_err(|e| LoadError::Cleanup(e.status()))?;
        crate::trace(&alloc::format!("EXIT_DATA_FREED bytes={size}"));
    }
    if status.is_error() {
        Err(LoadError::Start(status))
    } else {
        Ok(())
    }
}
