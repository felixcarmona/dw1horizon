# Third-party software

Horizon code and authored content use MIT unless noted below. Bundled font glyphs retain their upstream licences.

The player patcher and source replay require Python 3.10+ and use only its standard library: no NumPy and no Pillow. The browser runtime ships no NumPy wheel.

## Referenced by the repository

| Piece | How | Licence |
|---|---|---|
| [jype0/dw_decomp](https://github.com/jype0/dw_decomp), the Digimon World decompilation | git submodule `decomp/`, pinned to commit 83f99c5; our changes are the patches in `mods/patches/` | MIT |
| its own submodules: decomp-permuter, m2c, psyq_headers | fetched by `git submodule update --init --recursive` | MIT, GPL-3.0, none stated (the PlayStation SDK's headers): used only to compile, never shipped |
| [splat](https://github.com/ethteck/splat) and the decompilation's Docker toolchain (GCC for MIPS) | installed by the decompilation's `Dockerfile` (`tools/decomp-build.sh image`) | MIT; GPL-3.0 |

## Installed by the developer

| Piece | Used for | Licence |
|---|---|---|
| [mkpsxiso](https://github.com/Lameguy64/mkpsxiso) (`dumpsxiso`, `mkpsxiso`) | extracting the disc, assembling the developer's disc | GPL-2.0 |
| Python 3.10+ | player patcher, source replay and developer tools | PSF |
| [Segment Anything (SAM)](https://github.com/facebookresearch/segment-anything), Meta code and ViT-H model checkpoint | optional full-resolution foreground segmentation; `tools/maps/setup-sam.sh` downloads pinned code and a SHA-256-checked checkpoint into ignored `build/`; neither is committed | Apache-2.0 |
| [PyTorch](https://github.com/pytorch/pytorch) (`torch`) | optional SAM CPU inference, installed by `tools/maps/setup-sam.sh` | BSD-3-Clause (bundled components retain their own terms) |
| [opencv-python-headless](https://github.com/opencv/opencv-python) / [OpenCV](https://github.com/opencv/opencv) | map mask cleanup, outlines, tile grids and reachable-zone images; installed by `tools/maps/setup-sam.sh` | MIT packaging; Apache-2.0 OpenCV (bundled components retain their own terms) |
| Docker | runs the decompilation's toolchain | Apache-2.0 |

## Used by the web page (web/)

| Piece | How | Licence |
|---|---|---|
| [Pyodide](https://pyodide.org) 314.0.7 | fetched by `web/build-engine.sh` and served with the engine (not committed) | MPL-2.0 |
| [7z-wasm](https://github.com/use-strict/7z-wasm) 1.2.0 (7-Zip as WebAssembly) | loaded from jsDelivr when the visitor gives an archive | LGPL-2.1-or-later, with the unRAR licence restriction for RAR decoding |
| Plus Jakarta Sans | Google Fonts | SIL Open Font License 1.1 |
| ECM decoding (`web/js/ecm.js`) | our own, written from the format's description and ECMA-130 | MIT (this project) |

## Not included on purpose

Original disc images and extracted game files are not distributed here. The tree
does contain numeric gameplay configuration and authored deltas applied to
disc-derived assets; see the [content policy](content/README.md). Source builds
read the player's discs as described in [building](docs/building.md). Package
literal-data limits are documented in the
[patcher guide](docs/patcher.md#what-the-release-still-carries-that-is-not-ours).

## Menu icons

The 16x16 Digimon icons in `content/icons/` were drawn by hand for this project, pixel by pixel, as text files. They
hold no pixels or image data taken from any game, toy or website. Their pose and proportions were drawn while looking
at each species' published designs, including sprites of Bandai's V-Pet toys and the models of the source games, so the
icons resemble those designs on purpose. The characters themselves belong to Bandai. See the note at the top of the
[README](README.md). The icons are covered by this repository's licence only as far as our own work goes; that gives
no rights over the characters.

## Japanese bitmap font

`tools/font/japanese.txt` is the renamed **Digimon World Japanese subset**, derived
from [Fusion Pixel](https://github.com/TakWolf/fusion-pixel-font),
`fusion-pixel-10px-monospaced-ja.bdf`. The source release, checksum and glyph count
are pinned in `tools/font/japanese-license/source.json`. Fusion Pixel is SIL OFL
1.1; its copyright and licence accompany the subset in
`tools/font/japanese-license/OFL.txt`. The glyph data embedded in patch 0243 and
generated font tables is covered by these font terms too.

Upstream notices for Ark Pixel (SIL OFL 1.1), Galmuri (SIL OFL 1.1) and
Boutique Bitmap 9x9 (including its component-font terms) are retained in
`tools/font/japanese-license/upstream/`. The subset's renamed title avoids claiming
an upstream reserved font name. Contact addresses are omitted; copyright and
licence notices are retained.

## Bundled source-game readers

`tools/derive/importers/vendor/{dcb,dw2,dw3}` contains our readers from the
`digimoncardbattle`, `digimonworld2` and `digimonworld2003` research projects.
They are authored code covered by this repository's MIT licence, rather than
third-party converter implementations. `vendor/sources.json` records the source
project, commit and SHA-256 of every copied file; `vendor/README.md` describes
local numerical and dependency changes. They contain no game models, textures,
executables or assembly. Replay uses only the Python standard library.

## Console photo

`web/media/psx.webp` is a reduced copy of PSX-Console-wController.png by Evan-Amos, released into the
public domain (Wikimedia Commons).

## Raster implementation

`tools/image.py` implements PNG and raster operations with the Python standard library.
Its resampling/compositing and `tools/mediancut.py` retain Pillow arithmetic; the
required MIT-CMU (HPND) notice is in [tools/image-license.txt](tools/image-license.txt).
Optional OpenCV and SAM authoring tools use NumPy and PyTorch; SAM setup installs
neither torchvision nor Pillow. These optional tools are outside player replay.
