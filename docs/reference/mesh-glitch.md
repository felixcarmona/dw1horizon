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

## Remaining-mesh follow-up

The table above ranks pre-repair severity. The actual ten worst reference
outputs after PR 511 are 407, 409, 405, 323, 314, 196, 303, 326, 205 and 432.
Suijinmon, Kurisarimon and YukimiBotamon already pass. A fresh archive audit of
369 models reproduces 36 failing imports and zero failing native controls using
the archived, unchanged thresholds and three poses per selected slot.

Five targeted repairs follow final fitting and stability splitting in
mesh_cleanup.py. Reviewed TMD hashes are recorded by the repository tool,
python3 -m tools.models.mesh_cleanup review BEFORE_DIR; provider hashes are
written only by python3 -m tools.derive.steps.species pin.

* Armageddemon: slot 4's rear left foot crosses the middle left foot. Opening
  rear hip 24's local yaw by 12 degrees keeps the original swing and clears
  bones 20/26 across every decoded run tick: maximum crossing pairs 20 → 0,
  penetration 45.78 → 0 units. Whole-model sampled maximum falls 24 → 6.
  The foot's maximum floor excursion changes from 0.18 to 4.52 units; the clip
  passes the existing floor, motion, seam and collision QA. Fidelity records the
  intentional angular change as documented polish. A collinear mouth quad,
  with no surface in either half, is removed: true degenerate triangles 2 → 0.
* Cannondramon: both front feet have toe detail only one unit inside the sole.
  Insetting their existing detail ring another four units separates all three
  co-facing coplanar candidates while retaining ground-contact vertices.
* Lynxmon: the pelvis and two tail sections put their longitudinal flame cards
  on the same plane. Offsetting the latter cards by 4/8 local X units, moving
  both windings together, removes nine co-facing overlaps. Opposite windings of
  intentional flame cards remain; the legacy coplanar metric still fails.
* WarGrowlmon: two differently textured triangles occupy precisely the same
  armour surface and vertex IDs. Only the decal receives independent corners,
  offset approximately four units along its normal: co-facing pairs 1 → 0.
* Bastemon: four opaque packets duplicate their oriented geometry, material,
  normals and UVs, including cyclic corner permutations. Dropping them removes
  eight co-facing triangle pairs. Opposite faces and blended packets survive.

The new mesh-audit --details reports co-facing overlaps even when vertex IDs
or UVs match. The legacy metric excluded these cases, including the armour
surface and duplicated packets above. It still supplies the original envelope;
new pair diagnostics do not alter thresholds. Co-facing geometry alone is not
proof of visible z-fighting: transparent layers, joint contact and occlusion
still require inspection. mesh_review also attributes sampled crossings to
bone pairs, slot and tick, including adjacent bones omitted by legacy QA.

| Current priority | Residual evidence after this follow-up |
| --- | --- |
| 407 Armageddemon | Bent risk 21.76× native limit; repaired run pair clears; other sampled crossings remain (maximum 6). |
| 409 Kyubimon | Bent risk 11.36×; maximum 1,327 crossings remains. Tail/hip bones 15/19 reach 50.31 units through each other in slot 34 tick 0; overlapping tail tiers also remain. |
| 405 Cannondramon | Bent risk 10.88×; toe overlap clears, but bone pair 13/18 still crosses to 42.00 units in slot 3 tick 0. |
| 323 Lynxmon | Legacy coplanar area 2.10244 → 2.05058 heights² (5.72× limit), dominated by retained opposite flame faces; co-facing pairs 9 → 0. |
| 314 SkullSatamon | Bent risk 3.56×; pair 4/6 reaches 34.22 units in slot 36 tick 0. |
| 196 Halsemon | Bent risk 3.25×; pair 9/12 reaches 46.40 units in slot 2 tick 8. |
| 303 KingEtemon | Bent risk 3.24×; pair 14/21 reaches 30.19 units in slot 2 tick 8. |
| 326 WarGrowlmon | Bent risk 3.23×; decal clears, but body/arm intersections remain. Sampled maximum 238 → 239: surface separation is not an overall collision repair. |
| 205 MegaKabuterimon | Bent risk 2.89×; pair 3/11 reaches 85.19 units in slot 33 tick 0. |
| 432 Bastemon | Bent risk 2.42×; duplicate surfaces clear, but pair 12/14 reaches 37.48 units in slot 36 tick 0. |

These residual crossings are located geometric candidates, not all confirmed
visible penetrations. Simple rotations tested on Kyubimon's tail reduced some
pairs without clearing the fan and did not establish a safe natural-motion
repair; they were not shipped. Remaining rig and clip work is unfinished.
The additional reported controls were inspected too: Raidenmon and MegaGargomon
have no co-facing idle pairs but retain part crossings; MaloMyotismon has four
co-facing pairs between neighbouring parts, and Omnimon has six on the head.
Omnimon's first four candidate layers sample entirely transparent texels in
the supplied atlas bounding boxes, demonstrating why these counts alone cannot
establish the reported visible fault. Neither model is declared visually fixed.

Offline evidence uses the corrected psx_blend renderer: first-triangle culling
for an entire quad, four distinct corners for quad mean depth, four-unit depth
bins, reverse insertion within tied bins, affine textures, colour-zero discard,
and PSX blend rules. The original renderer culled halves independently and
sorted unquantised depths. Matched sheets cover eight elevated azimuths in idle
and a sampled deep-crossing pose for all ten plus the four additional reports.
They are orthographic, neutral-lighting evidence, without GTE perspective,
integer raster precision, runtime camera depth or device confirmation.

The [follow-up measurements](mesh-remaining-audit.json) retain before/after
metrics, pair locations, output hashes and preservation results.
All occupied clips of the five changed models retain timing, events, loops,
scale, translations and root travel; only Armageddemon slot 4 changes rotation.
Packet-format totals stay equal or decrease. Peak resident stays
100,256 → 100,256 / 100,352 bytes. WarGrowlmon uses 24 bytes of its earlier
504-byte saving; its final 95,332 bytes remain below its incoming 95,812.
The native envelope remains **36 → 36** failing imports:

183 Wormmon, 193 Digmon, 196 Halsemon, 199 Paildramon, 205 MegaKabuterimon,
215 Magnadramon, 218 Ikkakumon, 220 Vikemon, 223 LadyDevimon,
236 DemiDevimon, 238 Dolphmon, 270 PrinceMamemon, 274 Blossomon,
275 Scorpiomon, 283 Syakomon, 295 Vilemon, 303 KingEtemon,
306 GrapLeomon, 307 BlackKingNumemon, 311 Arukenimon, 312 Creepymon,
314 SkullSatamon, 315 Taomon, 318 Gallantmon, 323 Lynxmon,
326 WarGrowlmon, 402 NeoCrimson, 403 Beelzemon, 405 Cannondramon,
406 MaloMyotismon, 407 Armageddemon, 409 Kyubimon, 432 Bastemon,
471 Pichimon, 473 Nyokimon, 477 Yokomon.

Reproduce evidence from extracted before/after directories:

    python3 tools/models/battle_qa.py mesh-audit BEFORE --thresholds docs/reference/mesh-glitch-audit.json --samples 3 --jobs 4 --json before.json
    python3 tools/models/battle_qa.py mesh-audit AFTER --thresholds before.json --samples 3 --jobs 4 --details --json after.json
    python3 -m tools.models.mesh_review BEFORE AFTER 407 409 405 323 314 196 303 326 205 432 406 336 335 461 --out build/mesh-review
    python3 -m unittest tools.test_mesh_cleanup tools.test_psx_blend tools.test_mesh_stability tools.test_meshcheck tools.test_battle_qa tools.test_imported_model_edit

Validation: 67 tests, one private-fixture test skipped; Armageddemon run QA passes.
Raw evidence and matched images are under build/mesh/. This follow-up repairs
specific causes in five models; it does not finish the remaining ten-model
motion/mesh work or prove the 36 residual imports visually acceptable.


## Round 3: located part candidates and fixed-heap repairs

The native envelope alone flagged two of the five reported models in the
current archive: 406 and 409. The revised detector also locates deep crossings
between different bones, including adjacent pieces. A pair needs review when
its penetration exceeds both eight world units (two OT bins) and 2% of the
drawn pose height. Both directions of penetration are measured so bone numbering
cannot hide a candidate. Each record includes bones, slot, tick, depth and
adjacency. Sampling follows `--samples` and `--slots`, including exhaustive
`--samples 0 --slots`; it does not silently imply full-clip coverage.

`flags` now includes `part_interpenetration`. A model inside the native envelope
with such candidates receives `verdict: review`, while `envelope_verdict`
retains its comparable pass/fail result. Failures and errors exit nonzero;
`--strict-parts` additionally makes review candidates exit nonzero.
All five reported models are flagged before repair. This policy also exposes
native joint contacts and hidden or transparent surfaces: 172 of 178 native
controls also have part-review candidates. This broad probe provides locations,
not a selective visual-defect classifier or an acceptance threshold. That part
of the requested detector validation remains unmet. The existing OT ties and order-reversal probes
remain available alongside these located crossings. Triangle crossing depth is
vectorized, with a scalar-equivalence and operand-reversal regression test.

The earlier per-species no-growth rule is superseded by a fixed ceiling of
100,256 resident bytes, below the existing 100,352-byte allocation. This uses
headroom already present in smaller models; it does not resize any heap buffer.
Headroom is restricted to the 39 reviewed IDs: the original 36 failures and the
three additional reported controls. The repository tool records this scope in
`content/models/imports/mesh-headroom.json`. Unrelated imports retain their
previous provider pins. The 1,024-byte all-primitives packet-format growth cap remains relative to the
incoming pre-stability mesh, rather than restarting that allowance on a second
pass. Quads split by the shared pass increase from 4,817 to 5,568. Alternate
release outputs retain their existing pins and bypass both final repair passes
until independently reviewed. Reviewed TMD hashes and provider hashes were
written with the repository review and pin tools.

The targeted edits retain the texture and material state, skeleton, root motion,
clip timing, events and loops:

* Vilemon: replace two quads whose second GPU half is exactly collinear with
  their intact first triangle. This removes two zero-area faces and the fourth
  corner's incorrect contribution to sorting depth without removing a surface.
* Kyubimon: move the complete tail fan 60 local units rearward and 20 upward
  through its socket joint, extending and bending the existing root stalk to
  retain the connection. Every animation retains its original momentum; only
  initial translations and absolute assignments receive the constant offset.
* MaloMyotismon: advance both cannon caps eight local negative-Z units, reducing the lip
  cutting through each housing. Their independent motion and normals remain.
* Raidenmon: fit the two wide shoulder plates to 60% of their local width about
  their existing mounts, clearing the left calf/plate pair throughout all clips.
* MegaGargomon: fit the shoulder shells uniformly to 70% about their mounts and
  the calf shells radially to 90%, retaining joints, hands and gun origins.
* Omnimon: place all six animated face-mask triangles on independent corners
  six local Z units in front of the head. Retain transparent mask pixels for
  facial animation. Taper the distal calf rings into the boots and transform
  their normals with the deformation, retaining knee and ankle positions.

Full-clip targeted measurements cover 254 occupied slots / 8,984 ticks. The
following depths use the original directed limb-through-plane definition for
before/after comparison; the new review probe measures both directions.

| Model / pair | Deepest crossing before → after (units) |
| --- | ---: |
| 409 tail / thigh, bones 15/19 | 56.16 → 44.44 |
| 406 left cannon housing / cap, 2/3 | 36.17 → 27.80 |
| 406 right cannon housing / cap, 10/11 | 36.17 → 27.92 |
| 336 forearm / shoulder plate, 3/23 | 161.17 → 75.06 |
| 336 left calf / shoulder plate, 21/23 | 64.54 → 0 |
| 335 shoulder shell / forearm, 23/25 | 70.01 → 47.20 |
| 461 left calf / toe armour, 16/18 | 47.29 → 26.32 |
| 461 right calf / toe armour, 20/22 | 48.67 → 8.46 |

Omnimon's co-facing idle face pairs fall 6 → 0. All five still retain full-clip
crossings, including poses outside the default eight sampled slots. These are
partial repairs of located causes, not a declaration that the five models are
visually resolved. Matched orthographic sheets retain the renderer limitations
above. Runtime visual confirmation and crowded-scene packet profiling remain
unperformed; the packet-format cap alone does not prove scene safety.

All 183 canonical provider pairs match their pins. Their final atlas-stamped
outputs pass resident/cold-read storage checks; texture pins, native-record pins and alternate-release pins are
unchanged. Peak resident use stays 100,256 → 100,256 bytes. Full animation
comparison covers 8,971 slots / 351,943 ticks with exact decoded poses, root
travel, loop and event information, except for the documented constant tail
translation. Fresh source-to-provider checks verify all five reported models.
The related suite runs 78 tests: 77 pass and one private-fixture test is skipped.

The [round-three measurements](mesh-round-3-audit.json) record both envelope
results and part-review candidates, full-clip targeted evidence, hashes and
resident sizes. Raw tool output, preservation checks and matched atlas-stamped images are in
`build/` in the worktree. Atlas stamping applies the same flat-sprite UV and
texture transformation as archive assembly. The 144 unscoped imports retain
their original provider pins and exact final TMD bytes, so their baseline
measurements are reused. The 39 scoped outputs receive fresh final geometry
measurements; their clip probes retain the measured matching geometry/poses.


The unchanged native envelope falls **36 → 23** failing imports, with **zero new
failures** and **zero native envelope failures**. Thirteen of the original 36 now
pass that envelope: 199 Paildramon, 205 MegaKabuterimon, 215 Magnadramon,
223 LadyDevimon, 295 Vilemon, 306 GrapLeomon, 311 Arukenimon, 312 Creepymon,
315 Taomon, 318 Gallantmon, 402 NeoCrimson, 403 Beelzemon and 432 Bastemon.
Passing the envelope does not clear their independent part-review candidates.
Vilemon retains all 874 oriented nonzero triangles and their corner attributes.

The remaining 23 of the original 36 are:

183 Wormmon, 193 Digmon, 196 Halsemon, 218 Ikkakumon, 220 Vikemon,
236 DemiDevimon, 238 Dolphmon, 270 PrinceMamemon, 274 Blossomon,
275 Scorpiomon, 283 Syakomon, 303 KingEtemon, 307 BlackKingNumemon,
314 SkullSatamon, 323 Lynxmon, 326 WarGrowlmon, 405 Cannondramon,
406 MaloMyotismon, 407 Armageddemon, 409 Kyubimon, 471 Pichimon,
473 Nyokimon and 477 Yokomon.

To scope additional headroom to a baseline audit and the reported controls:

    python3 -m tools.models.mesh_cleanup review-headroom BEFORE.json --include 335 336 461
    python3 -m tools.derive.steps.species pin BUILD --prepared

TMD review guards use pre-cleanup provider meshes, before atlas stamping.
Run final comparisons on models after `species.flat_texture`/archive assembly,
not provider MMDs paired with an already stamped archive TIM. The report records
both the unchanged envelope result and the broad part-review flag. Runtime
visibility and a selective detector for the reported symptoms remain unfinished.

## Round 4: two cause repairs and bounded residual floors

Only 409, 406, 336, 335 and 461 were investigated, in that order. None is
certified visually clean. Exhaustive before/after crossing ledgers cover all
254 occupied slots / 8,984 decoded ticks, including adjacent pieces and both
penetration directions. The [round-four report](mesh-round-4/audit.json) links
compressed CSV ledgers containing every crossing's slot, motion category,
zero-based frame, bones, objects, reviewed part names, triangle-pair count and
depth. Unnamed source objects retain their exact object number. Slots 2/3 are
walk/condition walk, 4 is run, and 33–63 are battle slots. Other occupied slots
remain explicitly recorded rather than being omitted or called battle poses.
Depths in this section are symmetric; older directed-depth numbers are not
interchangeable with them. Crossings include hidden surfaces and joint contacts.

* Raidenmon: slot 43 drives forearm 3 through shoulder plate 23. A constant
  local rotation correction of −10° pitch, +10° yaw and −5° roll to that
  forearm clears this pair throughout the clip: maximum 59 triangle pairs /
  75.059 units becomes zero. Initial rotations and absolute rotation keys receive
  the offset; incremental keys retain the original motion. Timing, events,
  loops, root travel, scale, translations, mesh and every other clip are exact.
  The pair still reaches 62.527 units in slot 21 frame 7. In slot 43, existing
  contacts with adjoining objects 1 and 3 increase by at most 2.101 and 3.024
  units; there is no newly crossing bone pair. A proposed global plate rotation
  was rejected after it worsened plate-to-plate contact in another clip.
* Omnimon: the toe armour's rear lip sweeps into the boot and calf. Compress
  only its last 50 local Z units by 24%, retracting the rearmost corner by 12
  units while retaining toe-tip position, sole height, sockets and animation.
  Normals receive the inverse deformation. Across every clip, right calf/toe
  20/22 falls from 7 triangle pairs / 32.908 units to zero; right boot/toe 21/22
  falls from 10 pairs / 9.687 units to zero. Left calf/toe 16/18 improves from
  30.485 to 26.315 units. Further calf shortening was rejected because it
  worsened toe penetration. Face-layer co-facing idle pairs remain zero.
* Kyubimon, MaloMyotismon and MegaGargomon retain their incoming meshes and
  animation. Exact opaque duplicate-packet searches found nothing removable in
  any of the five models. No additional face deletion or layer bias was shipped.

| Model | Slots / ticks | Full-model maximum symmetric depth, before → after | Resident bytes, before → after |
| --- | ---: | ---: | ---: |
| 409 Kyubimon | 47 / 1,461 | 56.844 → 56.844 | 94,834 → 94,834 |
| 406 MaloMyotismon | 52 / 1,714 | 90.441 → 90.441 | 74,402 → 74,402 |
| 336 Raidenmon | 51 / 1,684 | 155.922 → 155.922 | 72,622 → 72,622 |
| 335 MegaGargomon | 52 / 2,009 | 75.232 → 75.232 | 95,994 → 95,994 |
| 461 Omnimon | 52 / 2,116 | 111.774 → 111.774 | 81,434 → 81,434 |

The detector continues to flag all five. Its original eight-slot, three-pose
probe retains respectively 65, 32, 47, 30 and 31 unique part candidates before
and after; envelope verdicts remain fail, fail, pass, pass and pass. This is
separate from the exhaustive CSV measurements and is not a clean bill of health.

The residual floor is **bounded**, not a proof that a model cannot be repaired.
For each certificate below, every relative rigid translation in a continuous
world-axis cube preserves at least one strict edge/triangle crossing at the
specified pose. Each part can move independently by the listed per-axis amount;
the relative cube is twice as wide. Different crossing witnesses cover different
subcubes. Five affine orientation determinants certify a strict crossing; their
extrema occur at cube corners. A separate verifier checks every leaf directly at
its eight corners and verifies the complete octant partition. Conservative
numerical margins reject near-zero signs. This is stronger than a finite offset
sweep, but does not cover rotations, local vertex reshaping, deletion, or larger
offsets. Natural-motion redesign beyond these bounds remains unproven.

| Model / retained witness | Slot / frame | Depth | Independent translation bound per part, each world axis |
| --- | ---: | ---: | ---: |
| 409 tail tiers 15/17 | 5 / 29 | 56.844 | ±8 units |
| 406 left cannon housing/cap 2/3 | 54 / 1 | 27.805 | ±8 units |
| 406 right cannon housing/cap 10/11 | 54 / 1 | 27.922 | ±8 units |
| 336 forearm/calf 3/21 | 21 / 4 | 155.922 | ±8 units |
| 335 shoulder shell/forearm 23/25 | 21 / 11 | 47.200 | ±8 units |
| 461 sword/calf 7/16 | 47 / 12 | 90.946 | ±4 units |
| 461 left calf/toe 16/18 | 40 / 36 | 26.315 | ±2 units |

At each of the tail-tier, cannon-cap, shoulder-shell and left calf/toe witnesses,
250 local rotation trials (each bone separately; −10°, −5°, 0°, +5°, +10° per
axis) also fail to clear the pair. These finite trials are not a continuous
rotation proof. Some other witnesses can clear in a single pose under tested
rotations; that does not demonstrate a full-clip repair without new contacts.
Full certificate geometry, verified subdivision trees, and trial results are in
[the certificate archive](mesh-round-4/certificates.json.gz). Rejected fits and
clip trials are in [the experiment archive](mesh-round-4/experiments.json.gz).

Matched atlas-stamped PSX-rule renders use first-triangle quad culling, the GPU
diagonal, four-unit ordering-table bins, reverse insertion for ties, affine
textures, colour-zero discard and PSX blend rules. Each pose has eight azimuths
at 30° elevation. Coverage includes idle, walk, condition walk, run and located
crossing poses. The two changed models additionally show the repaired poses.
The [render measurements](mesh-round-4/renders.json) retain every case and view.
Raw paired sheets remain under `build/renders/` in the worktree.

| Model | Matched pose/view cases | Changed pixels before → after | Pixels sensitive to a two-unit OT-bin phase change, before → after |
| --- | ---: | ---: | ---: |
| 409 | 40 | 0 | 2,086 → 2,086 |
| 406 | 48 | 0 | 309 → 309 |
| 336 | 56 | 24,063 | 1,439 → 1,198 |
| 335 | 48 | 0 | 1,011 → 1,011 |
| 461 | 72 | 6,277 | 2,256 → 2,244 |

Pixel differences show the scope of an edit; bin-phase sensitivity locates
ordering ambiguity. Neither number is a visible-glitch count. These remain
orthographic, neutral-lighting renders without GTE perspective or runtime
visibility confirmation. No full visual clearance or unrestricted repair floor
is established for any model.

Both changed models keep their resident sizes and packet formats. Peak remains
100,256 / 100,352 bytes: all other provider pins are unchanged and both edited
models remain below the existing peak. Resident/cold-read checks pass for all
five. Textures, alternate-release pins and native-record pins are unchanged.
Only the 336 and 461 canonical model pins changed, through the scoped repository
pin tool. Fresh source/delta/provider checks pass for all five. Full decoded
preservation checks cover 254 slots / 8,984 ticks; only the documented slot-43
rotations differ. The related suite runs 91 tests: 90 pass and one private-fixture
test is skipped. Changes are uncommitted.

Reproduce from final atlas-stamped model/texture folders with `index.json`:

```sh
# Repeat in order for 409, 406, 336, 335, 461; retain separate before/after outputs.
python3 -m tools.models.mesh_round4 BEFORE 409 --out build/round4-before
python3 -m tools.models.mesh_round4 AFTER 409 --out build/round4-after
python3 -m tools.models.mesh_round4 AFTER 409 --certificate 15 17 5 29 --trials --out build/409-floor.json
# For the Omnimon sword/calf certificate use --translation-limit 8 (relative cube).
python3 -m tools.models.mesh_round4 AFTER 461 --certificate 7 16 47 12 --translation-limit 8 --trials --out build/461-floor.json
# CASES.json is a list of [slot, zero-based frame] pairs, as retained in renders.json.
python3 -m tools.models.mesh_round4 BEFORE 336 --after AFTER --cases CASES.json --out build/round4-renders
python3 -m tools.models.mesh_round4 AFTER 336 --detector docs/reference/mesh-glitch-audit.json --out build/336-detector.json
python3 -m tools.derive.steps.species pin BUILD --prepared 336 461
python3 -m unittest tools.test_mesh_round4 tools.test_mesh_cleanup tools.test_psx_blend tools.test_mesh_stability tools.test_meshcheck tools.test_battle_qa tools.test_imported_model_edit tools.test_species_pins tools.test_motionstorage
```
