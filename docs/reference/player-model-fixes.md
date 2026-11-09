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

## Canine, larval and amphibian donor refinement

Stingmon's shoe meshes have mirrored widths and different joint origins. Their
centroids cannot define the sole frame. Forward and plantar directions are
calibrated from centered geometry. The left ankle now follows the
approved opposite-side foot performance at the opposing phase, calibrated to
that shoe frame. Only the affected leg's rotations change; the other limbs,
body, hands, mesh and nonlocomotion programs remain exact.

Kyubimon uses Garurumon's canine shoulder, hock and muzzle layout. Its
alternating walking footfalls are accelerated for the run instead of using a
bounding performance. The trunk has constant vertical position throughout
walk, tired walk and run. Individual limb solves clear interpolated swing
arcs without raising the whole animal. The tail fan retains its shape and
follows delayed native tail rotations. Cadence follows the native stride travel.

Wormmon keeps the uniform 0.65 Rookie resize. Kunemon supplies its segmented
body flexion and travelling proleg wave; the curl is reduced for Wormmon's
longer, lower silhouette. Its head attachments remain on their own joints.
Battle, care, mesh and attachment sizing remain exact to the resized model.

Gizamon's gait is rebuilt from the raw importer geometry. Betamon supplies a
low amphibian body and four short support limbs; Gabumon's upright performance
would not match that layout. The original long hind limbs fold rearward, with
paws beneath the flanks. Source lengths remain intact in sleep and settling.
The pinned prior delta protects unrelated combat programs, while the field and
care programs are authored from the raw model. No old field gait is reused.

Pinned recipes and prior deltas are under
`content/models/authoring/animal-refinement/` and `content/modeldelta/authoring/`.
Replay with `tools/models/field_animations/animal_refine.py RECIPE SOURCE OUT`.
`tools.test_animal_refinement` verifies provenance, unaffected channels and
programs, four-cycle playback, interpolated paw clearance, constant canine
trunk height and complete sleeping limb lengths. The USA Kyubimon variant
repeats the refinement on its own mesh.

### Larval binding, wing follow-through and amphibian pace

Wormmon uses Kunemon's complete native 28-bone hierarchy and animation
programs through `native_binding.py`, rather than transferred rotations on
its imported rig. The already reduced mesh is assigned piece by piece to
native larval joints; the head and segmented antennae stay together.
Mesh surface dimensions, texture coordinates and the Rookie size correction
are retained. Native joint translations use a uniform 0.65 scale; native
rotation, scale, timing and control instructions remain intact. Technique
slots select native actions, and effect origins use the scaled native joints.

Stingmon's four wing membranes remain attached to the thorax in their source
idle planes. Their orientations lag the thorax slightly, with delayed flex
between the upper and lower pairs. The membranes hinge down as the running
thorax leans, keeping their trailing planes relaxed. Every other bone and all non-field
programs retain the approved performance.

Gizamon alternates diagonal supports with visible swing clearance, body bob,
head response and delayed tail/fin motion. It walks at 20 units per logic tick
and runs at 40, within native Rookie pace (Betamon 15/35, Agumon 22.5/45).
Ankle planting and a second support solve keep stance toes on the floor.
Its source limb lengths, folded hind-leg support pose, sleep and combat
programs remain intact. The overlays and final provider hashes are pinned.

`tools.test_followthrough` guards the wing-only change and active paw/body
motion; `tools.test_native_bindings` compares Wormmon's hierarchy and all
native programs against the donor. Review videos also include actual
20-tick-per-second playback, alongside phase-aligned pose comparisons.

## Beelzemon: ordinary cannon strike

The World 2003 source `M377BLZB` is Blast Mode. Its Blaster is the
[right-arm weapon](https://wikimon.net/Beelzebumon%3A_Blast_Mode); the imported
mesh keeps it on bones 20–23, opposite the bare-hand chain 16–19. The native
Leomon hand strike previously drove the bare fist while the projectile origin
already followed cannon bone 22.

`tools/models/repair_beelzemon_attack.py` authors the complete firing action.
The free arm rises to brace below the cannon. The torso loads, turns into the
shot and takes the recoil; knee flexion and a small pelvis shift carry its
weight while both feet remain planted. The head counters the turn, and the
wings and tail follow with delayed motion. Small translation channels use a
stricter encoding tolerance so compression retains the weight shift.

The four short strikes share one 15-tick program. The nine casting aliases,
including Tremor, share a 44-tick program. Their existing events, durations and
technique rules remain exact. Field/care animations, Buster Dive, War Cry and
the finisher remain unchanged, as do the mesh, rig and texture.

The consumed resident model uses 99,480 bytes within the 100,352-byte partner
buffer. Every sector-aligned cold read fits 8,192 bytes. The intermediate delta
retains the old Buster Dive alias until the provider replays its reviewed dash;
storage is checked on that consumed result.

Native Andromon Pulse Laser and MetalGreymon Heat Laser provide the visual
reference. The side-by-side videos remain a separate review requirement;
physical regression checks cannot establish animation quality by themselves.
Reproduce event, weapon, bracing, foot placement and storage checks with the
pre-edit provider output at `MODEL_REPORT_DIR/before/403.MMD`:

```sh
MODEL_REPORT_DIR=build/reports PYTHONPATH=tools \
  python3 -W ignore -m unittest tools.test_beelzemon_attack
```

## Apocalymon: voice and Power Crane

The imported card-game model retains a humanoid torso, floating core and metal
claws. Its old voice pair, VBALL 48 / VLALL 2, belonged to Megadramon and
Gigadramon. It now borrows Myotismon's pair, 56 / 3, following the humanoid dark
character rather than the everyday animation donor. This is a native DW1 voice
substitution, not a newly imported canonical voice recording. Notes 53–55 are
present in the selected VBALL bank.

Power Crane, slot 51, now lashes all five mechanical chains rather than a single
claw. Each chain bends at its root, middle link and wrist; the wrists follow
the roots by three ticks. Both humanoid arms and the cloak react as the core
counters the load without tipping far over. The attack loads, extends, follows
through and settles into the existing ready pose. Duration (61 ticks), sound
event and all other animation programs remain exact. The forward claw keeps
the technique's effect at its local mesh point `(48, -64, -237)` on bone 17.

The resident model uses 100,348 of 100,352 bytes; all cold reads fit 8,192 bytes.
The small buffer margin is checked on the consumed model. Voice remains the
Myotismon pair VBALL 56 / VLALL 3. This is a DW1 adaptation of Apocalymon's
multi-claw attack; the native technique name Power Crane is not a card-game
attack name.

## Omnimon cape: game-equivalent review rendering

The cape has coincident exterior and lining plates with opposite winding,
single-sided flags and different white/red materials. Drawing both sides into
an offline z-buffer produces white speckles. With the game's face culling,
the same unchanged mesh and texture render solid. Keep the source plates and
materials; changing their UVs or removing the lining would damage the model.

`tools/animstudio.py` now culls by default. `--cull` remains explicit and
`--no-cull` is available for diagnostic comparisons. Check the cape from the
back as well as the front and side, then verify it in the native 2 MB engine.

## Omnimon: Grey melee and Garuru ranged techniques

The [official profile](https://digimon.net/reference_en/detail.php?directory_name=omegamon)
identifies the Grey sword in the left arm and the Garuru cannon in the right.
The imported mesh agrees: bones 3–7 carry Grey and 9–13 carry Garuru. The source
physical clip moved Garuru while Grey's shoulder and elbow remained fixed.
The ordinary sword repair is `tools/models/repair_omnimon_attack.py`, retained
from the native locomotion and weapon pass. It moves the shoulder/elbow action
onto Grey while preserving the body's anticipation, legs, cape, timing and
events. Garuru keeps its ready pose. There is one sword implementation.

| Ordinary technique | Action |
| --- | --- |
| Megaton Punch, Sonic Jab | Grey sword |
| Counter | Existing guard action |
| Tremor | Existing Garuru cast; range 3 |
| Buster Dive | Existing whole-body dash |
| Dynamite Kick | Existing kick |
| Ice Statue, Aurora Freeze, Giga Freeze, Water Blit | Existing Garuru cannon cast |
| Prominence Beam, Magma Bomb, Red Inferno, Fire Tower | Existing Garuru cannon cast |

Only slots 46 and 51 change. Other programs, the finisher and field animations
retain their exact decoded motion. `tools/test_native_polish.py` checks the
sword repair against its before/after artifacts, including exact unaffected
body channels and attack events. The former whole-body reflected alternative
has been removed.

## Tyrannomon scene: uninterrupted native strides

The black actor in the Ancient Glacial Region recruitment scene is native
MasterTyrannomon (`TIRS`, NPC twin 467); the red actor uses native Tyrannomon
(`ETYR`, 132). Both source walks use both feet. In the animation studio, TIRS
lifts its feet by 67/60 units and ETYR by 112/112; the partner MasterTyrannomon
walk retains Tyrannomon's full motion at its larger size, lifting both feet by
167 units. Native Greymon provides the biped reference. These clips retain
their original body, arm and tail motion.

Script 79 restarted the black actor's 31-tick walk every 15 ticks and restarted
the red actor's departure run every 10 ticks. `scriptSetEntityWalking` starts
the animation unconditionally, so those commands repeatedly replayed the
beginning of a stride. The scene now starts each movement once. Its existing
waits, sounds, facing changes, arrival checks and recruitment remain in place.
No model, texture, rig or animation program changes for either actor.

## SkullSatamon: posture after flatten recovery

The imported `M244SKST` keeps its source healthy battle idle in slot `0x21`.
The flatten transition starts `0x22`, the tired idle. Previously, recovery
restored the model scale and cleared the flatten flags while retaining that
stance; a healthy fighter could keep it until another action started.

`Restore-battle-idle-after-flatten-recovery.patch` selects the existing
healthy/tired idle when recovery ends. Low HP and poison still select the tired
stance. Active attacks, knockback, stun and confusion are preserved. SkullSatamon's
mesh, rig, textures, animation programs and provider pins remain unchanged.
The full nine-language build adds 52 bytes to BTL (151,248 bytes, still 74
sectors). Main BSS end stays at `0x801cdf84`, leaving 188,272 bytes of heap.
All 320 archive-backed screen setups fit; minimum margin is 3,552 bytes.

The host regression compiles the actual status-transition and idle-selection
functions with address/undefined-behavior sanitizers, covering health, poison,
the scaled native model and active reactions:

```sh
python3 tools/dev/playtest/flat_recovery_host.py build/decomp-dev build/flat-host
```

Use `--baseline` against the previous engine to reproduce the stale tired idle.

### Omnimon projectile origin

Native tracing found Prominence Beam borrowing Greymon bone 5 at `(100, 30, 0)`.
The previous scaled lookup did not match, leaving the effect on Grey's head.
Greymon mouth bones 4 and 5 now map to Garuru barrel bone 13, at the centre of
its six-vertex muzzle ring `(2, 202, 0)`. Bone-based missing rows use the same
barrel default; entity-centred impacts retain the engine's ordinary fallback.
Tremor uses range 3 and keeps its original cannon casting program.

### Greymon run and KingEtemon gestures

Greymon's native `GREY.MMD` is byte-identical to the original disc model.
Its run has 19 decoded poses with identical loop and event data. Native
MetalGreymon's model is also unchanged; the gold variant keeps the original
run program and all 21 decoded poses. Neither species receives a model gait edit.

Greymon's native run changes Euler charts at tick 17→18. Bone 19 moves only
8.8 degrees physically, but the previous 60 FPS renderer interpolated the
separate angles through a roughly 120-degree detour. The renderer now chooses
the nearer equivalent Euler chart before interpolating bones. Native tick
poses, model bytes, animation timing and the 20 FPS path stay intact. The
host regression runs 1,800 cases against the actual C helper, checks exact
endpoint orientations and bounds the repaired run seam within 0.2 degrees
of quaternion interpolation. The previous renderer reproduces the failure.

```sh
python3 tools/dev/playtest/bone_interpolation_host.py build/decomp-dev build/bone-interpolation
```

KingEtemon uses the World 2003 `M250KGET` model. Its crown, glasses and cape
agree with the [official design](https://digimon.net/reference_en/detail.php?directory_name=kingetemon).
The imported care and condition poses could leave both feet 40–100 units
above the floor, unlike their native Leomon donor. The repair changes only
the carrier height in those programs; acting, timing, events and horizontal
travel remain intact after the uniform size adjustment. The seated sleep
pose also gathers the lower cape behind the hips to keep its hem above the floor.

The victory uses native Etemon slot `0x2A`. Megaton Punch uses Etemon's own
Megaton Punch at `0x34`, replacing the imported jump-kick assignment. The
three poop throws use Etemon's Ult Poop Hell performance at `0x3A`.
These transfers retain KingEtemon's 23-bone rig and mesh. Anatomical leg
solves preserve native support and airborne clearance; wrist solves give
the raised gloves room beside the larger head. The cape panels trail the
torso. The fitted wrist tracks retain continuous Euler angles for the 60 FPS
renderer. Other attack programs, including the finisher, remain unchanged.

The final mesh and every translation are resized to 85%, with recorded
height 474 and radius 119. The original chibi pass is baked into the delta
and removed from the provider registry to prevent a second application.
The authoring recipe is `content/models/authoring/kingetemon.json`; run
`tools/models/repair_kingetemon.py` on its pinned effective input, then store
the result with `tools/models/edit.py put`.

The three throw attachment points resolve to glove bone 13. The bone-based
fallback shared by Rnd Spd Toss and Odor Spray moves from a foot to the glove.
Explicit origin mappings now also apply to entity points chosen by the missing-row fallback;
previously only a direct native table row passed through that mapping. Existing
species data had no matching entity-fallback remaps; the current audit finds
only the new fast-throw mapping affected. The engine adds no state or allocation.

Together the two engine fixes move nine-language `main_BSS_END` from
`0x801ce10c` to `0x801ce20c` (+256 bytes). Aligned heap is 187,632 bytes;
all 320 archive-backed screen setups fit, with minimum margin 2,912 bytes
on screen 207. The final KingEtemon provider uses 100,200 of 100,352 resident
bytes; its largest cold read is 6,144 of 8,192 bytes. No buffer is enlarged.

With the reviewed artifacts under `build/model-review/`, run:

```sh
PYTHONPATH=tools python3 -W ignore -m unittest tools.test_kingetemon
python3 tools/models/edit.py --from build/models5 check 303 --species-pins
```

### Status preview clearance

Status cameras reserve the heading, Life/care rows and the full vertical bob
of the sleeping badge. Grizzlymon's prior zoom already fit the panel; moving
its camera from `[-1103, 282, 1156]` to `[-806, 282, 1274]` keeps the same
45-pixel portrait height while shifting it right of the sleeping icon.

The audit covers all 291 raisable species at the first idle tick actually
rendered by the menu, including animated texture phases. It repairs 144 camera
positions (77 native IDs and 67 imports); 147 fitting positions stay unchanged.
No model, animation, field scale or combat data changes. Native camera rows are
read from each language executable, with record-original replacements applied
as at boot; imported cameras come from the archive.

```sh
python3 tools/status_portraits.py build/models5 --out build/status-audit --check
```

The camera fitter uses the smallest necessary depth increase, preserves the
old anchor where possible and verifies opaque pixels against the reserved UI.
The complete idle remains available as a conservative diagnostic, but fitting
its unseen travelling poses would shrink otherwise readable Status portraits.

## Nefertimon: Status, sleeping foreleg and voice

Species 198's high tail at the first idle tick made the Status fitter move the
whole model back to `[-1259, 319, 1584]`. The tail used roughly half the height
available above Life, leaving the face and body disproportionately small.
`nefertimon_care.py`, applied after the existing pace recipe, starts the same
83-tick idle at tick 66, where the existing tail swing is low. Every idle pose
and its closing frame remain; no events are removed. Status can then use
`[-187, 188, -325]`: its opaque bounds grow from about 49 to 77 pixels wide,
while staying 45 pixels tall and clearing the Status label, sleep badge and
Life rows. The field and battle idle share the shifted cycle.

The same layer changes only right shoulder, elbow and wrist rotations in
sleep slot 9. A two-bone solve keeps the paw on the ground and lets the elbow
follow the inherited breathing chest. The paw softly reaches forward as she
settles; the original timing, sound event, other limbs, head, wings, tail,
translations and scale channels remain. Native Garurumon's sleep is the
visual reference for the low forepaw carriage. Slot 11 is also used for care
celebrations and is unchanged.

The voice pair is now native Leomon's VBALL 42 / VLALL 3, also used by
SaberLeomon and GrapLeomon, replacing Unimon's 29 / 9. Gatomon and BlackGatomon
use Patamon's 27 / 1; Lynxmon uses Drimogemon's 34 / 7; Garurumon uses 20 / 7.
These are borrowed native banks, not imported feline recordings. There is no
Liollmon species or separate imported voice bank in the current provider.
Leomon is the large feline donor; its banks cover battle notes 53–55 and care
notes 48–52, including sleep's note 48. Pitch-correct preview WAVs were
exported for these alternatives. Auditory comparison remains unverified;
the donor choice is based on species provenance and note coverage.

Replay with the pre-care paced model available:

```sh
NEFERTIMON_BEFORE=BEFORE.MMD PYTHONPATH=tools \
  python3 -W ignore -m unittest tools.test_nefertimon_care
python3 tools/models/edit.py --from build/NAME check 198 --species-pins
```

The care tests check every preserved channel, the entire shifted idle cycle,
and the sleeping paw's ground clearance at ticks and interpolated frames.
The provider enforces the resident and cold-animation budgets. Geometry,
texture, battle clips and executable code are unchanged.

## Silphymon: Ultimate size and technique acting

The v0.0.7 player report matches two independent data problems. The corrected
head/ear and field-stride model still stands 584 units tall, above native
HerculesKabuterimon's 505-unit idle silhouette. Its species record says 567;
collision height alone does not resize the mesh. A uniform 0.80 bake reduces
the idle to about 467 units while retaining the reviewed chibi proportions.
Every animation translation, radius, height, bubble, target effect attachment
and status framing follows that scale. The original donor-side effect lookup
coordinates stay exact. Field cycles are shortened proportionately to retain
their follow pace.

Seven technique slots previously selected the same imported dive program:
Megalo Spark, Thunder Justice, Spinning Shot, Wind Cutter, Electric Cloud,
Buster Dive and Death Claw (slots 46, 48, 49, 51, 52, 55 and 59); Hurricane and Confused
Storm share Tremar, and the kick/punch/counter share Static Elect. The dive's
carrier rises from -231 to -588, explaining the upright launch before shots.

The initial attack repair is reproducible with
`tools/models/silphymon_attacks.py`. The follow-up
`tools/models/silphymon_leomon.py` fits native Leomon's motion to that resized
model: field/battle idle, walk, condition walk, run, hit, faint, get up, care
and attacks. It keeps the reviewed crouch and head/ear silhouette (about 467
units tall) and loose guard, and solves native foot paths with Silphymon's own
leg lengths. The unarmed field arm follows Leomon's free-arm motion. Ears respond two ticks behind the head.

Leomon supplies the matching physical, Static Elect and Megalo Spark
references. Its projectile fist supplies the remaining Air casts and Death
Claw, resampled to the existing technique clocks. Technique durations, effect
and sound timing, and integer entity-motion programs remain exact. In
particular, Buster Dive retains Patamon's 825-unit collision-window travel.
The voice banks are Leomon's 42 / 3, matching SaberLeomon, Lynxmon and Gryphonmon.
Those three share voice/step choices, but their original motion donors are
Monochromon, Drimogemon and Unimon respectively; shared voices alone do not
make them Leomon motion references.

Rotation fitting permits twelve angle units (about one degree). The encoded
support translation is corrected separately with zero fitting tolerance,
including intermediate display samples, so that compression cannot sink boots
through the floor. Standing strikes keep the fitted support stance while the
native pelvis turn carries into the chest. The kick solves Leomon's foot path
on the shorter legs; Buster Dive uses whole-body contact during its tumble.
Long hands and tail feathers receive bounded clearance turns, eased around
the native curves. Clearance tests include the whole mesh, not just the soles.
The previous blocking clip is retained: the native kneeling guard does not fit
this rig's long tail cleanly. The resident model uses 94,270 of 100,352 bytes;
cold reads remain within 8,192 bytes. No C, main executable allocation or engine patch
is added. The player build replays the ordinary pinned model delta.

Reconstruct the first revision with the previous recipe, then:

```sh
python3 tools/models/silphymon_leomon.py FIRST-REVISION.MMD AFTER.MMD
PYTHONPATH=tools python3 -W ignore -m unittest tools.test_silphymon_leomon
python3 tools/models/edit.py check 226 --species-pins
```

The regression assets use `build/silphymon/after/226-Silphymon.MMD` for the
first revision and `build/silphymon/leomon/226-Silphymon.MMD` for the follow-up.
Tests verify replay, unchanged resized mesh, fixed buffers, native cadence,
closed loops, effect clocks/events, exact dash trajectory and encoded support.

Use videos for visual review. `tools/dev/playtest/silphymon_video.py` records
captioned field slot playback in the actual emulator and separate real battle
attempts for every technique and the finisher. It accepts the same `EMU_PORT`,
`DW_SYMS`, disc, archive and card inputs as the species proof. Field slot
playback holds partner AI and calls the engine's animation entry point; it
is labelled accordingly and does not prove free following or combat damage.
Battle mode starts from a fresh card boot, equips the moves in the normal
combat engine and records damage in `evidence.json`. It uses the standard
technique-proof setup and starts a short recording when the requested slot
is first observed; a retry starts a fresh live encounter. HP/MP are test values. Field/follow checkpoints are for
visual review. Battle videos are silent to retain the standard test driver
timing; field clips include SPU audio. Compare with native Leomon and use `tools/animstudio.py video`
for additional donor comparisons. Videos contain disc assets and are not committed.
