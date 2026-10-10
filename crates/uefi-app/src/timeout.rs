use core::{cell::Cell, time::Duration};
use uefi::{
    Event, Status,
    boot::{self, EventType, TimerTrigger, Tpl},
};

pub struct AutoBoot(Option<Event>, Cell<bool>);
impl AutoBoot {
    pub fn new(seconds: u16) -> Result<Self, Status> {
        // SAFETY: no callback or context is installed. The event is closed
        // before any child starts or this application returns.
        let event = unsafe { boot::create_event(EventType::TIMER, Tpl::APPLICATION, None, None) }
            .map_err(|e| e.status())?;
        let timer = Self(Some(event), Cell::new(false));
        boot::set_timer(
            timer.0.as_ref().unwrap(),
            TimerTrigger::Relative(Duration::from_secs(u64::from(seconds))),
        )
        .map_err(|e| e.status())?;
        Ok(timer)
    }
    pub fn wait_with_key(&self, key: Event) -> Result<(), Status> {
        // SAFETY: this is a borrowed wait token, never closed here. Self owns the
        // timer for the entire wait. Firmware owns the console key event.
        let event = unsafe { self.0.as_ref().unwrap().unsafe_clone() };
        let index = boot::wait_for_event(&mut [key, event]).map_err(|e| e.status())?;
        // WaitForEvent consumes the signal. Preserve it for the next loop, which
        // checks keyboard input first so a simultaneous key still cancels boot.
        if index == 1 {
            self.1.set(true);
        }
        Ok(())
    }
    pub fn expired(&self) -> Result<bool, Status> {
        if self.1.get() {
            return Ok(true);
        }
        boot::check_event(self.0.as_ref().unwrap()).map_err(|e| e.status())
    }
}
impl Drop for AutoBoot {
    fn drop(&mut self) {
        if let Some(event) = self.0.take() {
            if boot::close_event(event).is_err() {
                crate::trace("TIMER_CLOSE_ERROR");
            }
        }
    }
}
