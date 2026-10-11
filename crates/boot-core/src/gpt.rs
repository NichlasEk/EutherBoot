//! Bounded, read-only GPT verification for firmware without PartitionInfo.
use alloc::vec::Vec;

pub const ESP: [u8; 16] = [
    0x28, 0x73, 0x2a, 0xc1, 0x1f, 0xf8, 0xd2, 0x11, 0xba, 0x4b, 0x00, 0xa0, 0xc9, 0x3e, 0xc9, 0x3b,
];
const END: [u8; 4] = [0x7f, 0xff, 4, 0];
#[derive(Debug, PartialEq, Eq)]
pub enum Error {
    Invalid,
    NotGpt,
    NotEsp,
}
#[derive(Debug)]
pub struct Partition {
    pub parent: Vec<u8>,
    pub number: u32,
    pub start: u64,
    pub size: u64,
    pub guid: [u8; 16],
}
fn u32le(b: &[u8], p: usize) -> u32 {
    u32::from_le_bytes(b[p..p + 4].try_into().unwrap())
}
fn u64le(b: &[u8], p: usize) -> u64 {
    u64::from_le_bytes(b[p..p + 8].try_into().unwrap())
}
pub fn partition_path(path: &[u8]) -> Result<Partition, Error> {
    if path.len() > 3072 {
        return Err(Error::Invalid);
    }
    let mut pos = 0;
    while pos + 4 <= path.len() {
        let len = u16::from_le_bytes([path[pos + 2], path[pos + 3]]) as usize;
        if len < 4 || pos + len > path.len() {
            return Err(Error::Invalid);
        }
        if path[pos..pos + 2] == [4, 1] {
            if len != 42 || path.get(pos + len..) != Some(END.as_slice()) {
                return Err(Error::Invalid);
            }
            let b = &path[pos..pos + len];
            if b[40] != 2 || b[41] != 2 {
                return Err(Error::NotGpt);
            }
            let mut parent = path[..pos].to_vec();
            parent.extend_from_slice(&END);
            let p = Partition {
                parent,
                number: u32le(b, 4),
                start: u64le(b, 8),
                size: u64le(b, 16),
                guid: b[24..40].try_into().unwrap(),
            };
            if pos == 0 || p.number == 0 || p.size == 0 || p.guid == [0; 16] {
                return Err(Error::Invalid);
            }
            return Ok(p);
        }
        if path[pos] == 0x7f {
            return Err(Error::NotGpt);
        }
        pos += len;
    }
    Err(Error::Invalid)
}
pub fn crc32(bytes: &[u8]) -> u32 {
    let mut crc = !0u32;
    for b in bytes {
        crc ^= *b as u32;
        for _ in 0..8 {
            crc = (crc >> 1) ^ (0xedb88320u32 & (0u32.wrapping_sub(crc & 1)));
        }
    }
    !crc
}
pub struct Header {
    pub table_lba: u64,
    pub table_bytes: usize,
    pub entry_size: usize,
    pub count: u32,
    first: u64,
    last: u64,
    crc: u32,
}
pub fn header(b: &[u8], last_block: u64) -> Result<Header, Error> {
    if !(512..=4096).contains(&b.len())
        || !b.len().is_power_of_two()
        || &b[..8] != b"EFI PART"
        || u32le(b, 8) != 0x10000
    {
        return Err(Error::Invalid);
    }
    let n = u32le(b, 12) as usize;
    if n < 92 || n > b.len() || u32le(b, 20) != 0 || u64le(b, 24) != 1 || u64le(b, 32) != last_block
    {
        return Err(Error::Invalid);
    }
    let mut check = b[..n].to_vec();
    check[16..20].fill(0);
    if crc32(&check) != u32le(b, 16) {
        return Err(Error::Invalid);
    }
    let count = u32le(b, 80);
    let entry_size = u32le(b, 84) as usize;
    let table_bytes = (count as usize)
        .checked_mul(entry_size)
        .ok_or(Error::Invalid)?;
    let table_lba = u64le(b, 72);
    let first = u64le(b, 40);
    let last = u64le(b, 48);
    if count == 0
        || entry_size < 128
        || !entry_size.is_power_of_two()
        || !(16384..=1024 * 1024).contains(&table_bytes)
        || table_lba < 2
        || first > last
        || last
            .checked_add(table_bytes.div_ceil(b.len()) as u64)
            .ok_or(Error::Invalid)?
            >= last_block
        || table_lba
            .checked_add(table_bytes.div_ceil(b.len()) as u64)
            .ok_or(Error::Invalid)?
            > first
    {
        return Err(Error::Invalid);
    }
    Ok(Header {
        table_lba,
        table_bytes,
        entry_size,
        count,
        first,
        last,
        crc: u32le(b, 88),
    })
}
pub fn verify(h: &Header, table: &[u8], p: &Partition) -> Result<[u8; 16], Error> {
    if table.len() != h.table_bytes
        || crc32(table) != h.crc
        || p.number == 0
        || p.number > h.count
        || p.size == 0
        || p.guid == [0; 16]
    {
        return Err(Error::Invalid);
    }
    let offset = (p.number as usize - 1) * h.entry_size;
    let e = &table[offset..offset + h.entry_size];
    let end = p.start.checked_add(p.size - 1).ok_or(Error::Invalid)?;
    if e[16..32] != p.guid
        || u64le(e, 32) != p.start
        || u64le(e, 40) != end
        || p.start < h.first
        || end > h.last
    {
        return Err(Error::Invalid);
    }
    if e[..16] != ESP {
        return Err(Error::NotEsp);
    }
    // Bit 2 (legacy BIOS bootable) does not disqualify a UEFI ESP.
    if u64le(e, 48) & 2 != 0 {
        return Err(Error::Invalid);
    }
    Ok(p.guid)
}
#[cfg(test)]
mod tests {
    use super::*;
    use alloc::vec;
    fn fixture() -> (Vec<u8>, Vec<u8>, Partition) {
        let mut table = vec![0; 16384];
        table[..16].copy_from_slice(&ESP);
        table[16..32].fill(3);
        table[32..40].copy_from_slice(&2048u64.to_le_bytes());
        table[40..48].copy_from_slice(&4095u64.to_le_bytes());
        let mut b = vec![0; 512];
        b[..8].copy_from_slice(b"EFI PART");
        b[8..12].copy_from_slice(&0x10000u32.to_le_bytes());
        b[12..16].copy_from_slice(&92u32.to_le_bytes());
        for (i, n) in [(24, 1u64), (32, 9999), (40, 34), (48, 9966), (72, 2)] {
            b[i..i + 8].copy_from_slice(&n.to_le_bytes());
        }
        b[80..84].copy_from_slice(&128u32.to_le_bytes());
        b[84..88].copy_from_slice(&128u32.to_le_bytes());
        b[88..92].copy_from_slice(&crc32(&table).to_le_bytes());
        seal(&mut b);
        (
            b,
            table,
            Partition {
                parent: vec![],
                number: 1,
                start: 2048,
                size: 2048,
                guid: [3; 16],
            },
        )
    }
    fn seal(b: &mut [u8]) {
        b[16..20].fill(0);
        let crc = crc32(&b[..92]);
        b[16..20].copy_from_slice(&crc.to_le_bytes());
    }
    #[test]
    fn verified_identity_and_corruption() {
        assert_eq!(crc32(b"123456789"), 0xcbf43926);
        let (mut b, mut t, mut p) = fixture();
        let h = header(&b, 9999).unwrap();
        assert_eq!(verify(&h, &t, &p), Ok([3; 16]));
        p.guid[0] = 4;
        assert_eq!(verify(&h, &t, &p), Err(Error::Invalid));
        p.guid[0] = 3;
        p.start += 1;
        assert_eq!(verify(&h, &t, &p), Err(Error::Invalid));
        p.start -= 1;
        t[0] ^= 1;
        assert_eq!(verify(&h, &t, &p), Err(Error::Invalid));
        b[40] ^= 1;
        assert!(header(&b, 9999).is_err());
    }
    #[test]
    fn rejects_bounds_and_wrong_type() {
        let (mut b, mut t, p) = fixture();
        t[..16].fill(1);
        b[88..92].copy_from_slice(&crc32(&t).to_le_bytes());
        seal(&mut b);
        assert_eq!(
            verify(&header(&b, 9999).unwrap(), &t, &p),
            Err(Error::NotEsp)
        );
        b[80..84].copy_from_slice(&u32::MAX.to_le_bytes());
        seal(&mut b);
        assert!(header(&b, 9999).is_err());
        let (mut b, _, _) = fixture();
        b[72..80].copy_from_slice(&u64::MAX.to_le_bytes());
        seal(&mut b);
        assert!(header(&b, 9999).is_err());
        let (b, _, _) = fixture();
        assert!(header(&b, 10000).is_err());
    }
    #[test]
    fn four_k_blocks_and_attribute_rules() {
        let (mut b, mut t, mut p) = fixture();
        b.resize(4096, 0);
        t[48..56].copy_from_slice(&4u64.to_le_bytes());
        b[88..92].copy_from_slice(&crc32(&t).to_le_bytes());
        seal(&mut b);
        let h = header(&b, 9999).unwrap();
        assert_eq!(verify(&h, &t, &p), Ok([3; 16]));
        p.size = 0;
        assert_eq!(verify(&h, &t, &p), Err(Error::Invalid));
        p.size = 2048;
        t[48..56].copy_from_slice(&2u64.to_le_bytes());
        b[88..92].copy_from_slice(&crc32(&t).to_le_bytes());
        seal(&mut b);
        assert_eq!(
            verify(&header(&b, 9999).unwrap(), &t, &p),
            Err(Error::Invalid)
        );
        for end in 0..512 {
            assert!(header(&b[..end], 9999).is_err());
        }
    }
    #[test]
    fn device_path_must_bind_exact_parent_and_geometry() {
        let mut b = vec![1, 1, 6, 0, 0, 0, 4, 1, 42, 0];
        b.extend_from_slice(&1u32.to_le_bytes());
        b.extend_from_slice(&2048u64.to_le_bytes());
        b.extend_from_slice(&2048u64.to_le_bytes());
        b.extend_from_slice(&[3; 16]);
        b.extend_from_slice(&[2, 2]);
        b.extend_from_slice(&END);
        let p = partition_path(&b).unwrap();
        assert_eq!(p.start, 2048);
        assert_eq!(p.parent, [1, 1, 6, 0, 0, 0, 0x7f, 0xff, 4, 0]);
        for end in 0..b.len() {
            assert!(partition_path(&b[..end]).is_err());
        }
        b[46] = 1;
        assert_eq!(partition_path(&b).unwrap_err(), Error::NotGpt);
    }
}
