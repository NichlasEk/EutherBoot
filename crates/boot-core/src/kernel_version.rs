//! Bounded display metadata only; never used to decide whether an image may boot.
use alloc::string::String;

fn u16_at(b: &[u8], n: usize) -> Option<u16> {
    Some(u16::from_le_bytes(b.get(n..n + 2)?.try_into().ok()?))
}
fn u32_at(b: &[u8], n: usize) -> Option<u32> {
    Some(u32::from_le_bytes(b.get(n..n + 4)?.try_into().ok()?))
}
fn release(bytes: &[u8]) -> Option<String> {
    let end = bytes.iter().position(|b| matches!(b, 0 | b' ' | b'\n'))?;
    let value = bytes.get(..end)?;
    if value.is_empty()
        || value.len() > 128
        || !value[0].is_ascii_digit()
        || !value.contains(&b'.')
        || !value
            .iter()
            .all(|b| b.is_ascii_alphanumeric() || b".-_+".contains(b))
    {
        return None;
    }
    Some(core::str::from_utf8(value).ok()?.into())
}

/// Random-access reads keep large kernels/initrds out of the menu's heap.
/// At most 96 section headers and 129 version bytes are inspected.
pub fn read(size: u64, mut read_at: impl FnMut(u64, &mut [u8]) -> Option<()>) -> Option<String> {
    let mut header = [0u8; 1024];
    read_at(0, &mut header)?;
    let mut linux = (0, size);
    if header.get(..2)? == b"MZ" {
        let pe = u32_at(&header, 0x3c)? as u64;
        if !(64..=1024 * 1024).contains(&pe) {
            return None;
        }
        let mut coff = [0u8; 24];
        read_at(pe, &mut coff)?;
        if &coff[..4] != b"PE\0\0" {
            return None;
        }
        let count = u16_at(&coff, 6)?;
        if !(1..=96).contains(&count) {
            return None;
        }
        let table = pe + 24 + u16_at(&coff, 20)? as u64;
        if table + u64::from(count) * 40 > size {
            return None;
        }
        let mut uname = None;
        for i in 0..count {
            let mut section = [0u8; 40];
            read_at(table + u64::from(i) * 40, &mut section)?;
            // Profiles may override the kernel: don't guess which will run.
            if &section[..8] == b".profile" {
                return None;
            }
            let offset = u32_at(&section, 20)? as u64;
            let length = u32_at(&section, 8)?.min(u32_at(&section, 16)?) as u64;
            if offset + length > size {
                return None;
            }
            if &section[..8] == b".uname\0\0" {
                uname = Some((offset, length));
            }
            if &section[..8] == b".linux\0\0" {
                linux = (offset, length);
            }
        }
        if linux.0 != 0 {
            if let Some((offset, length)) = uname {
                let mut bytes = [0u8; 129];
                let n = length.min(129) as usize;
                read_at(offset, &mut bytes[..n])?;
                if let Some(version) = release(&bytes) {
                    return Some(version);
                }
            }
            if linux.1 < header.len() as u64 {
                return None;
            }
            read_at(linux.0, &mut header)?;
        }
    }
    if &header[0x202..0x206] != b"HdrS" || u16_at(&header, 0x206)? < 0x200 {
        return None;
    }
    let pointer = u16_at(&header, 0x20e)?;
    if pointer == 0 {
        return None;
    }
    let offset = u64::from(pointer) + 0x200;
    let n = linux.1.checked_sub(offset)?.min(129) as usize;
    let mut bytes = [0u8; 129];
    read_at(linux.0 + offset, &mut bytes[..n])?;
    release(&bytes[..n])
}

#[cfg(test)]
mod tests {
    use super::*;
    use alloc::vec;
    fn parse(b: &[u8]) -> Option<String> {
        read(b.len() as u64, |offset, out| {
            out.copy_from_slice(b.get(offset as usize..offset as usize + out.len())?);
            Some(())
        })
    }
    #[test]
    fn direct_kernel_and_bad_metadata() {
        let mut b = vec![0u8; 2048];
        b[0x202..0x206].copy_from_slice(b"HdrS");
        b[0x206..0x208].copy_from_slice(&0x20fu16.to_le_bytes());
        b[0x20e..0x210].copy_from_slice(&0x200u16.to_le_bytes());
        b[1024..1043].copy_from_slice(b"7.2.9-arch1-1 test\0");
        assert_eq!(parse(&b).as_deref(), Some("7.2.9-arch1-1"));
        b[1025] = 27;
        assert_eq!(parse(&b), None);
        for n in 0..1024 {
            assert_eq!(parse(&b[..n]), None);
        }
    }
    #[test]
    fn uki_uname_and_embedded_fallback() {
        let mut b = vec![0u8; 4096];
        b[..2].copy_from_slice(b"MZ");
        b[0x3c] = 64;
        b[64..68].copy_from_slice(b"PE\0\0");
        b[70] = 2;
        b[88..96].copy_from_slice(b".linux\0\0");
        b[96..100].copy_from_slice(&2048u32.to_le_bytes());
        b[104..108].copy_from_slice(&2048u32.to_le_bytes());
        b[108..112].copy_from_slice(&2048u32.to_le_bytes());
        b[128..136].copy_from_slice(b".uname\0\0");
        b[136] = 64;
        b[144] = 64;
        b[148..152].copy_from_slice(&1024u32.to_le_bytes());
        b[1024..1040].copy_from_slice(b"6.18.55-1-lts\0\0\0");
        assert_eq!(parse(&b).as_deref(), Some("6.18.55-1-lts"));
        b[128..136].copy_from_slice(b".profile");
        assert_eq!(parse(&b), None);
        b[128..136].fill(0);
        b[2562..2566].copy_from_slice(b"HdrS");
        b[2566..2568].copy_from_slice(&0x20fu16.to_le_bytes());
        b[2574..2576].copy_from_slice(&0x200u16.to_le_bytes());
        b[3072..3078].copy_from_slice(b"6.1.0\0");
        assert_eq!(parse(&b).as_deref(), Some("6.1.0"));
        b[108..112].copy_from_slice(&u32::MAX.to_le_bytes());
        assert_eq!(parse(&b), None);
    }
}
