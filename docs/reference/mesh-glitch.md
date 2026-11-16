# General imported-mesh investigation (2026-11-16)

A common, reproducible contributor is nonplanar quads: libgs culls both GPU
triangles using the first triangle's NCLIP result. Opposite-facing halves can
therefore appear or disappear together as the model animates. The importer
merges triangle pairs with angles up to 25 degrees (sometimes 40); `meshfix.remerge`
also reassembles surviving source-quad halves without checking their angle.
The importer target of 713 primitives encouraged these merges. It is the
largest observed native primitive count, **not** an engine primitive-array bound
(see [MegaGargomon's source review](magnamon-megagargomon.md)).

This is a contributing cause, not a proven explanation of every reported glitch.
The controls falsify an important assumption in the requested detector: neither
coplanarity, depth ties, total bend area, nor triangle crossings reliably ranks
all five reports above natives. Raidenmon and Omnimon pass the native envelope
despite their reported symptoms. Do not interpret this envelope as a validated
visual-defect classifier, or tune species weights until the reports rank first.

## Evidence and controls

The archived device build was extracted with `meshcheck extract`: 369 models,
including every one of the 183 registered imports, 178 native controls (IDs 1–179,
excluding protagonist 0), and seven additional authored/record models.
`imported-models/` contains base delta targets; the archive and the provider's
last output contain the actual shipping meshes and generated binding skeletons.
Two supplied bases, 225 and 239, were stale against the committed delta targets;
current verified copies were used for rebuilding, without changing their pins.

The sibling Omnimon job decoded all 183 registered imports: 8,971 occupied slots
and 351,952 ticks, eight camera directions per tick, without truncation. Its
[measurements](omnimon-mesh-sweep.json) and [investigation](omnimon-mesh.md) are
retained. That job supplied a patch because its Git metadata was read-only; no
sibling commit existed to rebase onto. Its proposed full 95-quad Omnimon split
increased resident bytes from 80,780 to 82,680. This branch keeps the original
base delta and uses the shared budget-neutral final pass instead.

Before/after base-to-final bent-face risk (smaller half's area times
`1-cos(dihedral angle)`, divided by idle height squared):

| Species | Base risk | Final risk | Base/final maximum bend |
| --- | ---: | ---: | --- |
| 335 MegaGargomon | .008673 | .010341 | 83.54° / 85.10° |
| 336 Raidenmon | .001834 | .001834 | 40.17° / 40.17° |
| 406 MaloMyotismon | .026256 | .026256 | 71.29° / 71.29° |
| 409 Kyubimon | .049388 | .045751 | 73.08° / 72.38° |
| 461 Omnimon | .000619 | .000619 | 26.16° / 26.16° |

The defect already exists before current field/native overlays. Omnimon's
historical importer had bends up to 18.61°; chibi fitting increased that to
26.16°, before the recent spring animation edits. Nonuniform scaling can change
a bend's angle but preserves an actually planar face before integer rounding.
The observed 40–85° base bends cannot be attributed solely to final 16-bit
rounding. Bone merging or part penetration remains a separate hypothesis for
species whose actual surfaces intersect; this repair does not move them.

`model.c:2905,2913,2916` calls `GsSortObject4(...,2,...)`. The engine uses a
4096-entry OT; the shift gives depth bins of four units. The diagnostic probes
mean primitive depth at eight azimuths, elevation 30°, averaging the four
integer bin offsets. It measures only front-facing, projected-overlapping
primitive pairs, excludes shared mesh vertices, and tracks order reversals only
when both primitives overlap in both measured poses. This is an orthographic
camera probe, not a perspective/GTE/emulator reproduction. Legitimate occlusion
changes also reverse depth order. Native models have both ties and reversals;
there is no evidence here justifying an OT-size/shift change.

Coplanarity is measured in idle with the existing overlapping-area test (plane
distance <0.003 heights, normal cosine >.998, overlap >.0004 squared heights).
Tiny faces are below one square unit at a 500-unit height. Static zero-area
faces, repeated-index masks, and pose-collapsed faces are reported separately;
repeated-index masks are not automatically called accidental degeneracy.
Penetration uses the existing battle QA's triangle intersections between
non-parent/child pieces. Depth/penetration probes sample three evenly spaced
poses in each of slots 0,2,3,4,33,34,35,36; they are **not** exhaustive collision
or visibility proofs. Use `--samples 0` for every tick in selected slots, or
`--slots` with no numbers for every occupied slot. A 6000-tick guard fails
explicitly rather than silently cutting a clip.

## Shared repair and limits

`mesh_stability.apply` runs after every rig, grounding, care and technique pass
for imported species. It never moves or deletes an oriented surface triangle.
It splits the highest-risk bent quads along their existing GPU diagonal,
retaining per-corner normals, UVs, RGB, material, winding and both back faces.
Each half receives its own NCLIP and depth-sort entry.

The additional TMD bytes are funded only by exact animation compaction,
unused/duplicate final vertex/normal entries, and identical-corner Gouraud
shading represented as flat shading. Distinct normals or colors keep Gouraud
interpolation. Earlier rig/grounding passes retain their original pools and
landmarks. Resident size must not exceed that species' incoming resident size;
the change in the sum of all primitives' packet-format sizes is capped at
1024 bytes per model. This is not a bound on per-frame growth: a newly visible
half can emit a packet where the old quad was entirely culled. Neither model nor packet buffers are
resized. This format-size cap is **not** a crowded-scene packet-safety proof.
Models without a funded repair retain their original bytes; remaining bends are
reported rather than flattened, decimated or hidden.

This changes a common pipeline boundary rather than adding species-specific
mesh edits. Natives do not pass through it. Already pinned alternate-release outputs (the
seven World 3 USA variants) are preserved byte for byte until separately
verified; their existing pins remain valid. This compatibility boundary uses
the existing alternate-provider hashes rather than species-specific rules.
The shared repair is verified here on the reference/main build. The texture, skeleton, bone indices,
root travel, clip timing, events and loop structure remain unchanged. The pass
cannot eliminate genuine part penetration, coplanar decorative layers, or all
PSX pixel/painter artifacts. Budget-limited remaining hazards are intentional
limitations, not accepted visual failures or proof those species look correct.

## Reproduce

```sh
python3 tools/models/meshcheck.py extract BUILD/DIGI.DAT /tmp/mesh-final
python3 tools/models/battle_qa.py mesh-audit /tmp/mesh-final --samples 3 --jobs 4 --json before.json
# Exit 1 means at least one import lies outside the measured native envelope.
python3 tools/models/battle_qa.py mesh-audit AFTER_DIR --thresholds before.json --samples 3 --jobs 4 --json after.json
python3 -m tools.derive.steps.species pin build/mesh-glitch
# After a complete preparation, reuse overlay inputs while replaying final passes:
python3 -m tools.derive.steps.species pin build/mesh-glitch --prepared
```

Height normalization uses only nonzero-area surface triangles, excluding unused
grounding landmarks, so lossless pool compaction cannot change the denominator.
Thresholds are maxima measured from native controls and are reused unchanged
for comparisons. The JSON includes thresholds, all species, per-slot sample
coverage, candidate counts and rankings. Native controls passing an envelope
calibrated from them does not establish sensitivity to reported visual defects.
The full before/after logs and preservation evidence are in
`build/mesh-glitch-evidence/`; the compact checked-in report accompanies this note.
handheld-emulator confirmation and crowded-scene render-packet profiling
remain outstanding.

## Measured results
All 183 canonical pre-repair model/texture pairs match the committed prior pins.
All 183 outputs match the new provider pins. Full preservation checks cover
8,971 slots / 351,952 ticks: identical oriented triangle corner attributes,
decoded poses, root travel, loops and events. All 183 resident/cold storage audits
pass; peak resident is 100,256 / 100,352 bytes. The pass repairs 178 imports,
splitting 4,791 quads, and reduces total resident data by 228,948 bytes. No
species grows; the all-primitive packet-format size delta stays at or below 1,024 bytes.

| Reported species | Split quads | Resident bytes before → after | Discordant face/tick/view triples before → after | Reduction |
| --- | ---: | ---: | ---: | ---: |
| 461 Omnimon | 6 | 80,780 → 80,762 | 56,781 → 44,271 | 22.0% |
| 409 Kyubimon | 6 | 94,110 → 94,094 | 190,526 → 166,250 | 12.7% |
| 406 MaloMyotismon | 57 | 80,752 → 74,402 | 281,182 → 137,305 | 51.2% |
| 336 Raidenmon | 57 | 73,282 → 72,622 | 46,708 → 0 | 100.0% |
| 335 MegaGargomon | 101 | 96,078 → 95,686 | 168,338 → 28,622 | 83.0% |

These are projected face-level candidates, including occluded faces, not counts
of visible screen glitches. All top ten improve on this full-tick measure
(reductions 12.7–96.1%). Raidenmon has no remaining bent-quad culling
disagreement in the measured views. The native envelope passes MegaGargomon
after repair; Kyubimon and MaloMyotismon still fail. Raidenmon and Omnimon pass
both before and after, so the requested sensitivity to all five reports remains
unmet. Actual part crossings are retained: splitting a primitive does not move
its triangles.

| Rank | Species | Severity / native maximum |
| ---: | --- | ---: |
| 1 | 407 Armageddemon | 40.37 |
| 2 | 405 Cannondramon | 24.05 |
| 3 | 408 Suijinmon | 22.30 |
| 4 | 326 WarGrowlmon | 16.71 |
| 5 | 409 Kyubimon | 15.05 |
| 6 | 403 Beelzemon | 14.93 |
| 7 | 402 NeoCrimson | 9.41 |
| 8 | 406 MaloMyotismon | 8.64 |
| 9 | 431 Kurisarimon | 6.70 |
| 10 | 472 YukimiBotamon | 6.56 |
| 11 | 432 Bastemon | 6.07 |
| 12 | 314 SkullSatamon | 5.99 |
| 13 | 323 Lynxmon | 5.86 |
| 14 | 477 Yokomon | 5.80 |
| 15 | 303 KingEtemon | 4.58 |

Severity is the maximum ratio to a native metric limit. It is an investigation
priority, not a validated ranking of what a player sees. All 178 native controls
pass; 36 reference imports remain outside the envelope after repair:

407 Armageddemon, 405 Cannondramon, 326 WarGrowlmon, 409 Kyubimon, 403 Beelzemon, 402 NeoCrimson, 406 MaloMyotismon, 432 Bastemon, 314 SkullSatamon, 323 Lynxmon, 477 Yokomon, 303 KingEtemon, 318 Gallantmon, 306 GrapLeomon, 196 Halsemon, 312 Creepymon, 193 Digmon, 223 LadyDevimon, 205 MegaKabuterimon, 199 Paildramon, 215 Magnadramon, 471 Pichimon, 315 Taomon, 311 Arukenimon, 295 Vilemon, 274 Blossomon, 307 BlackKingNumemon, 473 Nyokimon, 283 Syakomon, 236 DemiDevimon, 218 Ikkakumon, 275 Scorpiomon, 238 Dolphmon, 183 Wormmon, 270 PrinceMamemon, 220 Vikemon.

The [complete compact report](mesh-glitch-audit.json) records every model,
threshold, repair budget, input/output hash and available full-tick comparison.
Validation: 97 tests passed, 8 private-fixture tests skipped; subsequent detector
normalization/compatibility regressions also pass (12 tests). Fresh
`edit.py check --species-pins` passes all five reported species. No on-device
visual or crowded-scene packet confirmation has been obtained.
