//! LLVM can lower uefi-rs' NUL-terminated UCS-2 scans to wcslen. The UEFI
//! target has no C runtime; provide the 16-bit Windows/UEFI ABI helper locally.
#[unsafe(no_mangle)]
unsafe extern "C" fn wcslen(text: *const u16) -> usize {
    let mut length = 0;
    // SAFETY: the compiler-generated caller supplies a readable, aligned,
    // NUL-terminated UCS-2 string. Volatile prevents folding back into wcslen.
    while unsafe { text.add(length).read_volatile() } != 0 {
        length += 1;
    }
    length
}
