fn main() {
    let path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "eutherboot.toml".into());
    let result = std::fs::read(&path)
        .map_err(|e| e.to_string())
        .and_then(|bytes| {
            let text = std::str::from_utf8(&bytes)
                .map_err(|_| "Configuration is not UTF-8".to_string())?;
            boot_core::config::parse(text)
        });
    match result {
        Ok(config) => println!(
            "Valid: {} EFI entries, default={}, timeout={}s",
            config.entries().len(),
            config.entries()[config.default_index()].id(),
            config.timeout()
        ),
        Err(error) => {
            eprintln!("Invalid configuration: {error}");
            std::process::exit(1);
        }
    }
}
