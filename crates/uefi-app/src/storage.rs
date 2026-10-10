//! Restricted UEFI filesystem adapter for the configuration transaction engine.
use alloc::{format, string::String, vec::Vec};
use boot_core::{
    config::MAX_BYTES,
    transaction::{self, Store},
};
use uefi::{
    CString16, Status, boot, cstr16,
    proto::media::file::{Directory, File, FileAttribute, FileInfo, FileMode},
};

pub struct UefiStore {
    directory: Directory,
}
impl UefiStore {
    pub fn open() -> Result<Self, String> {
        let mut fs = boot::get_image_file_system(boot::image_handle())
            .map_err(|e| format!("Filesystem: {:?}", e.status()))?;
        let mut root = fs
            .open_volume()
            .map_err(|e| format!("Volume: {:?}", e.status()))?;
        let dir = root
            .open(
                cstr16!("\\EFI\\EutherBoot"),
                FileMode::Read,
                FileAttribute::empty(),
            )
            .map_err(|e| format!("Config directory: {:?}", e.status()))?;
        Ok(Self {
            directory: dir
                .into_directory()
                .ok_or("Config location is not a directory")?,
        })
    }
    fn name(name: &str) -> Result<CString16, String> {
        if !matches!(
            name,
            transaction::LIVE
                | transaction::NEW
                | transaction::BACKUP
                | transaction::MARKER
                | "editor-fault"
                | "initrd-fault"
        ) {
            return Err("Unexpected configuration filename".into());
        }
        CString16::try_from(name).map_err(|_| "Invalid filename".into())
    }
    fn flush(&mut self) -> Result<(), String> {
        // Inspection keeps a read-only directory handle. Flush is a write-side
        // operation, so acquire a writable handle only after explicit Save.
        let mut directory = self
            .directory
            .open(cstr16!("."), FileMode::ReadWrite, FileAttribute::empty())
            .map_err(|e| format!("Open directory for flush: {:?}", e.status()))?;
        directory
            .flush()
            .map_err(|e| format!("Directory flush: {:?}", e.status()))
    }
}
impl Store for UefiStore {
    fn read(&mut self, name: &str) -> Result<Option<Vec<u8>>, String> {
        let file =
            match self
                .directory
                .open(&Self::name(name)?, FileMode::Read, FileAttribute::empty())
            {
                Ok(f) => f,
                Err(e) if e.status() == Status::NOT_FOUND => return Ok(None),
                Err(e) => return Err(format!("Read {name}: {:?}", e.status())),
            };
        let mut file = file
            .into_regular_file()
            .ok_or_else(|| format!("{name} is not a regular file"))?;
        let mut bytes = Vec::new();
        bytes
            .try_reserve_exact(MAX_BYTES + 1)
            .map_err(|_| "Out of memory")?;
        bytes.resize(MAX_BYTES + 1, 0);
        let mut used = 0;
        while used < bytes.len() {
            let n = file
                .read(&mut bytes[used..])
                .map_err(|e| format!("Read {name}: {:?}", e.status()))?;
            if n == 0 {
                break;
            }
            used += n;
        }
        if used > MAX_BYTES {
            return Err(format!("{name} is too large"));
        }
        bytes.truncate(used);
        Ok(Some(bytes))
    }
    fn create(&mut self, name: &str, bytes: &[u8]) -> Result<(), String> {
        if self.read(name)?.is_some() {
            return Err(format!("Refusing to overwrite {name}"));
        }
        let file = self
            .directory
            .open(
                &Self::name(name)?,
                FileMode::CreateReadWrite,
                FileAttribute::empty(),
            )
            .map_err(|e| format!("Create {name}: {:?}", e.status()))?;
        let mut file = file.into_regular_file().ok_or("Not a regular file")?;
        file.write(bytes)
            .map_err(|e| format!("Write {name}: {:?}", e.status()))?;
        file.flush()
            .map_err(|e| format!("Flush {name}: {:?}", e.status()))?;
        drop(file);
        self.flush()
    }
    fn remove(&mut self, name: &str) -> Result<(), String> {
        let file = match self.directory.open(
            &Self::name(name)?,
            FileMode::ReadWrite,
            FileAttribute::empty(),
        ) {
            Ok(f) => f,
            Err(e) if e.status() == Status::NOT_FOUND => return Ok(()),
            Err(e) => return Err(format!("Remove {name}: {:?}", e.status())),
        };
        let file = file
            .into_regular_file()
            .ok_or("Refusing to remove a directory")?;
        file.delete()
            .map_err(|e| format!("Delete {name}: {:?}", e.status()))?;
        self.flush()?;
        if self.read(name)?.is_some() {
            return Err(format!("Deletion not confirmed: {name}"));
        }
        Ok(())
    }
    fn rename(&mut self, from: &str, to: &str) -> Result<(), String> {
        if self.read(to)?.is_some() {
            return Err(format!("Rename destination exists: {to}"));
        }
        let file = self
            .directory
            .open(
                &Self::name(from)?,
                FileMode::ReadWrite,
                FileAttribute::empty(),
            )
            .map_err(|e| format!("Open for rename: {:?}", e.status()))?;
        let mut file = file.into_regular_file().ok_or("Not a regular file")?;
        let old = file
            .get_boxed_info::<FileInfo>()
            .map_err(|e| format!("File info: {:?}", e.status()))?;
        let mut buffer = [0u8; 512];
        let name = Self::name(to)?;
        let info = FileInfo::new(
            &mut buffer,
            old.file_size(),
            old.physical_size(),
            *old.create_time(),
            *old.last_access_time(),
            *old.modification_time(),
            old.attribute(),
            &name,
        )
        .map_err(|_| "Rename info buffer too small")?;
        file.set_info(info)
            .map_err(|e| format!("Rename {from}: {:?}", e.status()))?;
        file.flush()
            .map_err(|e| format!("Rename flush: {:?}", e.status()))?;
        drop(file);
        self.flush()
    }
    fn checkpoint(&mut self, stage: &str) -> Result<(), String> {
        crate::trace(&format!("SAVE_CHECKPOINT {stage}"));
        #[cfg(feature = "test-faults")]
        if self.read("editor-fault")?.as_deref() == Some(stage.as_bytes()) {
            crate::trace(&format!("FAULT_WAIT {stage}"));
            loop {
                boot::stall(core::time::Duration::from_millis(100));
            }
        }
        Ok(())
    }
}
