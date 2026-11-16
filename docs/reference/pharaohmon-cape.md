# Pharaohmon cape repair

Species 319, branch `pharaohmon-cape`, 2026-11-16. The missing-looking cape section
was a proportion-bake tear, not dropped polygons. The upper panel was narrowed
across x while the lower panel retained its width. Their four corresponding
join vertices separated by **84 units** in idle; after repair the gap is **0**.

The requested read-only main file,
`../dev/build/device/imported-models/319.MMD`, is the pre-overlay model
(SHA-256 `c7aa6ffba8b703e760eb61b5e0195979301a7d63e34e78a4afadcb4a62784c20`).
The species record actually sends
`../dev/build/device/imported-species-models/319-technique-timing.MMD` to the game
(SHA-256 `471d7d64f02251efe1e8983cfaead9a1bca2d154c2749a1190449e076d2de16c`).
Both were read only. Measuring the importer alone would miss the chibi tear and
the generated tired-walk/run collisions.

The complete source is DW3 `M358PHAR.BIN`, SHA-256
`7fb1cb357ed3b3cda17adfd4b360ad8bc04d8e7212d990681a84aa6c869bc0fd`.
`audit_reduction.py` loaded it with face dropping and mesh simplification disabled.
All 21 source objects matched, with 100% source-area coverage and no unassigned
final triangles. Both cape panels retain all 12 triangles each, no new boundaries,
no uncovered area, and no missing UV/opaque-to-transparent area. The complete
model retains 682 vertex entries and 709 primitives before and after.

The cause is `chibi.bone_scales`: bone 6 was `cloth`, bone 7 was `tail`.
The inferred principal length axis on the broad upper panel ran across its
width. `leg_axial=0.642` and the extra `fit=0.605` therefore narrowed only the
upper panel, while the lower panel's different axis shortened its length.
The species recipe now labels both panels as cloth and supplies their actual
length axes `[0,143,29]` and `[0,260,41]`. It removes the extra fit factors;
leg-length scaling applies along those axes and carries the child pivot with
its parent. This restores the original connected surface without adding faces,
changing UVs, or rebinding unrelated objects.

Slots 0–4 now turn the cape behind the legs in world space after gait composition.
The upper panel follows a small periodic motion; the hem receives that wave
0.12 cycles later and at a different pitch. The regression checks verify that
the angle between the panels changes, that every field loop closes, and that
no cape pitch jumps more than four degrees per tick. Idle and walk retain all
non-cape channels; the existing planted feet, root speeds, and two-cycle tired
walk/run remain. No runtime behavior was added.

| Slot | Decoded frames, including closing frame | Foot-crossing frames before → after | Peak foot penetration before → after | Minimum rear clearance before → after |
|---:|---:|---:|---:|---:|
| 0 | 67 | 0 → 0 | 0 → 0 | 23.87 → 66.16 |
| 1 | 21 | 0 → 0 | 0 → 0 | 41.53 → 25.38 |
| 2 | 26 | 12 → 0 | 40.11 → 0 | −107.40 → 29.55 |
| 3 | 57 | 56 → 0 | 53.75 → 0 | −131.28 → 19.22 |
| 4 | 25 | 25 → 0 | 57.20 → 0 | −137.68 → 20.63 |

All values are game-model units. Feet are bones 14,15,20,21; complete legs are
12–15 and 18–21; cape is 6–7. The shared `field_animations.meshclash.crossing`
engine measures actual triangle/surface crossings and the depth through the
cape triangle plane. This is also the crossing engine used by the sibling
`mesh_glitch`/`battle_qa` detector, which was read and reused directly for the
sweep's geometry diagnostics. No duplicate intersection detector was added.

There were **93/196 foot-crossing frames → 0/196**, and **101/196 whole-leg
crossing frames → 0/196**. Maximum whole-leg penetration was **62.37 → 0**.
`cloth_audit.rear_clearance` additionally bounds the entire width: at every
vertex height in the two meshes' common height interval it subtracts the
rearmost leg z from the foremost cape z. Each section is linear between these
heights, so positive clearance guarantees separation, even between samples
within a triangle. The minimum bound improves **−137.68 → +19.22**. Negative
clearance alone is an overlap candidate, not a penetration depth. This is a
per-frame geometric guarantee; it does not claim continuous-time collision
simulation between engine ticks.

The pre-overlay main model also has the reported problem: its walk has 19/26
whole-leg crossing frames, maximum penetration 77.03, and rear clearance −134.63.
The generated main final model is the appropriate before baseline in the table.

Final provider resident storage is **84,312 → 85,974 / 100,352 bytes**; all cold
reads also fit. Full file size is 109,006 → 110,646 bytes. The importer delta
remains byte-identical. Changing the baked cape length also changes its child
translations in attack clips. `edit.py repin --technique-inputs` regenerates the
Megaton Punch input pin after validating the complete provider and timing/storage
checks; `edit.py put --force` generates the final provider pin. No pin was edited
by hand.

Reproduce the measurements from this worktree:

```sh
python3 tools/models/edit.py --from ../dev/build/device get 319
python3 tools/models/audit_reduction.py --games ../dev/build/device/source-games \
  --out build/cape-source-final --ids 319 --jobs 1
python3 -m tools.models.cloth_audit --species 319 \
  --model build/cape-source-final/319/shipped.MMD --cape 6 7 \
  --feet 14 15 20 21 --legs 12 13 14 15 18 19 20 21 \
  --out build/cape-frames-final.json
python3 tools/models/edit.py --from ../dev/build/device check 319 --species-pins
python3 tools/models/chibi_proportions.py check 319
PYTHONWARNINGS=ignore python3 -m unittest tools.test_pharaohmon_gait \
  tools.test_chibi_proportions tools.test_motionstorage \
  tools.test_imported_model_edit tools.test_technique_timing
```

Private source-derived models/images remain under `build/`. Per-frame evidence
is `build/cape-frames-before.json` and `build/cape-frames-final.json`; source
comparison is `build/cape-source-final/319/result.json` and its six-view image.
The suite passed 48 tests (four unrelated asset-dependent cases skipped), plus
the added cape-lag regression. The explicit species-319 proportion and provider
checks passed with actual assets.

## Other imported cloth: audit only

The sweep reads main's final species records, uses their actual generated rigs,
and checks every decoded frame in slots 0–4. It includes labelled cloth and its
tail-chain descendants, plus anatomy from the individual cape/skirt recipes.
Source-surface comparisons use the existing reduction audit. The table reports
intersection candidates, including hidden intersections and designed attachments;
it does not assert that every crossing is visible from the game camera.
No other species is fixed by this branch.

| Species | Foot-crossing frames / frames tested | Peak foot depth | Source surface coverage/status |
|---|---:|---:|---|
| 206 MagnaAngemon | 0/85 | 0.00 | 63.0%, partial |
| 207 Seraphimon | 24/124 | 57.54 | 100.0%, complete |
| 209 Lillymon | 0/161 | 0.00 | 100.0%, complete |
| 214 Shakkoumon | 49/195 | 23.20 | 100.0%, complete |
| 223 LadyDevimon | 0/185 | 0.00 | 100.0%, complete |
| 225 Shurimon | 0/357 | 0.00 | 100.0%, complete |
| 228 Baronmon | 38/238 | 24.41 | 100.0%, complete |
| 229 Phantomon | no feet | 0.00 | 100.0%, complete |
| 230 Rosemon | 0/321 | 0.00 | 100.0%, complete |
| 241 Wizardmon | 0/85 | 0.00 | 100.0%, complete |
| 242 Sorcermon | 0/85 | 0.00 | 100.0%, complete |
| 245 Piedmon | 0/285 | 0.00 | 100.0%, complete |
| 255 Valkyrimon | 12/218 | 25.99 | 100.0%, complete |
| 277 SkullMeramon | 0/92 | 0.00 | 100.0%, complete |
| 288 Boltmon | 0/97 | 0.00 | 100.0%, complete |
| 297 Marsmon | 0/233 | 0.00 | 100.0%, complete |
| 300 SlashAngemon | 16/143 | 24.40 | 100.0%, complete |
| 308 Dinohyumon | 18/237 | 9.71 | 100.0%, complete |
| 312 Creepymon | 155/155 | 38.39 | 100.0%, complete |
| 314 SkullSatamon | 19/103 | 15.53 | 100.0%, partial |
| 315 Taomon | 29/143 | 25.34 | 100.0%, complete |
| 316 Sakuyamon | unverified anatomy | 0.00 | 100.0%, complete |
| 318 Gallantmon | 0/217 | 0.00 | 100.0%, complete |
| 321 Knightmon | 26/164 | 32.18 | 100.0%, complete |
| 322 Kyukimon | 0/203 | 0.00 | 100.0%, complete |
| 325 Musyamon | 19/149 | 28.12 | 100.0%, complete |
| 331 Vemmon | 0/108 | 0.00 | 100.0%, complete |
| 351 Kotemon | 129/143 | 30.15 | 100.0%, complete |
| 373 WarGreymon | 0/217 | 0.00 | 100.0%, complete |
| 400 Apocalymon | no feet | 0.00 | 100.0%, partial |
| 402 NeoCrimson | 73/217 | 59.03 | 72.8%, partial |
| 404 BlackWarGreymon | 0/217 | 0.00 | 100.0%, complete |
| 406 MaloMyotismon | 0/161 | 0.00 | 88.5%, partial |
| 430 Zanbamon | 0/112 | 0.00 | 98.6%, partial |
| 461 Omnimon | 0/214 | 0.00 | 100.0%, complete |

Foot/cloth crossing candidates: 207 Seraphimon, 214 Shakkoumon, 228 Baronmon, 255 Valkyrimon, 300 SlashAngemon, 308 Dinohyumon, 312 Creepymon, 314 SkullSatamon, 315 Taomon, 321 Knightmon, 325 Musyamon, 351 Kotemon, 402 NeoCrimson.

The complete matched cloth surfaces show no new holes. MaloMyotismon
(406) is a missing-cloth candidate: matched source object 25 (lower cloth/tail
chain) has 19.9% uncovered area, with 14 → 10 triangles; source object 24
is unmatched. Its whole-source coverage is only 88.5%, so this is not a
complete reconstruction or a confirmed cause. Other partial comparisons are
206 MagnaAngemon (63.0%), 314 SkullSatamon (100% source-area fit but 64
unassigned final triangles and reduced hands), 400 Apocalymon (100% source-area
fit but unassigned triangles; its three cape objects themselves have zero
uncovered area), 402 NeoCrimson (72.8%), and 430 Zanbamon (98.6%). These remain
unverified where correspondence failed; they are not clean bills of health.

A same-rig/same-pool join check also compares cloth-to-cloth and
cloth-to-parent vertices that meet within 2.5 units in the pre-overlay model.
No other measured compatible join grows by more than eight units in final idle.
Native replacements require source-surface correspondence instead; this join
check cannot validate their reassigned pools. Sakuyamon has no separate cloth
anatomy and remains unverified for foot/cloth intersections. Phantomon and
Apocalymon have no feet. Some swept groups are armour, feathers or loincloths;
whole-leg/cloth contact at their designed attachments is not automatically a
visible defect. Full per-frame sweep and detector diagnostics are in
`build/cloth-sweep.json`; source details are under `build/cloth-source-sweep/`
and `build/cloth-source-extra/`. No source game assets are committed.
