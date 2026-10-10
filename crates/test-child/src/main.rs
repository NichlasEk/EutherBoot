#![no_std]
#![no_main]

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
    let context_ok = boot::open_protocol_exclusive::<LoadedImage>(boot::image_handle())
        .map(|image| image.device().is_some() && image.file_path().is_some())
        .unwrap_or(false);
    if !context_ok {
        trace("CHILD_CONTEXT_ERROR");
        return Status::DEVICE_ERROR;
    }
    trace("CHILD_CONTEXT_OK");
    system::with_stdout(|out| {
        let _ = out.clear();
    });
    uefi::println!(
        "EUTHERBOOT EFI TEST CHILD\n\nIndependent executable reached through LoadImage / StartImage.\n\nENTER: return SUCCESS\nESC: return ABORTED\n\nNo disks or firmware variables are changed."
    );
    trace("CHILD_READY");
    loop {
        match system::with_stdin(|stdin| stdin.read_key()) {
            Ok(Some(Key::Printable(c))) if char::from(c) == '\r' => {
                trace("CHILD_RETURN_SUCCESS");
                return Status::SUCCESS;
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
