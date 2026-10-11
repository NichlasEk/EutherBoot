//! Read-only discovery; selections can be handed to an unsaved editor draft.
use alloc::{format, string::String, vec::Vec};
use boot_core::{Menu, discovery::safe_component};
use uefi::{
    CString16, Guid, Handle, Status, boot,
    proto::{
        console::text::{Key, ScanCode},
        device_path::DevicePath,
        media::{
            file::{Directory, File, FileAttribute, FileMode},
            fs::SimpleFileSystem,
        },
    },
    system,
};

use crate::{
    images::{candidate, own_bytes},
    volumes::{MAX_VOLUMES, identity, protocol},
};
const MAX_ENTRIES: usize = 2048;
const MAX_TARGETS: usize = 64;
const MAX_DEPTH: usize = 4;

pub struct Selection {
    pub partition_guid: String,
    pub path: String,
}
struct Volume {
    handle: Handle,
    id: Guid,
    path: Vec<u8>,
}
struct Target {
    volume: usize,
    path: String,
}
struct Scan {
    volumes: Vec<Volume>,
    targets: Vec<Target>,
    visited: usize,
    skipped: usize,
    incomplete: bool,
    first_error: Option<Status>,
    filesystem_count: usize,
    own: Vec<u8>,
    read_budget: usize,
}

impl Scan {
    fn walk(
        &mut self,
        volume: usize,
        root: &mut Directory,
        path: &str,
        depth: usize,
    ) -> Result<(), Status> {
        let name = CString16::try_from(path).map_err(|_| Status::UNSUPPORTED)?;
        let mut dir = root
            .open(&name, FileMode::Read, FileAttribute::empty())
            .map_err(|e| e.status())?
            .into_directory()
            .ok_or(Status::UNSUPPORTED)?;
        // Fixed aligned buffer; pathological directory records do not cause unbounded allocation.
        #[repr(align(8))]
        struct Buffer([u8; 1024]);
        let mut buffer = Buffer([0; 1024]);
        loop {
            if self.visited >= MAX_ENTRIES
                || self.targets.len() >= MAX_TARGETS
                || self.read_budget < 4096
            {
                self.incomplete = true;
                break;
            }
            let Some(info) = dir.read_entry(&mut buffer.0).map_err(|e| e.status())? else {
                break;
            };
            self.visited += 1;
            let component = String::from(info.file_name());
            if component == "." || component == ".." {
                continue;
            }
            if !safe_component(&component) {
                self.skipped += 1;
                continue;
            }
            let next = format!("{path}\\{component}");
            if next.len() > 240 {
                self.incomplete = true;
                continue;
            }
            if info.attribute().contains(FileAttribute::DIRECTORY) {
                if depth >= MAX_DEPTH {
                    self.incomplete = true;
                    continue;
                }
                if let Err(status) = self.walk(volume, root, &next, depth + 1) {
                    self.incomplete = true;
                    crate::trace(&format!("DISCOVERY_READ_ERROR {next} {status:?}"));
                }
            } else if component.to_ascii_lowercase().ends_with(".efi") {
                match candidate(root, &next, &self.own, &mut self.read_budget) {
                    Ok(true) => self.targets.push(Target { volume, path: next }),
                    Ok(false) => self.skipped += 1,
                    Err(status) => {
                        self.incomplete = true;
                        crate::trace(&format!("DISCOVERY_READ_ERROR {next} {status:?}"));
                    }
                }
            }
        }
        Ok(())
    }
    fn collect() -> Result<Self, Status> {
        let own = own_bytes()?; // Fail closed if exact self-copy exclusion is unavailable.
        let mut scan = Self {
            volumes: Vec::new(),
            targets: Vec::new(),
            visited: 0,
            skipped: 0,
            incomplete: false,
            first_error: None,
            filesystem_count: 0,
            own,
            read_budget: 64 * 1024 * 1024,
        };
        let handles = boot::find_handles::<SimpleFileSystem>().map_err(|e| e.status())?;
        if handles.len() > MAX_VOLUMES {
            return Err(Status::OUT_OF_RESOURCES);
        }
        scan.filesystem_count = handles.len();
        for handle in handles {
            match identity(handle) {
                Ok(id) => {
                    let path = protocol::<DevicePath>(handle)?;
                    if path.as_bytes().len() > 3072 {
                        scan.incomplete = true;
                        continue;
                    }
                    scan.volumes.push(Volume {
                        handle,
                        id,
                        path: path.as_bytes().into(),
                    });
                }
                Err(Status::UNSUPPORTED) => scan.skipped += 1,
                Err(s) => {
                    scan.incomplete = true;
                    scan.first_error.get_or_insert(s);
                    crate::trace(&format!("DISCOVERY_VOLUME_ERROR {s:?}"));
                }
            }
        }
        scan.volumes.sort_by_key(|v| format!("{}", v.id));
        // A cloned partition GUID must never silently select one of two devices.
        let duplicates: Vec<Guid> = scan
            .volumes
            .windows(2)
            .filter(|v| v[0].id == v[1].id)
            .map(|v| v[0].id)
            .collect();
        if !duplicates.is_empty() {
            scan.incomplete = true;
            crate::trace("DISCOVERY_DUPLICATE_GUID");
        }
        scan.volumes.retain(|v| !duplicates.contains(&v.id));
        for volume in 0..scan.volumes.len() {
            crate::trace(&format!("DISCOVERY_VOLUME {}", scan.volumes[volume].id));
            let result = (|| {
                let mut fs = protocol::<SimpleFileSystem>(scan.volumes[volume].handle)?;
                let mut root = fs.open_volume().map_err(|e| e.status())?;
                scan.walk(volume, &mut root, "\\EFI", 0)
            })();
            if let Err(s) = result {
                if s != Status::NOT_FOUND {
                    scan.incomplete = true;
                }
                crate::trace(&format!("DISCOVERY_VOLUME_READ {s:?}"));
            }
        }
        scan.targets.sort_by(|a, b| {
            a.volume.cmp(&b.volume).then_with(|| {
                a.path
                    .to_ascii_lowercase()
                    .cmp(&b.path.to_ascii_lowercase())
            })
        });
        scan.targets
            .dedup_by(|a, b| a.volume == b.volume && a.path.eq_ignore_ascii_case(&b.path));
        for target in &scan.targets {
            crate::trace(&format!(
                "DISCOVERY_TARGET {} {}",
                scan.volumes[target.volume].id, target.path
            ));
        }
        Ok(scan)
    }
    fn verify(&self, target: &Target) -> Result<(), Status> {
        let volume = &self.volumes[target.volume];
        if identity(volume.handle)? != volume.id
            || protocol::<DevicePath>(volume.handle)?.as_bytes() != volume.path
        {
            return Err(Status::MEDIA_CHANGED);
        }
        let mut fs = protocol::<SimpleFileSystem>(volume.handle)?;
        let mut root = fs.open_volume().map_err(|e| e.status())?;
        if !candidate(
            &mut root,
            &target.path,
            &self.own,
            &mut (4 * 1024 * 1024 + 4096),
        )? {
            return Err(Status::UNSUPPORTED);
        }
        Ok(())
    }
    fn draw(&self, selected: usize, notice: &str, picking: bool) {
        system::with_stdout(|out| {
            let _ = out.clear();
        });
        uefi::println!(
            "EUTHERBOOT {} | DISCOVER EFI APPLICATIONS\n",
            env!("CARGO_PKG_VERSION")
        );
        uefi::println!(
            "{} GPT ESPs, {} applications. {} skipped.",
            self.volumes.len(),
            self.targets.len(),
            self.skipped
        );
        uefi::println!(
            "{}\n",
            if self.incomplete {
                "Partial scan: errors, duplicate IDs or limits reached."
            } else {
                "Read-only scan. No automatic boot or saved changes."
            }
        );
        uefi::println!(
            "Firmware filesystems: {} | Verified ESPs: {}",
            self.filesystem_count,
            self.volumes.len()
        );
        if let Some(status) = self.first_error {
            uefi::println!("Partition identification: {status:?}");
        }
        let first = selected / 4 * 4;
        for (i, target) in self.targets.iter().enumerate().skip(first).take(4) {
            uefi::println!(
                "{} ESP {}",
                if i == selected { ">" } else { " " },
                self.volumes[target.volume].id
            );
            // Keep one path line per entry even at 640x480; full path on confirmation.
            let path = &target.path;
            if path.len() <= 60 {
                uefi::println!("  {path}");
            } else {
                uefi::println!("  ...{}", &path[path.len() - 57..]);
            }
        }
        if self.targets.is_empty() {
            uefi::println!("No eligible applications found.");
        }
        uefi::println!(
            "\n{} / {}\n{}\nUp/Down: select  {}  R: rescan  Esc: back",
            if self.targets.is_empty() {
                0
            } else {
                selected + 1
            },
            self.targets.len(),
            notice,
            if picking {
                "Enter: add to draft"
            } else {
                "Enter: start  A: add to draft"
            }
        );
    }
}

pub fn run() -> Option<Selection> {
    browse(false)
}
pub fn pick() -> Option<Selection> {
    browse(true)
}
fn browse(picking: bool) -> Option<Selection> {
    crate::trace("DISCOVERY_OPEN");
    'scan: loop {
        system::with_stdout(|out| {
            let _ = out.clear();
        });
        uefi::println!(
            "EUTHERBOOT | Scanning EFI System Partitions...\nRead-only; automatic boot disabled."
        );
        let scan = match Scan::collect() {
            Ok(scan) => scan,
            Err(status) => {
                system::with_stdout(|out| {
                    let _ = out.clear();
                });
                uefi::println!("Discovery unavailable: {status:?}\n\nR: retry   Esc: menu");
                crate::trace(&format!("DISCOVERY_ERROR {status:?}"));
                loop {
                    match key() {
                        Some(Key::Special(ScanCode::ESCAPE)) | None => return None,
                        Some(Key::Printable(c)) if char::from(c).eq_ignore_ascii_case(&'r') => {
                            continue 'scan;
                        }
                        _ => {}
                    }
                }
            }
        };
        let mut menu = Menu::default();
        let mut notice = String::new();
        loop {
            scan.draw(menu.selected, &notice, picking);
            crate::trace(&format!(
                "DISCOVERY_READY targets={} selected={} partial={}",
                scan.targets.len(),
                menu.selected,
                scan.incomplete
            ));
            match key() {
                None | Some(Key::Special(ScanCode::ESCAPE)) => {
                    crate::trace("DISCOVERY_CLOSED");
                    return None;
                }
                Some(Key::Special(ScanCode::UP)) => menu.previous(scan.targets.len()),
                Some(Key::Special(ScanCode::DOWN)) => menu.next(scan.targets.len()),
                Some(Key::Printable(c)) if char::from(c).eq_ignore_ascii_case(&'r') => {
                    continue 'scan;
                }
                Some(Key::Printable(c))
                    if char::from(c).eq_ignore_ascii_case(&'a')
                        || (picking && char::from(c) == '\r') =>
                {
                    if let Some(target) = scan.targets.get(menu.selected) {
                        system::with_stdout(|out| {
                            let _ = out.clear();
                        });
                        uefi::println!(
                            "ADD TARGET TO UNSAVED DRAFT?\n\nESP {}\n{}\n\nDefault and timeout stay unchanged.\nY: add to draft   Any other key: cancel",
                            scan.volumes[target.volume].id,
                            target.path
                        );
                        crate::trace("DISCOVERY_IMPORT_CONFIRM");
                        if matches!(key(), Some(Key::Printable(c)) if char::from(c).eq_ignore_ascii_case(&'y'))
                        {
                            match scan.verify(target) {
                                Ok(()) => {
                                    crate::trace("DISCOVERY_PICKED");
                                    return Some(Selection {
                                        partition_guid: format!(
                                            "{}",
                                            scan.volumes[target.volume].id
                                        ),
                                        path: target.path.clone(),
                                    });
                                }
                                Err(s) => {
                                    notice = format!("Target check: {s:?}. Rescan before retry.")
                                }
                            }
                        }
                    }
                }
                Some(Key::Printable(c)) if char::from(c) == '\r' => {
                    if let Some(target) = scan.targets.get(menu.selected) {
                        system::with_stdout(|out| {
                            let _ = out.clear();
                        });
                        uefi::println!(
                            "START EFI APPLICATION?\n\nESP {}\n{}\n\nDiscovered application; identity is not authentication.\nThe application can access disks and firmware.\n\nY: start this application   Any other key: cancel",
                            scan.volumes[target.volume].id,
                            target.path
                        );
                        crate::trace("DISCOVERY_CONFIRM");
                        if matches!(key(), Some(Key::Printable(c)) if char::from(c).eq_ignore_ascii_case(&'y'))
                        {
                            notice = match scan.verify(target) {
                                Err(s) => format!("Target check: {s:?}. Rescan before retry."),
                                Ok(()) => {
                                    crate::trace(&format!(
                                        "DISCOVERY_BOOT {} {}",
                                        scan.volumes[target.volume].id, target.path
                                    ));
                                    match crate::loader::chainload_path(
                                        scan.volumes[target.volume].handle,
                                        &target.path,
                                    ) {
                                        Ok(()) => "EFI application returned successfully.".into(),
                                        Err(e) => e.notice(),
                                    }
                                }
                            };
                            crate::trace(&format!("DISCOVERY_RETURN {notice}"));
                        } else {
                            crate::trace("DISCOVERY_CANCELLED");
                        }
                    }
                }
                _ => {}
            }
        }
    }
}
fn key() -> Option<Key> {
    crate::input::read_blocking()
}
