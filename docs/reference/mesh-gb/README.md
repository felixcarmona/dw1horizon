All four species now pass the unchanged native mesh envelope. All four retain
independent part-interpenetration review candidates; this is not a claim of
complete in-game visual clearance. The [audit](audit.json) retains the original
thresholds, sampled metrics, complete clip summaries, hashes, storage audits
and per-view render measurements. Compressed CSVs retain every crossing's
slot, zero-based frame, bones, objects, adjacency, triangle-pair count and
symmetric depth, including shallow and hidden contacts.

| Species | Failing metric before → after | Native limit | Envelope |
| --- | ---: | ---: | --- |
| 220 Vikemon | Sampled crossings 602 → 582 | 595 | fail → pass |
| 236 DemiDevimon | Coplanar area 0.47279 → 0.31059 heights² | 0.35881 | fail → pass |
| 238 Dolphmon | Order reversals 8.75945% → 6.91705% | 7.22231% | fail → pass |
| 270 PrinceMamemon | Coplanar area 0.43037 → 0.14155 heights² | 0.35881 | fail → pass |

Vikemon's stored weapons penetrate the shoulder region. Moving objects 17/18
eight local Z units rearward retains their mounts and original motion. The
alternate facial layer occupies the base head's exact corners: objects 2's
packets 88–91 receive independent corners four Z units forward. Co-facing idle
pairs fall 12 → 0. Some contacts improve while others worsen; this fit is not a
full-model collision clearance.

DemiDevimon's paired wing-tip faces occupy the same thin sheet with opposite
windings. Both are required for visibility from opposite sides. The complete
undersides of objects 3/6, packets 2/3, receive independent corners two local Y
units apart from the upper surface. Each two-panel underside moves together,
retaining its internal shared seam. The ears and inner wing layers remain.

Dolphmon's adjacent tail shells overlap across long collars: local Z extents
reach 82–105 units while successive sockets advance only 45–86 units. Objects
5–8 compress axially to 78% about Z=40; the largest corner shift is 14 units.
The cross sections, skeleton, socket positions and original wave remain.
Normals receive the inverse deformation. Radial fits from 95% down to 80%
increased the reversal rate and were rejected. Axial trials at 95%, 90%, 85%
and 80% gave reversal rates 8.567%, 8.591%, 8.052% and 7.276%; the final 78%
fit reaches 6.917%. No waveform, root translation or event was adjusted.

PrinceMamemon's inner cape surface shares the outer sheet's geometry and uses
a different texture region. Packets 177–179, 183–185 and 187 of object 6 move
as one layer three local Y units away, including the folded bottom panel.
Moving complete sheets by a common offset preserves their existing panel
relationships; independent per-packet normal offsets were rejected because
they would pull adjoining panels apart. The body and decorative layers remain.

The latter two repairs separate opposite-facing render layers, which are not
co-facing z-fighting candidates: both already had zero co-facing idle overlaps.
The legacy coplanarity metric counts opposite faces and different triangulations
of two-sided cards. Its reduction establishes separation and envelope passage,
not that these layers explain a reported visible glitch. No exact opaque
duplicate packet was found in any species; no surface was deleted.

| Species | Co-facing idle pairs | Bent quads | Bent risk before → after | Degenerate / zero-area faces |
| --- | ---: | ---: | ---: | ---: |
| 220 | 12 → 0 | 45 → 45 | 0.00014452 → 0.00014349 | 0 / 0 |
| 236 | 0 → 0 | 15 → 15 | 0.00003252 → 0.00003252 | 0 / 0 |
| 238 | 2 → 0 | 16 → 18 | 0.00002437 → 0.00002686 | 0 / 0 |
| 270 | 0 → 0 | 18 → 18 | 0.00003186 → 0.00003186 | 0 / 0 |

All bent-risk values remain below the native limit 0.00303987. Tiny faces,
repeated-index collapses and pose-collapsed rest faces are also zero. Further
splitting cannot be added under the existing packet allowance: the original
pre-stability packet growth is already 1,008 / 1,008 / 1,020 / 1,012 bytes,
respectively, against 1,024. These edits leave every packet format unchanged.

Exhaustive symmetric crossings cover all 204 occupied slots / 7,519 ticks in
both versions. These counts include adjacent joints and all occupied field,
care, training and battle slots; they are distinct from the default detector's
eight slots and three sampled poses per slot.

| Species | Slots / ticks | Full-model maximum triangle pairs | Maximum symmetric depth, units | Sampled unique deep part pairs |
| --- | ---: | ---: | ---: | ---: |
| 220 | 52 / 2,058 | 1,611 → 1,625 | 142.429 → 141.804 | 78 → 78 |
| 236 | 50 / 2,244 | 444 → 444 | 41.211 → 41.211 | 10 → 11 |
| 238 | 48 / 1,591 | 676 → 556 | 48.347 → 48.498 | 18 → 15 |
| 270 | 54 / 1,626 | 339 → 346 | 100.170 → 100.362 | 14 → 14 |

Layer separation can introduce or deepen small contacts: DemiDevimon gains
one sampled deep-pair candidate. Passing the envelope does not remove that
review obligation. The complete before/after ledgers expose regressions as well
as improvements. The deepest baseline witnesses are Vikemon bones 18/22 in
slot 54 frame 10; DemiDevimon 2/10 in slot 29 frame 46; Dolphmon 4/10 in slot
49 frame 14; and PrinceMamemon 10/18 in slot 42 frame 29. Large residual
crossings remain and no unrestricted repair floor is claimed.

Matched PSX-rule sheets cover idle, walk, condition walk, run and located
crossing poses at eight azimuths and 30° elevation. The renderer uses the GPU
quad diagonal, first-triangle culling, four-unit OT bins, reverse insertion for
ties, affine textures, colour-zero discard and PSX blending. Idle and one deep
pose sheet per species are retained alongside this report; all matched sheets
are under `build/renders/` in the worktree.

| Species | Pose/view cases | Changed pixels | Two-unit OT-bin phase-sensitive pixels, before → after | Detector tie rate, before → after |
| --- | ---: | ---: | ---: | ---: |
| 220 | 48 | 81,216 | 2,383 → 2,652 | 1.1432% → 1.2026% |
| 236 | 56 | 14,728 | 845 → 889 | 3.5183% → 3.5226% |
| 238 | 56 | 36,210 | 2,620 → 2,086 | 4.0378% → 3.5204% |
| 270 | 48 | 12,111 | 964 → 984 | 1.4482% → 1.4602% |

Pixel differences measure edit scope; bin-phase sensitivity measures ordering
ambiguity, not visible defects. Some phase sensitivities worsen. These are
orthographic, neutral-lighting renders without GTE perspective, runtime camera
or integer raster precision. Runtime visibility and crowded-scene confirmation
remain outstanding.

Every decoded pose, scale, translation, rotation, root trajectory, timing,
event and loop remains exact across all 7,519 ticks. Textures, skeletons and
primitive materials/UVs remain exact. Source content skeletons differ from the
final native-binding skeletons for 236 and 270; audits use the final bindings.
Resident bytes change 96,986 → 97,058; 78,682 → 78,778; 46,348 → 46,348;
and 66,696 → 66,856, respectively. All 183 canonical provider model pins match
their prepared files and pass resident/cold-read checks. Their measured peak
remains **100,256 / 100,352 bytes**. Only these four canonical model pins
changed, through the scoped repository review/pin tools; texture, alternate
release and native-record pins are unchanged.

Fresh source/delta/provider verification passes 4/4. The related suite runs
95 tests: 94 pass, one private-fixture test is skipped. The suite includes four scoped
fixture tests checking the actual edits, decoded motion, materials, UVs, packet
formats and storage. Changes remain uncommitted.

Reproduce using final atlas-stamped pairs with final-binding `index.json`:

```sh
python3 docs/reference/mesh-gb/reproduce.py build/before build/after --out build/recheck --ledgers --renders
python3 tools/models/edit.py --from build/prepared check --species-pins 220 236 238 270
python3 -m unittest tools.test_mesh_gb tools.test_mesh_round4 tools.test_mesh_cleanup tools.test_psx_blend tools.test_mesh_stability tools.test_meshcheck tools.test_battle_qa tools.test_imported_model_edit tools.test_species_pins tools.test_motionstorage
# Review hashes and provider pins must only be written with repository tools:
python3 -m tools.models.mesh_cleanup review build/review-provider --ids 220 236 238 270
python3 -m tools.derive.steps.species pin build/prepared --prepared 220 236 238 270
```
