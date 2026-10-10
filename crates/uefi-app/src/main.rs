#![no_std]
#![no_main]
extern crate alloc;
mod graphics;
mod loader;
use boot_core::{ENTRIES, Menu};
use uefi::{
    boot,
    prelude::*,
    proto::console::text::{Key, ScanCode},
    system,
};

#[cfg(feature = "qemu-debug")]
fn trace(message: &str) {
    // QEMU debugcon only; no firmware variables or disk writes.
    for byte in message.bytes().chain(core::iter::once(b'\n')) {
        unsafe {
            core::arch::asm!("out dx, al", in("dx") 0xe9u16, in("al") byte, options(nomem, nostack, preserves_flags));
        }
    }
}
#[cfg(not(feature = "qemu-debug"))]
fn trace(_message: &str) {}

fn render(menu: &Menu, notice: &str, text: bool) -> bool {
    if !text && graphics::draw(menu.selected, notice).is_ok() {
        return false;
    }
    system::with_stdout(|out| {
        let _ = out.clear();
    });
    uefi::println!("EUTHERBOOT | SYSTEM REGIS\n\n");
    for (i, entry) in ENTRIES.iter().enumerate() {
        uefi::println!("{} {}", if i == menu.selected { ">" } else { " " }, entry);
    }
    uefi::println!(
        "\n{}\nUp/Down: select  Enter: open  F2: text  Esc: return",
        notice
    );
    trace("TEXT_READY");
    true
}
#[entry]
fn main() -> Status {
    if uefi::helpers::init().is_err() {
        return Status::ABORTED;
    }
    trace("EUTHERBOOT_START");
    system::with_stdout(|out| {
        let _ = out.enable_cursor(false);
        let _ = out.clear();
    });
    let mut menu = Menu::default();
    let mut text = render(
        &menu,
        "No boot target will be started automatically.",
        false,
    );
    trace("MENU_READY selected=0");
    loop {
        let key = system::with_stdin(|stdin| stdin.read_key());
        match key {
            Ok(Some(Key::Special(ScanCode::UP))) => menu.previous(ENTRIES.len()),
            Ok(Some(Key::Special(ScanCode::DOWN))) => menu.next(ENTRIES.len()),
            Ok(Some(Key::Special(ScanCode::ESCAPE))) => {
                trace("EXIT_FIRMWARE");
                return Status::SUCCESS;
            }
            Ok(Some(Key::Special(ScanCode::FUNCTION_2))) => {
                text = true;
            }
            Ok(Some(Key::Printable(c))) if char::from(c) == '\r' => {
                trace("ACTIVATE");
                if menu.selected == 2 {
                    trace("EXIT_FIRMWARE");
                    return Status::SUCCESS;
                }
                if menu.selected == 0 {
                    trace("CHAINLOAD_REQUEST");
                    // Free the previous frame and all protocol borrows before
                    // StartImage; no graphical state is retained across a child.
                    let notice = match loader::test_child() {
                        Ok(()) => {
                            trace("CHAINLOAD_RETURN_SUCCESS");
                            alloc::string::String::from("EFI application returned successfully.")
                        }
                        Err(error) => {
                            let notice = error.notice();
                            trace(&alloc::format!("CHAINLOAD_ERROR {error:?}"));
                            notice
                        }
                    };
                    text = render(&menu, &notice, text);
                    trace("MENU_RESUMED");
                } else {
                    text = render(
                        &menu,
                        "Read-only preview. Editor arrives in milestone E.",
                        text,
                    );
                }
                continue;
            }
            Ok(Some(_)) => continue,
            Ok(None) => {
                boot::stall(core::time::Duration::from_millis(10));
                continue;
            }
            Err(_) => {
                trace("INPUT_ERROR");
                return Status::DEVICE_ERROR;
            }
        }
        trace(match menu.selected {
            0 => "SELECT 0",
            1 => "SELECT 1",
            _ => "SELECT 2",
        });
        text = render(&menu, "Development preview / no disk or NVRAM writes", text);
    }
}
