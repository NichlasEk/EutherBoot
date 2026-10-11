# Regis embedded glyph masks

The main menu embeds antialiased ASCII and Swedish glyph masks generated from Liberation
Sans Regular (16 px) and Liberation Serif Regular (42 px). These assets retain
the SIL Open Font License; see LICENSE for attribution and full terms.

The binary format stores characters 32 through 126 followed by ÅÄÖåäöÉé, each as one advance byte
followed by an 8-bit coverage mask. Body cells are 20 by 24; title cells 48 by 56.
No runtime font lookup, disk access or font parsing is required. Unsupported
characters render as a question mark; display names accept the supported alphabet. Technical paths remain ASCII.

Regenerate with `python3 scripts/build-fonts.py` using Python Pillow and the
Liberation fonts under `/usr/share/fonts/liberation/`. Normal Rust builds use
the checked-in masks and do not require these generation dependencies.

Input font SHA-256 at generation:

- `LiberationSans-Regular.ttf`: `baccc64becc3eb7d104b7c84d99f5314a0a1f896e2b3ea6c2f22fc08d2003bee`
- `LiberationSerif-Regular.ttf`: `86b9ea1c2f41bed9d7c09ccad4abc2894b33df5de60e5bbbece5d48610911870`
