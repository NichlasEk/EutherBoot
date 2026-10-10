//! Recoverable multi-file save. FAT rename is NOT claimed to be power-loss atomic.
use crate::config;
use alloc::{string::String, vec::Vec};
pub const LIVE: &str = "eutherboot.toml";
pub const NEW: &str = "eutherboot.toml.new";
pub const BACKUP: &str = "eutherboot.toml.bak";
pub const MARKER: &str = "eutherboot.toml.txn";

pub trait Store {
    fn read(&mut self, name: &str) -> Result<Option<Vec<u8>>, String>;
    fn create(&mut self, name: &str, bytes: &[u8]) -> Result<(), String>;
    fn remove(&mut self, name: &str) -> Result<(), String>;
    fn rename(&mut self, from: &str, to: &str) -> Result<(), String>;
    /// Fault-test boundary; production implementations simply return success.
    fn checkpoint(&mut self, _stage: &str) -> Result<(), String> {
        Ok(())
    }
}
pub fn validate(bytes: &[u8]) -> Result<(), String> {
    let s = core::str::from_utf8(bytes).map_err(|_| String::from("Configuration is not UTF-8"))?;
    config::parse(s).map(|_| ())
}
fn required(s: &mut impl Store, name: &str) -> Result<Vec<u8>, String> {
    s.read(name)?
        .ok_or_else(|| alloc::format!("Missing {name}"))
}
fn verify(s: &mut impl Store, name: &str, expected: &[u8]) -> Result<(), String> {
    if required(s, name)? != expected {
        return Err(alloc::format!("Readback mismatch: {name}"));
    }
    Ok(())
}
pub fn pending(s: &mut impl Store) -> Result<bool, String> {
    Ok(s.read(NEW)?.is_some() || s.read(MARKER)?.is_some())
}
/// Called only after explicit confirmation. `expected` is the exact file that
/// was inspected, providing optimistic concurrency protection before mutation.
pub fn save(s: &mut impl Store, expected: &[u8], draft: &[u8]) -> Result<(), String> {
    validate(expected)?;
    validate(draft)?;
    if pending(s)? {
        return Err("Unfinished save; choose recovery first".into());
    }
    verify(s, LIVE, expected)?;
    s.create(NEW, draft)?;
    verify(s, NEW, draft)?;
    s.checkpoint("after-stage")?;
    s.create(MARKER, b"EutherBoot transaction v1\n")?;
    verify(s, MARKER, b"EutherBoot transaction v1\n")?;
    // Do not discard the earlier backup until the new stage is verified and
    // the live file is still the valid version the user inspected.
    verify(s, LIVE, expected)?;
    s.remove(BACKUP)?;
    s.rename(LIVE, BACKUP)?;
    verify(s, BACKUP, expected)?;
    s.checkpoint("after-backup")?;
    s.rename(NEW, LIVE)?;
    verify(s, LIVE, draft)?;
    s.checkpoint("after-install")?;
    s.remove(MARKER)?;
    Ok(())
}
/// Explicit recovery: keep the validated current file and discard staging.
pub fn keep_current(s: &mut impl Store, expected: &[u8]) -> Result<(), String> {
    validate(expected)?;
    verify(s, LIVE, expected)?;
    s.remove(NEW)?;
    s.remove(MARKER)?;
    Ok(())
}
/// Explicit recovery: restore a verified backup, preserving it throughout.
/// A marker remains until readback succeeds. Interrupted recovery is repeatable.
pub fn restore_backup(s: &mut impl Store, expected_backup: &[u8]) -> Result<(), String> {
    validate(expected_backup)?;
    verify(s, BACKUP, expected_backup)?;
    if s.read(MARKER)?.is_none() {
        s.create(MARKER, b"EutherBoot recovery v1\n")?;
    }
    s.remove(NEW)?;
    s.create(NEW, expected_backup)?;
    verify(s, NEW, expected_backup)?;
    s.remove(LIVE)?;
    s.rename(NEW, LIVE)?;
    verify(s, LIVE, expected_backup)?;
    s.remove(MARKER)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    extern crate std;
    use super::*;
    use std::collections::BTreeMap;
    #[derive(Clone, Default)]
    struct Memory {
        files: BTreeMap<String, Vec<u8>>,
        fail: Option<usize>,
        ops: usize,
        corrupt_new: bool,
    }
    impl Memory {
        fn mutation(&mut self) -> Result<(), String> {
            self.ops += 1;
            if self.fail == Some(self.ops) {
                Err("Injected I/O failure".into())
            } else {
                Ok(())
            }
        }
    }
    impl Store for Memory {
        fn read(&mut self, n: &str) -> Result<Option<Vec<u8>>, String> {
            Ok(self.files.get(n).cloned())
        }
        fn create(&mut self, n: &str, b: &[u8]) -> Result<(), String> {
            self.mutation()?;
            if self.files.contains_key(n) {
                return Err("Exists".into());
            }
            self.files.insert(
                n.into(),
                if self.corrupt_new && n == NEW {
                    b"partial write".to_vec()
                } else {
                    b.into()
                },
            );
            Ok(())
        }
        fn remove(&mut self, n: &str) -> Result<(), String> {
            self.mutation()?;
            self.files.remove(n);
            Ok(())
        }
        fn rename(&mut self, a: &str, b: &str) -> Result<(), String> {
            self.mutation()?;
            if self.files.contains_key(b) {
                return Err("Exists".into());
            }
            let data = self.files.remove(a).ok_or("Missing")?;
            self.files.insert(b.into(), data);
            Ok(())
        }
    }
    fn fixture() -> (Memory, Vec<u8>, Vec<u8>) {
        let old = include_bytes!("../../../eutherboot.toml").to_vec();
        let new = String::from_utf8(old.clone())
            .unwrap()
            .replace("timeout = 0", "timeout = 8")
            .into_bytes();
        let mut m = Memory::default();
        m.files.insert(LIVE.into(), old.clone());
        (m, old, new)
    }
    #[test]
    fn saves_preserve_exact_previous_file_and_remove_marker() {
        let (mut m, old, new) = fixture();
        save(&mut m, &old, &new).unwrap();
        assert_eq!(m.files[LIVE], new);
        assert_eq!(m.files[BACKUP], old);
        assert!(!pending(&mut m).unwrap());
    }
    #[test]
    fn every_failed_save_mutation_retains_a_valid_original_and_recovers() {
        for failure in 1..=6 {
            let (mut m, old, new) = fixture();
            m.fail = Some(failure);
            assert!(save(&mut m, &old, &new).is_err());
            assert!(m.files.get(LIVE) == Some(&old) || m.files.get(BACKUP) == Some(&old));
            m.fail = None;
            if m.files.get(LIVE) == Some(&old) {
                keep_current(&mut m, &old).unwrap()
            } else {
                restore_backup(&mut m, &old).unwrap()
            }
            assert_eq!(m.files[LIVE], old);
            assert!(!pending(&mut m).unwrap());
        }
    }
    #[test]
    fn corrupt_stage_readback_cannot_replace_the_original() {
        let (mut m, old, new) = fixture();
        m.corrupt_new = true;
        assert!(
            save(&mut m, &old, &new)
                .unwrap_err()
                .contains("Readback mismatch")
        );
        assert_eq!(m.files[LIVE], old);
        assert!(!m.files.contains_key(BACKUP));
        assert!(pending(&mut m).unwrap());
        keep_current(&mut m, &old).unwrap();
        assert!(!pending(&mut m).unwrap());
    }
    #[test]
    fn stale_or_invalid_drafts_cannot_mutate_disk() {
        let (mut m, old, new) = fixture();
        assert!(save(&mut m, &old, b"broken").is_err());
        assert_eq!(m.ops, 0);
        m.files.insert(LIVE.into(), new.clone());
        assert!(save(&mut m, &old, &new).is_err());
        assert_eq!(m.ops, 0);
        m.files.insert(NEW.into(), new.clone());
        assert!(save(&mut m, &new, &old).is_err());
        assert_eq!(m.ops, 0);
    }
    #[test]
    fn failed_recovery_never_removes_backup() {
        for failure in 1..=6 {
            let (mut m, old, new) = fixture();
            save(&mut m, &old, &new).unwrap();
            m.fail = Some(m.ops + failure);
            assert!(restore_backup(&mut m, &old).is_err());
            assert_eq!(m.files[BACKUP], old);
            m.fail = None;
            restore_backup(&mut m, &old).unwrap();
            assert_eq!(m.files[LIVE], old);
        }
    }
}
