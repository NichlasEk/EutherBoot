#![no_std]
extern crate alloc;
pub mod config;
pub mod discovery;
pub mod draft;
pub mod gpt;
pub mod linux;
pub mod transaction;

/// Bounded selection: navigation never activates an entry.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Menu {
    pub selected: usize,
}
impl Menu {
    pub fn next(&mut self, count: usize) {
        if count > 0 {
            self.selected = (self.selected + 1) % count;
        }
    }
    pub fn previous(&mut self, count: usize) {
        if count > 0 {
            self.selected = (self.selected + count - 1) % count;
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn navigation_wraps_without_activation() {
        let mut m = Menu::default();
        m.previous(3);
        assert_eq!(m.selected, 2);
        m.next(3);
        assert_eq!(m.selected, 0);
        m.next(3);
        assert_eq!(m.selected, 1);
    }
    #[test]
    fn empty_menu_is_safe() {
        let mut m = Menu::default();
        m.next(0);
        m.previous(0);
        assert_eq!(m.selected, 0);
    }
}
