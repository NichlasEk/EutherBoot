//! Independent consumer for the temporary LoadFile2 provider integration test.
use alloc::vec;
use core::{mem::MaybeUninit, ptr};
use uefi::{
    Status, boot, guid,
    proto::{
        device_path::build::{DevicePathBuilder, media::Vendor},
        media::load_file::LoadFile2,
    },
};
use uefi_raw::{
    Boolean,
    protocol::{device_path::DevicePathProtocol, media::LoadFile2Protocol},
};

pub fn probe() -> Result<(), Status> {
    let mut storage = [MaybeUninit::uninit(); 24];
    let path = DevicePathBuilder::with_buf(&mut storage)
        .push(&Vendor {
            vendor_guid: guid!("5568e427-68fc-4f3d-ac74-ca555231cc68"),
            vendor_defined_data: &[],
        })
        .and_then(|b| b.finalize())
        .map_err(|_| Status::BAD_BUFFER_SIZE)?;
    let mut remaining = path;
    let handle = match boot::locate_device_path::<LoadFile2>(&mut remaining) {
        Ok(h) => h,
        Err(e) if e.status() == Status::NOT_FOUND => {
            crate::trace("CHILD_INITRD_ABSENT");
            return Ok(());
        }
        Err(e) => return Err(e.status()),
    };
    let mut protocol =
        boot::open_protocol_exclusive::<LoadFile2>(handle).map_err(|e| e.status())?;
    // SAFETY: LoadFile2 is repr(transparent) over the ABI protocol. Scoped borrow
    // is retained only during these synchronous calls, and dropped before return.
    let raw = (&mut *protocol as *mut LoadFile2).cast::<LoadFile2Protocol>();
    let call = unsafe { (*raw).load_file };
    let end = remaining.as_ffi_ptr().cast::<DevicePathProtocol>();
    let mut size = 0;
    // SAFETY: All non-null inputs/buffers are live with the declared size. NULL
    // parameters are intentional contract tests; no invalid non-null pointer.
    unsafe {
        if call(
            ptr::null_mut(),
            end,
            Boolean::FALSE,
            &mut size,
            ptr::null_mut(),
        ) != Status::INVALID_PARAMETER
            || call(raw, ptr::null(), Boolean::FALSE, &mut size, ptr::null_mut())
                != Status::INVALID_PARAMETER
            || call(raw, end, Boolean::FALSE, ptr::null_mut(), ptr::null_mut())
                != Status::INVALID_PARAMETER
            || call(raw, end, Boolean::TRUE, &mut size, ptr::null_mut()) != Status::UNSUPPORTED
            || call(
                raw,
                path.as_ffi_ptr().cast(),
                Boolean::FALSE,
                &mut size,
                ptr::null_mut(),
            ) != Status::NOT_FOUND
        {
            return Err(Status::PROTOCOL_ERROR);
        }
        if call(raw, end, Boolean::FALSE, &mut size, ptr::null_mut()) != Status::BUFFER_TOO_SMALL
            || size == 0
            || size > 16384
        {
            return Err(Status::BAD_BUFFER_SIZE);
        }
        let required = size;
        let mut bytes = vec![0xa5u8; required + 16];
        size = required - 1;
        if call(
            raw,
            end,
            Boolean::FALSE,
            &mut size,
            bytes.as_mut_ptr().cast(),
        ) != Status::BUFFER_TOO_SMALL
            || size != required
            || bytes.iter().any(|b| *b != 0xa5)
        {
            return Err(Status::PROTOCOL_ERROR);
        }
        // Repeat exact and oversized copies, checking trailing canaries each time.
        for capacity in [required, required + 16] {
            bytes.fill(0xa5);
            size = capacity;
            if call(
                raw,
                end,
                Boolean::FALSE,
                &mut size,
                bytes.as_mut_ptr().cast(),
            ) != Status::SUCCESS
                || size != required
                || bytes[required..].iter().any(|b| *b != 0xa5)
            {
                return Err(Status::PROTOCOL_ERROR);
            }
            let hash = bytes[..required]
                .iter()
                .fold(0xcbf29ce484222325u64, |h, b| {
                    (h ^ u64::from(*b)).wrapping_mul(0x100000001b3)
                });
            crate::trace(&alloc::format!(
                "CHILD_INITRD_BYTES size={required} fnv={hash:016x}"
            ));
        }
    }
    crate::trace("CHILD_INITRD_CONTRACT_OK");
    Ok(())
}
