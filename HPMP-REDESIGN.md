# HP/MP bubble proposals for v0.0.8

Design review only. No game code, texture build recipe, condition rule, or patch
series changes. The recommended starting point is **04: native battle HUD icons**:
the heart is already associated with HP and the blue orb with MP, and both have
strong silhouettes at the observed field size. No design is implemented.

## Review assets

The numbered sheet is `build/hpmp-redesign/HPMP-REDESIGN-sheet.png`.
Each of its six rows contains three **320×240 images at 1:1**: HP alone with
Square, MP alone with Square, and the full condition group with Square. The
right column shows exact **4× nearest-neighbour** crops of both single cases
and the group. View the sheet at 100% for a native-size judgement; an image
viewer fitting the whole sheet to a window will shrink the game panels.

Individual files follow `01-hp-1x.png`, `01-mp-1x.png`, `01-all-1x.png` and
`01-{hp,mp,all}-4x.png`, through option 06. Transparent candidate icons are
also exported by name. All output is under `build/hpmp-redesign/`.

| # | HP / MP treatment | Reading and tradeoff |
|---|---|---|
| 01 | Red heart with a white cross / shaded blue orb | Large silhouettes, no label plate. The small cross is secondary detail and could be removed if it reads as a shine. |
| 02 | Red droplet / pale blue lightning | Different shapes as well as colours. The droplet may suggest bleeding, and lightning may suggest electricity rather than MP. |
| 03 | Bare red HP / blue MP | Two hand-pixelled letters directly on grey, without a band or disk. Readable in this fixed sample, but thin strokes remain vulnerable to projection and screen distance. |
| 04 | Existing battle HUD heart / MP orb | Preferred. Exact native 11×11 texels, no resize in this mockup. Familiar and clear; no new pictogram vocabulary. |
| 05 | Small resource symbol above a low bar | Shows approximately 29% with two of seven fill pixels. Adds detail and requires live fill rendering; the small symbols read less immediately. |
| 06 | One resource bubble: heart, orb, or both | HP-only and MP-only retain the large symbols; both low use a small heart plus a blue energy spark. Seven bubbles in the maximum group. The small combined symbols are the weakest at 1×. |

The combined proposal intentionally avoids literal `HP/MP` lettering: four
letters and a separator would recreate the cramped label problem. It changes
presentation only; the two care needs and their menu entries would stay separate.

## Pixel size and provenance

The source evidence is the existing `hpmp-native-proof.png` and
`hpmp-eight-needs-4x.png` native 2 MB verification sheets described in
[BUBBLE-DESIGN.md](BUBBLE-DESIGN.md). Local copies are named
`source-native-proof.png` and `source-eight-needs-4x.png` in the output directory.
`evidence.json` records SHA-256 hashes of both inputs and the local texture atlas.
This task reuses those captures; it does not claim a fresh emulator run.

The field background is an exact 320×240 panel from the native proof, including
the existing clock and care HUD. Other-condition pictograms come from an exact
integer reduction of the previously enlarged proof crop. The Square cap is
sampled from the same native evidence. The bubble circle is traced at the
observed **17×14 screen pixels**; the single case has a small tail. The regular
full group uses two rows of four at **17 px horizontal / 14 px vertical pitch**.
The combined proposal centres three lower bubbles beneath four upper bubbles.

New icons are authored as **11×11 pixel grids**, pasted at 1:1 into the shell.
Every pixel is intentional; there is no font rendering, vector rasterization,
AI image generation, antialiasing, or filtered icon resize. The trace preserves
the grey native style; these are offline composites, not emulator renders of a
new implementation. The source capture's projected bubble size is one real
field sample, not a promise of fixed size at every camera depth.

Option 04 locally reads ETCTIM entry 0, palette `(256,491)`, icon rectangles
`(144,48,11,11)` and `(155,48,11,11)` within that entry. These correspond to the
battle renderer's UVs `(144,176)` and `(155,176)` on its texture page;
`BTL_STATUS_BAR_SPRITES` confirms both 11×11 rectangles. Disc-derived icon
PNGs, scene captures and review sheets remain ignored under `build/`.
Only authored grids, this document and the offline sheet renderer are tracked.

## Assets and projected cost

`design/hpmp/pixels.json` contains the authored 11×11 grids and colour key.
`design/hpmp/render.py` is an offline review tool; it is not used by a game build.
The exported PNG files are review assets, not proposed runtime PNG loads.

A 16×16 4-bit tile costs **128 B** and one 16-colour palette costs **32 B**.
The current HP/MP reservation uses **448 B**: a 16×16 tile, a 32×16 tile,
and two palette rows, inside already existing fixed-size texture uploads.

| Options | Conservative texture occupancy | GPU packets relative to the current two resource bubbles | Resident memory |
|---|---:|---|---|
| 01–04 | Two 16×16 cells + two palettes = **320 B** | Same two shells and two icons; no extra quads planned | No bitmap arrays or heap buffers planned; executable delta must be measured during implementation |
| 05 | Same **320 B**, with live clipped fill quads | Up to **two additional FT4s / 80 command bytes per frame** for two live fills | Fill code cost unmeasured |
| 06 | Three 16×16 cells + one shared palette = **416 B** | Both low: one shell + one combined icon, saving **two FT4s / 80 command bytes per frame** | Collector/layout code cost unmeasured |

These are occupancy estimates within existing uploads, not new upload or main
heap allocations. For 01–04, the 128 B reduction in occupied texture/palette
space does not shrink a fixed-size disc file. Option 04 could potentially sample
the already loaded native HUD cells directly, but field texture lifetime and
palette preservation must be verified before claiming zero duplicate art.
The combined palette fits within 16 colours including transparency; the three
cells can occupy the existing 16×16 plus 32×16 reservation with a shared palette.
The dynamic bar would use a sampled fill strip inside the tile, not pre-baked
percentage frames. Packet sizes follow the existing FT4 path's 40 B per quad.

**Actual cost of this task:** zero game binary bytes, zero added VRAM uploads,
zero heap change. No C files changed, so no new `main_BSS_END` measurement or
heapcheck run is applicable to this mockup work. Future implementation needs a
full nine-language build, before/after `main_BSS_END`, normal heapcheck on 2 MB,
and live projection/animation, Square spacing and screen-edge verification.

## Recreate the sheet

With the local proof inputs and the player's extracted texture atlas available:

```sh
.venv/bin/python design/hpmp/render.py \
  --proof build/hpmp-redesign/source-native-proof.png \
  --eight build/hpmp-redesign/source-eight-needs-4x.png
```

The renderer checks grid dimensions, derives option 04 from the local atlas,
exports all 18 native panels and their 4× crops, and records input hashes.
This is a design aid, not a game test. Motion, other projection sizes, colour
accessibility and physical PlayStation display readability remain untested.
