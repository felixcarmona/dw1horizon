# Model translucency audit

MarineAngemon (248) is faithful to **Digimon Digital Card Battle (USA)**,
`F.DRV/230.PAK` (`SLUS_013.28`). Its source has **386/462 ABE polygons
(83.55%)**, exactly the measured imported MMD and final provider output. No
opacity correction is appropriate. The body and wings are intentionally ghostly.

The source OMD0 block header's low byte is a GPU mode byte: bit 1 is ABE.
`vendor/dcb/mesh.py` reads that byte, `dcb2mmd.load` copies `semi` and TPAGE
ABR, and `mmdport.build_tmd` writes them to the TMD mode and TPAGE bits 5–6.
The CLUTs are copied as unsigned 16-bit words through the source VRAM reader
and `mmdport.build_tim`; neither stage forces STP onto a palette. The shared
batch palette merger uses `dw2mmd.merge_palettes`, whose colour distance
penalizes an STP mismatch. MarineAngemon requires no palette merging. Its
seven used palettes are word-identical to the source, including bit 15.

Source CLUT x is 368. Their y positions become these final CLUT rows:

| Source y | Final row | STP indices (inclusive) | Polygons | ABE |
|---|---:|---|---:|---|
| 112 | 0 | 1–7 | 18 | on |
| 113 | 1 | 1–10, 13–15 | 18 | on |
| 114 | 2 | 0–15 | 218 | on |
| 115 | 3 | 1–15 | 12 | on |
| 116 | 4 | 1–15 | 120 | on |
| 117 | 5 | 0–14 | 52 | off |
| 119 | 6 | none | 24 | off |

The **52 heart polygons and 24 gold collar polygons stay opaque**, despite
STP in the heart palette. Eye texels whose palette entries lack STP also stay
opaque on ABE polygons. Sixteen polygons sample both blending and opaque
texels. `0x0000` discards a texel; `0x8000` is visible black, with STP set:
it must not be mistaken for a transparent hole. All 44,556 sampled source vs
final MarineAngemon texel words agree. Tournament flat-sprite stamping changes
unused image rows, so comparing the whole index image alone reports a difference.

## Other outliers and the actual conversion bug

| Species | Source ABE / primitives | Final ABE / primitives | Source blend on ABE |
|---|---:|---:|---|
| 248 MarineAngemon (Card Battle) | 386/462 | 386/462 | half |
| 409 Kyubimon (World 2003, M374KYBI) | 224/1020 | 152/713 | additive |
| 251 Solarmon (Card Battle, 202.PAK) | 88/446 | 88/446 | additive |
| 227 Apemon (Card Battle, 212.PAK) | 82/471 | 82/471 | half |
| 294 Datamon (World 2, M141NANO) | 54/501 | 54/501 | half |
| 232 BomberNanimon (Card Battle, 213.PAK) | 41/425 | 41/425 | additive |

No reported ABE share is a conversion artefact. Kyubimon's reduction retains
its source-authored flame polygons. The Card Battle models' sampled words and
palettes agree with the source conversion, and Datamon's repacked texture and
palette words agree too. The World 2 packer checks texel colours against the
original page; no STP coercion was found.

**A separate World 3 blend-mode bug was confirmed.** `dw3mmd.load` interpreted
render register E as a boolean and hardcoded ABR 0. In PAL `FIGHTSTG.PRO`, the
renderer at `0x80085350` dispatches state writes; `0x800853c0` stores E at
`sp+0x48`. `0x80085484..0x800854a8` writes `(E - 1) & 3` into TPAGE bits 5–6
when E is nonzero. The packet emitters at `0x80084cdc`, `0x80084d8c`,
`0x80084ed0` and `0x80084f80` enable GPU command bit 1 when that state is
nonzero. Thus E=0 is opaque, E=1 half, E=2 additive, E=3 subtractive,
E=4 quarter-additive. This mapping is now preserved, including during quad
pairing. ABE remains unchanged.

DW1 does **not** force every model to ABR 0. Its `updateTMDTextureData`
(`decomp/src/main/graphics.c` in the local digimonworld reference) masks with
`0xFFE0FFFF`, retaining TPAGE bits 5–6 and relocating only the page coordinates.
The partner/NPC model loader supplies pages `0x15`/`0x16..0x18`, which do not
add blend bits. MarineAngemon therefore uses half blending in both games;
Solarmon and BomberNanimon already retained their source additive modes.

Scanning all frozen World 3 import recipes found E=2 in Kyubimon, Marsmon,
Fujinmon, BlackWarGreymon and MagnaAngemon. BlackWarGreymon's final mesh has
no ABE faces, so its bytes remain unchanged. The correction changes only
TPAGE words in these final provider outputs:

| Species | TPAGE words changed | Final MMD bytes before = after |
|---|---:|---:|
| 409 Kyubimon | 152 | 121362 |
| 297 Marsmon | 32 | 108898 |
| 317 Fujinmon | 24 | 101998 |
| 206 MagnaAngemon | 8 | 113332 |

The evidence directory's actual sizes are authoritative if later animation
edits change those sizes. Geometry, animations, TIMs, ABE flags and resident
heap budget are unchanged by this correction. Reversing just the corrected
ABR words reproduces each old final provider SHA-1 pin exactly. Importer
sources/deltas were rebased with `edit.py rebase`, overlay inputs moved with
`edit.py repin`, and final pins written with `edit.py put`. USA variants are
regenerated with `variants.py make`; pins are never edited manually.

## Reproduce and review

`tools/models/audit_textures.py` now reports ABE counts and shares in its JSON
and warns above 16%. All opaque/partially transparent native models pass
(ToyAgumon is 15.1%). The four wholly translucent native species, Poyomon,
ClearAgumon, BlueMeramon and Rockmon, are explicit reviewed exceptions. This
is a review warning, never an instruction to strip authentic effects.

`tools/models/psx_blend.py` renders affine UVs with back-face culling, CLUT
STP, zero-word discard, 5-bit channel arithmetic, clamping, and all four PSX
blend equations. It uses neutral lighting, orthographic projection and mean
primitive depth sorting; it does not reproduce the games' precise GTE lighting,
OT buckets or fixed-point rasterizer. The checkerboard exposes background
contributions. An ABE-off panel is explicitly a diagnostic, not a proposed fix.

```sh
python tools/models/audit_translucency.py --from BUILD \
  --before BEFORE_PROVIDER_PAIRS --after AFTER_PROVIDER_PAIRS \
  --out build/translucency/evidence
python -W ignore -m unittest tools.test_psx_blend tools.test_audit_textures \
  tools.test_imported_model_edit tools.test_model_variants
```

Use a Python with NumPy and Pillow for the evidence tool. The before provider
pairs must pass the previous final SHA-1 pins; after pairs must pass the new
pins. An `ID.json` beside the after pairs supplies a replaced provider skeleton.
`materials.json` records per-polygon opaque/blended/discarded texel counts and
all palette STP indices. `translucency.png` is the single comparison grid sent
using `~/Projects/media-gateway/bin/mg-send`.
