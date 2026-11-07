# Lighter low-resource icon proposals

Mockups only, following review of the implemented 4a icons. The dark empty area
and small red/blue base are too dominant and too small respectively at native
resolution. These five alternatives explore a lighter empty container and a
larger, brighter coloured base. No option is implemented or selected here.

## Review sheet

`build/hpmp-low-review/HPMP-LOW-LIGHT-proposals-1-5.png`

Each numbered row contains separate **320×240 native-scale** field composites
for HP and MP side by side, then the **eight-bubble group plus Square**. The right
column shows exact **4× nearest-neighbour** details of both resources and the
group. View at 100% to assess the native panels; fitting the complete sheet to a
small window will shrink those panels.

| # | Empty area and outline | Coloured base / tradeoff |
|---|---|---|
| 1 | Near-white interior `(246,246,238)`, single-pixel dark outline `(48,48,56)` | Bright red/blue with a lighter surface row. Strong empty-container contrast; no dark mass inside. |
| 2 | Mid-grey interior `(156,156,164)`, the same dark outline | Same bright fill as 1. Quieter contrast than white, while substantially lighter than the implemented graphite. |
| 3 | Red/blue outline, interior matching the light-grey bubble | Same bright low fill. Colour identifies the resource even around the empty area, but the coloured outline can compete with the fill-level cue. |
| 4 | Pale, desaturated native colour/shading above; dark outer outline | Saturated bright bottom. Retains more of the native HUD material/shading, with a less explicit empty-container appearance. |
| 5 | Near-white interior and dark outline, plus a small red medical cross or blue energy spark | Same bright low fill. Adds a direct health/energy cue; the small upper symbol introduces extra detail. |

All five use **four coloured screen rows**, approximately **35–36% of the
11-pixel footprint height**, with the bottom boundary retained separately. The
heart tapers, so equal fill height does not mean equal coloured area between HP
and MP. These are static low-warning designs, not proposed exact percentage
meters or threshold changes.

## Pixel treatment and source captures

The base scenes are the existing original-2-MB captures:

- `build/hpmp-4a-proof/hp29.png`
- `build/hpmp-4a-proof/mp29.png`
- `build/hpmp-4a-edges/centre.png`

These are composites over those captures, not emulator renders of the proposed
art. Only the resource-icon rectangles are edited. Field scenery, characters,
the bubble shells, the six other condition icons, the clock and Square remain
the captured pixels.

Each resource retains the native battle HUD silhouette, fitted with nearest
point sampling to its actual **12×11 screen-pixel footprint**. The full native
silhouette restores the small lower tip/rounding that is truncated in the
current captured projection. A continuous one-screen-pixel outer border replaces
the heavy edge treatment. The orb's inner black ring is removed in the container
variants so its interior reads as empty space; option 4 retains pale shading
based on the native art. No filtered resizing, antialiasing, text band or disk
is introduced into the icon.

The fill colours are bright red `(248,64,80)` and blue `(24,152,248)`, with a
lighter top row `(255,128,136)` / `(112,216,255)`. The optional coloured outlines
are red `(192,32,48)` and blue `(16,96,192)`. These are review RGB colours;
any later implementation would need PSX palette quantization and live sampling
checks before its appearance could be accepted.

## Local assets and validation

All generated review assets and the offline authoring script remain ignored:

- `build/hpmp-low-review/render.py`
- `build/hpmp-low-review/evidence.json` — source hashes, footprints and dimensions.
- `build/hpmp-low-review/{1..5}-{hp,mp,group}-1x.png` — 15 native composites.
- `build/hpmp-low-review/{1..5}-{hp,mp,group}-4x.png` — 15 exact integer zooms.
- `build/hpmp-low-review/HPMP-LOW-LIGHT-proposals-1-5.png` — numbered sheet.

Recreate locally with `.venv/bin/python build/hpmp-low-review/render.py` when the
source captures and extracted atlas are available. The script and disc-derived
PNGs are local review assets and are not part of this documentation-only commit.

All 15 composites were checked at 320×240. All 15 zooms were checked against exact
4× replication of their source crops. Pixels outside the resource rectangles
were checked against the real captures. The entire sheet was visually inspected
before upload.

A later selected treatment is expected to fit the current two 16×16 4-bit cells
and two palettes, **320 B of existing upload occupancy**. That is an estimate,
not a measured implementation cost. There is no C change, runtime asset change,
heap change, build or new emulator run in this mockup revision. Physical display
readability and the final appearance after PSX sampling remain untested.
