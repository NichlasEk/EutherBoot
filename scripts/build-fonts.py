#!/usr/bin/env python3
"""Generate embedded antialiased ASCII masks; requires Pillow and Liberation fonts."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parents[1]/'crates/uefi-app/assets/fonts'
for name,face,size,w,h in [('body','Sans',16,20,24),('title','Serif',42,48,56)]:
    font=ImageFont.truetype(f'/usr/share/fonts/liberation/Liberation{face}-Regular.ttf',size)
    data=bytearray()
    for n in range(32,127):
        im=Image.new('L',(w,h));ImageDraw.Draw(im).text((0,0),chr(n),font=font,fill=255)
        data.append(round(font.getlength(chr(n))));data.extend(im.tobytes())
    (root/f'{name}.bin').write_bytes(data)
