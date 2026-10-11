use core::{cell::Cell, time::Duration};
use uefi::{
    Event, Status,
    boot::{self, EventType, TimerTrigger, Tpl},
};

pub struct AutoBoot {
    deadline: Option<Event>,
    tick: Option<Event>,
    fired: Cell<bool>,
    ticked: Cell<bool>,
    remaining: Cell<u16>,
}
impl AutoBoot {
    pub fn new(seconds: u16) -> Result<Self, Status> {
        let mut timer = Self {
            deadline: None,
            tick: None,
            fired: Cell::new(false),
            ticked: Cell::new(false),
            remaining: Cell::new(seconds),
        };
        // SAFETY: callback-free events owned here; Drop closes both, including
        // partial initialization failures, before child launch or firmware return.
        timer.deadline = Some(
            unsafe { boot::create_event(EventType::TIMER, Tpl::APPLICATION, None, None) }
                .map_err(|e| e.status())?,
        );
        timer.tick = Some(
            unsafe { boot::create_event(EventType::TIMER, Tpl::APPLICATION, None, None) }
                .map_err(|e| e.status())?,
        );
        boot::set_timer(
            timer.tick.as_ref().unwrap(),
            TimerTrigger::Periodic(Duration::from_secs(1)),
        )
        .map_err(|e| e.status())?;
        boot::set_timer(
            timer.deadline.as_ref().unwrap(),
            TimerTrigger::Relative(Duration::from_secs(u64::from(seconds))),
        )
        .map_err(|e| e.status())?;
        Ok(timer)
    }
    pub fn wait_with_key(&self, key: Event) -> Result<(), Status> {
        // SAFETY: wait tokens are borrowed; only Drop closes the owned events.
        let deadline = unsafe { self.deadline.as_ref().unwrap().unsafe_clone() };
        let tick = unsafe { self.tick.as_ref().unwrap().unsafe_clone() };
        let index = boot::wait_for_event(&mut [key, deadline, tick]).map_err(|e| e.status())?;
        // Preserve consumed signals; the next iteration checks keyboard first.
        match index {
            1 => self.fired.set(true),
            2 => self.ticked.set(true),
            _ => {}
        }
        Ok(())
    }
    pub fn expired(&self) -> Result<bool, Status> {
        if self.fired.get() {
            return Ok(true);
        }
        boot::check_event(self.deadline.as_ref().unwrap()).map_err(|e| e.status())
    }
    pub fn countdown(&self) -> Result<Option<u16>, Status> {
        let signaled = self.ticked.replace(false)
            || boot::check_event(self.tick.as_ref().unwrap()).map_err(|e| e.status())?;
        if !signaled {
            return Ok(None);
        }
        // This display tick never controls the boot deadline. Even on slow
        // firmware the independent one-shot timer remains authoritative.
        let remaining = self.remaining.get().saturating_sub(1).max(1);
        self.remaining.set(remaining);
        Ok(Some(remaining))
    }
}
impl Drop for AutoBoot {
    fn drop(&mut self) {
        for event in [self.tick.take(), self.deadline.take()]
            .into_iter()
            .flatten()
        {
            if boot::close_event(event).is_err() {
                crate::trace("TIMER_CLOSE_ERROR");
            }
        }
    }
}
