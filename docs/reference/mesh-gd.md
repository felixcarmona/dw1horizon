# Imports 307, 314, 323 and 326

All four pass the unchanged native mesh-stability envelope after these edits.
All four still have geometric part-intersection review candidates. Envelope
acceptance does not establish that their reported in-game glitches are resolved.
The [measurements](mesh-gd/audit.json) include both verdicts, every sampled clip,
full-clip maxima, residual pairs, geometry diagnostics and preservation checks.

BlackKingNumemon's crown and Lynxmon's flame cards have opposing faces whose
quad packets used different GPU diagonals. Aligning eight crown backs and 95
card backs to their corresponding fronts preserves both windings, boundary,
corner positions, normals, UVs, colors, materials and packet sizes. It changes
the diagonal's interpolation on the back. On the slightly warped crown sheets,
it also makes the two sides follow the same surface. No back faces are deleted.
Lynxmon's cards are planar: their coplanar-area reduction largely reflects the
legacy detector's exclusion of matching triangle index sets, rather than the
removal of a visible overlap. The old count cannot itself prove z-fighting.
Both models already had zero co-facing idle overlaps before this round.

SkullSatamon's objects 2/3/9 and WarGrowlmon's objects 0/1/5/6/7/10/15/19/21
receive bounded fits of their retained bent panels. Integer vertex adjustments
reduce disagreement between quad-half normals. Each vertex stays within four
local units and the original object's bounds; shared vertices move together.
Every triangle retains 85–115% of its original area, with normal rotation below
15.2 degrees. Artist shading normals remain. Skeletons, mount transforms,
textures and animation programs are exact. No faces are dropped or new packets
added. Authored old/new coordinates are guarded against the reviewed input TMD.
These fits address panel curvature without creating cracks at shared vertices.

An initial WarGrowlmon foot fit was rejected: bone pair 19/20's maximum contact
grew from 43.363 to 54.559 units in slot 21 frame 10. The final fit leaves that
foot (object 17) unchanged. No rejected coordinates enter the authored recipe.

| Species | Severity / native max | Bent risk | Coplanar area (heights²) | Sample crossing maximum |
| --- | ---: | ---: | ---: | ---: |
| 307 BlackKingNumemon | 1.497 → 0.256 | 0.000152 → 0.000152 | 0.53724 → 0.00000 | 142 → 141 |
| 314 SkullSatamon | 1.723 → 0.889 | 0.005237 → 0.002703 | 0.01932 → 0.13979 | 146 → 130 |
| 323 Lynxmon | 5.715 → 0.301 | 0.000000 → 0.000000 | 2.05058 → 0.00790 | 183 → 179 |
| 326 WarGrowlmon | 3.233 → 0.849 | 0.009829 → 0.002579 | 0.00941 → 0.00999 | 239 → 234 |

The detector uses three poses in slots 0/2/3/4/33/34/35/36, unchanged thresholds
from `mesh-glitch-audit.json`, and eight elevated camera directions. Degenerate,
collapsed-index and tiny-face counts are zero throughout; exact opaque duplicate
packet searches and co-facing idle overlap counts are also zero throughout.
Remaining bent quads are reported, not called planar or invisible.

| Species | Slots / ticks | Full-model maximum crossing pairs | Maximum symmetric depth (units) |
| --- | ---: | ---: | ---: |
| 307 BlackKingNumemon | 52 / 2,580 | 946 → 946 | 88.787 → 88.780 |
| 314 SkullSatamon | 50 / 1,473 | 858 → 849 | 53.437 → 51.169 |
| 323 Lynxmon | 49 / 1,617 | 1259 → 1253 | 116.822 → 113.883 |
| 326 WarGrowlmon | 50 / 2,126 | 907 → 892 | 89.787 → 89.378 |

The compressed `ID-before.csv.gz` and `ID-after.csv.gz` files in
[the evidence directory](mesh-gd/) contain every crossing's slot, frame, object,
bones, adjacency, triangle-pair count and symmetric depth, across all 201 occupied
slots / 7,796 decoded ticks. Counts include adjacent pieces and hidden contacts;
these exhaustive maxima use different coverage from the sampled envelope.
No new full-clip bone pair crosses after the final fits. Some existing contacts
still deepen (maximum per-pair increases: 0 / 0.774 / 0 / 5.441 units); the JSON records those increases instead of claiming a universal
collision improvement. No easing or other motion change was needed for the
accepted geometry edits: decoded poses, translations, root travel, timing,
events, loops and slot aliases remain exact for every tick.

The retained crossing certificates cover BlackKingNumemon bones 1/17 at slot
13 frame 15 and Lynxmon bones 15/22 at slot 44 frame 7. Independent corner
verification certifies strict crossings throughout a relative translation cube
of ±8 world units (each part may independently move ±4 on each world axis).
These are bounded witnesses, not impossibility proofs for rotations, reshaping
or motion redesign. Of 250 finite local rotation trials, respectively zero and
23 clear these pairs in that single pose; that does not prove full-clip clearance.
Certificates and triangle geometry are in `mesh-gd/crossing-certificates.json.gz`.

| Species | Discordant face/tick/views | Changed pixels | OT-bin-phase pixels |
| --- | ---: | ---: | ---: |
| 307 BlackKingNumemon | 20,175 → 20,175 | 15,303 | 1,478 → 1,478 |
| 314 SkullSatamon | 194,956 → 121,411 | 63,526 | 1,624 → 1,608 |
| 323 Lynxmon | 0 → 0 | 141,588 | 2,049 → 2,055 |
| 326 WarGrowlmon | 247,525 → 103,899 | 49,299 | 1,203 → 1,283 |

Each species has seven matched poses × eight elevated azimuths: idle, walk,
condition walk, run and its three deepest pre-edit pair poses. The PSX-rule
renderer uses first-triangle quad culling, the GPU diagonal, four-unit OT bins,
reverse insertion for ties, affine textures, color-zero discard and PSX blend
rules. Changed pixels measure edit scope; bin-phase pixels measure sensitivity
to a two-unit depth-bin phase change. Neither is a visible-glitch count.
Lynxmon and WarGrowlmon retain slightly higher phase sensitivity. Paired sheets
are under `build/renders/`; all per-view numbers are in `mesh-gd/*-renders.json`.
These are orthographic renders, without GTE perspective, runtime camera depth,
on-device confirmation or crowded-scene packet profiling.

Resident bytes are unchanged: 74,440 / 81,436 / 78,652 / 95,332, respectively.
Cold streams round-trip with identical animations. All-primitives packet-format
totals are unchanged at 29,332 / 35,672 / 24,432 / 36,072 bytes. The global peak
therefore stays 100,256 / 100,352 bytes: all unrelated provider pins, including
the measured peak holders, remain unchanged. Only these four canonical model
pins change, through the scoped repository pin tool; texture, native-record,
alternate-release and delta pins remain exact. Fresh source/delta/provider
checks pass all four. Related suite: 94 tests, 93 passed, one private-fixture
skip. Work remains uncommitted.

Reproduce on final atlas-stamped model/texture folders with `index.json`:

```sh
python3 -m tools.models.mesh_gd_review BEFORE AFTER --out build/review-gd --crossings --renders
python3 -m tools.derive.steps.species pin BUILD --prepared 307 314 323 326
python3 -m unittest tools.test_mesh_gd tools.test_mesh_round4 tools.test_mesh_cleanup tools.test_psx_blend tools.test_mesh_stability tools.test_meshcheck tools.test_battle_qa tools.test_imported_model_edit tools.test_species_pins tools.test_motionstorage
```
