# Operating-system icons

The vendored SVGs come from Simple Icons at the exact commit and URLs recorded
in `manifest.json`. That manifest includes each icon's original source,
guidelines and license metadata where provided. The collection's CC0 license
and disclaimer are included here. Brand names and marks identify boot entries;
they do not imply affiliation or endorsement. `windows.svg` is a locally drawn
four-pane window under this repository's GPL-3.0-only license.

Run `python scripts/build-os-icons.py` (Python Pillow and `rsvg-convert`) to
regenerate the committed 64x64 alpha masks and `src/os_icons.rs`, entirely
offline. Cargo builds use the committed masks and do not require these tools.
A preview sheet is written to `artifacts/icons/icon-sheet.png`.

Masks are rendered at 4x content resolution then downsampled. Normal colors
are derived from the source brand color and adjusted to at least 3:1 against
the brightest menu card surface in each theme. High contrast uses white
silhouettes. Unknown entries retain the terminal icon.

Matching uses whole words in the entry's display name, ignoring ASCII case
and punctuation. Distribution variants are matched before their parent;
`Debian GNU/Linux (reserv)` stays Debian, and `Ubuntu MATE` stays Ubuntu MATE.
This is visual identification, not OS discovery or installer support.
