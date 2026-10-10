use alloc::vec::Vec;
use boot_core::ENTRIES;
use font8x8::{BASIC_FONTS, UnicodeFonts};
use uefi::{
    Status, boot,
    proto::console::gop::{BltOp, BltPixel, BltRegion, GraphicsOutput},
};
const NAVY: BltPixel = BltPixel::new(8, 21, 35);
const GOLD: BltPixel = BltPixel::new(184, 161, 105);
const WHITE: BltPixel = BltPixel::new(218, 225, 229);
const MUTED: BltPixel = BltPixel::new(119, 143, 161);
struct Canvas {
    pixels: alloc::vec::Vec<BltPixel>,
    w: usize,
    h: usize,
}
impl Canvas {
    fn rect(&mut self, x: usize, y: usize, w: usize, h: usize, color: BltPixel) {
        for yy in y..(y + h).min(self.h) {
            for xx in x..(x + w).min(self.w) {
                self.pixels[yy * self.w + xx] = color;
            }
        }
    }
    fn text(&mut self, x: usize, y: usize, s: &str, scale: usize, color: BltPixel) {
        for (i, c) in s.chars().enumerate() {
            if let Some(glyph) = BASIC_FONTS.get(c) {
                for (yy, row) in glyph.iter().enumerate() {
                    for xx in 0..8 {
                        if row & (1 << xx) != 0 {
                            self.rect(
                                x + i * 8 * scale + xx * scale,
                                y + yy * scale,
                                scale,
                                scale,
                                color,
                            );
                        }
                    }
                }
            }
        }
    }
    fn center(&mut self, y: usize, s: &str, scale: usize, color: BltPixel) {
        self.text(
            self.w.saturating_sub(s.len() * 8 * scale) / 2,
            y,
            s,
            scale,
            color,
        );
    }
    fn crown(&mut self, x: usize, y: usize, s: usize) {
        self.rect(x, y + 8 * s, 24 * s, 4 * s, GOLD);
        for (dx, dy) in [(0, 2), (10, 0), (20, 2)] {
            self.rect(x + dx * s, y + dy * s, 4 * s, 9 * s, GOLD);
        }
        self.rect(x + 4 * s, y + 6 * s, 16 * s, 3 * s, GOLD);
    }
}
pub fn draw(selected: usize, notice: &str) -> Result<(), Status> {
    let handle = boot::get_handle_for_protocol::<GraphicsOutput>().map_err(|e| e.status())?;
    // SAFETY: single-threaded application; no driver disconnect/uninstall or
    // ExitBootServices while this borrow exists. No text-console calls occur
    // until it is dropped. GET_PROTOCOL preserves the bound console driver.
    let mut gop = unsafe {
        boot::open_protocol::<GraphicsOutput>(
            boot::OpenProtocolParams {
                handle,
                agent: boot::image_handle(),
                controller: None,
            },
            boot::OpenProtocolAttributes::GetProtocol,
        )
    }
    .map_err(|e| e.status())?;
    let (w, h) = gop.current_mode_info().resolution();
    if w < 640 || h < 480 || w > 3840 || h > 2160 {
        return Err(Status::UNSUPPORTED);
    }
    let mut pixels = Vec::new();
    pixels
        .try_reserve_exact(w * h)
        .map_err(|_| Status::OUT_OF_RESOURCES)?;
    pixels.resize(w * h, NAVY);
    let mut c = Canvas { pixels, w, h };
    let s = if h >= 700 && w >= 900 { 2 } else { 1 };
    let cx = w / 2;
    c.rect(32, 32, w - 64, 1, GOLD);
    c.text(40, 48, "SYSTEM REGIS", 1, GOLD);
    c.text(w - 40 - 16 * 8, 48, "UEFI / x86_64", 1, MUTED);
    let top = 90;
    c.crown(cx - 12 * s, top, s);
    c.crown(cx - 40 * s, top + 24 * s, s);
    c.crown(cx + 16 * s, top + 24 * s, s);
    c.rect(cx - s, top + 20 * s, 2 * s, 3 * s, GOLD);
    c.rect(cx - 2 * s, top + 23 * s, 4 * s, 42 * s, GOLD);
    c.rect(cx - 12 * s, top + 57 * s, 24 * s, 3 * s, GOLD);
    c.rect(cx - 2 * s, top + 65 * s, 4 * s, 10 * s, GOLD);
    c.center(top + 90 * s, "EUTHERBOOT", s + 1, WHITE);
    let start = top + 114 * s;
    let left = cx - 220;
    for (i, label) in ENTRIES.iter().enumerate() {
        let y = start + i * 42;
        if i == selected {
            c.rect(left, y, 440, 34, BltPixel::new(22, 43, 61));
            c.rect(left, y, 3, 34, GOLD);
            c.text(left + 16, y + 12, ">", 1, GOLD);
        }
        c.text(
            left + 40,
            y + 12,
            label,
            1,
            if i == selected { WHITE } else { MUTED },
        );
    }
    c.center(h - 95, notice, 1, MUTED);
    c.rect(32, h - 64, w - 64, 1, GOLD);
    c.text(
        40,
        h - 44,
        "UP/DOWN  Select    ENTER  Open    F2  Text    ESC  Return",
        1,
        MUTED,
    );
    c.text(w - 40 - 5 * 8, h - 44, "0.1.0", 1, GOLD);
    gop.blt(BltOp::BufferToVideo {
        buffer: &c.pixels,
        src: BltRegion::Full,
        dest: (0, 0),
        dims: (w, h),
    })
    .map_err(|e| e.status())
}
