use alloc::vec::Vec;

use uefi::{
    Status, boot,
    proto::console::gop::{BltOp, BltPixel, BltRegion, GraphicsOutput},
};
const NAVY: BltPixel = BltPixel::new(9, 15, 24);
const GOLD: BltPixel = BltPixel::new(208, 184, 125);
const WHITE: BltPixel = BltPixel::new(238, 229, 205);
const MUTED: BltPixel = BltPixel::new(165, 177, 192);
struct Canvas {
    pixels: alloc::vec::Vec<BltPixel>,
    w: usize,
    h: usize,
}
impl Canvas {
    fn rect(&mut self, x: usize, y: usize, w: usize, h: usize, color: BltPixel) {
        let color = palette(color);
        for yy in y..(y + h).min(self.h) {
            for xx in x..(x + w).min(self.w) {
                self.pixels[yy * self.w + xx] = color;
            }
        }
    }
    fn text(&mut self, x: usize, y: usize, text: &str, title: bool, color: BltPixel) {
        let color = palette(color);
        let (data, w, h): (&[u8], usize, usize) = if title {
            (include_bytes!("../assets/fonts/title.bin"), 48, 56)
        } else {
            (include_bytes!("../assets/fonts/body.bin"), 20, 24)
        };
        let mut pen = x;
        for ch in text.chars() {
            let offset = boot_core::presentation::glyph_index(ch) * (1 + w * h);
            for yy in 0..h {
                for xx in 0..w {
                    if pen + xx >= self.w || y + yy >= self.h {
                        continue;
                    }
                    let alpha = data[offset + 1 + yy * w + xx] as u32;
                    let dst = &mut self.pixels[(y + yy) * self.w + pen + xx];
                    let mix =
                        |a: u8, b: u8| ((a as u32 * (255 - alpha) + b as u32 * alpha) / 255) as u8;
                    *dst = BltPixel::new(
                        mix(dst.red, color.red),
                        mix(dst.green, color.green),
                        mix(dst.blue, color.blue),
                    );
                }
            }
            pen += data[offset] as usize;
        }
    }
    fn width(text: &str, title: bool) -> usize {
        let (data, stride): (&[u8], usize) = if title {
            (include_bytes!("../assets/fonts/title.bin"), 2689)
        } else {
            (include_bytes!("../assets/fonts/body.bin"), 481)
        };
        text.chars()
            .map(|c| data[boot_core::presentation::glyph_index(c) * stride] as usize)
            .sum()
    }
    fn center(&mut self, y: usize, text: &str, title: bool, color: BltPixel) {
        self.text(
            self.w.saturating_sub(Self::width(text, title)) / 2,
            y,
            text,
            title,
            color,
        );
    }
    fn blend(&mut self, x: usize, y: usize, color: BltPixel, alpha: u32) {
        if x >= self.w || y >= self.h {
            return;
        }
        let dst = &mut self.pixels[y * self.w + x];
        let mix = |a: u8, b: u8| ((a as u32 * (255 - alpha) + b as u32 * alpha) / 255) as u8;
        *dst = BltPixel::new(
            mix(dst.red, color.red),
            mix(dst.green, color.green),
            mix(dst.blue, color.blue),
        );
    }
    fn line(&mut self, x0: usize, y0: usize, x1: usize, y1: usize, color: BltPixel) {
        let color = palette(color);
        let dx = x1 as i64 - x0 as i64;
        let dy = y1 as i64 - y0 as i64;
        let length = dx * dx + dy * dy;
        if length == 0 {
            return;
        }
        for y in y0.min(y1).saturating_sub(1)..=(y0.max(y1) + 1).min(self.h - 1) {
            for x in x0.min(x1).saturating_sub(1)..=(x0.max(x1) + 1).min(self.w - 1) {
                let mut coverage = 0;
                for sy in [1, 3, 5, 7] {
                    for sx in [1, 3, 5, 7] {
                        let px = (x as i64 - x0 as i64) * 8 + sx;
                        let py = (y as i64 - y0 as i64) * 8 + sy;
                        let dot = px * dx + py * dy;
                        let cross = px * dy - py * dx;
                        if dot >= 0 && dot <= length * 8 && cross * cross <= length * 36 {
                            coverage += 1;
                        }
                    }
                }
                self.blend(x, y, color, coverage * 255 / 16);
            }
        }
    }
    fn emblem(&mut self, x: usize, y: usize, size: usize) {
        let pixels = include_bytes!("../assets/emblem/regis-144.rgba");
        for yy in 0..size {
            for xx in 0..size {
                let i = ((yy * 144 / size) * 144 + xx * 144 / size) * 4;
                self.blend(
                    x + xx,
                    y + yy,
                    BltPixel::new(pixels[i], pixels[i + 1], pixels[i + 2]),
                    pixels[i + 3] as u32,
                );
            }
        }
    }
    fn panel(&mut self, x: usize, y: usize, w: usize, h: usize, selected: bool) {
        let radius = 12i64;
        let inside = |px: i64, py: i64, inset: i64| {
            let r = (radius - inset) * 8;
            let cx = px.clamp(radius * 8, (w as i64 - radius) * 8);
            let cy = py.clamp(radius * 8, (h as i64 - radius) * 8);
            (px - cx) * (px - cx) + (py - cy) * (py - cy) <= r * r
        };
        for yy in 0..h {
            for xx in 0..w {
                let mut outer = 0;
                let mut inner = 0;
                for sy in [1, 3, 5, 7] {
                    for sx in [1, 3, 5, 7] {
                        let px = xx as i64 * 8 + sx;
                        let py = yy as i64 * 8 + sy;
                        if inside(px, py, 0) {
                            outer += 1;
                        }
                        if inside(px, py, 1) {
                            inner += 1;
                        }
                    }
                }
                let edge = if selected {
                    GOLD
                } else {
                    BltPixel::new(46, 62, 79)
                };
                self.blend(x + xx, y + yy, palette(edge), outer * 255 / 16);
                let light = if selected { 8 } else { 0 } + ((h - yy) * 8 / h) as u8;
                self.blend(x + xx, y + yy, surface(light), inner * 255 / 16);
            }
        }
    }
    fn icon(&mut self, x: usize, y: usize, label: &str) {
        let accent = BltPixel::new(114, 215, 213);
        if label.to_ascii_lowercase().contains("arch") {
            for pair in [
                (0, 64, 28, 0),
                (28, 0, 56, 64),
                (0, 64, 20, 52),
                (36, 52, 56, 64),
                (20, 52, 28, 36),
                (28, 36, 36, 52),
            ] {
                self.line(x + pair.0, y + pair.1, x + pair.2, y + pair.3, accent);
            }
        } else {
            self.panel(x, y + 6, 60, 48, false);
            self.line(x + 12, y + 20, x + 22, y + 28, GOLD);
            self.line(x + 22, y + 28, x + 12, y + 36, GOLD);
            self.rect(x + 29, y + 35, 17, 2, accent);
            self.rect(x + 27, y + 56, 6, 8, GOLD);
            self.rect(x + 16, y + 64, 28, 2, GOLD);
        }
    }
}

fn render(paint: impl FnOnce(&mut Canvas, usize, usize)) -> Result<(), Status> {
    if crate::ui::text() {
        return Err(Status::UNSUPPORTED);
    }
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
    let (output_w, output_h) = (w, h);
    let scale = (h / 480).min(w / 640).clamp(1, 3);
    let (w, h) = (w / scale, h / scale);
    let mut pixels = Vec::new();
    pixels
        .try_reserve_exact(output_w * output_h)
        .map_err(|_| Status::OUT_OF_RESOURCES)?;
    pixels.resize(w * h, palette(NAVY));
    let mut c = Canvas { pixels, w, h };
    paint(&mut c, w, h);
    // Expand backwards in the already-reserved output buffer. Source indices are
    // never greater than their destination, so no unread pixel is overwritten.
    if scale > 1 {
        c.pixels.resize(output_w * output_h, palette(NAVY));
        for y in (0..output_h).rev() {
            for x in (0..output_w).rev() {
                c.pixels[y * output_w + x] =
                    c.pixels[(y / scale).min(h - 1) * w + (x / scale).min(w - 1)];
            }
        }
    }
    gop.blt(BltOp::BufferToVideo {
        buffer: &c.pixels,
        src: BltRegion::Full,
        dest: (0, 0),
        dims: (output_w, output_h),
    })
    .map_err(|e| e.status())
}

pub fn draw(labels: &[&str], selected: usize, notice: &str) -> Result<(), Status> {
    render(|c, w, h| {
        let cx = w / 2;
        let compact = h < 600;
        c.text(32, 24, "SYSTEM REGIS", false, GOLD);
        c.text(w - 135, 24, "UEFI / x86_64", false, MUTED);
        // Quiet circuit geometry frames the controls without obscuring them.
        for i in 0..5 {
            let x = 24 + i * 18;
            let y = h - 150 - i * 15;
            let ink = BltPixel::new(23, 44, 58);
            c.line(x, h - 80, x, y, ink);
            c.line(x, y, x + 65, y - 65, ink);
            c.line(x + 65, y - 65, x + 100, y - 65, ink);
        }
        let crest = if compact { 48 } else { h / 2 - 230 };
        let emblem_size = if compact { 96 } else { 144 };
        c.emblem(
            cx - emblem_size / 2,
            crest.saturating_sub(emblem_size - 96),
            emblem_size,
        );
        c.center(crest + 96, "EutherBoot", true, WHITE);
        c.center(
            crest + 154,
            "The machine belongs to its owner.",
            false,
            MUTED,
        );
        let entries = labels.len().saturating_sub(2);
        let visible = ((w - 80) / 174).clamp(1, 5);
        let first = if selected < entries {
            selected / visible * visible
        } else {
            0
        };
        let count = (entries - first).min(visible);
        let top = if compact { 244 } else { h / 2 + 5 };
        let card_h = if compact { 108 } else { 132 };
        let start = cx - count * 174 / 2 + 7;
        for (slot, i) in (first..first + count).enumerate() {
            let x = start + slot * 174;
            c.panel(x, top, 160, card_h, i == selected);
            c.icon(x + 50, top + 6, labels[i]);
            let mut label: alloc::string::String = labels[i].into();
            while Canvas::width(&label, false) > 140 {
                label.pop();
            }
            if label.len() < labels[i].len() {
                while Canvas::width(&label, false) > 125 {
                    label.pop();
                }
                label.push_str("...");
            }
            c.text(
                x + (160 - Canvas::width(&label, false)) / 2,
                top + card_h - 27,
                &label,
                false,
                if i == selected { WHITE } else { MUTED },
            );
        }
        let tool_y = top + card_h + 14;
        for (n, title) in [
            crate::ui::choose("Configuration", "Inställningar"),
            "Firmware",
        ]
        .iter()
        .enumerate()
        {
            let x = cx - 150 + n * 158;
            c.panel(x, tool_y, 142, 32, selected == entries + n);
            c.text(
                x + 12,
                tool_y + 5,
                title,
                false,
                if selected == entries + n { GOLD } else { MUTED },
            );
        }
        if entries > visible {
            c.text(
                w - 105,
                tool_y + 5,
                &alloc::format!("{} / {}", selected.min(entries - 1) + 1, entries),
                false,
                MUTED,
            );
        }
        let mut short: alloc::string::String = notice.into();
        while Canvas::width(&short, false) > w - 64 {
            short.pop();
        }
        c.center(h - 80, &short, false, MUTED);
        c.rect(32, h - 49, w - 64, 1, BltPixel::new(45, 57, 69));
        c.text(
            32,
            h - 36,
            crate::ui::choose(
                "Arrows Select   Enter Open   F2 Text   F3 Edit   F4 Scan   Esc",
                "Pilar Välj   Enter Öppna   F2 Text   F3 Ändra   F4 Sök   Esc",
            ),
            false,
            MUTED,
        );
        c.text(w - 75, h - 36, env!("CARGO_PKG_VERSION"), false, GOLD);
    })
}

fn palette(c: BltPixel) -> BltPixel {
    let rgb = (c.red, c.green, c.blue);
    let mapped = match crate::ui::theme() {
        2 => match rgb {
            (9, 15, 24) => (233, 231, 224),
            (238, 229, 205) => (23, 35, 52),
            (165, 177, 192) => (83, 97, 116),
            (208, 184, 125) => (115, 85, 27),
            (46, 62, 79) | (45, 57, 69) | (23, 44, 58) => (176, 175, 167),
            (114, 215, 213) => (22, 106, 113),
            _ => rgb,
        },
        3 => match rgb {
            (9, 15, 24) => (0, 0, 0),
            (238, 229, 205) | (165, 177, 192) => (255, 255, 255),
            (208, 184, 125) => (255, 225, 107),
            (46, 62, 79) | (45, 57, 69) => (150, 150, 150),
            _ => rgb,
        },
        _ => rgb,
    };
    BltPixel::new(mapped.0, mapped.1, mapped.2)
}
fn surface(light: u8) -> BltPixel {
    match crate::ui::theme() {
        2 => BltPixel::new(249 - light / 2, 248 - light / 2, 243 - light / 2),
        3 => BltPixel::new(12 + light, 12 + light, 12 + light),
        _ => BltPixel::new(16 + light, 27 + light, 41 + light),
    }
}

impl Canvas {
    fn clipped_text(&mut self, x: usize, y: usize, value: &str, max: usize, color: BltPixel) {
        let mut text: alloc::string::String = value.into();
        if Self::width(&text, false) > max {
            while Self::width(&text, false) > max.saturating_sub(20) {
                text.pop();
            }
            text.push_str("...");
        }
        self.text(x, y, &text, false, color);
    }
    fn heading(&mut self, title: &str, w: usize, compact: bool) {
        self.emblem(24, 12, if compact { 48 } else { 72 });
        self.text(
            if compact { 84 } else { 112 },
            16,
            "SYSTEM REGIS",
            false,
            GOLD,
        );
        self.text(
            if compact { 84 } else { 112 },
            if compact { 38 } else { 42 },
            title,
            !compact && Self::width(title, true) < w - 144,
            WHITE,
        );
        self.rect(24, if compact { 72 } else { 112 }, w - 48, 1, GOLD);
    }
}

/// Generic graphical prompt/confirmation/details screen; caller keeps all input semantics.
pub fn sheet(title: &str, lines: &[&str], footer: &str) -> Result<(), Status> {
    render(|c, w, h| {
        let compact = h < 600;
        c.heading(title, w, compact);
        let mut y = if compact { 90 } else { 142 };
        for line in lines {
            let mut row = alloc::string::String::new();
            for ch in line.chars() {
                row.push(ch);
                if Canvas::width(&row, false) > w - 80 {
                    row.pop();
                    if y + 24 < h - 72 {
                        c.text(32, y, &row, false, WHITE);
                    }
                    y += 24;
                    row.clear();
                    row.push(ch);
                }
            }
            if y + 24 < h - 72 {
                c.text(32, y, &row, false, WHITE);
            }
            y += 28;
        }
        c.rect(24, h - 62, w - 48, 1, GOLD);
        c.clipped_text(32, h - 47, footer, w - 64, MUTED);
    })
}

pub fn editor(
    draft: Option<&boot_core::draft::Draft>,
    selected: usize,
    editing: bool,
    message: &str,
) -> Result<(), Status> {
    use crate::ui::choose as t;
    render(|c, w, h| {
        let compact = h < 600;
        c.heading(t("Boot settings", "Startinställningar"), w, compact);
        let status = if editing {
            t("DRAFT - not saved", "UTKAST - inte sparat")
        } else {
            t("READ ONLY", "ENDAST LÄSNING")
        };
        c.text(w - 220, if compact { 39 } else { 74 }, status, false, GOLD);
        let top = if compact { 84 } else { 132 };
        if let Some(d) = draft {
            let count = if compact { 3 } else { 5 };
            let first = selected / count * count;
            let list_width = if compact { w - 48 } else { (w / 3).min(310) };
            if !compact {
                c.panel(24, top, list_width, h - 360, false);
            }
            for (slot, (i, e)) in d
                .entries
                .iter()
                .enumerate()
                .skip(first)
                .take(count)
                .enumerate()
            {
                let y = top + if compact { slot * 30 } else { 14 + slot * 52 };
                c.panel(
                    32,
                    y,
                    list_width - 16,
                    if compact { 28 } else { 46 },
                    i == selected,
                );
                let marker = if e.id == d.default { "* " } else { "  " };
                c.clipped_text(
                    44,
                    y + if compact { 2 } else { 10 },
                    &alloc::format!("{marker}{}", e.name),
                    list_width - 42,
                    if i == selected { GOLD } else { WHITE },
                );
            }
            let x = if compact { 32 } else { list_width + 48 };
            let y = if compact { top + 100 } else { top + 12 };
            let available = w - x - 32;
            if !compact {
                c.panel(x - 8, top, available + 16, h - 360, false);
            }
            if let Some(e) = d.entries.get(selected) {
                c.clipped_text(
                    x + 8,
                    y,
                    &alloc::format!("N  {}: {}", t("Name", "Namn"), e.name),
                    available - 16,
                    WHITE,
                );
                c.clipped_text(
                    x + 8,
                    y + 30,
                    &alloc::format!("P  {}: {}", t("Path", "Sökväg"), e.path),
                    available - 16,
                    MUTED,
                );
                if !compact {
                    c.clipped_text(
                        x + 8,
                        y + 65,
                        &alloc::format!("K  {}: {}", t("Type", "Typ"), e.kind),
                        available - 16,
                        MUTED,
                    );
                    c.clipped_text(
                        x + 8,
                        y + 100,
                        &alloc::format!(
                            "U  {}: {}",
                            t("Partition", "Partition"),
                            if e.partition_guid.is_empty() {
                                t("own volume", "egen volym")
                            } else {
                                &e.partition_guid
                            }
                        ),
                        available - 16,
                        MUTED,
                    );
                    c.text(
                        x + 8,
                        y + 140,
                        t("F6  Complete entry details", "F6  Postens alla detaljer"),
                        false,
                        MUTED,
                    );
                }
            }
            let global_y = if compact { top + 163 } else { h - 212 };
            let default = d
                .entries
                .iter()
                .find(|e| e.id == d.default)
                .map(|e| e.name.as_str())
                .unwrap_or(&d.default);
            c.clipped_text(
                32,
                global_y,
                &alloc::format!("D  {}: {}", t("Default", "Förval"), default),
                w / 2 - 48,
                WHITE,
            );
            c.clipped_text(
                w / 2,
                global_y,
                &alloc::format!("T  {}: {} s", t("Autoboot", "Autostart"), d.timeout),
                w / 2 - 32,
                WHITE,
            );
            let theme = match d.theme.as_str() {
                "system-regis-light" => t("Light", "Ljus"),
                "high-contrast" => t("Contrast", "Kontrast"),
                "text" => "Text",
                _ => "Regis",
            };
            c.clipped_text(
                32,
                global_y + 26,
                &alloc::format!("G  {}: {}", t("Theme", "Tema"), theme),
                w / 2 - 48,
                GOLD,
            );
            c.clipped_text(
                w / 2,
                global_y + 26,
                &alloc::format!(
                    "L  {}: {}",
                    t("Language", "Språk"),
                    if d.language == "sv" {
                        "Svenska"
                    } else {
                        "English"
                    }
                ),
                w / 2 - 32,
                GOLD,
            );
            if first + count < d.entries.len() || first > 0 {
                c.text(
                    w - 90,
                    top - 24,
                    &alloc::format!("{}/{}", selected + 1, d.entries.len()),
                    false,
                    MUTED,
                );
            }
        } else {
            c.text(
                32,
                top,
                t(
                    "No valid configuration. Use B/C recovery.",
                    "Ingen giltig konfiguration. Återställ med B/C.",
                ),
                false,
                WHITE,
            );
        }
        let controls = if editing {
            [
                t(
                    "A Add   R Remove   I Import   V Validate",
                    "A Lägg till   R Ta bort   I Importera   V Kontrollera",
                ),
                t(
                    "N Name  P Path  U Partition  K Type  C Cmdline  J Initrd",
                    "N Namn  P Sökväg  U Partition  K Typ  C Kommandorad  J Initrd",
                ),
                t(
                    "F5 Preview   S Save   Esc Discard   F2 Text   F6 Details",
                    "F5 Visa   S Spara   Esc Kasta   F2 Text   F6 Detaljer",
                ),
            ]
        } else {
            [
                t(
                    "E Edit   B Restore backup   C Keep current",
                    "E Ändra   B Återställ backup   C Behåll nuvarande",
                ),
                t(
                    "Up/Down Select   F6 Details   F2 Text",
                    "Upp/Ned Välj   F6 Detaljer   F2 Text",
                ),
                t("Esc Return to boot menu", "Esc Tillbaka till startmenyn"),
            ]
        };
        c.clipped_text(32, h - 139, crate::ui::tr(message), w - 64, MUTED);
        c.rect(24, h - 106, w - 48, 1, GOLD);
        for (i, line) in controls.iter().enumerate() {
            c.clipped_text(32, h - 94 + i * 27, line, w - 64, WHITE);
        }
    })
}
