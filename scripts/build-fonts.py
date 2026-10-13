#!/usr/bin/env python3
"""Generate embedded antialiased ASCII and Swedish masks; requires Pillow and Liberation fonts."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parents[1]/'crates/uefi-app/assets/fonts'
for name,face,size,w,h in [('small','Sans',13,16,19),('body','Sans',16,20,24),('title','Serif',42,48,56)]:
    font=ImageFont.truetype(f'/usr/share/fonts/liberation/Liberation{face}-Regular.ttf',size)
    data=bytearray()
    for char in [chr(n) for n in range(32,127)] + list("ÅÄÖåäöÉé"):
        im=Image.new('L',(w,h));ImageDraw.Draw(im).text((0,0),char,font=font,fill=255)
        data.append(round(font.getlength(char)));data.extend(im.tobytes())
    (root/f'{name}.bin').write_bytes(data)
