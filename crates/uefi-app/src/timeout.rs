use core::time::Duration;
use uefi::{
    Event, Status,
    boot::{self, EventType, TimerTrigger, Tpl},
};

pub struct AutoBoot(Option<Event>);
impl AutoBoot {
    pub fn new(seconds: u16) -> Result<Self, Status> {
        // SAFETY: no callback or context is installed. The event is closed
        // before any child starts or this application returns.
        let event = unsafe { boot::create_event(EventType::TIMER, Tpl::APPLICATION, None, None) }
            .map_err(|e| e.status())?;
        let timer = Self(Some(event));
        boot::set_timer(
            timer.0.as_ref().unwrap(),
            TimerTrigger::Relative(Duration::from_secs(u64::from(seconds))),
        )
        .map_err(|e| e.status())?;
        Ok(timer)
    }
    pub fn expired(&self) -> Result<bool, Status> {
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
