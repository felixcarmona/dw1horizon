# Saberdramon surface culling

Species 106 uses a native DW1 mesh carried by a record-original delta. It does
not run through the imported-model provider's stability pass. Its disc mesh
contains 16 nonplanar quads (3.23–7.37 degrees), including the leg and foot
pieces. libgs uses the first triangle's NCLIP result for both GPU triangles;
as a piece rotates, a visible half can disappear with its back-facing neighbour.
This is the same geometry defect repaired for imports in PR 511.

The final pre-edit model reproduces 5,705 discordant face/tick/view triples
across every occupied clip: 46 clips, 1,832 decoded ticks, eight elevated
azimuths. Splitting all 16 along the existing GPU diagonal reduces that count
to zero. The record delta now stores this corrected mesh. All 606 ordered,
oriented surface triangles retain positions, normals, UVs, RGB, material and
winding; all decoded motion, root travel, loop points and events are identical.
Exact animation compaction, identical shading and final pool compaction pay for
the splits: resident bytes 46,834 → 45,738; packets 428 → 444; packet-format
bytes +408. Archive peak remains 100,256 / 100,352 bytes.

There are no tiny, degenerate or pose-collapsed triangles in Saberdramon and
no ABE-enabled packets or blended texel samples. Texture bytes stay unchanged.
Depth ties and order reversals are measured separately in the accompanying
[report](saberdramon-mesh-audit.json), resetting comparison history at every
clip boundary. Legitimate occlusion also changes depth order; these counts
alone do not justify changing the ordering table or moving surfaces. Two
co-facing idle overlap candidates remain, without opaque duplicate packets.

A sampled PSX-rule rendering search checks the first affected tick for each
clip/view, choosing its largest projected discordant half. The best matched
192-pixel comparison changes 26 pixels (slot 47, tick 13, azimuth 45 degrees).
This shows a visible rendering difference, but is not an in-game reproduction
or proof that every reported blink has been eliminated. The exhaustive
numbers above describe geometry/facing, including occluded surfaces, rather
than visible pixel failures. The local matched image is
`build/saber/culling-best.png`.

## Skeletal controls

Every occupied clip of these final models was also scanned. No control has
tiny, zero-area or pose-collapsed triangles, or exact opaque duplicate packets.

| Species | Clips / ticks | Remaining bent quads | Discordant triples | ABE packets |
| --- | ---: | ---: | ---: | ---: |
| 26 SkullGreymon | 51 / 1,703 | 2 | 211 | 0 |
| 277 SkullMeramon | 53 / 1,459 | 14 | 2,437 | 0 |
| 268 SkullMammothmon | 52 / 1,797 | 46 | 10,612 | 0 |
| 241 Wizardmon | 49 / 1,522 | 95 | 33,614 | 40 |
| 242 Sorcermon | 49 / 1,601 | 90 | 33,501 | 40 |

The four imported controls already received the shared budget-neutral pass.
Reapplying it finds only 0–2 spare resident bytes, insufficient for any further
split. Their remaining bends are retained, consistent with that pass's
per-model budget contract. SkullGreymon is an unchanged native control rather
than a record-original import; its two bends are only 3.07/3.31 degrees.
Its general repair probe could fund both splits, but this change does not add
a new native-record routing path. Wizardmon and Sorcermon's blended texels
are recorded separately (162/24 sampled texels); ABE by itself does not
establish an erroneous bone material. No additional clear duplicate or
accidental degenerate surface was found to remove safely. These controls are
not declared fixed; their residual culling candidates remain follow-up work.

## Reproduction and validation

Prepare a pre-edit archive extraction as `build/saber/before` with
`tools/models/meshcheck.py extract BUILD/DIGI.DAT build/saber/before`.
The model sources come from the player's extracted disc files.

```sh
python3 tools/models/meshcheck.py flicker build/saber/before 106 26 277 268 241 242 --out build/saber/before.json
# On the pre-edit 106.MMD, call mesh_stability.apply(data, index['106']['bones']);
# write its returned bytes, then store through the repository delta/pin tool:
python3 tools/models/edit.py put 106 build/saber/106-split.MMD
python3 tools/models/edit.py check 106 --species-pins
python3 -W ignore::ResourceWarning -m unittest tools.test_saberdramon_mesh tools.test_mesh_stability tools.test_meshcheck tools.test_mesh_cleanup tools.test_psx_blend tools.test_imported_model_edit tools.test_recordoriginals
```

All 58 tests pass with the disc extraction and pre-edit model available. The
new regression verifies every final tick and all ordered disc surface corner
attributes; its pre-edit fixture check additionally compares complete decoded
motion, events and loops and reproduces the stored repaired output exactly.
Provider SHA-1 and source/delta/target SHA-256 checks pass. Pins were written
only by `tools/models/edit.py put`. Changes are left uncommitted.
