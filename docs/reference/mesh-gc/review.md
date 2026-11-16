# Four-species mesh review

All four retain native-envelope failures. These are partial cause repairs with
explicitly bounded residual floors, **not** a proof that broader mesh or motion
redesign cannot repair them, and not runtime visual clearance. The detector's
thresholds are unchanged. [audit.json](audit.json) contains before/after metrics,
per-slot summaries, hashes, render measurements, preservation and storage checks.
Compressed frame ledgers include every crossing, adjacent pieces and both depth
directions: 199 occupied clips / 6,838 ticks per side. No sampled result is called
exhaustive. Pair counts include hidden surfaces and joint contacts.

| Species | Sampled crossing maximum | Full-clip crossing maximum | Full-clip deepest crossing | Native severity | Resident bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| 274 Blossomon | 766 → 766 | 1,080 → 1,080 | 59.190 → 59.190 | 1.747 → 1.747 | 89,868 → 89,868 |
| 275 Scorpiomon | 84 → 84 | 389 → 380 | 90.108 → 90.108 | 1.229 → 1.038 | 75,594 → 75,674 |
| 283 Syakomon | 68 → 42 | 275 → 251 | 41.480 → 41.480 | 1.452 → 1.452 | 28,938 → 28,938 |
| 303 KingEtemon | 428 → 428 | 929 → 929 | 46.535 → 46.535 | 2.665 → 2.665 | 100,256 → 100,256 |

Blossomon remains unchanged. All 166 legacy coplanar candidates are within rigid
objects 0/1, with zero co-facing candidates and no exact opaque duplicates. They
are retained opposite windings. Coplanar area is 0.62667 heights² against a
0.35881 limit. Removing backs would damage the visible flower/body cards. The
5% petal fit was rejected: full-model depth increased 59.190 → 59.645 and one
petal pair worsened by 3.015 units. Slot 34 frame 10 still reaches 766 legacy
crossing pairs; the exhaustive ledger attributes all pairs, not only petals.

Scorpiomon's curling tail tiers overlap. Objects 16/17/18 now fit radially to
85%, preserving longitudinal coordinates, mounts, skeleton and animation.
Inverse-scale normals follow the fit. Four bends introduced by integer rounding
are split along their existing GPU diagonal, retaining both halves and corner
attributes. Across every clip, tier pairs 17/19 and 18/19 improve from
71.198/73.106 to 60.551/63.837 units. There is no newly crossing bone pair;
existing torso/tier 1/18 worsens by 6.430 units and 1/17 by 1.649. This tradeoff
and the unchanged global maximum are explicit residuals. All legacy idle
coplanar candidates belong to unchanged object 0, with zero co-facing pairs.
Its area ratio 0.44108 → 0.37234 changes through the drawn-height denominator;
this is **not** a coplanar-surface repair. The remaining ratio still fails.

Syakomon's lower shell (object 5) moves eight local negative-Y units to separate
the rims. In idle frame 0 the whole-model crossing count falls 138 → 83 and
depth 33.456 → 20.194; the comparable detector maximum falls 68 → 42. Across
all clips, shell pair 1/6 still reaches 34.493 versus 34.417 units. Contacts
3/6 and 2/6 worsen by at most 1.865/1.559 units; no new pair appears. The
full-model depth remains 41.480. The unchanged 122 tiny faces are the inner
creature and eyes: 82/20/20 triangles on objects 2/3/4, hidden by bone 3's
closed-shell scale [40,40,40] relative to 4096. These surfaces are required when
the shell opens. Tiny-face count exceeds 84; tie rate is 0.104245 → 0.105865,
against 0.076849. No co-facing pair, opaque duplicate or bent quad was found.

KingEtemon's overlapping body-card seam is repaired: five existing corners
on the left strip retract by 4–6 local X units to X=2, retaining its outer
edge, both windings, UVs and normals. Co-facing idle pairs fall 3 → 0 without
additional storage. Its 281 residual bent quads have normalized risk
0.00810103 against 0.00303987. It already occupies the entire 100,256-byte
ceiling. Repeating existing exact decoded-animation compaction saves zero;
the cheapest further quad split costs 20 resident bytes. There are no exact
opaque duplicate packets to fund it. Tested 5/10/15% hip radial fits did not
improve the selected full-model maxima and were rejected. Part pair 2/26
reaches 46.535 units in walk slot 2 frame 1. Final co-facing idle pairs and true
zero-area faces are zero in every reviewed model. Zero-area repeated-index
masks and pose-collapsed faces are also zero; tiny faces remain only in Syakomon.

## Bounded residual certificates

Each certificate archive contains the full triangle geometry and a verified
subdivision tree. For the specified pose, every relative world-axis translation
within ±8 units retains a strict edge/triangle crossing: both parts may move
independently by ±4 units per axis. An independent verifier checks all cube
corners and the complete partition. At each witness, all 250 local rotation
trials (each bone separately, −10/−5/0/+5/+10 degrees per axis) retain a crossing.
Those finite rotation trials do not prove a continuous rotation floor.

| Species | Bones | Slot / zero-based frame | Symmetric depth |
| --- | --- | --- | ---: |
| 274 | 2/7 | 21 / 13 | 59.175 |
| 275 | 1/2 | 56 / 5 | 77.223 |
| 283 | 1/2 | 21 / 1 | 37.168 |
| 303 | 2/26 | 2 / 1 | 46.535 |

The metric floors in audit.json are separately bounded: retained opposite
windings and fixed idle height for 274/275; retained visibility-mask scale and
triangles for 283; exact retained geometry/attributes/programs and the existing
lossless encoder for 303. They do not exclude reshaping, reassignment, another
encoding, larger offsets, or natural motion redesign. Thus an unrestricted
repair floor and full visual resolution remain unproven.

## PSX-rule evidence and validation

Matched sheets under build/renders use first-triangle quad culling, the GPU
diagonal, four-unit OT bins with reversed tie insertion, affine textures,
colour-zero discard and PSX blending. Coverage includes idle, walk, condition
walk, run and the located deepest/certificate poses at eight elevated azimuths. Additional
views cover Blossomon slot 34 frame 10 and Scorpiomon's repaired curl poses.

| Species | Pose/view cases | Changed pixels | Two-unit OT phase-sensitive pixels before → after |
| --- | ---: | ---: | ---: |
| 274 | 56 | 0 | 1,301 → 1,301 |
| 275 | 72 | 87,799 | 392 → 381 |
| 283 | 48 | 382,258 | 2,771 → 2,005 |
| 303 | 40 | 6,562 | 981 → 956 |

Pixel counts measure edit scope and ordering sensitivity, not visible glitches.
These orthographic renders omit runtime camera/GTE perspective and integer GPU
precision. Device and crowded-scene packet profiling remain outstanding.

All 199 clips / 6,838 ticks preserve exact decoded scale, rotation, translation,
root travel, events and loops. Textures and generated skeletons are exact.
Only canonical model pins 275/283/303 change, through the scoped repository pin
command; all other model, texture, native and alternate pins are unchanged.
The packet-format deltas relative to the incoming pre-stability meshes are
−532, +812, −40, +284 bytes respectively, each below +1,024. Resident and
sector-aligned cold reads pass for all four; peak stays 100,256 / 100,352 bytes.
The related suite runs 91 tests, 90 pass and one fixture-dependent test skips. Fresh source/delta/provider pin
checks pass for all four species, including the final seam repair.

Reproduce measurements and independently verify final floors:

```sh
python3 docs/reference/mesh-gc/reproduce.py BEFORE AFTER --out build/gc-review
python3 -m tools.derive.steps.species pin BUILD --prepared 275 283 303
python3 -m unittest tools.test_mesh_round4 tools.test_mesh_cleanup tools.test_psx_blend tools.test_mesh_stability tools.test_meshcheck tools.test_battle_qa tools.test_imported_model_edit tools.test_species_pins tools.test_motionstorage
```

BEFORE/AFTER require final atlas-stamped pairs and index.json with generated
bindings. The certificate and CSV archives accompany this note; rejected fit
measurements are retained in fit-trials.json.gz. Changes remain uncommitted.
