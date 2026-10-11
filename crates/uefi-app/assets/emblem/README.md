# System Regis emblem

`regis-steel-gold.png` is the image-generated concept approved by the user on
2026-10-11: a steel sword behind three gold crowns. The original generated RGBA
PNG is retained, including its transparency. It is not an official insignia.

`regis-144.rgba` is a 144×144, row-major, 8-bit RGBA conversion, embedded in the
UEFI binary. Regenerate with `bash scripts/build-emblem.sh` (ImageMagick).
The renderer alpha-composites it over the navy canvas; no PNG decoder or
runtime file reads are involved. Compact layouts render it at 96×96.

This remains a raster asset, not a vector tracing. The PNG is the editable
source reference for future refinement; existing approved artwork is preserved.
