//! One bounded, read-only configuration source on the application's own volume.
use alloc::{format, string::String, vec::Vec};
use boot_core::config::{self, Config, MAX_BYTES};
use uefi::{
    Status, boot, cstr16,
    proto::{
        device_path::media,
        loaded_image::LoadedImage,
        media::file::{File, FileAttribute, FileMode},
    },
};

pub fn read() -> Result<Vec<u8>, Status> {
    let mut fs = boot::get_image_file_system(boot::image_handle()).map_err(|e| e.status())?;
    let mut root = fs.open_volume().map_err(|e| e.status())?;
    let handle = root
        .open(
            cstr16!("\\EFI\\EutherBoot\\eutherboot.toml"),
            FileMode::Read,
            FileAttribute::empty(),
        )
        .map_err(|e| e.status())?;
    let mut file = handle.into_regular_file().ok_or(Status::UNSUPPORTED)?;
    let mut bytes = Vec::new();
    bytes
        .try_reserve_exact(MAX_BYTES + 1)
        .map_err(|_| Status::OUT_OF_RESOURCES)?;
    bytes.resize(MAX_BYTES + 1, 0);
    let mut used = 0;
    while used < bytes.len() {
        let n = file.read(&mut bytes[used..]).map_err(|e| e.status())?;
        if n == 0 {
            break;
        }
        used += n;
    }
    if used > MAX_BYTES {
        return Err(Status::BAD_BUFFER_SIZE);
    }
    bytes.truncate(used);
    Ok(bytes)
}

pub fn own_path() -> Result<String, Status> {
    let image = boot::open_protocol_exclusive::<LoadedImage>(boot::image_handle())
        .map_err(|e| e.status())?;
    let path = image.file_path().ok_or(Status::UNSUPPORTED)?;
    let mut name = String::new();
    for node in path.node_iter() {
        let file: &media::FilePath = node.try_into().map_err(|_| Status::UNSUPPORTED)?;
        let part = file
            .path_name()
            .to_cstring16()
            .map_err(|_| Status::UNSUPPORTED)?;
        name.push_str(&String::from(&part));
    }
    if name.is_empty() {
        return Err(Status::UNSUPPORTED);
    }
    Ok(name)
}

pub fn validate(bytes: &[u8]) -> Result<Config, String> {
    let source = core::str::from_utf8(bytes).map_err(|_| String::from("Config is not UTF-8"))?;
    let config = config::parse(source)?;
    let own = own_path().map_err(|s| format!("Cannot verify own EFI path: {s:?}"))?;
    if config
        .entries()
        .iter()
        .any(|e| e.path().eq_ignore_ascii_case(&own))
    {
        return Err("Configuration points to EutherBoot itself".into());
    }
    Ok(config)
}
pub fn load() -> Result<Config, String> {
    let mut store = crate::storage::UefiStore::open()?;
    if boot_core::transaction::pending(&mut store)? {
        return Err(
            "Unfinished configuration save. F3 opens recovery; automatic boot disabled.".into(),
        );
    }
    drop(store);
    let bytes = read().map_err(|s| format!("Config read: {s:?}"))?;
    validate(&bytes)
}
