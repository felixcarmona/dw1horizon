# Status portrait size audit

Player reports 1569040038556209162 (Devidramon), 1569039446786052166
(Triceramon), and 1569060624288190574 (small portraits, illustrated with
Veemon) prompted this audit of all 291 raisable species, including every
import and all eight handmade babies, against baseline `024209eb`.

## Cause

Status uses the species' `partner.status_screen_position` camera translation,
not its field collision size. Native rows live in `RAISE_DATA`; imported rows
live in the existing species record. `renderDigiviceEntity` resets idle slot 0
and advances it once each render pass. Earlier camera fits of complete idle
travel left some species too far away. The subsequent UI-clearance fitter
could only increase depth and skipped the minimum-height check for unchanged
portraits. Thus an 18-pixel Infermon passed the ordinary audit, and several
larger silhouettes occupied much less space than their live pose allowed.

PR #336 (`2a7d5305`) already supplied per-species camera fitting and improved
Nefertimon's visible width from 48 to 77 pixels. The later `83dcaa85` fix
keeps Devidramon and Triceramon above Life and clear of labels. Both already
fit on this baseline; their camera coordinates are retained. Nefertimon is
also retained. The new work addresses the remaining small portraits.

A rebuilt-archive comparison exposed a second cause for Magnamon: its native
binding recipe carries a complete partner override, including stale portrait
coordinates. Updating the species JSON alone was silently overwritten. The
recipe camera now matches the species camera, and an asset-free consistency
test guards every native binding that overrides this field.

## Repair and acceptance

The opt-in `--enlarge-small` audit compares visible height with the largest
raster-verified fit of the actual first pose. Below 85% of that attainable
height, it moves the camera closer and refits the offset. Every candidate
must clear the Status label, the full sleeping-badge bob, panel edges and
Life/care rows in all animated texture phases. The ordinary audit now checks
the 20-pixel height floor for every species too.

Only `partner.status_screen_position` changes in species data. No engine
patch, new resident table, model, texture, animation, field scale or record
size is needed. The existing patch series remains unchanged.

| ID | Species | Before height | After height |
|---|---|---:|---:|
| 15 | Punimon | 25 px | 45 px |
| 21 | Birdramon | 24 px | 42 px |
| 59 | Phoenixmon | 21 px | 43 px |
| 62 | WereGarurumon | 33 px | 44 px |
| 106 | Saberdramon | 24 px | 42 px |
| 107 | Soulmon | 36 px | 45 px |
| 122 | Hagurumon | 31 px | 45 px |
| 180 | Veemon | 37 px | 45 px |
| 188 | Aquilamon | 29 px | 38 px |
| 192 | Imperialdramon | 35 px | 42 px |
| 197 | Magnamon | 37 px | 45 px |
| 200 | Pegasusmon | 37 px | 45 px |
| 211 | MetalSeadramon | 37 px | 45 px |
| 215 | Magnadramon | 34 px | 44 px |
| 218 | Ikkakumon | 37 px | 44 px |
| 219 | Zudomon | 36 px | 43 px |
| 222 | BlackGatomon | 24 px | 45 px |
| 227 | Apemon | 30 px | 45 px |
| 228 | Baronmon | 37 px | 45 px |
| 234 | Gatomon | 25 px | 45 px |
| 236 | DemiDevimon | 28 px | 36 px |
| 240 | Gesomon | 30 px | 43 px |
| 243 | Starmon | 35 px | 45 px |
| 244 | SuperStarmon | 35 px | 44 px |
| 246 | Infermon | 18 px | 28 px |
| 250 | Shadramon | 34 px | 43 px |
| 293 | Gryphonmon | 29 px | 43 px |
| 303 | KingEtemon | 38 px | 45 px |
| 328 | Snimon | 35 px | 45 px |
| 409 | Kyubimon | 32 px | 44 px |
| 470 | Pabumon | 25 px | 45 px |

## Reproducing the check

Build the everything recipe as described in [developing](../developing.md),
then run:

```sh
python3 tools/status_portraits.py build/NAME --out build/status-audit --enlarge-small --check
python3 -m unittest tools.test_status_portraits
python3 tools/dev/playtest/status_portraits.py build/NAME.cue \
  --exe build/NAME/exe/SLUS_010.32 --audit build/repair-audit/audit.json \
  --out build/status-runtime
```

Keep the repair audit from a `--fix --enlarge-small` pass for the runtime
comparison. The harness loads real models through a fixture evolution, verifies
the built camera, temporarily restores the old camera for the before image,
then captures the built view and its sleeping badge. It requires original
2 MB RAM and does not replace engine routines. Offline contact sheets are
schematic previews; emulator screenshots are the check of actual drawing.

The worktree report records the build, checks, runtime captures and media
session. The software rasterizer approximates fixed-point GTE projection and
lighting; its height figures are diagnostic, not a promise of exact emulator
pixel equality. Real-console testing and other source-disc variants remain
separate checks.
