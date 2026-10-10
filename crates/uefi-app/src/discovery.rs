//! Read-only, opt-in discovery. No persistent entries or automatic selection.
use alloc::{format, string::String, vec::Vec};
use boot_core::{
    Menu,
    discovery::{is_x64_application, safe_component},
};
use uefi::{
    CString16, Guid, Handle, Status, boot,
    proto::{
        ProtocolPointer,
        console::text::{Key, ScanCode},
        device_path::DevicePath,
        loaded_image::LoadedImage,
        media::{
            file::{Directory, File, FileAttribute, FileInfo, FileMode, RegularFile},
            fs::SimpleFileSystem,
            partition::{GptPartitionAttributes, GptPartitionType, PartitionInfo},
        },
    },
    system,
};

const MAX_VOLUMES: usize = 32;
const MAX_ENTRIES: usize = 2048;
const MAX_TARGETS: usize = 64;
const MAX_DEPTH: usize = 4;

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
    own: Vec<u8>,
    read_budget: usize,
}

// SAFETY: callers are synchronous and never disconnect, uninstall protocols or
// run another image while a borrow is held. GET_PROTOCOL preserves drivers.
fn protocol<P: ProtocolPointer + ?Sized>(
    handle: Handle,
) -> Result<boot::ScopedProtocol<P>, Status> {
    unsafe {
        boot::open_protocol::<P>(
            boot::OpenProtocolParams {
                handle,
                agent: boot::image_handle(),
                controller: None,
            },
            boot::OpenProtocolAttributes::GetProtocol,
        )
    }
    .map_err(|e| e.status())
}
fn identity(handle: Handle) -> Result<Guid, Status> {
    let partition = protocol::<PartitionInfo>(handle)?;
    let entry = partition.gpt_partition_entry().ok_or(Status::UNSUPPORTED)?;
    let kind = entry.partition_type_guid;
    let attributes = entry.attributes;
    let id = entry.unique_partition_guid;
    if kind != GptPartitionType::EFI_SYSTEM_PARTITION
        || attributes.contains(GptPartitionAttributes::LEGACY_BIOS_BOOTABLE)
        || id == uefi::guid!("00000000-0000-0000-0000-000000000000")
    {
        return Err(Status::UNSUPPORTED);
    }
    Ok(id)
}
fn read_prefix(file: &mut RegularFile, bytes: &mut [u8]) -> Result<usize, Status> {
    let mut used = 0;
    while used < bytes.len() {
        let n = file.read(&mut bytes[used..]).map_err(|e| e.status())?;
        if n == 0 {
            break;
        }
        used += n;
    }
    Ok(used)
}
fn own_bytes() -> Result<Vec<u8>, Status> {
    let name = CString16::try_from(crate::config::own_path()?.as_str())
        .map_err(|_| Status::UNSUPPORTED)?;
    let device = protocol::<LoadedImage>(boot::image_handle())?
        .device()
        .ok_or(Status::NOT_FOUND)?;
    let mut fs = protocol::<SimpleFileSystem>(device)?;
    let mut root = fs.open_volume().map_err(|e| e.status())?;
    let mut file = root
        .open(&name, FileMode::Read, FileAttribute::empty())
        .map_err(|e| e.status())?
        .into_regular_file()
        .ok_or(Status::UNSUPPORTED)?;
    let size = file
        .get_boxed_info::<FileInfo>()
        .map_err(|e| e.status())?
        .file_size();
    if size == 0 || size > 4 * 1024 * 1024 {
        return Err(Status::BAD_BUFFER_SIZE);
    }
    let mut bytes = Vec::new();
    bytes
        .try_reserve_exact(size as usize)
        .map_err(|_| Status::OUT_OF_RESOURCES)?;
    bytes.resize(size as usize, 0);
    if read_prefix(&mut file, &mut bytes)? != bytes.len() {
        return Err(Status::END_OF_FILE);
    }
    Ok(bytes)
}
/// Header classification and exact current-binary exclusion, including renamed copies.
fn candidate(
    root: &mut Directory,
    path: &str,
    own: &[u8],
    budget: &mut usize,
) -> Result<bool, Status> {
    // Charge the maximum requested bytes before each read, including self-copy comparisons.
    fn read(file: &mut RegularFile, bytes: &mut [u8], budget: &mut usize) -> Result<usize, Status> {
        *budget = budget
            .checked_sub(bytes.len())
            .ok_or(Status::OUT_OF_RESOURCES)?;
        read_prefix(file, bytes)
    }
    let name = CString16::try_from(path).map_err(|_| Status::UNSUPPORTED)?;
    let mut file = root
        .open(&name, FileMode::Read, FileAttribute::empty())
        .map_err(|e| e.status())?
        .into_regular_file()
        .ok_or(Status::UNSUPPORTED)?;
    let size = file
        .get_boxed_info::<FileInfo>()
        .map_err(|e| e.status())?
        .file_size();
    let mut prefix = [0u8; 4096];
    let n = read(&mut file, &mut prefix, budget)?;
    if !is_x64_application(&prefix[..n], size) {
        return Ok(false);
    }
    if size == own.len() as u64 {
        file.set_position(0).map_err(|e| e.status())?;
        let mut offset = 0;
        while offset < own.len() {
            let end = (offset + prefix.len()).min(own.len());
            let len = end - offset;
            if read(&mut file, &mut prefix[..len], budget)? != len {
                return Err(Status::END_OF_FILE);
            }
            if prefix[..len] != own[offset..end] {
                return Ok(true);
            }
            offset = end;
        }
        return Ok(false);
    }
    Ok(true)
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
            own,
            read_budget: 64 * 1024 * 1024,
        };
        let handles = boot::find_handles::<SimpleFileSystem>().map_err(|e| e.status())?;
        if handles.len() > MAX_VOLUMES {
            return Err(Status::OUT_OF_RESOURCES);
        }
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
    fn draw(&self, selected: usize, notice: &str) {
        system::with_stdout(|out| {
            let _ = out.clear();
        });
        uefi::println!("EUTHERBOOT | DISCOVER EFI APPLICATIONS\n");
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
            "\n{} / {}\n{}\nUp/Down: select  Enter: inspect  R: rescan  Esc: menu",
            if self.targets.is_empty() {
                0
            } else {
                selected + 1
            },
            self.targets.len(),
            notice
        );
    }
}

pub fn run() {
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
                        Some(Key::Special(ScanCode::ESCAPE)) | None => return,
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
            scan.draw(menu.selected, &notice);
            crate::trace(&format!(
                "DISCOVERY_READY targets={} selected={} partial={}",
                scan.targets.len(),
                menu.selected,
                scan.incomplete
            ));
            match key() {
                None | Some(Key::Special(ScanCode::ESCAPE)) => {
                    crate::trace("DISCOVERY_CLOSED");
                    return;
                }
                Some(Key::Special(ScanCode::UP)) => menu.previous(scan.targets.len()),
                Some(Key::Special(ScanCode::DOWN)) => menu.next(scan.targets.len()),
                Some(Key::Printable(c)) if char::from(c).eq_ignore_ascii_case(&'r') => {
                    continue 'scan;
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
    loop {
        match system::with_stdin(|stdin| stdin.read_key()) {
            Ok(Some(key)) => return Some(key),
            Err(_) => return None,
            Ok(None) => boot::stall(core::time::Duration::from_millis(10)),
        }
    }
}
