#![no_std]
#![no_main]
extern crate alloc;

use uefi::{
    boot,
    prelude::*,
    proto::{
        console::text::{Key, ScanCode},
        loaded_image::LoadedImage,
    },
    system,
};

// This independent fixture is QEMU-only, never an installation artifact.
fn trace(message: &str) {
    for byte in message.bytes().chain(core::iter::once(b'\n')) {
        unsafe {
            core::arch::asm!("out dx, al", in("dx") 0xe9u16, in("al") byte, options(nomem, nostack, preserves_flags));
        }
    }
}

#[entry]
fn main() -> Status {
    if uefi::helpers::init().is_err() {
        return Status::ABORTED;
    }
    trace("CHILD_STARTED");
    // Independent read-only evidence of the firmware's actual enforcement mode.
    for name in [uefi::cstr16!("SecureBoot"), uefi::cstr16!("SetupMode")] {
        let mut byte = [0u8; 1];
        match uefi::runtime::get_variable(
            name,
            &uefi::runtime::VariableVendor::GLOBAL_VARIABLE,
            &mut byte,
        ) {
            Ok((data, _)) if data.len() == 1 => {
                trace(&alloc::format!("CHILD_FIRMWARE {name}={}", data[0]));
            }
            _ => trace(&alloc::format!("CHILD_FIRMWARE {name}=unknown")),
        }
    }
    let context_ok = boot::open_protocol_exclusive::<LoadedImage>(boot::image_handle())
        .map(|image| image.device().is_some() && image.file_path().is_some())
        .unwrap_or(false);
    if !context_ok {
        trace("CHILD_CONTEXT_ERROR");
        return Status::DEVICE_ERROR;
    }
    trace("CHILD_CONTEXT_OK");
    // Report the actual firmware-provided child volume, not the parent's intent.
    if let Ok(image) = boot::open_protocol_exclusive::<LoadedImage>(boot::image_handle()) {
        if let Some(device) = image.device() {
            if let Ok(partition) = boot::open_protocol_exclusive::<
                uefi::proto::media::partition::PartitionInfo,
            >(device)
            {
                if let Some(entry) = partition.gpt_partition_entry() {
                    let guid = entry.unique_partition_guid;
                    trace(&alloc::format!("CHILD_VOLUME {guid}"));
                }
            }
        }
    }
    system::with_stdout(|out| {
        let _ = out.clear();
    });
    uefi::println!(
        "EUTHERBOOT EFI TEST CHILD\n\nIndependent executable reached through LoadImage / StartImage.\n\nENTER: return SUCCESS\nESC: return ABORTED\nD: Exit with error data\n\nNo disks or firmware variables are changed."
    );
    trace("CHILD_READY");
    loop {
        match system::with_stdin(|stdin| stdin.read_key()) {
            Ok(Some(Key::Printable(c))) if char::from(c) == '\r' => {
                trace("CHILD_RETURN_SUCCESS");
                return Status::SUCCESS;
            }
            Ok(Some(Key::Printable(c))) if char::from(c) == 'd' => {
                trace("CHILD_EXIT_DATA");
                let mut data: [u16; 14] = [
                    70, 105, 120, 116, 117, 114, 101, 32, 101, 114, 114, 111, 114, 0,
                ];
                // SAFETY: no live protocol borrows/resources. Firmware copies this
                // valid UCS-2 buffer before returning to the parent via Exit().
                let _ = unsafe {
                    boot::exit(
                        boot::image_handle(),
                        Status::ABORTED,
                        core::mem::size_of_val(&data),
                        data.as_mut_ptr().cast(),
                    )
                };
                return Status::ABORTED;
            }
            Ok(Some(Key::Special(ScanCode::ESCAPE))) => {
                trace("CHILD_RETURN_ABORTED");
                return Status::ABORTED;
            }
            Err(_) => {
                trace("CHILD_INPUT_ERROR");
                return Status::DEVICE_ERROR;
            }
            _ => boot::stall(core::time::Duration::from_millis(10)),
        }
    }
}
