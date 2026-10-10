//! Sleep on firmware keyboard events; retain polling only for broken event firmware.
use core::{
    sync::atomic::{AtomicBool, Ordering},
    time::Duration,
};
use uefi::{boot, proto::console::text::Key, system};

static REPORTED_FALLBACK: AtomicBool = AtomicBool::new(false);

pub fn idle(timer: Option<&crate::timeout::AutoBoot>) {
    let result = system::with_stdin(|stdin| stdin.wait_for_key_event())
        .map_err(|e| e.status())
        .and_then(|key| {
            if let Some(timer) = timer {
                timer.wait_with_key(key)
            } else {
                boot::wait_for_event(&mut [key])
                    .map(|_| ())
                    .map_err(|e| e.status())
            }
        });
    if result.is_err() {
        if !REPORTED_FALLBACK.swap(true, Ordering::Relaxed) {
            crate::trace("INPUT_EVENT_FALLBACK");
        }
        boot::stall(Duration::from_millis(10));
    }
}

pub fn read_blocking() -> Option<Key> {
    loop {
        match system::with_stdin(|stdin| stdin.read_key()) {
            Ok(Some(key)) => return Some(key),
            Ok(None) => idle(None),
            Err(_) => return None,
        }
    }
}
