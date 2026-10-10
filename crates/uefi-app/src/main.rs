#![no_std]
#![no_main]
extern crate alloc;
mod compiler_support;
mod config;
mod discovery;
mod editor;
mod graphics;
mod images;
mod loader;
mod storage;
mod timeout;
mod volumes;
use alloc::{format, string::String, vec::Vec};
use boot_core::Menu;
use uefi::{
    boot,
    prelude::*,
    proto::console::text::{Key, ScanCode},
    system,
};

#[cfg(feature = "qemu-debug")]
fn trace(message: &str) {
    for byte in message.bytes().chain(core::iter::once(b'\n')) {
        // QEMU-only diagnostic port, compiled out in normal builds.
        unsafe {
            core::arch::asm!("out dx, al", in("dx") 0xe9u16, in("al") byte, options(nomem, nostack, preserves_flags));
        }
    }
}
#[cfg(not(feature = "qemu-debug"))]
fn trace(_message: &str) {}

fn render(labels: &[&str], menu: &Menu, notice: &str, text: bool) -> bool {
    if !text && graphics::draw(labels, menu.selected, notice).is_ok() {
        return false;
    }
    system::with_stdout(|out| {
        let _ = out.clear();
    });
    uefi::println!("EUTHERBOOT | SYSTEM REGIS\n");
    let first = menu.selected / 8 * 8;
    for (i, entry) in labels.iter().enumerate().skip(first).take(8) {
        uefi::println!("{} {}", if i == menu.selected { ">" } else { " " }, entry);
    }
    uefi::println!(
        "\n{}/{}\n{}\nUp/Down: select  Enter: open  F2: text  F3: editor  F4: discover  Esc: return",
        menu.selected + 1,
        labels.len(),
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
    let mut first = true;
    loop {
        if let Some(status) = session(first) {
            return status;
        }
        first = false;
    }
}
fn session(allow_timeout: bool) -> Option<Status> {
    let (config, diagnostic) = match config::load() {
        Ok(c) => {
            trace(&format!(
                "CONFIG_OK entries={} default={} timeout={}",
                c.entries().len(),
                c.default_index(),
                c.timeout()
            ));
            (Some(c), None)
        }
        Err(e) => {
            trace(&format!("CONFIG_ERROR {e}"));
            (None, Some(e))
        }
    };
    let entries = config.as_ref().map(|c| c.entries()).unwrap_or(&[]);
    let mut labels: Vec<&str> = entries.iter().map(|e| e.name()).collect();
    labels.push("Configuration (read-only)");
    labels.push("Return to firmware");
    let mut menu = Menu {
        selected: config.as_ref().map(|c| c.default_index()).unwrap_or(0),
    };
    let mut seconds = config.as_ref().map(|c| c.timeout()).unwrap_or(0);
    let target_diagnostic = if allow_timeout && seconds > 0 {
        config.as_ref().and_then(|c| {
            let entry = &c.entries()[c.default_index()];
            entry.partition_guid()?;
            loader::entry_device(entry).err().map(|e| {
                seconds = 0;
                let message = format!("{} Automatic boot disabled.", e.notice());
                trace(&format!("DEFAULT_UNAVAILABLE {message}"));
                message
            })
        })
    } else {
        None
    };
    let default_unavailable = target_diagnostic.is_some();
    let mut notice = diagnostic.clone().or(target_diagnostic).unwrap_or_else(|| {
        if seconds == 0 || !allow_timeout {
            String::from("No automatic boot. Select an entry and press Enter.")
        } else {
            format!("Auto-start after {seconds}s. Any key cancels.")
        }
    });
    let mut text = render(
        &labels,
        &menu,
        &notice,
        diagnostic.is_some()
            || default_unavailable
            || config.as_ref().is_some_and(|c| c.theme() == "text"),
    );
    // Start the deadline only after the menu is visible. Never arm it again
    // following a key, configuration error, load error, or returning child.
    let mut timer = if allow_timeout && seconds > 0 {
        match timeout::AutoBoot::new(seconds) {
            Ok(t) => {
                trace("TIMEOUT_ARMED");
                Some(t)
            }
            Err(s) => {
                notice = format!("Timer unavailable: {s:?}. Automatic boot disabled.");
                text = render(&labels, &menu, &notice, text);
                None
            }
        }
    } else {
        None
    };
    trace(&format!("MENU_READY selected={}", menu.selected));
    loop {
        let key = match system::with_stdin(|stdin| stdin.read_key()) {
            Ok(k) => k,
            Err(_) => {
                trace("INPUT_ERROR");
                return Some(Status::DEVICE_ERROR);
            }
        };
        let mut activate = false;
        let mut redraw = false;
        if let Some(key) = key {
            // Input wins if both keyboard and timer are ready in this poll.
            if timer.take().is_some() {
                trace("TIMEOUT_CANCELLED");
                notice = "Automatic boot cancelled.".into();
                redraw = true;
            }
            match key {
                Key::Special(ScanCode::UP) => {
                    menu.previous(labels.len());
                    redraw = true;
                }
                Key::Special(ScanCode::DOWN) => {
                    menu.next(labels.len());
                    redraw = true;
                }
                Key::Special(ScanCode::ESCAPE) => {
                    trace("EXIT_FIRMWARE");
                    return Some(Status::SUCCESS);
                }
                Key::Special(ScanCode::FUNCTION_4) => {
                    if let Some(target) = discovery::run() {
                        if editor::run_import(Some(target)) {
                            return None;
                        }
                    }
                    notice = "Discovery closed. Automatic boot disabled.".into();
                    redraw = true;
                }
                Key::Special(ScanCode::FUNCTION_3) => {
                    if editor::run() {
                        return None;
                    }
                    notice = "Editor closed. Configuration unchanged.".into();
                    redraw = true;
                }
                Key::Special(ScanCode::FUNCTION_2) => {
                    text = true;
                    redraw = true;
                }
                Key::Printable(c) if char::from(c) == '\r' => activate = true,
                _ => {}
            }
        } else if let Some(t) = &timer {
            match t.expired() {
                Ok(true) => {
                    timer = None;
                    trace("TIMEOUT_FIRED");
                    activate = true;
                }
                Ok(false) => {}
                Err(s) => {
                    timer = None;
                    notice = format!("Timer error: {s:?}. Automatic boot disabled.");
                    trace("TIMEOUT_ERROR");
                    redraw = true;
                }
            }
        }
        if activate {
            trace("ACTIVATE");
            if menu.selected == labels.len() - 1 {
                trace("EXIT_FIRMWARE");
                return Some(Status::SUCCESS);
            }
            if let Some(entry) = entries.get(menu.selected) {
                trace(&format!(
                    "CHAINLOAD_REQUEST id={} path={}",
                    entry.id(),
                    entry.path()
                ));
                notice = match loader::chainload(entry) {
                    Ok(()) => {
                        trace("CHAINLOAD_RETURN_SUCCESS");
                        "EFI application returned successfully.".into()
                    }
                    Err(e) => {
                        trace(&format!("CHAINLOAD_ERROR {e:?}"));
                        e.notice()
                    }
                };
                text = render(&labels, &menu, &notice, text);
                trace("MENU_RESUMED");
            } else {
                text = true;
                notice = if let Some(e) = &diagnostic {
                    format!(
                        "{e}\nNo configured targets enabled.\nSource: \\EFI\\EutherBoot\\eutherboot.toml"
                    )
                } else {
                    format!(
                        "Source: \\EFI\\EutherBoot\\eutherboot.toml\n{} entries. Default: {}. Timeout: {}s.\nRead-only inspection; F3 opens the editor.",
                        entries.len(),
                        entries[config.as_ref().unwrap().default_index()].id(),
                        config.as_ref().unwrap().timeout()
                    )
                };
                text = render(&labels, &menu, &notice, text);
                trace("CONFIG_INSPECT");
            }
        } else if redraw {
            trace(&format!("SELECT {}", menu.selected));
            text = render(&labels, &menu, &notice, text);
        } else {
            boot::stall(core::time::Duration::from_millis(10));
        }
    }
}
