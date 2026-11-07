# Player model reports

## Native locomotion and weapon pass

Marsmon, GrapLeomon, ExVeemon and Stingmon use Leomon's native walking,
tired walking and running timing and limb trajectories, fitted to their own
bone lengths. Garudamon combines those legs with Angemon's wing curves;
Sakuyamon uses Angemon's staff-bearing performance. Existing faces and textures
remain intact. GrapLeomon retains its reviewed chibi proportions. ExVeemon's
neck piece and head attachment are shortened to 78% across every animation.

Kyubimon uses Elecmon's four-paw trajectories, with its own two-link legs solved
to the native paws and its tail fan retained. A uniform 0.78 resize includes
every animation, radius, height, bubble and effect attachment. Field loops are
sampled before resizing and encoded again to avoid rounded momentum accumulating
a height error at each seam. ChaosLord uses Machinedramon's walk and run; its
existing tired performance is kept because that donor has no tired clip.

Omnimon's Megaton Punch and Sonic Jab carry the existing cannon-arm strike
onto the sword shoulder and elbow. Body anticipation, legs, cape, timing and
attack events remain exact. The cannon keeps its ready pose. Buster Dive keeps
its separately repaired dash.

The authored outputs are stored as ordinary model deltas. The former field
overlays for the five affected species are baked before editing and disabled,
so later generators cannot restore the previous gait or proportions. Recipes
under `content/models/authoring/native-polish/` pin the input, donor, skeleton
and output; `tools/models/field_animations/native_polish.py` replays them.
The output must also pass `edit.py check --species-pins` and the disc's resident
and cold-animation limits.

```sh
python3 tools/models/field_animations/native_polish.py \
  content/models/authoring/native-polish/297.json BEFORE.MMD AFTER.MMD
POLISH_MODELS=build/polish PYTHONPATH=tools \
  python3 -W ignore -m unittest tools.test_native_polish
```

The decoded checks cover unchanged mesh and nonlocomotion programs after the
explicit proportion changes, native timing, loop closure, field pace, and sole
clearance at logic ticks and both intervening display frames. Sword checks
preserve every unaffected channel and every event.

World 3 USA has its own Kyubimon mesh. Its variant first carries the pinned
pre-polish delta onto that source, then solves and resizes that mesh through the
same native recipe. The variant generator checks its ordinary copy/add delta
for foreign source-data windows and pins the final provider output. This avoids
matching resized PAL vertex coordinates against different USA vertices.

Pegasusmon remains unchanged in this pass. Its static texture audit finds no
invalid palette rows, UV ranges or palette-data sampling. Coincident head,
shoulder and wing faces have opposite winding, as in the source import; they
are intentional backs. Its animation streams contain no texture-copy commands.
Those checks alone do not establish the cause of an intermittent field defect.

## Gallantmon: helmet eyes

The full-resolution eye repair is already included in v0.0.6. The final provider
uses the repaired model and texture directly, without a field overlay. Its eight
helmet faces sample a dedicated 56 by 32 texture rectangle beginning at (125, 0).
The source palette, model size and animation programs are preserved by
`tools/models/repair_gallantmon.py`.

A culled front, three-quarter and side render of the current pinned model shows
both yellow eyes. The model and texture pins must be checked together:

```sh
python3 tools/models/edit.py --from build/model-fixes-wolf check 318 --species-pins
```

The repair was introduced by commit `2068525a`; this report does not require a
second texture alteration.

## Submarimon: water outlet and preferred terrain

Blasting Spout's Whamon origin `[2, -102, 0, 155]` maps to Submarimon's
front drill, bone 7, at local `[0, 0, -180]`. The outlet follows the drill
through the finisher, rather than following the middle of the hull.
Other technique origin mappings are unchanged.

Preferred terrain is region 8: Coela Point and both Dragon Eye Lake screens
carry it in their MAP headers. Region 4, used previously, belongs to Tropical
Jungle. These region classes are distinct from the map-name indices.

## Mega size comparison

Size adjustments are baked into vertices and all animation translations,
including root momentum; rotation and bone-scale channels are unchanged.
The comparison uses native Machinedramon at the same camera scale.

| Species | Uniform multiplier | Idle height before / after |
|---|---:|---:|
| MaloMyotismon | 1.37 | 475 / 650 |
| Imperialdramon | 0.85 | 600 / 510 |

Imperialdramon's wide wings and quadrupedal body retain their silhouette.
Its final celebration is baked before resizing, so field and battle slots use
the same proportions. Attached effect origins and condition bubbles follow the
same multiplier; radius, height and status framing are updated with the model.
`tools/models/resize.py` refuses storage overflow and checks all animation
controls and non-translation channels remain exact.

## MegaKabuterimon: size and evolution route

MegaKabuterimon uses a uniform 0.90 multiplier (idle height 558 → 502),
keeping this Ultimate below HerculesKabuterimon while retaining its broad shell.
The existing curated route is Kabuterimon (19) → MegaKabuterimon (205) →
HerculesKabuterimon (60). No level-skipping route is added. Source records and
`content/tables/evolution-tree.json` already agree on both edges; the built
chart audit must also show these links with NEW DIGIMON enabled.

## VenomMyotismon: loose long-arm run

The run's shoulders drive alternating arcs, followed by the elbows and then
the heavy gauntlets. Smooth periodic reversals avoid a rigid held-fist pose.
Devimon's native long-arm motion is the visual reference. The existing chest,
head, wing, tail and supported-leg performance remains unchanged, as do root
travel, scale channels, clip duration and sound/control events. The authoring
pass checks every unselected channel over four decoded cycles and changes only
run slot 4. Final provider output retains the animation storage gate.

## Beelzemon: Blast Mode silhouette and face

The winged M377BLZB source is Blast Mode. Its irises should be green, as shown
in the [official reference](https://digimon.net/reference/detail.php?directory_name=beelzebumonblastmode).
Only the two iris shades swap red and green channels in an isolated palette;
blue, shade steps, gold highlights and all other palettes remain exact.

The source reader must honor empty section-table slots: otherwise the free hand
is truncated. The complete untouched model has 905 primitives, including a
hidden effect mesh. Culled front, three-quarter, side and back comparisons show
that the import lost helmet spikes, wing-tip surfaces and belt detail. The
repair rebuilds the whole head (130 source triangles), all six wing sections
and all four belt sections, using the existing DW1 proportion bake. The source
jaw and all three green eyes retain their full-resolution texture patches.
The current cannon, five claws and boot spikes are present and retained.

Exact triangle pairing and unused-pool cleanup recover space. New pairs keep
the same diagonal, shared UVs and normals, winding and material; they must form
convex quads. A small fit of the existing broad body/leg panels supplies the
remaining slots. Their six extent landmarks are pinned, preserving width,
height and depth. Head, wing tips, belts, arms, cannon, hands and boots are protected
from this fit. Animation bytes stay exact. The result keeps the 713-primitive,
172-vertices-per-object and original resident/cold-buffer limits.

`tools/models/repair_beelzemon.py` is an authoring tool; it needs NetworkX and
takes the untouched source, DW1-proportioned MMD/TIM, pinned raw importer MMD,
and output stem. The player build needs no authoring dependency: plain deltas
and final provider pins carry the result. Store with `tools/models/edit.py put
403`, then run `check 403 --species-pins`.

`tools/test_beelzemon_face.py` takes `BEELZEMON_BEFORE`, `BEELZEMON_AFTER`,
`BEELZEMON_SOURCE` and `BEELZEMON_IMPORT`. It checks every restored source
triangle with its winding, UVs and normals; retained protected geometry;
body-panel extents; unchanged acting; texture isolation and storage budgets.

## Silphymon and Starmon: field strides

Silphymon's Card Battle rig carries the head on bone 3 and its ears on bones 4
and 5. The proportion recipe previously treated only bone 5 as the head,
enlarging that ear alone. Both ears now retain the source head proportions.
The corrected proportion bake is stored before the final walk delta; the
provider uses the resulting model directly.

The field walk, condition walk and run use native Kokatorimon motion for
Silphymon and native Leomon motion for Starmon. Anatomical chain calibration
and inverse kinematics fit the native foot paths to the imported leg lengths.
The feet keep their own orientation with native heel and toe roll. Clearance
is checked at logical ticks and intermediate blend samples. Silphymon's stride
uses longer timing for its larger body; Starmon's retains the native timing.
Upper-body acting and secondary motion keep the gait loose. Meshes, rigs,
care clips and attack programs are preserved after the proportion correction.
Starmon shares the repaired walk and run with battle slots 35 and 36, matching
the native donor and replacing its separate imported battle shuffle.

The authoring tools are `tools/models/field_animations/silphymon_walk.py` and
`starmon_walk.py`. Silphymon's `--prepare` option reconstructs the corrected
proportion bake from its pinned pre-edit import. Store final results with
`tools/models/edit.py put`, then check the provider pins. The replay tests use
`MODEL_REPORT_DIR` for the pre-edit and reviewed files:

```sh
MODEL_REPORT_DIR=build/reports PYTHONPATH=tools python3 -m unittest \
  tools.test_player_model_reports tools.test_dws_battle_moves
```

Saberdramon uses the native DW1 model. The reviewed provider and integrated
record preserve its source primitives, UVs and texture pages, with identical
palette rows and sampled texels. A reported tan wing-root surface does not
justify altering those assets without a demonstrated import regression.

The story compiler already gives Starmon's replacement of the noncombat
Unimon placement usable attack priorities. This behavior is present in
v0.0.6; its regression tests cover the actual placement and moves. It does
not establish that a later report of inactivity is resolved: verify the live
wild encounter and its technique execution before changing battle behavior.

## Locomotion anatomy refinement

The unarmed Leomon-based imports use the native free-arm shoulder, elbow and
wrist performance on both sides. The sword-bearing arm is reflected by its
joint directions before transfer, offset by half a cycle so opposite arms
follow opposite legs. Stingmon maps shoulders 13/17, elbows 14/18
and wrists 16/20 to native 5/8, 6/9 and 7/10; both forearm-to-wrist chords are
calibrated. Hand meshes hang from the wrists. Ankle-to-toe directions and toe
meshes are calibrated separately so an imported idle twist cannot turn a foot
sideways. Sakuyamon's toe joints 6/10 participate in its foot solve.

GrapLeomon keeps its proportions and uses a more upright torso and head during
travel, with unarmed arm carriage. Kyubimon retains its own quiet quadruped
reference and tail fan; reduced body pitch and paw lift keep its run low.
ChaosLord uses its source knee bend planes and a cyclic Euler fit. Fitting
rotation charts around the seam avoids the large clearance lift that previously
left its run above the floor. ExVeemon remains unchanged.

Gizamon retains its source mesh, front support, head and tail acting. Its hind
paws sit at half-width 85 rather than 120 during travel. The source bend plane
and complete leg lengths support the narrower stance. Sleep and settling keep
the hind paws outside the flanks as the body lowers. These changes are baked
after the previous field overlay, which no longer runs over the final delta.

Wormmon uses a uniform 0.65 resize across vertices and all animation translations,
including field, battle and care programs. Its idle height changes from about
288 to 186 units and its width from 363 to 235; native Agumon measures 253 high
and 202 wide. Radius, height, effect attachments, condition bubble and status
framing follow the resize. Field cycles are retimed to retain ordinary follow
speeds with the smaller stride.

Recipes and pinned input deltas live under
`content/models/authoring/gait-refinement/` and `content/modeldelta/authoring/`.
`tools.test_gait_refinement` replays the artifacts and checks unaffected programs,
meshes, cyclic playback, interpolated sole clearance and resident/cold storage.
The World 3 USA variant repeats the refinement on its own Kyubimon mesh.
