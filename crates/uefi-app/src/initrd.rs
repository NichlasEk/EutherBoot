//! Owned, temporary Linux LoadFile2 provider. No filesystem access in the callback.
use alloc::{boxed::Box, vec::Vec};
use core::{
    ffi::c_void,
    mem::MaybeUninit,
    ptr::{self, NonNull},
};
use uefi::{
    Handle, Identify, Status, boot, guid,
    proto::{
        device_path::{
            DevicePath,
            build::{DevicePathBuilder, media::Vendor},
        },
        media::load_file::LoadFile2,
    },
};
use uefi_raw::{
    Boolean,
    protocol::{
        device_path::{DevicePathProtocol, DeviceSubType, DeviceType},
        media::LoadFile2Protocol,
    },
};

const INITRD_GUID: uefi::Guid = guid!("5568e427-68fc-4f3d-ac74-ca555231cc68");
fn path(buffer: &mut [MaybeUninit<u8>; 24]) -> Result<&DevicePath, Status> {
    DevicePathBuilder::with_buf(buffer)
        .push(&Vendor {
            vendor_guid: INITRD_GUID,
            vendor_defined_data: &[],
        })
        .and_then(|b| b.finalize())
        .map_err(|_| Status::BAD_BUFFER_SIZE)
}
pub fn ensure_absent() -> Result<(), Status> {
    let mut buffer = [MaybeUninit::uninit(); 24];
    let mut device_path = path(&mut buffer)?;
    match boot::locate_device_path::<LoadFile2>(&mut device_path) {
        Ok(_) => Err(Status::ALREADY_STARTED),
        Err(e) if e.status() == Status::NOT_FOUND => Ok(()),
        Err(e) => Err(e.status()),
    }
}

#[repr(C)]
struct Context {
    protocol: LoadFile2Protocol, // first field: callback's This points at Context
    data: Vec<u8>,
    path: [MaybeUninit<u8>; 24],
}
// SAFETY: Firmware invokes this only while Context is registered and alive. UEFI
// callers must supply readable input pointers and a writable buffer of BufferSize
// bytes. NULLs and path/policy/size are checked; arbitrary invalid pointers cannot
// be validated by a firmware service. No allocation, protocol borrowing or I/O.
unsafe extern "efiapi" fn load(
    this: *mut LoadFile2Protocol,
    file_path: *const DevicePathProtocol,
    policy: Boolean,
    size: *mut usize,
    buffer: *mut c_void,
) -> Status {
    if this.is_null() || file_path.is_null() || size.is_null() {
        return Status::INVALID_PARAMETER;
    }
    if policy != Boolean::FALSE {
        return Status::UNSUPPORTED;
    }
    // SAFETY: The callback contract guarantees a readable node header.
    let node = unsafe { ptr::read_unaligned(file_path) };
    if node.major_type != DeviceType::END
        || node.sub_type != DeviceSubType::END_ENTIRE
        || node.length != [4, 0]
    {
        return Status::NOT_FOUND;
    }
    // SAFETY: repr(C) first field, stable allocation, immutable while published.
    // Borrow only payload, disjoint from the caller's mutable protocol interface.
    let data = unsafe { &(*this.cast::<Context>()).data };
    let required = data.len();
    let capacity = unsafe { size.read_unaligned() };
    unsafe {
        size.write_unaligned(required);
    }
    if buffer.is_null() || capacity < required {
        crate::trace("INITRD_SIZE_QUERY");
        return Status::BUFFER_TOO_SMALL;
    }
    // SAFETY: Caller owns a writable buffer of at least required bytes, distinct
    // from this private immutable payload. Payload is live until unregistration.
    unsafe {
        ptr::copy_nonoverlapping(data.as_ptr(), buffer.cast(), required);
    }
    crate::trace("INITRD_COPIED");
    Status::SUCCESS
}

pub struct Provider {
    context: NonNull<Context>,
    handle: Option<Handle>,
    published: bool,
    #[cfg(feature = "test-faults")]
    fail_cleanup_once: bool,
}
impl Provider {
    pub fn install(data: Vec<u8>) -> Result<Self, Status> {
        ensure_absent()?;
        if data.is_empty() {
            return Err(Status::INVALID_PARAMETER);
        }
        let mut context = Box::new(Context {
            protocol: LoadFile2Protocol { load_file: load },
            data,
            path: [MaybeUninit::uninit(); 24],
        });
        path(&mut context.path)?;
        // Raw ownership avoids holding a Rust &mut Context across synchronous
        // protocol notifications or child callbacks. Drop always reclaims it.
        let context = NonNull::new(Box::into_raw(context)).unwrap();
        let mut owner = Self {
            context,
            handle: None,
            published: false,
            #[cfg(feature = "test-faults")]
            fail_cleanup_once: fault() == "cleanup",
        };
        // SAFETY: Both interfaces point into the stable context allocation. The
        // complete device path is installed first; the callable protocol last.
        let handle =
            unsafe { boot::install_protocol_interface(None, &DevicePath::GUID, owner.path_ptr()) }
                .map_err(|e| e.status())?;
        owner.handle = Some(handle);
        #[cfg(feature = "test-faults")]
        if fault() == "install" {
            return Err(Status::DEVICE_ERROR);
        }
        unsafe {
            boot::install_protocol_interface(
                Some(handle),
                &LoadFile2::GUID,
                context.as_ptr().cast(),
            )
        }
        .map_err(|e| e.status())?;
        owner.published = true;
        crate::trace("INITRD_INSTALLED");
        Ok(owner)
    }
    fn path_ptr(&self) -> *const c_void {
        // SAFETY: Context exists for the entire owner lifetime; no reference escapes.
        unsafe { ptr::addr_of!((*self.context.as_ptr()).path).cast() }
    }
    fn remove(&mut self) -> Result<(), Status> {
        #[cfg(feature = "test-faults")]
        if self.fail_cleanup_once {
            self.fail_cleanup_once = false;
            return Err(Status::ACCESS_DENIED);
        }
        if let Some(handle) = self.handle {
            if self.published {
                // SAFETY: Child execution/borrows have ended. A firmware refusal
                // retains the allocation and prevents returning to our caller.
                unsafe {
                    boot::uninstall_protocol_interface(
                        handle,
                        &LoadFile2::GUID,
                        self.context.as_ptr().cast(),
                    )
                }
                .map_err(|e| e.status())?;
                self.published = false;
            }
            unsafe {
                boot::uninstall_protocol_interface(handle, &DevicePath::GUID, self.path_ptr())
            }
            .map_err(|e| e.status())?;
            self.handle = None;
            crate::trace("INITRD_REMOVED");
        }
        Ok(())
    }
}
impl Drop for Provider {
    fn drop(&mut self) {
        while let Err(status) = self.remove() {
            // Leaking data alone would not keep callback *code* alive if EutherBoot
            // returned/unloaded. Keep control until removal succeeds; never proceed
            // to another image or firmware with our callback still registered.
            crate::trace("INITRD_CLEANUP_BLOCKED");
            uefi::system::with_stdout(|out| {
                let _ = out.clear();
            });
            uefi::println!(
                "EUTHERBOOT / INITRD CLEANUP\n\nProtocol removal failed: {status:?}\nR: retry cleanup. Or power off the machine.\nBoot and firmware return are blocked while the provider is active."
            );
            loop {
                if let Ok(Some(uefi::proto::console::text::Key::Printable(c))) =
                    uefi::system::with_stdin(|stdin| stdin.read_key())
                {
                    if char::from(c).eq_ignore_ascii_case(&'r') {
                        break;
                    }
                }
                boot::stall(core::time::Duration::from_millis(10));
            }
        }
        // SAFETY: No installed interfaces remain. Exactly one owner reclaims Box.
        unsafe {
            drop(Box::from_raw(self.context.as_ptr()));
        }
    }
}

#[cfg(feature = "test-faults")]
fn fault() -> alloc::string::String {
    use boot_core::transaction::Store;
    crate::storage::UefiStore::open()
        .ok()
        .and_then(|mut s| s.read("initrd-fault").ok().flatten())
        .and_then(|b| alloc::string::String::from_utf8(b).ok())
        .unwrap_or_default()
}
