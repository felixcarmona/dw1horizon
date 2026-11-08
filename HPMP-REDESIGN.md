# HP/MP bubble proposals for v0.0.8

**Selected for v0.0.8: proposal 4, faded native colour**, with pale native
shading above a saturated lower approximately 35%. The dark 4a treatment below
is historical; the faded treatment supersedes it. The six-option and 4a–4e
sections retain the design-review history; their recommendations and cost estimates predate this selection.

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


## Option 04 follow-up: explicitly low resources (4a–4e)

The plain heart can suggest affection or a request for petting. These five
variants keep the **native battle HUD heart and MP orb as their source**, with
pixel edits inside the same 11×11 canvas. The new review sheet is
`build/hpmp-redesign/HPMP-04-LOW-sheet.png`. It has five numbered rows, each with
HP-only, MP-only and all eight conditions plus Square at native 320×240, followed
by exact 4× crops of both single cases and the complete group. The backdrop,
shell, spacing and source 2 MB evidence are the same as the initial sheet.

| Variant | Treatment | Native-size assessment |
|---|---|---|
| **4a** | Both icons have a dark empty upper area; only the bottom approximately 30% of their height retains native colour. | The empty/low gauge reads through its large dark area and thin coloured base. The heart’s taper makes its remaining red smaller than the orb’s blue. |
| **4b** | Native filled heart with a five-pixel white medical cross and dark-red corner pixels behind it; orb partly empty. | The cross clarifies health; HP urgency relies on the condition bubble appearing, while the MP icon explicitly shows depletion. |
| **4c** | Native icons with a red exclamation mark against a dark lower-right corner. | Strong warning contrast. The marker remains visible at 1× but is tiny and covers some native shading. An arrow was discarded during review because it resembled a cross at this size. |
| **4d** | Native heart with a dark stepped crack; native orb dimmed to one-third channel intensity. | The crack and loss of glow suggest damage/depletion. The heart can still suggest heartbreak or sadness, and the dark orb can look inactive. |
| **4e** | Partly empty native heart with a white medical cross in its empty area; partly empty native orb. | **Preferred refinement:** combines a medical health cue with the low-gauge cue. The empty dark area gives the cross clear contrast. |

The fifth idea combines the most useful cues from 4a and 4b. It retains the
heart’s original outline and avoids adding another small object. None of these
variants adds text, a label band or a recovery disk.

The depletion line is fixed at source row 7: rows 0–6 keep the original black
outline but replace coloured pixels with dark graphite; rows 7–10 retain their
native colours. That is approximately the bottom 30% by height, not 30% of the
shape’s area or an exact live percentage meter. In particular, the heart tapers
to a point. These mockups represent the existing below-30% warning state.
They do not propose changing its threshold or continuously animating a fill.

### Follow-up assets and cost

`design/hpmp/native_variants.py` contains the hand-pixelled cross, warning and
crack masks and the deterministic palette edits applied to the locally derived
native icons. It contains no native bitmap data. The offline renderer’s
`--variants` mode exports `4a-hp.png` / `4a-mp.png` through `4e-hp.png` /
`4e-mp.png`, plus `4a-{hp,mp,all}-1x.png` and the corresponding `-4x.png` crops
for each variant. `evidence-04-low.json` records the input hashes.

Each alternative needs only the same two 16×16 4-bit cells plus two 16-colour
palettes: **320 B of occupancy**, within the current 448 B allocation. The
cross, crack and exclamation mark are baked into those cells, so no extra GPU
quad, text rendering, animation state or resident bitmap is planned. These are
five mutually exclusive review alternatives, not ten runtime icon uploads.
A static depleted warning icon needs no percentage tracking beyond the
existing condition threshold. Palette edits mean even 4a requires derived
warning artwork rather than directly sampling the unmodified native HUD icon.
Executable cost remains unmeasured until implementation; this mockup revision
changes no game binary, main heap or upload size.

Recreate the new sheet with:

```sh
.venv/bin/python design/hpmp/render.py --variants \
  --proof build/hpmp-redesign/source-native-proof.png \
  --eight build/hpmp-redesign/source-eight-needs-4x.png
```

All five rows were visually inspected in their native panels and enlarged
crops before sending. The 15 native panels and 15 integer 4× crops were checked
for dimensions and exact pixel replication. This remains an offline design
review: no fresh emulator build/run, projection sweep or physical hardware
validation has been performed.


## Previous implementation: dark 4a depleted native HUD icons

The field care renderer replaces the recovery disks and their label plates with
11×11 native heart/orb icons. The empty upper region uses **RGB5 (10,10,11)**,
about **RGB (80,80,88)**, brighter than the design mockup’s graphite, to distinguish
it from the original near-black outline. Only the bottom source rows 7–10 retain
their native colour; no cross, warning marker, crack or text is added. The fill
is a static low-resource warning, not an exact live percentage gauge.

`tools/care_bubble_art.py` derives both icons from the player’s ETCTIM entry 0,
using the original HUD palette at `(256,491)`. It preserves the native silhouette,
transparent texels, black outline and lower red/blue colours, replacing only
upper coloured texels with the empty shade. It stores each 11×11 icon at the
upper left of an existing 16×16 cell `(224,0)` or `(224,16)` in entry 1, with private
palettes in FEEL_EF rows 13/14. The standalone FEEL_EF repeats these palettes so
its ordinary upload cannot erase them. The original battle HUD stays unchanged.

The new unnumbered patch
`Show-depleted-native-HUD-icons-for-HP-and-MP-care-needs.patch` changes only the
resource icon descriptor and scale. Each icon spans 19.25 source units inside
the unchanged 26-unit native circle; the game’s ordinary point sampling and
perspective determine its final native-screen footprint. The eight condition
slots, strict `<30%` thresholds, tails, group animation, layout, viewport/clock
clamp and existing Square badge behaviour remain unchanged.

Two 16×16 4-bit cells plus two palettes occupy **320 B**, down from **448 B** for
the disk/label version. These bytes occupy existing fixed-size uploads and do
not add a disc file, file-table entry, resident art array, heap allocation or GPU
quad. The former MP cell’s extra 16×16 half is unused again. The renderer still
emits one shell and one icon quad per resource bubble.

The focused art tests verify reserved-byte-only writes, unchanged file sizes,
native silhouettes and bottom colours, palette persistence, empty-area contrast,
and surviving red/blue fill across sampling phases at 8–14 projected pixels.
The existing care/threshold host checks and 194,400 layout cases pass.
The full nine-language build and live 2 MB proof passed. The evidence is below.


### Build, memory and live 2 MB evidence

The full build used the standard command with `--jobs 8 --name hpmp-redesign`
and all nine languages; no English-only subset or heap override was used.

| Measurement | Previous disk/label renderer | 4a renderer | Change |
|---|---:|---:|---:|
| `main_BSS_END` | `0x801CE104` | `0x801CE0F4` | **−16 B** |
| Aligned main heap | 187,888 B | 187,904 B | **+16 B** |
| Reserved art/palette occupancy | 448 B | 320 B | **−128 B** |

The old renderer was recompiled locally with the completed build’s identical
English text bank, nine-language padding and generated option headers. The
exported base ELF and all nine language ELFs agree on the new `main_BSS_END`.
Normal heapcheck passes; all **320 actual-archive screen setups fit**, with a
minimum **3,184 B margin on screen 207**. No persistent state or extra GPU packet
is introduced. The texture-space saving does not reduce fixed file/upload sizes.

All **nine language atlases** have byte-identical icon cells and palettes, and
all **eight standalone FEEL copies** preserve them. ETCTIM remains **125,632 B**
in every language. `build/hpmp-atlas-audit.json` records the per-language hashes;
`build/hpmp-heap-delta.json` records the C comparison, and the build’s `heap.txt`
and `story-heap.json` record the full heap gates.

A fresh boot of the resulting disc uses **2,097,152 bytes of RAM**, with 8 MB
mode explicitly false. The proof covers HP 29%, MP 29%, both at exactly 30%,
each at 31%, both plus hunger and Square, empty inventory, full resources,
optional and critical recovery ordering, and healing through the real care menu.
One small recovery raises HP **290 → 790**, consumes one item and clears the HP
bubble. The acceptance fixture sets discipline to 100 so normal item refusal
cannot randomly turn this healing check into a Scold menu check; game refusal
rules are unchanged.

The maximum group was then recorded for **120 presented native frames** at
centre, left, right, top, top-left and top-right: **720 frames total**. Every
frame retains all eight conditions and Square, stays inside 320×240 and clears
the visible clock. Actual resource GPU rectangles are logged, and their captured
framebuffer pixels are checked: HP always retains at least **9 red pixels**,
MP at least **14 blue pixels**. The upper empty region retains at least **50
grey pixels in HP** and **38 in MP** across these recordings. These counts
verify visible fill at the sampled real field depths; they do not claim a
minimum for every possible camera depth.

| Position | Recorded group bounds, including Square |
|---|---|
| Centre | `(125,53)–(200,87)` |
| Left | `(75,52)–(150,86)` |
| Right | `(241,52)–(317,86)` |
| Top | `(127,6)–(197,36)` |
| Top-left | `(76,6)–(144,36)` |
| Top-right | `(248,6)–(317,36)` |

The inspected live review sheet is
`build/hpmp-4a-proof/HPMP-4a-2MB-sheet.png`: nine unaltered 320×240 captures,
each paired with an exact 4× nearest-neighbour crop. It includes both single
resources with Square, the hunger combination, and all six maximum-group
positions. It was visually checked before sending. Native proof data is in
`build/hpmp-4a-proof/result.json`; per-frame geometry and colour minima are in
`build/hpmp-4a-edges/result.json`. Both proof emulators have stopped.

Reproduce the live checks after the full build:

```sh
.venv/bin/python tools/dev/playtest/hpmp_bubbles.py build/hpmp-redesign.cue \
  --exe build/hpmp-redesign/exe/SLUS_010.32 --card AGUMON.mcd \
  --out build/hpmp-4a-proof --port 41084 --smoke
.venv/bin/python tools/dev/playtest/hpmp_extremes.py build/hpmp-redesign.cue \
  --exe build/hpmp-redesign/exe/SLUS_010.32 --card AGUMON.mcd \
  --fixture build/hpmp-4a-proof --out build/hpmp-4a-edges \
  --port 41085 --frames 120 --check-resource-fill
.venv/bin/python tools/dev/playtest/hpmp_contact.py build/hpmp-4a-proof \
  --edges build/hpmp-4a-edges
DW_SELFTEST_DECOMP=build/decomp-dev DW_SELFTEST_DERIVE=build/hpmp-redesign \
  DW_SELFTEST_OUT=build/hpmp-selftest-final \
  DW_SELFTEST_REPORT=build/hpmp-selftest-final/report.jsonl tools/selftest.sh
```

Physical PlayStation and CRT readability remain untested. The existing Chinese
8 MB restriction is unchanged: its atlas is verified in the nine-language build;
the live low-resource and edge checks use English on 2 MB.


The complete standard selftest passes **128 groups, 0 failed, 0 skipped**.
Its final structured report is `build/hpmp-selftest-final/report.jsonl` and its
console log is `build/selftest-final.log`. Patch-series application is included
in that run. The earlier interrupted run is retained separately for diagnosis;
the final result comes from a complete fresh run.

## Current implementation: proposal 4, faded native colour

The dark 4a art is superseded by proposal 4 from
[the lighter-treatment review](HPMP-LOW-LOOK-MOCKUPS.md). Native battle HUD
silhouettes remain 11×11, with a continuous dark outer contour, pale desaturated
native shading above, and saturated red/blue below. Internal black rings fade
with the native shading instead of forming a dark mass. The original battle HUD
is untouched.

The PSX RGB5 outline is `(6,6,7)`. Lower fill is HP `(30,8,10)` / MP `(3,19,30)`,
with a lighter surface row `(31,16,17)` / `(14,26,31)`. Source row 6 starts the
coloured base; the remaining four rows retain the contour, giving roughly 35%
coloured height after field sampling. The pale top follows the proposal's
`116 + 0.30 × native mean + 0.16 × native channel`, quantized to RGB5. Even the
former inner dark ring becomes mid-grey; the outer contour remains dark.

Both generated palettes fit 16 entries. Two existing 16×16 4-bit cells plus two
32-byte palettes still occupy **320 B**. All nine language atlases derive this
same art, and the standalone FEEL uploads retain its palettes. This revision has
no C patch, sprite descriptor, scale, threshold, layout or Square behavior change.
It remains a static `<30%` warning rather than an exact live gauge.

### Faded-art build and 2 MB evidence

The standard nine-language full build passes. Image SHA-1:
`56fb21c2c7051f3be4addcdc0ae169e82af194f1`. All nine ETCTIM files remain 125,632 B
and have identical resource cells/palettes. All standalone FEEL copies preserve
the palettes. All ten exported ELFs retain `main_BSS_END = 0x801CE0F4`; aligned
heap remains **187,904 B**, a **0 B delta** from dark 4a. Normal heapcheck passes;
all **320** actual-archive setups fit, minimum **3,184 B on screen 207**.
Local audit: `build/hpmp-faded-audit.json`; build log:
`build/faded-full-build.log`.

Fresh proof explicitly checks **2,097,152 B RAM / 8 MB false**. HP and MP 29%,
30% and 31% cases, combined hunger, empty inventory, menu ordering and recovery
use pass. Recovery raises HP **290 → 790**, consumes one item and clears its
bubble. Six maximum-condition positions each pass 120 presented frames:
**720 frames** with all eight bubbles plus Square inside the viewport and clear
of the clock. Minimum coloured pixels per resource quad are **18 HP / 26 MP**;
minimum pale pixels are **44 HP / 46 MP**. These minima apply to the captured
camera depths and animation phases, not every possible field projection.

The inspected review sheet `build/hpmp-faded-proof/HPMP-FADED-2MB-sheet.png`
contains nine unmodified 320×240 frames plus exact nearest-neighbour 4× crops:
HP alone, MP alone, hunger combination, and all eight conditions at centre,
left, right, top, top-left and top-right. Results and raw evidence remain under
`build/hpmp-faded-proof/` and `build/hpmp-faded-edges/`. Reproduce using the commands
above with these new output/fixture directories. Physical PlayStation/CRT
readability remains untested. Chinese retains its existing 8 MB requirement;
its new atlas and executable are checked, while fresh live proof uses English
on 2 MB.

The complete standard selftest passes **128 groups, 0 failed, 0 skipped**.
Log: `build/faded-selftest.log`; structured results:
`build/hpmp-faded-selftest/report.jsonl`. The focused final art/palette tests
also pass (8 tests). Both live-proof emulators stopped after capture.
