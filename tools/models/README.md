# Model tools

`delta.py` owns the plain model delta codec. Source-game imports and their
reviewed field overlays remain in derive; immutable recipes remain under
`content/imports/` and `content/modeldelta/`.

Run developer tools from the repository root:

`audit_reduction.py` compares the complete private source meshes/textures with
pinned final provider outputs and writes a ranked table and six-view contact
images. See [the audit guide](../../docs/mods/mesh-reduction-audit.md) for source
setup, coverage limits and interpretation.

```sh
python3 tools/models/edit.py get 183
python3 tools/models/edit.py --from build/everything check 183 --species-pins
python3 tools/models/verify_deltas.py verify --sources DIR
python3 tools/models/audit_origins.py --help
python3 tools/models/audit_textures.py disc DISC_DIR   # faces sampling noise, palettes or empty texels
python3 tools/species.py --content BUILD/species flat-audit BUILD/DIGI.DAT BUILD/ALLTIM.TIM   # every flat sprite
python3 tools/flatsprite.py sheet OUT.png DISC_DIR      # every species' flat frames on one sheet
```

`tools/flatsprite.py` gives each texture the frames a flattened Digimon is drawn with (the species' icon in the
originals' two colours, where the model leaves room); the build runs it for DIGI.DAT and the disc's ALLTIM.TIM.

The editor can extract the three source games with repeated `--source-disc`
arguments. `--from DERIVE_OUT` reuses their extracted inputs. Its cache lives in
`build/imported-model-edit/`; accepted models still have to pass every
source, delta, target and species pin. Rejected edits leave deltas and pins intact.
Species pins cover the final provider output, including technique repairs on
models without field overlays and models selected by native builders.
The origin audit uses a disposable workspace outside the repository.

Other conversion and animation entry points remain at their recorded paths:
frozen import recipes refer to those paths. Do not move them or rebase their
deltas as a side effect of a package cleanup.

Reviewed field generators and channel helpers live in `field_animations/`. The
provider registry names their full Python modules. These modules retain direct
script entry points where the original generator had a CLI. Model codecs and
converters referenced by frozen recipes keep their recorded entry paths.

The frozen model-delta README retains its historical command spellings. Use
`tools/models/delta.py` for the codec and `tools/models/edit.py` for the editor;
`tools/models/edit.py --help` describes get/put/check/rebase and source-disc
options. Earlier editor work directories are now `build/imported-model-edit/`.

Species 290 (Clockmon): `field_animations/clockmon_gait.py` writes slots 0, 2, 3 and 4 again (a 90-tick idle, a 12-tick
walk, a 14-tick tired walk, an 8-tick run at 15, 10 and 38 units a tick) on the importer's model: the chassis is placed
per tick, the rider swings on after it, each toe stays planted in stance and the short legs are carried by chassis yaw
and a scheduled foot roll. `python3 -m tools.models.field_animations.clockmon_gait --source SRC.MMD --out-dir DIR`
(SRC from `edit.py get 290` before the change), then `edit.py put 290 DIR/290-Clockmon.MMD`; the reviewed-source pin in
`content/models/imports/celebrations.json` follows the new model. Test: `tools.test_clockmon_gait` (`CLOCKMON_MODEL`).

Species 329 (Ghoulmon): `field_animations/ghoulmon_gait.py` writes slots 2, 3 and 4 again (a 26-tick walk, a 34-tick tired walk and a
14-tick run at 17, 11 and 38 units a tick; the idle is kept) with `quadruped.py` on the model's own two legs: planted flat soles with heel
strike and toe-off, hips against torso, swinging arms with late forearms and claws, flapping wing membranes and a whipping three-link tail.
`python3 -m tools.models.field_animations.ghoulmon_gait --source SRC.MMD --out AFTER.MMD` (SRC from `edit.py get 329` before the change),
then `edit.py put 329 AFTER.MMD`. Test: `tools.test_ghoulmon_gait` (`GHOULMON_MODEL`).

Species 297 (Marsmon): `field_animations/marsmon_gait.py` writes slots 0, 2, 3 and 4 again (a 150-tick idle, a 22-tick walk, a 26-tick tired
walk and a 14-tick run at 16, 11 and 38 units a tick) with `quadruped.py` on the model's own two legs: planted boots
with their outward splay, hips against shoulders, swinging, opening fists and a trailing cape, and a swaggering, proud character (the idle shifts the weight, looks aside, raises a fist and flicks the cape).
`python3 -m tools.models.field_animations.marsmon_gait --source SRC.MMD --out AFTER.MMD` (SRC from `edit.py get 297`
before the change), then `edit.py put 297 AFTER.MMD`. Test: `tools.test_marsmon_gait` (`MARSMON_MODEL`).

Species 352 (Monmon): `field_animations/monmon_gait.py` writes slots 0, 2, 3 and 4 again (a 60-tick idle; a 24-tick skipping walk, a 28-tick tired walk and a 20-tick run, two different ground cycles each, at 16, 11 and
36 units a tick) with `quadruped.py` on the model's two legs after mirroring the import's lopsided rest pose onto the left side (`rest_fix`): planted feet on short quick steps (a long-short skip, a bouncing body), a head that tilts from side to side, the
gloves swinging against the feet and the leaf, club and tail trailing on springs. It blinks: the eye is painted on the head texture, so `field_animations/monmon_face.py` stamps a half-shut and a shut frame into the texture's free rows and each clip copies them over the eye (texture moves).
`python3 -m tools.models.field_animations.monmon_gait --source SRC.MMD --out AFTER.MMD --tex SRC.TIM --out-tex AFTER.TIM` (SRC from `edit.py get 352` before the change), then
`edit.py put 352 AFTER.MMD AFTER.TIM`. Test: `tools.test_monmon_gait` (`MONMON_MODEL`).

Species 318 (Gallantmon): `field_animations/gallantmon_gait.py` writes slots 0, 2, 3 and 4 again (a 120-tick idle, a 24-tick walk, a 30-tick tired
walk and an 18-tick run with a flight phase, at 16, 11 and 38 units a tick) with `quadruped.py` on the model's own two legs: planted soles, a weighted
knight's body (hips against shoulders, the lance arm and the shield arm swinging apart, pauldrons following, plume and cape trailing late). Slots 33, 35 and 36
play the new idle, walk and run. `python3 -m tools.models.field_animations.gallantmon_gait --source SRC.MMD --out AFTER.MMD` (SRC from `edit.py get 318`
before the change), then `edit.py put 318 AFTER.MMD`. Test: `tools.test_gallantmon_gait` (`GALLANTMON_MODEL`).

Species 320 (Growlmon): `field_animations/growlmon_gait.py` writes slots 0, 2, 3 and 4 again (a 96-tick idle, a 32-tick walk, a 44-tick tired
walk and a 28-tick run at 16, 11 and 36 units a tick, each walking clip two different cycles) with `quadruped.py` on the model's own two
legs: planted feet, hips against shoulders, swinging arms, springs on neck, head and jaw and a three-link tail that trails the hips; a heavy
brute's character, and blinking eyes (`growlmon_face.py`: eye frames in spare texels, pasted over the painted eye by texture-move events).
`python3 -m tools.models.field_animations.growlmon_gait --source SRC.MMD --out AFTER.MMD --tex SRC.TIM --out-tex AFTER.TIM` (SRC from
`edit.py get 320` before the change), then `edit.py put 320 AFTER.MMD AFTER.TIM`. Test: `tools.test_growlmon_gait` (`GROWLMON_MODEL`).

Species 324 (Maildramon): a native binding (Unimon donor) whose recipe asks for the post-chibi stage `field_animations/maildramon_gait.py`
(`"gait": "maildramon_gait"` in `content/models/imports/native-bindings.json`), which writes slots 2, 3 and 4 again with planted
legs under the donor's own trunk, wings and tail (`quadruped.py`, profile key `claws`). It runs in the build; offline:
`python -m tools.models.field_animations.maildramon_gait --source BOUND.MMD --rig 324-report.json --out OUT.MMD`. After changing it,
`edit.py put 324 MMD TIM --force` rewrites the species pin. Test: `tools.test_maildramon_gait` (`MAILDRAMON_MODELS`).


Species 304 (Divermon): `field_animations/divermon_gait.py` writes slots 0, 2, 3 and 4 again (a 240-tick idle; a walk, tired walk and
run of two different strides each, 32, 36 and 24 ticks at 18, 12 and 36 units a tick) with `quadruped.py` on the model's two legs: boots flat with a 7 degree splay,
pelvis against chest, a level harpoon arm, and head, arms, ears, tank and tail as damped springs that differ from one stride to the next (the
profile's `vary` hook; the legs repeat so the feet stay planted). v3 adds a little hop (an extra aerial lift and a springier landing squash
at each footfall) and a wobble (hip and chest roll, a pelvis sway across the feet, a head cock, swinging tank and ears), and a face:
`field_animations/divermon_face.py` pastes spare-texel frames over the painted eye and the strip of teeth with texture moves (the profile's
`events` hook replaces the source clip's own), so the eyes blink (3-5 ticks, a few per idle, one per stride) and the mouth breathes in the idle,
pants in the run and droops when tired; `--tex SRC.TIM --out-tex AFTER.TIM` writes the stamped texture, `edit.py put 304 AFTER.MMD AFTER.TIM`.
`python3 -m tools.models.field_animations.divermon_gait --source SRC.MMD --out AFTER.MMD` (SRC from `edit.py get 304`
before the change), then `edit.py put 304 AFTER.MMD`. Test: `tools.test_divermon_gait` (`DIVERMON_MODEL`).

Species 373 (WarGreymon): `field_animations/wargreymon_gait.py` is a field overlay in the same way: the chibi proportions, then slots 0 (also 33), 2, 3 and 4 written again with `quadruped.py` and a body hook on one shared gait phase (pelvis weight shift, hip/chest counter-turn, lagging head, arms swinging against the legs with trailing claws, back plates, cloth and thigh plates, springs for the follow-through); walk and run are two cycles each (44 and 24 ticks), the tired walk one slumped cycle of 28, the idle 96 ticks. Test: `tools.test_wargreymon_gait` (`WARGREYMON_MODEL`). `quadruped.py` profiles may now set `tol` (the encoder tolerance, one value or one per bone) and a gait's `plateau`.

Species 308 (Dinohyumon): `field_animations/dinohyumon_gait.py` is a field overlay (like Hookmon's): it applies the chibi
proportions and then writes slots 0 (also 33), 2, 3 and 4 again with `quadruped.py` on the two legs: a 96-tick idle, a
walk, tired walk and run of two different cycles each (32, 60 and 28 ticks) at 17, 11 and 38 units a tick, each foot planted with a constant
30 degree outward splay; cycle B lifts, lands and bobs unlike cycle A and the clip eases from one into the other (`compose` hook in
`quadruped.py`), and the arms, head, feather and loincloth follow through on loose springs (the chibi clips flipped the feet by up to 167 degrees and slid the tired walk's soles 172 %).
Bound in `content/models/imports/species.py`; test `tools.test_dinohyumon_gait` (`DINOHYUMON_MODEL`, from `edit.py get 308`).

Species 322 (Kyukimon): `field_animations/kyukimon_gait.py` is a field overlay (like Dinohyumon's): it applies the chibi
proportions and then writes slots 2, 3 and 4 again with `quadruped.py` on the two legs, in two different cycles each (32, 44 and 28
ticks) at 18, 13 and 36 units a tick with planted feet. One gait phase drives the whole body: hips, body and chest wind against each
other, the arms swing against the legs, the head steadies and follows late, the five tail segments pass a wave down the tail, the strap
and the wing spikes trail (the chibi clips played the idle's own 74-tick loop on every bone above the hips and left head, hands, strap
and wing spikes still). The idle (slot 0, also 33) is the chibi build's. Bound in `content/models/imports/species.py`; test
`tools.test_kyukimon_gait` (`KYUKIMON_MODEL`, from `edit.py get 322`; the test applies the species' slot aliases like the build).

Species 334 (Mummymon): `field_animations/mummymon_gait.py` is a field overlay of the same kind: after the chibi proportions it
rewrites slots 2, 3 and 4 (the idle is the chibi's own: it does not slide) with `quadruped.py` on its two hind legs, the soles pivoting
at the ball of the foot: a walk, tired walk and run of two cycles each (30, 40 and 28 ticks) at 16, 11 and 38 units a tick, eased one into the other,
with the arms, head, hat, strips and rifle following on loose springs and the rifle arm carried bent so the gun stays off the floor (the chibi clips
slid the soles 65 to 202 % of the travel). `quadruped.py` takes a per-bone `tol` from the profile to keep the clips inside the resident buffer.
Bound in `content/models/imports/species.py`; test `tools.test_mummymon_gait` (`MUMMYMON_MODEL`, from `edit.py get 334`).

Species 335 (MegaGargomon): `field_animations/megagargomon_gait.py` is the base generator of its celebrations overlay: it applies the chibi
proportions and writes slots 0 (also 1, 18, 33), 2, 3 and 4 again with `quadruped.py` (80-tick idle; walk, tired walk and run of two
cycles, 17, 11 and 36 units a tick), with the torso, hips, cannons, arms, head, fins and flaps moving on loose springs. New keys: a gait's
`clear` (floor margin for fast legs) and the profile's `tol` (encoder tolerance, per bone). Bound in `content/models/imports/celebrations.json`;
test `tools.test_megagargomon_gait` (`MEGAGARGOMON_MODEL`: the model the overlay receives).

Species 351 (Kotemon): `field_animations/kotemon_gait.py` writes slots 2, 3 and 4 (26, 30 and 22 ticks at 16, 11 and 36 units a
tick) inside the `kotemon-field` overlay (`imported_equipment.py`, which then repairs the hidden swords and the hit clips): each
foot is placed first, the thigh stub slides at most 10 units under the skirt and the leg turns to reach it, the foot rolls (heel strike with the outer edge first, toe push-off, flex before landing) and the two feet and two cycles lift differently, every touchdown presses the hips and skirt down (`squash`, `sway`), the shoulders move as one unit about the shinai's grip, and the upper body bounces on a spring on each beat (`hop`).
Test `tools.test_kotemon_gait` (`KOTEMON_MODEL`, from `edit.py get 351`); the pin in `species-pins.json` is checked with `edit.py check 351 --species-pins`.

Species 319 (Pharaohmon): `field_animations/pharaohmon_gait.py` is a field overlay on top of the celebrations recipe: it
rewrites slots 3 (tired walk, 56 ticks at 11 units a tick) and 4 (run, 24 ticks at 36) with `quadruped.py` on the two legs,
planted soles and two different cycles each (the `compose` hook); the idle and the walk are the celebrations build's, untouched.
`python3 -m tools.models.field_animations.pharaohmon_gait --source EDIT.MMD --out AFTER.MMD` (EDIT.MMD from `edit.py get 319`).
Bound in `content/models/imports/species.py`; test `tools.test_pharaohmon_gait` (`PHARAOHMON_MODEL`, from `edit.py get 319`).

Species 321 (Knightmon): `field_animations/knightmon_gait.py` is the base generator of its celebration overlay (the one
that keeps slots 11 and 42): it applies the chibi proportions and then writes the tired walk (slot 3, 22 ticks at 11.5
units a tick) and the run (slots 4 and 36, 16 ticks at 38) again with `quadruped.py` on the two legs (thigh, knee guard that
follows, knee, foot, toe plate). The two legs step half a cycle apart with the same lift and stance, so the tired walk is
even (the previous clip stood the left foot 10 ticks and the right 5, slid 79 % and lifted 74 against 58 units: a limp; the
previous run slid 61 and 26 %, 17 ticks a cycle, root steps 26 to 50). The arms swing as pendulums (the sword arm half as much),
the forearm and the sword late, head, cloak, scabbard and loincloth on loose springs. The idle and the walk are untouched
byte for byte. Bound in `content/models/imports/celebrations.json` (`base_generator`); test `tools.test_knightmon_gait`
(`KNIGHTMON_MODEL`, from `edit.py get 321`).

Species 327 (Gargoylemon): `field_animations/gargoylemon_gait.py` is a field overlay in the same way: it applies the chibi
proportions and then writes slots 0 (also 33, now one animation), 2, 3 and 4 again with `quadruped.py` on its two hind legs
(a profile `toes` entry merges the toe bone into each foot's sole): a 120-tick idle with breathing, glances and a raised arm, and a
walk, tired walk and run of two different cycles each (36, 52 and 24 ticks) at 16, 10 and 36 units a tick, each foot planted
(slip under 6 %). The long arms swing from the shoulder with the claws late, the wings follow the body's rise and fall on a
spring (each wing is one bone: no tip lag), the tail and head trail. Bound in `content/models/imports/species.py`; test
`tools.test_gargoylemon_gait` (`GARGOYLEMON_MODEL`, from `edit.py get 327`).

Species 432 (Bastemon): `field_animations/bastemon_gait.py` (test `tools.test_bastemon_gait`, `BASTEMON_MODEL` from `edit.py get 432`)
is the overlay generator of its import ('bastemon-field' in `content/models/imports/species.py`): it runs the celebrations' build
(chibi proportions and the salute) and then writes the idle, walk, tired walk and run again from one gait phase per clip. The
earlier clips were not planted (stance slip 39 % mean and 141 % worst in the walk, 27 and 184 % tired) and the run went at 38.5 units a tick.
Now `quadruped.py` plants each sole and the body sits lower on bent knees (the chibi legs are nearly straight at rest, so a planted stride
needs the bend); the hips and the body wind against each other, the upper arms swing against the legs on their sides with a late
forearm, the head follows late, the hair and the two hip ribbons carry a wave down each chain (they stream out in the run) and every
loose part passes through a spring; two eased cycles per clip. Walk 12 ticks a cycle at 15 units a tick (24 ticks), tired walk 14 at 10.5
(28), run 10 at 36 (20), idle 60. Studio stance slip (mean, worst; the studio counts the foot bone): walk 3 and 7 %, 5 and 43 % (two feet); tired 19 and 40 %, 14 and 33 %; run 12 and 36 %, 12 and 36 % (the
foot bone is still counted while the heel peels; the soles themselves are planted to under 1 %, as `quadruped.py` measures). Weaker: ten part pairs
brush a few vertices more than the chibi clips do (ribbon against arm and thigh, forearm and head against the torso, thighs against the hips in
the tired walk; 344 against 346 in the pair maxima summed, pinned in the test), and the swinging feet of the walk and the tired walk step
3.4 to 3.6 times their median tick (every other bone stays under 2.5).

Species 354 (Renamon): `field_animations/renamon_gait.py` (test `tools.test_renamon_gait`, `RENAMON_MODEL` from `edit.py get 354`)
is the overlay generator of its import ('renamon-field' in `content/models/imports/species.py`): it applies the chibi
proportions and then writes the idle, walk, tired walk and run again from one gait phase per clip. The chibi clips replayed the
idle's loop on the tail and hands (equal to the idle's ranges to a tenth of a degree), left head and body nearly still and
turned each shoulder in one channel, so only the legs followed the stride. Now the hips and body wind against each other, the
arms swing against the legs on their sides with a soft elbow and a late hand, the head follows late and the four tail segments
carry a wave, the torso undulates in an S, the hands flick a little paw every stride, with two eased cycles per clip and loose springs on arms, head and tail. Feet stay planted (`quadruped.py`); the step is a cat's line: a low smooth lift, a quiet heel-first landing, hind feet almost in front of each other (`step_style` in the generator: `lift`, `arc`, `heel`, `settle`, `track`).
Walk 28 ticks at 16 units a tick (stance slip 6 % mean, 37 % worst; before 48 ticks at 13, 3-4 and 8 %), tired walk 40 at 11
(4 and 34 %; before 48 ticks, 5 and 16 %), run 24 at 40 (7 and 27 %; before 56 ticks, 3 and 6 %), idle 60 ticks (before 53),
root speed constant. Weaker: the run's stance slip is higher (worst 27 against 6 % in the studio metric) and
its second difference peaks higher on the short cycle (59 against 69 degrees per tick squared on a leg bone).

Species 202 (Submarimon): `repair_submarimon.py` removes four stencil faces that sit on its body plates and keeps the
rear screw turning in every clip (see player-model-fixes.md); `python3 -W ignore -m unittest tools.test_submarimon`.

Species 224 uses `metalgreymon.py`: native DW1 MTGR.MMD and ALLTIM entry 12,
recoloured gold at build time. Its native rig, field and care programs are kept;
technique slots select unchanged native clips while retaining 224's move list
and save slots. The provider registry selects its `builder` during imports.
See [motion](../../docs/reference/motion.md#metalgreymon-vaccine-donor-provenance)
for palette selections, technique routing and storage. Run
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_native_metalgreymon`.

Species 470-477 are the hand-made babies (`babies/`): a DW1 donor baby's rig and
animations with our mesh and texture, replayed from plain deltas
(`content/modeldelta/babies.json`); `babies/authoring/` holds the drawing scripts.
Run `python3 -m tools.models.babies check` and
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_native_babies`.

Piedmon (245) played one 104-tick floating gesture in its idle, walk, condition walk and run (the three walks differed
only in root speed and arm amplitude), and the boots, which never touch the ground, slid with the body.
`field_animations/piedmon_levitate.py` writes slots 0 and 1 (idle), 2, 3 and 4 again as four levitating clips: a
breathing idle (104 ticks), a glide (24), a slumped glide (28) and a leaning run (20) with the importer's root speeds,
the same mean hover height of the body (44 units above the ground, ribbons aside), arms, boots, collar and ribbons that
follow the body a little later, and exact loops. Slots 18 and 33 keep the native idle. Stored in the plain delta
(`python3 -m tools.models.field_animations.piedmon_levitate --source SRC --out AFTER.MMD`, then
`tools/models/edit.py put 245 AFTER.MMD`); check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_piedmon_levitate`.

Kiwimon (282): `field_animations/kiwimon_gait.py` rewrites the walk, tired walk and run (slots 2, 3, 4; 36 plays the run)
with `quadruped.py` on its own legs (3-6 left, 7-10 right: thigh, shin, ankle pad as the planted paw, toes riding on it);
the imported clips had borrowed another leg length (a 60-unit body bob, one leg swung 85 units, soles sliding up to 100 %).
The body, head, beak and rump are written by the module's `body` hook, the toes by `extra`; the idle (slots 0 and 33) is a calm 60-tick loop on planted soles. Offline delta:
`python3 -m tools.models.field_animations.kiwimon_gait --source SRC --out AFTER.MMD`, then `tools/models/edit.py put 282 AFTER.MMD`;
check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_kiwimon_gait`.

DemiDevimon (236) binds its imported mesh to Birdramon's native skeleton and
programs through `field_animations/native_binding.py`. The recipe in
`content/models/imports/native-bindings.json` assigns every rigid piece, fits
the wing spars and trailing web, and scales native translations once. Native
timing, rotations, scales and controls remain intact. Texture-copy commands
are removed because the imported atlas has another layout; effect origins
use the scaled native joints. The imported delta and texture remain pinned.

WarGrowlmon (326) wears Growlmon's (320) skeleton and field programs: recipe `326` in `native-bindings.json`, with `donor_species` 320 (the
donor is an imported species, so `native_binding.py` reads its model from the imported base models, `BASE_MODELS`, instead of the DW1
extraction, and `edit.py` hands that model to the provider pin and `chibi_proportions.py` to its check). The `stretch` piece rule scales a
piece unevenly along the world axes. After Growlmon's delta changes, renew `donor_sha256` in the recipe and re-pin 326
(`edit.py put 326 FILE --force`). Test: `tools.test_native_bindings` (needs `edit.py get 320`).

BomberNanimon (232) wears native Nanimon's (53, `NANI.MMD`) 20-bone skeleton and every animation program, unchanged
(scale 1): its 13 rigid pieces map one to one onto Nanimon's joints (arms and legs swung joint to joint, gloves and
boots turned with their forearm and shin, the body and fuse set 4 up and 22 forward of its old place) and its
techniques play Nanimon's clips (training slot 57 is Nanimon's training clip, hit tick 10). Recipe `232` in
`native-bindings.json`; the overlay runs on the model of the plain delta, whose earlier boxer clips stay only as
provenance. `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_bombernanimon_native` (after
`edit.py get 232`) pins the field slots to Nanimon's.

Replay the native binding checks with the original DW1 extraction present:

```sh
BINDING_MODELS=build/imported-model-edit/edit PYTHONPATH=tools \
  python3 -W ignore -m unittest tools.test_native_bindings
```

Use `tools/models/edit.py get 236` to populate that folder first. Provider
checks (`check 236 --species-pins`) also regenerate and verify the final rig.

Measure final field speeds and voice-note coverage with:

```sh
python3 tools/models/audit_field.py --from build/dev-everything --out build/field-audit.json
PYTHONPATH=tools python3 -m unittest tools.test_field_audit tools.test_model_provider
```

The audit uses each overlay report's generated skeleton. Its JSON includes
walk/condition/run durations, root travel per tick, bank-4 notes and missing
voice tones. Long programs (40 ticks or more) need an in-game switch-latency
measurement as well as an offline speed measurement.

Imported bone-scale consistency, the complete corrected-species list and the
replay commands are documented in [the scale audit](../../docs/reference/motion-scale-audit.md).

Vilemon (295) wears native Ogremon's (34, `CHDAT/MMD1/OGRE.MMD`) 18-bone skeleton at scale 0.72, so its hips, shoulders and
head sit where Vilemon's own do; its 20 bones map by body part (chest, pelvis, thigh, shin, foot, left and right arms, head, jaw).
The toes ride the foot bone and the fist rides the hand bone. Ogremon has no wing bones, so the two wings sit rigid on the
chest (placed by `pieces` offsets) and sway with it. Slots below the techniques are Ogremon's own programs (idle 16, walk 22,
condition walk 24, run 20 ticks); at the scale the walk is 17.6, the condition walk 16.2 and the run 36.1 units per tick, so the
condition walk stays slower than the walk with no retiming. The 11 techniques play Ogremon's clips by range (punches and
kicks, claws, fire, quake, war cry) and the training slot 57 plays Sonic Jab's. The wings and jaw are the only parts with a
different body than Ogremon's: the upper-arm shoulder vertices overlap the chest box by 3 to 4 of 28 in every pose, forearms
and fists never do. `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_vilemon_native` (after `edit.py get 295`).

Minotarumon (330) wears native Ogremon's (34, `CHDAT/MMD1/OGRE.MMD`) 18-bone skeleton at scale 0.88: its 20 bones map by body
part (pieces 17, 19 and 20 to Ogremon's head, 5 and 6 and 9 and 10 each pair to one foot), pieces 6, 10, 19 and 20 share a
donor bone and are placed by `pieces` offsets, and the recipe's `spread` fits the pieces on the donor's joints. The idle is
Ogremon's own (16 ticks); the walk, condition walk and run are its clips retimed by `pace` (22 ticks at 18, 30 at 13, 20 at 41 units
per tick). Species pin: `edit.py put 330 ... --force`; its model delta is unchanged, so only the provider pin in
`species-pins.json` changed. `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_minotarumon_native` (after `edit.py get 330`).

HiAndromon (302) wears native Andromon's (40, `CHDAT/MMD1/ANDR.MMD`) 21-bone skeleton at scale 1.2 (mesh pieces scaled by
0.857 so the chibi proportions stay): its 25 bones map by body part (chest and chest plates to the torso, each shoulder
armour to its own side's shoulder pivot, wrist and hand to the hand, heel and toes to the foot). Slots below the techniques
are Andromon's own programs (idle 20, walk 20 ticks; the condition walk, 22 ticks, rounded off by `pace`'s `smooth`: a cyclic [1, 2, 1] filter, repeated, over rotations and the root's travel per tick) and the run retimed to 18 ticks by `pace` (its
`close` key makes the last pose the first, for a donor loop that closes only within a unit or two). Speeds are 25.2, 19.7
and 40 units per tick. Andromon's left foot slides in its own stance, so foot slip is native, not repaired.
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_hiandromon_native` (after `edit.py get 302`).

GrapLeomon (306) wears native Leomon's (48, `CHDAT/MMD1/LEOM.MMD`) skeleton at scale 0.98 and its idle, walk, condition walk, run and
technique clips; the mesh is unchanged. The forearm and shin drums sit on four extra bones appended to the rig (`spin` in the
recipe: `bones` {source bone: spin axis in its own frame, `sign`}, `quarters` {slot: quarter turns per loop}) that turn about
their own axis in the four field clips while the donor bones carry them along. `PYTHONPATH=tools python3 -W ignore -m unittest
tools.test_grapleomon_native` (after `edit.py get 306`).

Assaultmon (310) wears native Centarumon's (36, `CHDAT/MMD1/CENT.MMD`) 27-bone skeleton at scale 1.45 with the recipe flag
`spread_fit` (pieces fit on the donor joints after the `spread` offsets). Four legs go onto four legs (front 4 bones on 3, hind 3
on 4), arms and guns on the arm bones, the shoulder cannons rigid on the torso. `pace` rows with `ground` retime the walk (20 ticks,
25.4), tired walk (30, 17.0) and run (21, 48.2) and keep the soles on the floor. Stance slip stays above the usual limits and the
run's closing tick jumps; the notes are in `docs/reference/motion.md`.
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_assaultmon_native` (after `edit.py get 310`).

Zudomon's reviewed model is uniformly resized to 85% with `resize.py`, including
mesh vertices and translation tracks in every clip. Its radius, height and
bone-local effect/bubble offsets use the same factor. Rotation, visibility,
timing, sounds and technique assignments remain unchanged. The resize is stored
through `edit.py put`, so no later field generator can restore the larger size.
`tools.test_zudomon_size` compares decoded acting and world-space mesh points
across all clips, including the hammer, with the before/after models supplied
as `ZUDOMON_BEFORE` and `ZUDOMON_AFTER`.

Angewomon keeps the original mesh, rig and acting, with the existing field
celebrations baked before a uniform 0.74 resize of mesh vertices and animation
translations. Its helmet height is close to native Angemon at a shared world
scale. World 2 and World 3 mesh trials on Angemon and Myotismon did not improve
the posture and wing silhouette, so their bindings are excluded. The model
provider uses the resized delta directly.

`PYTHONPATH=tools python3 -m unittest tools.test_angewomon_size` checks the
reviewed before/after files under `build/angewomon-redo/`; override them with
`ANGEWOMON_BEFORE` and `ANGEWOMON_AFTER` for reconstructed inputs.

The six-species [creature motion review](../../docs/reference/reviewed-creature-motion.md)
records native-donor field/care changes, uniform sizes, sound donors and replay
checks. `reviewed_motion.py` authors its pinned plain deltas offline; player
builds use those deltas directly.

Garbagemon's can uses the idle attachment to its torso across every occupied
clip. The Piximon retarget had assigned an independently moving appendage to
the can, separating it from the body during attacks and care animations. The
repair in `field_animations/garbagemon.py` keeps the arms, head, lid, gun, root
travel, timing and support height. Its eating loop is expanded without changing
its played duration or events. The plain model delta stores the repair; no
runtime allocation or rig change is needed. Inherited bank-1 note-15 wing cues
are removed, retaining the existing Sukamon battle and care voices.

With reconstructed before/after models, run `GARBAGEMON_BEFORE=BEFORE.MMD
GARBAGEMON_AFTER=AFTER.MMD PYTHONPATH=tools python3 -W ignore -m unittest
tools.test_garbagemon_attachment`. It checks the attachment and grounding over
every occupied clip, unchanged acting and semantic events, absence of wing
cues, and original-console resident/cold-animation storage limits.

Garbagemon's (269) face acts by texture moves: the eyes blink (open, half shut, shut) and the grin opens (closed, half,
wide: the upper teeth slide up and the lower ones down over a dark mouth). The frames sit in texels no face samples,
stored as the small bands that differ from the painted picture, and every clip starts and ends with open eyes and a shut
mouth. The idle (slots 0, 1, 18 and 33 share it) is the old 19-tick loop repeated seven times so that it holds an
irregular blink, a double blink and a slow yawn; the walk, tired walk and run keep their lengths. Run
`python3 -m tools.models.field_animations.garbagemon_face --out AFTER.MMD --tim-out AFTER.TIM` on the model before this change
(`edit.py get 269`), then `edit.py put 269 AFTER.MMD AFTER.TIM`; check with `tools.test_garbagemon_face`.

Zudomon's (219) walk, condition walk and run took their legs from a gait solver
but kept the idle's slow 96-tick performance in the chest, head, arms, hammer
and tail, so the halves moved on different beats (one upper beat per four steps
in the walk, per eight in the run). `field_animations/zudomon_gait.py` puts the
upper body on the legs' beat: pelvis and chest counter-rotate (the hips turn
back so the feet stay), the chest leans over the planted foot, the free arm
swings against its leg, the hammer arm swings a third as far and lags it, and
the tail sways against the hips; the run leans forward and the condition walk
droops. The hammer carry is lifted just enough to keep the head off the floor.
Legs, root travel, loop lengths and footstep sounds are unchanged; the channels
are stored at tolerance 7 to stay inside the resident animation buffer with the
Buster Dive clip: `--source build/imported-model-edit/edit/219-Zudomon.MMD
--out AFTER.MMD`, then `tools/models/edit.py --from build/everything put 219 AFTER.MMD`.

Rosemon's (230) walk, condition walk and run had their legs stepping five, five
and eight times per loop while the pelvis, chest, head, arms, cape and braid
replayed the idle's 83-tick performance once per loop, and the planted foot
slid at 30-40% of the body's speed. `field_animations/rosemon_gait.py` (the
`after_generator` of its `pace.json` row, run on the paced clips) rewrites slots
2, 3 and 4 from one step phase: feet fixed in the world while they support, heel
to toe roll, lifted swing, pelvis height from the reach of both legs, pelvis and
chest counter-turning, arms against the opposite legs, cape, braid and leaves
lagging. Every channel holds a whole number of cycles per loop. The arms are a
pendulum from the shoulder: the elbow trails it by an eighth of a cycle and the
wrist trails the elbow, the left arm is about a tenth smaller and slightly later,
and the upper arm twists and the shoulder lifts with each step; they stay clear of
the hips and skirt at every tick. The run is a light jog, five strides per loop (16 ticks a cycle), shaped
on the proportions of a native humanoid run (Angewomon's): each foot on the ground about a third
of the cycle, the foot landing under the body and pushing off far behind it, a low
heel lift (about 55 units), the legs nearly straight in stance and folding to about 95 degrees in the swing, a pelvis bob of about 10 units, a few degrees of forward lean and arms that swing
about 30 degrees with the hands between hip and chest height. The
idle (slot 0) is rewritten too, standing upright instead of leaning back, with the
feet planted and the same 83-tick loop. Loop lengths and root speeds are
unchanged; footstep sounds are re-placed at the heel strikes. Leg channels are
stored at tolerance 2 (the feet stay planted), arms at 9 and the rest at 24, to
stay inside the resident animation buffer (99952 B).
`tools.test_rosemon_gait` needs the paced model in `ROSEMON_PACED`.

Valkyrimon (255) uses a uniform 0.8 resize and native Angemon field motion,
with its existing rig and chibi proportions. The offline authoring recipe is
`field_animations/valkyrimon.py`; `field_animations/valkyrimon_limbs.py` then clears the limbs from the body (elbow and hips turned a few degrees where
they went through the chest or the other leg), calms the walk and run, keeps the legs apart, hangs the left thigh's
cloth from the pelvis and gives the idle breathing, keeping the timing (checked by
`tools/test_valkyrimon_limbs.py`); player builds replay the plain delta.
[The motion notes](../../docs/reference/valkyrimon-motion.md) record the source
mismatch, size comparison, replay commands and original-console checks.

Aquilamon (188) had one 89-tick flight flap in its idle, walk, condition walk
and run, the whole bird climbing about 300 units on every downstroke and gliding
back to the floor. `field_animations/aquilamon.py` keeps that flap and holds the
bird at a steady hover (the climb scaled to 15-22%, the wing tips just clearing
the floor at the bottom of the downstroke); the walk plays the beat 1.25 times
faster and the run twice as fast, pitched further nose-down:
`--source build/everything/imported-models/188.MMD --out AFTER.MMD`, then
`tools/models/edit.py --from build/everything put 188 AFTER.MMD`.

Hawkmon (184) had its right foot bound turned about 58 degrees outward in every
clip, a walk, condition walk and run that pushed the feet up to 60 units into
the floor, and an idle that rose onto its tiptoes. `field_animations/hawkmon.py`
keeps its own clips (the walk hops as before, its cycle eased from 12 to 16
ticks; the run keeps 12 ticks with the body leaning forward, the wings swept
back and beating, a longer stride and a higher hop that lifts both feet) and
corrects the feet per tick: the right foot turned forward, a foot on the floor laid as flat as its
reach allows, a foot under the floor raised inside its leg; the idle keeps a
quarter of its rise.

Lillymon (209) had the idle, walk, condition walk and run as one frozen pose that only the root travelled through.
`field_animations/lillymon_flight.py` runs after her celebration overlay and writes those five slots again: a hover
with a gentle three-beat flutter, a forward-leaning cruise with two wing beats per loop and a streamlined, faster run
with three, the legs, arms, hair and flower following the body a beat later. Tick counts, distance per loop and footstep
sounds are kept (the run's travel is spread smoothly over the loop instead of in bursts). Check with
`tools/models/edit.py get 209` and `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_lillymon_flight`.

LadyDevimon (223) had the same frozen field slots: none of her bones moved, only the root travelled.
`field_animations/ladydevimon_flight.py` (overlay `ladydevimon-flight`) writes the idle, walk, condition walk and run
again on her reviewed model as four different, easy flights: an upright hover (60 ticks, two slow beats), a glide leaning
10 degrees with the wings spread and held, a low, heavy tired walk with drooping wings, hanging head and limp legs, and a
dash leaning 23 degrees with the wings swept back and the legs streamlined. Hair, cloth and chain lag. Tick counts (idle
excepted), distance per loop, footstep sounds and hover height are kept (the tired walk sits lower on purpose).
Check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_ladydevimon_flight`.

Quetzalmon (249) held one frozen pose in all four field clips (not one bone moved, only the root travelled).
`field_animations/quetzalmon_flight.py` (overlay `quetzalmon-flight`) writes the idle, walk, condition walk and run
again as four flights: a hover (54 ticks, two beats), a steady flight leaning 15 degrees, a low, heavy tired flight with
hanging wings and a nodding head, and a leaning flight of three slow beats in 48 ticks for the walk and a lighter flight of two beats in 20 ticks for the run, wings kept low and spread, with the body, neck, tail and crest following the wings through damped springs; neck, tail
and crest carry a wave and the head stays level. Tick counts, distance per loop and footstep sounds are kept.
Check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_quetzalmon_flight` (needs `tools/models/edit.py get 249`).

Flymon (262) played one 29-tick pose sequence in its idle, walk, condition walk and run (they differed only in root
speed). `field_animations/flymon_flight.py` writes them again as four flights, stored in the plain delta
(`python3 -m tools.models.field_animations.flymon_flight --source build/imported-model-edit/edit/262-Flymon.MMD --out AFTER.MMD`,
then `tools/models/edit.py put 262 AFTER.MMD`): a hover (30 ticks, two small beats; the import's loops were 29 ticks), a relaxed flight leaning 11 degrees
(30 ticks, three beats), a heavy, low flight with two big slow beats (40 ticks) and a dash leaning 30 degrees with four
quick small beats and the limbs streamlined back (20 ticks). Wings stay on their hinges; abdomen, legs, arms and antennae
follow through springs. Root speeds are 18, 13 and 38 units per tick. Check with
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_flymon_flight` (needs `tools/models/edit.py get 262`).

Dolphmon (238) had one native 73-tick swim, lifted off the ground, in all four field slots (idle, walk, condition walk,
run), so they differed only in root speed. `field_animations/dolphmon_gaits.py` (overlay `dolphmon-gaits`) runs after
`dolphmon.py` (which keeps the sleeping clip) and writes slots 0, 2, 3 and 4 again on the reviewed rig: a belly-resting
idle (72 ticks: slow left-right turns, head glances, chattering jaw, flipper paddling, a soft tail wave), a flipper
scoot (20 ticks, 22 units: flippers push alternately along the floor, the body turns over the pushing side, the tail
wave travels to the fluke), a slower, heavier condition walk (30 ticks, 14 units: short strokes, panting jaw) and a run
(14 ticks, 40 units: the walk's scoot made quicker and bigger, with longer strokes and a wider sway). Nothing moves
vertically: the body bone keeps one height, the lowest mesh point stays within a unit of the floor, and the clips only
turn about the vertical axis, roll a little and stroke the flippers. Resident animation storage 47 556 of 100 352 B.
Check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_dolphmon_gaits` (needs `edit.py get 238`).

Magnadramon (215) had the idle, walk, condition walk and run as one 89-tick wave of the wing blades, body and tail
that only the root travelled through. `field_animations/magnadramon_flight.py` runs after its steady glide and writes
those five slots again: a hover with two slow, wide wing beats, a forward-leaning cruise with three beats per loop
and a streamlined, faster run with four, a beat running from the inner blade pair to the outer, the tail and the limbs
following the body a beat later. Ticks, distance per loop and the other slots are kept. Check with
`tools/models/edit.py get 215` and `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_magnadramon_flight`.
Armadillomon (185) held its head level or lowered in the field idle, walk and
run, so the shell's front rim covered the brow. `field_animations/armadillomon_head.py`
adds one constant lift to the head joint in those clips (and the condition walk),
leaving every other channel as `armadillomon.py` and the pace pass wrote it.

Ankylomon's (189) run threw its legs out sideways and swung the paws far over
the ground. `field_animations/ankylomon.py` replaces only the run with a heavy
trot from `quadruped.py`; its paws are bound sole-backwards, so the profile's
`paw_flat` gives their flat standing rotation, and `tail_up` carries the club
tail clear of the ground. The 73-frame idle and walk stay as they were.

Angewomon's (190) walk and run slid the feet without the legs carrying them.
`field_animations/angewomon.py` takes native Angemon's walk, condition walk and
run the way `valkyrimon.py` does (legs solved onto his feet, his lean on the
body), with her own swinging arms (he carries a staff), and the sash ends and
lowest feathers kept off the ground. Buster Dive is applied after it at build.

Imperialdramon's (192) walk and run swung every limb on its own and slid the
hands and feet. `field_animations/imperialdramon.py` writes the walk, condition
walk and run on all fours with `quadruped.py` (a walk with each hand landing
just before the foot behind it, and a gallop), each hand and foot standing at
its own turned-out idle angle (per-leg `paw_flat`). The hips sit right behind
the shoulders: the knees bend out and a lifted arm's elbow swings out past the
thigh (`swing_pole`), so the legs of a side do not pass through each other. The
forearm blades always point ahead (`aim`) and the hands swing wide (`wide`), so
they do not sweep through the head, and the body dips onto each landing in the
walks and bounds in the run. The idle keeps its crouch and roar with every hand
and foot planted where it stands at the first tick (the crouch had pushed the
hind feet into the floor).

Pegasusmon's (200) idle stood on a raised right foreleg and swung the
hindquarters, and its walk and run crossed and slid the hooves.
`field_animations/pegasusmon.py` writes them all again: a 24-tick idle square on
four planted hooves (the right foreleg the left's mirror) that only breathes,
with the neck, tail and wings answering late, then a four-beat walk, a slower
condition walk and a gallop from `quadruped.py` (the short caps between the
upper leg bones and the cannons named in `links`).

Paildramon's (199) walk snapped a foot from one place to another between two
ticks and slid both feet; the run was the walk sped up.
`field_animations/paildramon.py` takes native Leomon's walk and run the way
`angewomon.py` does, on the paildramon-field proportions it now bakes in (the
overlay is retired; `content/models/authoring/199-paildramon.json` keeps it as
provenance): the feet are solved onto Leomon's footfalls with each knee bending
out over the wide stance, the body takes part of his lean, the arms part of his
swing, and the condition walk is his walk slower and lower (his own slides).
Buster Dive is applied after it at build.

Halsemon's (196) walk and run threw the feet across each other and slid them,
and the run bounded like a cat. `field_animations/halsemon.py` writes a
lateral-sequence walk, a slower condition walk and a firm-backed trot with
`quadruped.py`, every foot flat at its own turned-out idle angle and the short
hock bones above the hind feet holding their angle (`links`).

Raidramon's (201) walk and run crossed the legs through each other and slid the feet
over the floor. `field_animations/raidramon.py` writes a lateral-sequence walk, a slower
condition walk and a trot with `quadruped.py`; the shoulder plates hold still above short
upper arms and the hock bones above the hind feet hold their angle (`links`). The forelegs
hang from plates stood turned in the rest pose, so the profile gives its bend directions in
the world (`pole_world`). Its old field overlay (weight transfer and pace retime of a
73-frame walk) is gone: the gait now lives in the model delta.
Tortomon's (261) walk, condition walk and run were noisy, identical in the last two, slid
the feet through the whole stance and stepped further than the short legs reach.
`field_animations/tortomon.py` writes a lateral-sequence walk (16 ticks, 12 units a tick),
a slower and lower condition walk (22 ticks, 9) with the head hung, and a trot (10 ticks,
36) with `quadruped.py`; the whole body hangs from the shell bone. Own clips instead of a
native binding: the 21-bone short-legged rig has one shell bone carrying everything and
a native donor would stretch the legs. The legs are folded Z shapes, so the profile bends
the front knee downwards (`pole`) and widens the checks with `floor` and `stance_slip`.
ExTyrannomon's (266) arms hung almost still in the walk, condition walk and run.
`field_animations/extyrannomon_arms.py` rewrites only the two arm bones (7 and 8, one rigid
piece each: shoulder disc, cannon and claws) of slots 2, 3 and 4 and leaves every other bone,
the cycle lengths, the events and the idle byte for byte. Each arm is a damped spring driven
by the pitch of the leg on its side, in opposite phase, so it trails the leg by a tick or two
and closes the loop on integers; footfall kicks, a slight sway-driven abduction and a roll of
the disc come on top. The ticks where an arm would sink into the body or a leg are bounded
inside the swing, never worse than the original clip. Slot 36 shares the run program.
A planted stride longer than about 55 units (ankle travel against the hip) cannot be reached
without the IK capping the leg at full stretch or full fold, where the foot sticks and then pops,
so each foot is planted for only about a quarter of the cycle (duty 0.28, 0.26 and 0.17) and
each leg's stance window is placed on its own hip (`leg_reach`: the rig's hips are not
symmetric). In the stance the sole is flat and does not move in the world (0 to 4 units, the
ankle 2 to 4), the shin and knee turn over the planted ankle, the heel peels off at the end of
the stance and the foot swings in a high arc (`arc`) and lands flat. The swinging wrist's
distance from the hip eases into its minimum (`fold_soft`) instead of being capped at it. No
clip reaches the IK's stretch or fold limit on any tick (the hip-ankle distance stays 30 to 71
units, limits 25 and 75), and no leg joint moves more than 18 degrees or 14 units a tick in the
walks (the trot's planted feet move with the body at 36 a tick, so its bounds are wider). The
thigh swings 45 to 70 degrees and the knee bends about 60 to 90, the foot rises 26 to 34 units;
weight comes from smooth constant-speed curves, a low bob, the shell's roll and the lagged head
and tail. Slot 36 shares the run's program and changes with it; slots 27 and 35
keep the old pattern. `tools/test_tortomon_gait.py` covers it.

Mammothmon's (267) hind legs dragged: the old walk, condition walk and run never planted
a foot and stretched the legs to 167-200 units. `field_animations/mammothmon_gait.py`
rewrites slots 2, 3 and 4 with `quadruped.py` (front legs included, planted the same way;
the idle, slot 0, is untouched). The hind leg only reaches about 150 units planted, and
planted stride is speed x ticks x duty, so the cycles are short: walk 20 ticks at 15, condition
walk 24 at 11, trot 10 at 36 (before 25 at 30, 25 at 21, 21 at 53). The hind feet slip under
7 % of the root speed in the walks and about 18 % in the trot's stance, lift 22-32 units and land
heel first; the trunk, ears and jaw nod on lagged closed loops (profile `extra`). `heel`,
`floor_skip` and `extra` are opt-in profile keys. `tools/test_mammothmon_gait.py` covers it.
Woodmon's (272) imported gaits left the trunk bone still, replayed the idle's arm curve in
every gait and slid the feet (85 to 98 % of the body's travel), so the limbs worked on a
frozen trunk. `field_animations/woodmon.py` keeps `quadruped.py` for the four root legs (a
lateral-sequence walk of 12 ticks at 15 units a tick, a slower tired walk of 16 ticks at 11
and a trot of 10 ticks at 38; each foot flat and still in stance, slip under 1 %) and moves
everything above them with the footfalls through the new profile key `body`: a function that
replaces the shared chest and head motion for a rig with neither. The trunk bone (1) bobs
twice a cycle with a landing weight, rolls over the loaded side, shifts its weight
sideways, yaws against the hips, leans into the run and slouches in the tired walk; the
log arms (2-3, 4-5) swing opposite to the legs of their side, the forearm following the
shoulder late and folding as the arm comes forward; the claw hands on the chest (6-11) trail
the trunk. A native donor was rejected: the nearest one (Cherrymon) is a 26-bone biped
whose feet slip 89 to 112 %. The old pace overlay is removed. The imported idle (slots 0 and 33,
the same pose list) flailed the log arms 45 to 90 degrees and the claws 40 to 100 on a still body;
it is rewritten as a calm 40-tick loop: slow breathing and a small turn of the trunk, the arms and
claws sway 11 to 20 degrees, each joint a little later than the one above it, and the legs stay
planted (the hips turn against the trunk, ankles drift under 4 units). Slots 35 and 36 play the walk
and run and follow.

Tapirmon's (287) imported gaits slid every foot (slip 112 to 232 % of the body's travel), swung the head
sideways in the tired walk and left the idle hopping. Its rig has no tail, knee or paw bones: four short
two-bone legs (hind 8-9 and 3-4, front 17-18 and 19-20; the lower bone of each front leg includes the paw, the
hind lower bone carries a long rear foot plate 10-12 and 5-7 pointing backwards), a rear block (2) behind the
body (1), the head (13), snout (14) and two ears (15, 16). `quadruped.py` needs three-bone legs, and no native
quadruped has this leg shape, so `field_animations/tapirmon.py` solves each leg itself: planted flat soles slide back
at the body's speed in stance, a swing path matches that speed at lift-off and landing, and a per-tick body-height
solver keeps every leg inside its reach (the short legs limit a stride to about 75 units, so the cycles are short:
walk 9 ticks at 16 units, tired walk 13 at 10; the run is a light gallop of one 14-tick cycle at 38 units: the hind pair pushes off together, both pairs leave the floor for a few ticks while the feet stay near the body, the front pair reaches and lands together, and the back arches and stretches with the chest and rear block pitching in turn; each clip has its own attitude: the tired head hangs low with drooping ears and a low rear block, the run carries the body and head low with the ears swept back). The body, rear block, head, snout and ears move on lagged
closed loops; the tired walk keeps the head low and facing forward. The idle (slots 0 and 33) is a 64-tick loop:
breathing, a look to one side, a sniff, an ear twitch and a tail flick, legs planted. `tools/test_tapirmon_gait.py` covers it.

Gryphonmon's (293) imported clips kept the paws sliding (44 to 53 % mean foot slip, 84 % at worst in the walk) under a
crouched body, flapped the wings stiffly with every step and repeated the walk as the idle. No native rig matches four
legs, two wings and a chain tail (Garurumon and Elecmon have no wings, Birdramon and Airdramon are bird or serpent plans),
so `field_animations/gryphonmon_gait.py` gives `quadruped.py` a profile of the rig: walk 22 ticks at 16 units, tired
walk 28 at 11 and a gallop of 16 at 38, with the hocks and elbows folding backwards and the long paws planted by their sole
point (mean sole slip 4 to 6 %). The walk is proud: the neck arched and the head high, a high-stepping eagle paw, a shoulder roll, a heavy lagged
tail and the wings beating once a stride (each wing is one chain on the chest's z hinge: a quick downstroke and a slower upstroke of
the arm, the fan on its end a few ticks behind and wider, so it trails; turning the fan about another axis opens a gap between the two mesh pieces); the run
beats them wider; the tired walk hangs the head and beats low and slow. The idle is a 96-tick loop with a breath, a slow wing stretch, a beak
scan to each side, a settling dip, a tail flick and three blinks. The old walk-speed overlay is gone: the celebration overlay
(slot 42) now starts from this model. `tools/test_gryphonmon_gait.py` covers it.
Grizzlymon's (296) imported walk and run slid every foot (slip 39 to 63 % of the body's travel, a 64-tick run) on a
stiff trunk, which read as a robot. `field_animations/grizzlymon_gait.py` rebuilds the idle (slots 0, 1 and 18), walk,
tired walk and run with `quadruped.py`: the walk (24 ticks, 15 units/tick) is a bear's lateral sequence with every paw
planted flat and still in stance (slip about 10 %), the body rolls and shifts its weight over the loaded paw while
shoulders and hips turn against each other, the shoulder rises over the planted fore paw and the head hangs low and swings
slowly; the tired walk (28 ticks, 11) drags the same way with the head and tail hanging; the run (15 ticks, 38) is a low
rotary lope with the spine flexing; the idle (96 ticks) breathes, shifts its weight and sniffs with the feet planted.
The character is menacing: the head is pushed 10-28 units out ahead of the shoulders, hangs low and lunges with every
fore step (`thrust`, `lunge`, `head_drop` in the gait rows), each fore landing drops the body (`impact`), the chest rolls
over the loaded paw by 8-13 degrees peak to peak, and the idle sweeps the head wide, lowers it over the loop, growls
(`jaw_open`, `swell`) and lifts and sets down a fore paw. The
fore legs are nearly straight at rest (102 + 32 units), which limits the fore stride, so the cycles are short; the hind shin
plates dig into the floor when they tilt, so the profile gives `flat_shin` (a new `quadruped.py` key that straightens the
hock above the ankle). A gait with speed 0 is an idle: the feet stay put. The old pace overlay is removed.
`tools/test_grizzlymon_gait.py` covers it.

Cyclonemon's (281) idle, walk, condition walk and run were rebuilt (old ticks 20/21/21/19, root speeds 25/21/44
units/tick, feet slipping 103-132 %, a heavy hunch in the condition walk). `field_animations/cyclonemon_gait.py`
plants the heavy left arm like a crutch and both hind feet with `quadruped.py`: idle 48 ticks (feet planted, slow
breathing and sway), walk 18 ticks at 15, condition walk 26 at 11 (lower, no exaggerated hunch), run 12 at 38 (forward
lean, bigger bob). The feet slip under 4 % of the root speed. Bone 1 carries a uniform scale of 1.3 that every bone
under it inherits, so `quadruped.py` has the opt-in profile keys `scale` (rotations read with it divided out, offsets
and soles multiplied in), `paw_rest` and `body` (a per-species body pose); the shoulder pad (bone 2) takes the twist
about the line to the elbow that keeps it nearest its place on the torso. Slots 0 and 33 (the battle idle it plays)
change with the idle; the resident animation buffer ends at 99,238 of 100,352 bytes. `tools/test_cyclonemon_gait.py`
covers it.

Ebidramon's (305) idle, walk, tired walk and run were four streams with the same keys (a 60-tick tail curl, only the root
faster) and its battle idle (slot 33) was that curl sunk 40 units into the floor. Nothing but the tail fan can reach the
floor (the six swimmerets end 200 units above it), so `field_animations/ebidramon_swim.py` (offline model delta) makes every
clip a hover like Piedmon's, slow and smooth (one stroke per loop): the fan skims the floor at its lowest and never goes through it. Idle 96 ticks (slots 1, 18, 33
follow it), walk 48 ticks at 22 units a tick, tired walk 64 at 14, run 32 at 40 (slot 36 follows it). The abdomen flexes as a
wave that ends in the fan, the swimmerets row front to back, the arms and antennae lag the body. Stance slip does not apply
(no foot is planted). The resident animation buffer ends at 85,254 of 100,352 bytes; the encoder tolerance is 8 except for
the body bone (1), which keeps the small bob. `tools/test_ebidramon_swim.py` covers it.

Crabmon's (284) idle, walk, condition walk and run were one pose cycle with only the root faster (23/25/25/25 ticks,
speeds 16/10/48, no leg ever stepped, the shell lay almost on the floor). `field_animations/crabmon_scuttle.py` is an
offline model delta: six two-bone legs (bones 2-13) are solved with damped least squares so every tip stands still on the
floor in its stance (a leg's lowest vertex is put on the floor, not only its tip), the shell (bone 1) rides 20 to 40 units
above them, and the two claws (14-16 small, 17-20 big with its finger) carry on. Idle 84 ticks (slow breath, claws
shifting with lag, one finger snap), walk 22 ticks at 15 (two strides, tetrapod pairs), condition walk 28 at 10 (a
metachronal wave, lower shell, claws drooping), run 14 at 38 (alternating tripods with a flight phase, shell pitched
forward). Feet slip about 1 %. Slots 1 and 18 follow the idle; the resident animation buffer ends at 79,116 of 100,352
bytes. The eyes are painted on the shell, so there is no glance or blink. `tools/test_crabmon_scuttle.py` covers it.

Dokugumon's (298) idle, walk, condition walk and run (61/25/29/21 ticks) swung the legs as one block (foot slip 90 to
115 %, the body low). `field_animations/dokugumon_gait.py` is an offline model delta: the six three-bone legs (bones 4-21)
are solved with damped least squares so every tip stands still on the floor in its stance, the body (bone 1) rides 46
units above the old height and the feet are set wide, with the middle legs outermost. Two groups of three alternate
(front right, middle left, rear right, then the others): walk 20 ticks (two strides of 10) at 18 units, condition walk 32
at 12 (a stalking one-leg-at-a-time step, low body), run 16 at 40 (with a flight phase); the abdomen (2, 3) swings against
the body's twist, the face and fangs (22, 23) and the two palps (24-27) move softly. Idle 72 ticks (breathing, two front legs and a
middle leg paw once in place). Stance slip is under 2 % on average; slot 33 follows the idle; the resident animation buffer ends
at 93,940 of 100,352 bytes. `tools/test_dokugumon_gait.py` covers it.

Arukenimon's (311) idle, walk, condition walk and run (70/22/20/18 ticks) swung the six legs as rigid posts (foot slip 75 to
120 %), the condition walk rolled the body 40 degrees and folded three legs 100 to 280 units off the floor (109 vertices of
an arm inside the body), the sleeves flailed 110 degrees in every clip and the run travelled at 66 units a tick.
`field_animations/arukenimon_gait.py` is an offline model delta on the same planted-tip solver: the six two-bone legs
(bones 13-24) are solved so each tip stands still in its stance, two alternating groups of three; walk 24 ticks at 24 units,
condition walk 36 at 13 (one leg at a time, low and hunched), run 16 at 44 (with a flight phase), idle 96 (breathing, glances,
one arm lifting, a front paw). The torso turns against the pelvis, the head stays level and lags it, the arms and sleeves are
delayed pendulums. Slots 33, 35 and 36 follow the idle, walk and run; the celebration overlay keeps its own slots and its
reviewed-source pin now names this model. `tools/test_arukenimon_gait.py` covers it.

Fujinmon's (317) walk, tired walk and run (26/29/16 ticks at 21.9/17.3/52.8 units a tick) drove the legs with rotations from
another rig: the soles slid over the floor (44, 120 and 83 % of the body's speed on average, 460 % at worst), the run kicked a
foot 200 units up for one tick and the chest turned 56 degrees against the pelvis in a walk. `field_animations/fujinmon_gait.py`
is an offline model delta on the planted-foot solver (`quadruped.py`): both legs are solved so each sole stands still in its
stance, and a hand-written body drives everything above them (pelvis and chest turning against each other, the body sinking on
each landing, the cannon arms swinging against the legs as delayed pendulums, the head steady, the scarf trailing). Walk 20 ticks
at 18 units, tired walk 28 at 12 (low, chest and head down), run 14 at 40 (a flight phase, 10 degrees more lean, arms pumping).
The spiked pauldrons (bones 6 and 10) are rotors: the model's own idle and run turn them about the local x axle, but its walk
and tired walk did not, and the first version of this gait stopped them; now they turn one whole turn each loop at 18, 13 and
26 degrees a tick (walk, tired walk, run). Only slots 2, 3 and 4 (and the battle run, slot 36, which aliases the run) change; the idle is the model's own and slot 35, a
battle program of its own, is untouched. Stance slip is 3 to 6 % on average and 32 % at worst; the resident animation buffer
ends at 78,620 of 100,352 bytes. `tools/test_fujinmon_gait.py` covers it.

Magnamon (197) is bound to native Leomon (`native_binding.py`). Its boots kept
the source's fighting stance, turned 35 and 93 degrees outward, its fists kept
the guard pose's forward point, and its broad legs crossed over Leomon's narrow
hips. The recipe now turns the boots forward (`yaw`), turns each fist with its
forearm (`follow`) and sets Leomon's hip joints 20 units further apart in every
program (`spread`, written in each program's start pose). Leomon's walk and run
did not suit it either: they hunched the torso, crouched the run and pointed the
long boots into the floor. `field_animations/magnamon.py` runs after the binding
and replaces the walk, condition walk and run with clips authored on the bound
skeleton from its own upright idle, the arms let down from the guard: boots
landing heel first under each hip and rolling flat, legs solved onto them, hips
turning with the swinging leg and the chest against them, arms swinging opposite
to the legs. Every curve is eased unevenly, the body moves in overlap (hips
first, chest, head and forearms later) and the two sides differ a little, with
amplitudes close to native Leomon's. The source's guard binds the two arms in
different orientations, so the shoulders read uneven at rest and in every
program. Its arm pieces are exact mirrors, so the recipe now builds the left arm
as the mirror of the bound right arm (`mirror`; Leomon's rig is mirror symmetric
at rest). The shoulder armour hung from the upper arms like sleeves; it now
rides on the chest at each shoulder, its point rising up and out like a
pauldron (`aim` sets a piece whole in a given orientation of Leomon's rest
pose), so it stays up while the arms swing. The cycles are 16, 14 and 10 ticks at
the binding's field speeds (18.4, 16.25 and 41 a tick, unchanged). Its thigh
is short, so any change of hip height swings the knee a long way: the planted
leg keeps one slight bend, the heel peels off where the stride reaches past it,
the body sinks only by what a leg still cannot reach, and the knee points
forward along the boot, turned by half the hips' yaw but never by their roll.
The left leg is built as the mirror of the right one, and the recipe sets the
shoulders 20 units further out (`spread`) with the arms hanging out and the
elbows bent, so the arms swing clear of the thigh armour; the run leans in,
drives the arms and has both boots in the air between steps.

Wizardmon (241) is bound to native Angemon (`native_binding.py`, recipe 241) and plays
Angemon's own idle, walk, condition walk and run, root travel included (21.25, 16.25 and
37.5 units a tick). Its source stands turned 45 degrees side-on, so the recipe turns the
whole source forward first (`source_yaw`); the staff is turned from its source direction
onto a held-out direction clear of the hat brim and thighs (`swing`) and rides Angemon's
staff hand, bone 9; the free glove is turned 70 degrees about the forearm (`roll`) so its
palm faces the body, not forward. Angemon's hips are set 22 units further apart
(`spread`) so the broad trousers never meet. Angemon's wing bones carry no wings here:
the cape hangs from 10 and 11 and the whole hair tail from 12, set out behind the head
clear of the cape by `spread`. `field_animations/wizardmon_native.py` runs after the
binding: in the field clips it holds the upper arms further out from the body
(`ARMS_OUT`), and in every program it replaces the wing beat on those three bones with
followers that take part of the head's (cape top, hair) or chest's (cape hem) turn a
few ticks late and trail back with the root's speed, which wraps around each endless loop (`closed`) so the
loop ends on the pose it began from and the cape and hair do not creep further with every pass. Techniques and
the training clip (57, Angemon's 46) are Angemon's; the record's effect points and
condition bubble are carried onto the new bones (`species_patch`).

Sorcermon (242) is Wizardmon's body with a crystal staff, and is bound the same way (recipe 242, same map, `source_yaw`,
`spread` and glove `roll`; `field_animations/sorcermon_native.py` runs the same followers). Its staff differs: the crystal head is
turned face-on, the staff is held out to the side (`swing`, with a `roll` about its length) and slid 70 units along its length
(`offset`) so the hand holds its lower part; with Wizardmon's mace direction the crystal touched the hat brim and the butt end
the left thigh. Like Wizardmon's, Sorcermon's followers close each endless loop on its first pose (`closed`), so its cape and hair
do not creep further with every pass of a walk or run.
Its techniques play the Angemon clip each shares with Wizardmon (Electric Cloud, Static Elect, Wind Cutter, Confused
Storm) and a cast clip of its kind for the ice moves (Winter Blast Hurricane's, Aqua Magic War Cry's, the shots Megalo
Spark's, Spinning Shot's and Static Elect's), the finisher Angemon's. Its effect points are carried by world position onto the head (bone 3) and the staff head (bone 9); the condition bubble
is Wizardmon's, over the same hat.

VioletElecmon (256) is native Elecmon's (18, `CHDAT/MMD0/ELEC.MMD`) body in other colours: its 22 rigid pieces are
Elecmon's pieces one to one (object n is object n), so recipe `256` maps them onto Elecmon's 25-bone skeleton, which
has two extra empty bones (1 and 15) the import lacked, at scale 1 with no stretch. Each piece is moved by a small
`offset` (at most 15 units, the head 41 forward) so its box lies where Elecmon's does; its ears are 30 units shorter
than Elecmon's, which stays. Every program below the techniques is Elecmon's own (idle 31 ticks, walk, condition walk
and run 21 ticks at 15.7, 14.5 and 50 units a tick), the techniques play Elecmon's clip for each move it shares
(Static Elect, Megalo Spark, Electric Cloud, Wind Cutter, Muscle Charge, Super Thunder Strike), Elecmon's kick
for Sonic Jab and Muscle Charge's clip for War Cry, and training slot 54 is Elecmon's training clip (46, hit tick 10).
The record's effects use Elecmon's (`effects_like` 18) and the condition bubble rides the head (bone 3).
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_violetelecmon_native` (after `edit.py get 256`).

MetalTyrannomon (260) wears native Tyrannomon's (8, `CHDAT/MMD0/TYRA.MMD`) 27-bone skeleton and programs: the
cyborg's 23 rigid pieces map onto it by role (head, torso, jaw plate, three tail bones, two three-bone legs, and each
arm's upper arm and forearm), at scale 1 with no stretch. The legs, tail, head and torso are moved by an `offset` onto
where Tyrannomon's piece sits. The arms are not: the source has no hand, so the forearm block and its three claws are
one rigid group on Tyrannomon's forearm bone (the claws on the donor's hand and claw bones turned at a wrist the heavy
forearm does not have, which read as broken wrists). Each arm is fitted by joint: `spread` moves Tyrannomon's shoulder
and elbow to where the cyborg's are (the right arm mirrors the left) in every program, the pieces stay on those joints,
and the forearm group is turned (`swing`) so its claws hang along Tyrannomon's forearm instead of out sideways. The hand
and claw bones stay empty, as does the pelvis; the side pipe with the yellow muzzle has no counterpart and rides the head. The run (slot 4) is the one clip whose arms are not the donor's: the donor's thin arms swing close to the body, which on
this heavy body reads as arms glued to the torso, so `arm_pump` (`native_arms.py`) re-poses the shoulder and the forearm
(claws rigid with it) on every tick: held out, pumped front to back against the leg on their side, the elbow closing as the
arm comes forward and arriving late, and lifted so the claw tips clear the floor. The legs, tail, head, other clips and
techniques stay the donor's.
Every program below the techniques is Tyrannomon's own but for the arms' two start translations (idle 21 ticks, walk 23,
condition walk 27 and run 21 ticks at 22.7, 17.7 and 50 units a tick), each of the 14 techniques plays Tyrannomon's clip of
its kind (the moves they share their own: Prominence Beam, Megaton Punch, Dynamite Kick), and training slot 60 is
Tyrannomon's training clip (hit tick 10, set in the recipe's `partner`). The borrowed effect points travel with their
pieces and the condition bubble sits over the head (bone 3).
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_metaltyrannomon_native` (after `edit.py get 260`).

PrinceMamemon (270) wears native Mamemon's (13, `CHDAT/MMD0/MAME.MMD`) 19-bone skeleton and programs at scale 2.2, so
the gold sphere (Mamemon's body, radius 120) keeps the size it has in the source. The sphere, crown, cape and face plane
are one rigid group on the body bone. Each arm is the epaulette and sleeve stretched along Mamemon's shoulder-to-elbow
and elbow-to-wrist segments, with cuff, fist and thumb as one rigid glove on the big fist bone; the thigh, shin and boot
sit on Mamemon's leg bones (the boots `offset` down so the soles stand on the floor as the donor's do, the thighs and shins
a little to clear the sphere). Mamemon's empty bones (1, 2, 6, 11, 15) stay empty. Every program below the techniques
is Mamemon's own with its translations scaled (idle 17 ticks, walk 15, condition walk 19 and run 15), each of the 15
techniques plays Mamemon's clip of its kind (Buster Dive, Counter and Dynamite Kick are Mamemon's own; the three moves it
lacks borrow the nearest by role) and training slot 61 is Mamemon's training clip (hit tick 8, in the recipe's `partner`).
The condition bubble and the effect points are moved onto Mamemon's bones by fitting each source piece to where it
landed. `native_animation_donor` keeps Mamemon's own Buster Dive from being replaced.
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_princemamemon_native` (after `edit.py get 270`).

ChaosLord (289) wears native Machinedramon's (115, `CHDAT/MMD3/MUGE.MMD`) 32-bone skeleton at scale 1; its 29 bones
map almost one to one (waist, chest, arms, three left fingers, cannons, neck, head, jaw, pelvis, legs, tail). The two
thrusters sit rigid on the chest; Machinedramon's claw hand, second neck bone and cannon tips stay empty, and the right
forearm and claw are one piece on the forearm bone. Native Machinedramon has no care slots, so `donor_builder` in the
recipe makes the donor from `content/models/partners/machinedramon.py`; slots below 46 are that model's, the 15
techniques play Machinedramon's seven clips by kind (Megaton Punch for the punches and kicks) and slot 3 is the walk
retimed through `pace.retime` (recipe `pace`) so the condition walk is slower than the walk. The idle (slot 0, and slot 33 which shares it, 37 ticks) and the run (slot 4, and slot 36 which shares it) are the species' own clips from before the binding, retargeted in world space (`original_run` in the pace row, `limbs` in the recipe): every tick each source bone's world motion since the bind pose is
applied to its donor bone's bind placement (the pieces were fitted there), and the donor bones are solved root to
leaves: the local rotation that gives that world rotation, and for the waist and pelvis (which hang from the height
bone) the offset that puts the joint where that motion took it. Each limb in `limbs` (legs, arms, tail: base, middle, end
bone) keeps the end bone's world rotation and has the donor's own bone lengths reach the end joint, bending to the side the
original's rotations bent it. The root keeps the source's travel (the run: 19 ticks, 47.5 per tick; the idle stands) and donor bones with no
source bone (the second neck bone, claw hand, cannon tips) hold their pose and follow their parent. A bone whose angles
end the loop written the other way round is flipped from the tick whose in-between frames stay nearest the true turn.
The body is lifted per tick only as far as the ground rule needs. Against the original posed by its own run the mean vertex
distance is 26 (the fitted pieces already differ by 25 at rest); the limbs' base and middle bones (thighs, shins, upper
arms, tail) turn 8 to 24 degrees from the original's because the donor's legs are shorter and bent, everything else 3
degrees at most. The condition bubble and
effect points are moved onto Machinedramon's bones. `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_chaoslord_native`
(after `edit.py get 289`).

Deltamon (292) wears native Tyrannomon's (8, `CHDAT/MMD0/TYRA.MMD`) 27-bone skeleton at scale 1.2. Greymon's (5) was
tried first and left: its own native walk already slips 36 on average (172 at worst) against Tyrannomon's 8 (26), and its
tired walk dips 171 below the floor. Each source bone goes to the donor bone of the same body part (the chest and the
belly on the torso bone so they never part, neck and head, the arms, both legs with their three bones, stretched joint
to joint). The two spiked tails have no counterpart: Tyrannomon's tail swings too far for a ground tail of this length,
so the six tail pieces sit rigid on the pelvis. The hips are moved 45 forward (`spread`: the donor's hips sit behind
the belly the source's legs hang from) and the pieces fitted to the unspread rest, feet lifted 22 and shins 20 so the
soles meet the floor. The skull's back-of-the-arm block rides on the skull so the arm swing cannot expose it. The 11
techniques play Tyrannomon's clips by kind (`technique_slots`) and the training slot 60 plays its charge clip. `pace`
retimes the tired walk to 30 ticks at 16 per tick and the run to 24 ticks at 50 (scale 1.2 would give 23 and 65), and
`arm_pump` (`native_arms.py`) re-poses the two heavy arms in those slots so the heads swing clear of the floor. The
walk keeps the donor's uneven pace through a stride (22 ticks, 27.3 on average). The mouths come from `jaws`
(`native_jaws.py`): the head's jaw follows a calm raised-cosine curve written per clip in the recipe (`peak` degrees,
`cycles` per loop, `base` degrees always open): one slow opening per loop, two in the run, a held-open mouth with a
4 degree pulse when tired. The skull's and the metal head's jaws replay the source's own jaw turns of the same clip
(`replay` 1.0: 13-14 degrees, one slow hump per loop, at most 1.8 degrees a tick), stretched over the retimed clip by
phase. All turn the donor bones that carry the pieces (the head's jaw; the finger bones of the hands, which carry no
mesh) about the source jaw's own horizontal axis (opening and closing vertically, never swinging sideways; the axis is
carried with the bone from the bind pose into each tick's pose) and hinge carried onto the fitted piece, so loops close on the clip's own ticks. Known limits: the tired walk keeps a
stance slip of 30 mean (the donor's own is 5), the run's heel strike sinks 37 against the donor's 14 times the scale, and
the idle tail tips dip up to 18 below the floor line. The condition bubble and effect point are moved to Tyrannomon's
head and jaw bones. The resident model uses about 85,400 of 100,352 bytes.
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_deltamon_native` (after `edit.py get 292`).

KingEtemon (303) wears native Etemon's skeleton and field programs: `species 303` in `native-bindings.json`, donor 42
(`CHDAT/MMD1/ETEM.MMD`), scale 1.2. The cape has no donor bones, so its pieces ride the pelvis and chest; the tired
walk and run are retimed by `pace` (with its `lift` key for the floor), and `hands` (`native_hands.py`) sets the gloves on the forearms. The two gloves (pieces 13 and 16) are not twins
(a fist across the belly, an open hand hanging) and carried that pose into Etemon's hand frame, which sits 81-97
degrees off its forearm: an `aim` rule per glove now lays it along the hand bone's x with 8 degrees of droop, palm on
`palm`; `hands` then turns the palm to the thigh, bends the wrist (not a roll about the forearm) by the forearm's late
swing, and `clear` leans the whole arm from the shoulder, then the wrist, on the ticks a forearm or glove enters a leg,
foot or the body. The idles (0, 33) keep part of the donor's own hand turn (`keep`). The resident model uses about 89,600 of
100,352 bytes. `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_kingetemon_native` (after `edit.py get 303`).

Flamedramon (195) walked like a catwalk: the procedural stride (`gaits.py`)
swung and dropped the hips from side to side, twisted the chest the other way
and held the arms out wide, and clips on Leomon's footfalls kept Leomon's hunch.
`field_animations/flamedramon.py` replaces the walk, condition walk and run with
clips authored on Flamedramon's own bind pose (upright, arms hanging, feet under
the hips): each foot stays on its own track under the hip, lands flat and peels
its heel at push-off, the pelvis turns with the swinging leg and the shoulders
counter it, the arms swing opposite to the legs and the tail follows late.
Nothing moves on a plain sine or in lockstep: each curve has its own uneven ease
(`upright_gait.wave`), the chest, head, arms and tail follow the hips one after
another, and the two sides differ a little, with pelvis, chest and arm
amplitudes taken from native Agumon's and Leomon's walks and runs. The
run is an 8-tick cycle with lean, hard arm drive and an airborne phase against
the 14-tick walk, at the reviewed field speeds (`upright_gait.py` holds the
pieces both modules share). The result is stored in the plain delta and the
`flamedramon-field` overlay is no longer applied.

ExVeemon (194) keeps its reviewed clips with two repairs in
`field_animations/exveemon.py`. The tail turns only about a third as far from
its mean in the idle, walk, condition walk and run, so it still sways at half
the size. In the walks the swinging ankle came up almost to the hip and the
knee flipped up through the belly: the legs are solved again with the knee
forward and out to its own side, the swing ankle capped in height (its foot
turned toward standing as far as it was lowered), and the condition walk's
dragging feet held mostly on their footprints. The body is kept on its claws at
the ticks and the 60 fps thirds.

Hookmon (299) runs a small post-pass (`field_animations/hookmon_polish.py`) after the chibi proportions: stance feet planted at their touchdown spot with the footstep sounds on those ticks,
trailing arms, hook and head, a breathing idle. See `docs/reference/motion.md`.

Snatchmon (331) runs a small post-pass (`field_animations/snatchmon_polish.py`) after the chibi proportions: planted stance feet with the footstep sounds on the touchdowns,
an arm swing against the hind legs, a trailing head and chain, a raised trunk. See `docs/reference/motion.md`.

Antylamon (309) runs a small post-pass (`field_animations/antylamon_polish.py`) after the chibi proportions: its walk's two stray shoulder keys replaced by a curve and the leg
lift-off kinks eased where the foot is off the floor (stance ticks untouched). See `docs/reference/motion.md`.

Digmon's (193) run was its walk played with twice the travel.
`field_animations/digmon.py` builds the run from the walk's own poses on a
14-tick cycle instead of 20, at the same field speed: thighs swing further, the
upper body leans forward and the body leaves the floor around each of the
walk's two hops. In the walk, condition walk and run the long toe claws pointed
through the floor and the right drill dug into it; the ankles and toes turn
toward standing as far as keeps the claws up and the arm swings up at the
shoulder just enough to clear its drill, checked at the ticks and the thirds.

Seraphimon's (207) idle beat all ten wing feathers through 60 degrees, and its walk and run slid the feet.
`field_animations/seraphimon_native.py` stores a calm 48-tick idle (wings, head and arms a few degrees, feet
unmoved) and a walk, condition walk and run on native Angemon's footfalls (legs solved onto his feet, planted for the
whole stance; the run's stride shortened and its lean halved), with arms swinging against the opposite leg, lightly
fluttering wings that lag the body (swept back in the run) and a tabard kept off the floor. `seraphimon.py`, the chibi
overlay's base, now only keeps the victory on screen.

VenomMyotismon's (212) native walk and condition walk held both gauntlets out in
front like a boxer's; only the run does that. `repair_venom_run.polish_walk_arms`
(applied after its supported-leg recipe and run polish) hangs the arms from the
shoulders: the shoulders keep the native swing timing in a smaller range (the
condition walk, whose shoulders hardly move, follows the thighs), the elbows
bend further a tick or two later as the arm comes forward, and the heavy hands
trail the elbows. Only those X rotations change; the gauntlets stay clear of the
floor.

Vikemon's (220) walk, condition walk and run kept the legs' stride (16, 26 and
13 ticks) but left everything above the pelvis on the idle's one-breath loop.
`field_animations/vikemon_stride.py` rebuilds the upper body from its own mean
pose plus terms locked to the stride phase: a pelvis bob, chest twist against
the hips, roll over the planted foot, a forward lean, neck and head arriving
later, arms against their own side's leg, and the back rig and tail lagging.
The legs, lengths, travel and sounds stay; the pelvis is raised so no foot
sinks. The upper bones are fitted at the import's tolerance (8) and the legs
at 3, through `mmd.encode_anim`'s optional per-bone `tol` dict, to stay inside
the resident model buffer.

Devidramon (216) walked with its upper body on a different beat from its legs: the walk and run took the
native upper-body clips (the walk's is the idle's, one beat per loop) while the legs stepped three and two times
per loop, and pace.py's retime left a planted foot moving at 18 against a body speed of 20 (run 30 against 38),
14% and 27% slip. `field_animations/devidramon.py` now replays each native upper-body channel at the stride's
beat (`BEATS`; wings and tail at about half their swing), turns the pelvis with the leading leg, the chest against
it and the head against the chest, swings the arms (a calm third to half of a first pass's swing) against the legs with the forearms folding late, and writes the
legs for the field speeds directly (walk 10 a tick in the 72-tick loop, which pace.py plays in 36 at 20; run 38).
Stance slip is now 4-6% (walk), 6% (run) and 5-8% (condition walk). The storage budget forced coarser keys
(`tol` in pace.json) on the walk and condition walk.

BlackGatomon (222) walked and ran on cycles of 16 and 10 ticks whose legs only swept back and forth while the head,
gloves and pelvis swung wide. The run is now the donor walk's own gait (16 ticks at the run's travel). The walk and
condition walk (8 ticks at 15, 12 at 9.5, the pace manifest's floors) keep a calm share of the head, pelvis and
arm swing, and `field_animations/black_gatomon_calm.py` writes their legs as a planted step: heel strike, flat
sole, roll over the toes, lift and land, the pelvis rising and falling with the one-segment legs. The legs reach
about 27 units, which sets the cycle length for the travel; stance slip is 23% (walk) and 18% (condition walk).
Gatomon (234) has BlackGatomon's rig (same bones and parents, about 3 percent larger), so it moves exactly like it: its pace.json row
is row 222's with its own source hash, `field_animations/black_gatomon.py` accepts both sources, and `black_gatomon_calm.py` takes the
species from the pace pass. Idle and care stay the native clips (the old `gatomon.py` layer is gone). Walk, condition walk and
run are 8, 12 and 16 ticks at 15, 9.5 and 38 per tick; the resident clips take 83004 of 100352 B (BlackGatomon 82018).
Shurimon's (225) field clips were one native 83-tick gesture loop with only the legs replaced and the whole clip
re-timed, so chest, head, arms, crest, leaves and star were identical in the walk, condition walk and run and the feet
slid (40, 40 and 68 percent of the root speed on average). `field_animations/shurimon_gait.py` authors idle, walk,
condition walk and run again on the model's own skeleton and the result is stored with `tools/models/edit.py put 225`
(the generator starts from the model of the commit before, see its SOURCE_SHA256). Legs: a two-bone solver per tick
plants each foot in the world in stance (heel, flat, toe roll about fixed sole points) and flies the ankle on a Hermite
path in swing, at root speeds of 12 (walk), 8 (condition walk) and 28 (run) per tick, lowered from 20, 13.3 and 38 so that a foot cycle
can last 20, 24 and 16 ticks (it was 13.3, 15 and 11.4, a pecking cadence) with strides the legs can reach; the clips are
40, 72 and 80 ticks long (two, three and five foot cycles; the run has a flight phase), with calm foot clearance and knees
pointing mostly forward. Pelvis bob, a wide sway and roll over the
stance foot, chest twist and a steady head (drooping in the condition walk), arms swinging against the opposite leg with bending
elbows, and crest, cloak leaves and back star lagging with second-harmonic ripples all use whole cycles per clip. The idle
(144 ticks) plants both feet, breathes three times, shifts its weight, looks around and once per loop jerks an arm
and snaps its head. Run `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_shurimon_gait`.
Blossomon's (274) walk, condition walk and run kept the five stalk roots at their rest pose, only the whole body bobbing
114-167 units and rolling 25-39 degrees, so the roots slid 90-195 % of the root speed, the root speed was not constant,
the trunk hardly turned and the vines made the same 15-20 degree gesture in all three.
`field_animations/blossomon_gait.py` authors idle (96 ticks), walk (48 ticks, 15 per tick), condition walk (60 ticks, 10)
and run (33 ticks, 36) on the model's own skeleton (bone 1 pelvis, 2 trunk, 8 head, 9 face, 3-7 the five roots, 10-12 and
13-15 the right upper and lower vines, 16-21 the left ones, 22 and 23 the leaves); the result is stored with
`tools/models/edit.py put 274`. The roots walk as a low-duty bound in diagonal groups, three steps per loop (16, 20 and 11
ticks a step, the run with a flight phase), each planted in the world in stance (its local translation and rotation are
solved from the pelvis each tick, so a tilted root stays above the floor) and swinging on a smoothstep; stance slip is
under 11 %. The trunk pitches on every step, twists against the pelvis and lags it, the head and face lag the trunk,
and the vines sway at a third of the step rate, so no vine or head turns faster
than 6 degrees a tick. The blink and footstep events are carried over. Slots 1, 18 and 33 share the idle's program,
so they change too. Run `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_blossomon_gait`.
Silphymon (226) held both wing-arms out and up at shoulder height in every field clip (shoulder joints turned
100-200 degrees from the rig's rest, where the arms hang at its sides), a chest hunched 57 degrees and feet that slid
79-99 % of the ground speed in the walk. `field_animations/silphymon_posture.py` writes the idle (48 ticks), walk,
condition walk and run (16 ticks, two steps per loop, footstep sounds on their ticks) as small turns from that rest
pose: arms hanging with bent elbows and swinging against the legs, pelvis/chest/head turning on the step beat, wings and
tail a beat late, each leg solved to a planted foot (walk slip 21 % mean) with a footstep on it: heel strike with the
toes up, a roll to flat, the heel rising over the ball of the foot, toe-off and a swing with the toes curled down
(the contact point does not move over the floor; foot pitch spans 46 / 30 / 42 degrees in walk / condition walk / run). Root speeds and slot 1 are unchanged:
`--source build/imported-model-edit/edit/226-Silphymon.MMD --out AFTER.MMD` on the model before this change, then
`tools/models/edit.py put 226 AFTER.MMD`; check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_silphymon_posture`.

Gesomon (240): `field_animations/gesomon_rest.py` lowers the idle onto the floor, rewrites the arms of the idle, walk and run, and writes the tired walk over
`gesomon.build`'s walk and run; all four are baked into the delta (`python3 -m tools.models.field_animations.gesomon_rest
--source build/imported-model-edit/edit/240-Gesomon.MMD --out AFTER.MMD`, then `edit.py put 240 AFTER.MMD`;
check with `tools.test_gesomon_rest`).
Shadramon (250): `field_animations/shadramon_loose.py` rewrites the idle (slot 0, no hop, claws planted) and loosens the upper body of the
walk and run over the strides `shadramon.py` made (legs re-solved to the same ankles); `python3 -m tools.models.field_animations.shadramon_loose
--source build/imported-model-edit/edit/250-Shadramon.MMD --out AFTER.MMD` on the model before this change, then `edit.py put 250 AFTER.MMD`;
check with `tools.test_shadramon_loose`.
Tylomon (254): `field_animations/tylomon_swim.py` rewrites idle, walk, condition walk and run as travelling swimming waves; `python3 -m tools.models.field_animations.tylomon_swim
--source build/imported-model-edit/edit/254-Tylomon.MMD --out AFTER.MMD` on the model before this change, then `edit.py put 254 AFTER.MMD`; the pins of
`locomotion.json` and `celebrations.json` follow the new model; check with `tools.test_tylomon_swim`.
Plesiomon (271): `field_animations/plesiomon_swim.py` rewrites idle (slots 0, 1 and 18), walk, condition walk and run as four swimming movements (neck and tail
waves, rowing flippers on springs); `python3 -m tools.models.field_animations.plesiomon_swim --source build/imported-model-edit/edit/271-Plesiomon.MMD --out AFTER.MMD`
on the model before this change, then `edit.py put 271 AFTER.MMD`; it has no overlay pass; check with `tools.test_plesiomon_swim`.
Scorpiomon (275): `field_animations/scorpiomon_swim.py` rewrites idle (64 ticks), walk (32, 26 units a tick), tired walk (44, 14) and run (20, 42) of a model with no legs that hovers about 150 units above the floor (carapace, face plate, mouth plates, eyes, two three-segment claws, one side blade per flank, a tail chain ending in a fan): blades row in turn, claws curl with a lag per segment, a wave runs down the tail, the body bobs, sways and rolls; `python3 -m tools.models.field_animations.scorpiomon_swim --source build/imported-model-edit/edit/275-Scorpiomon.MMD --out AFTER.MMD` on the model before this change, then `edit.py put 275 AFTER.MMD`; check with `tools.test_scorpiomon_swim`.



Solarmon (251): `field_animations/solarmon_gaits.py` lengthens the three nubs on each gear hand to full teeth and evens the gears (eight identical teeth 45 degrees apart, the same on both hands; vertices only) and writes
four different clips (idle, walk, tired walk, run) over the recipe chain's model, each with constant root travel and constant whole-step
ring and gear spins, and `solarmon_face.py` makes the eyes blink by texture moves over the painted eye disc (the frames in texels no face samples; every clip starts
and ends with open eyes; the mouth stays as painted). Baked into the delta (`python3 -m
tools.models.field_animations.solarmon_gaits --source build/imported-model-edit/edit/251-Solarmon.MMD --tim build/imported-model-edit/edit/251-Solarmon.TIM
--out AFTER.MMD --tim-out AFTER.TIM`, then `edit.py put 251 AFTER.MMD AFTER.TIM`; check with `tools.test_solarmon_gaits`).

Apemon (227) has no field overlay: its idle, walk, condition walk and run are stored in its plain delta
(`edit.py put 227`). `field_animations/apemon.py` is the generator that authored them from the model before this
pass (`APEMON_BEFORE`, see `tools/test_apemon_gait.py`): four limbs solved per tick with fixed planted fists and feet,
a diagonal-sequence walk (tired shamble and run too: sides half a cycle apart, front and hind a quarter, never paired 2-and-2) with hind feet that strike heel first, roll flat, lift the heel and push off through the toes (a swing
that lifts early, lands toe-up and differs a few percent per side and per stride), a one-stride tired shamble and a gallop with a flight phase, the pelvis and chest twisting
against each other with the limbs, a forward knuckle lean, a head kept level, and a grounded idle (breathing, weight
shift, head look and one fist lift, no hop). The staff keeps the pose it was made in, across the back, lowered a few units so it rests on the body in every clip. Other programs are unchanged.
Baronmon (228) hovered: its idle, walk, condition walk and run were one 94-tick loop (only the root's travel differed)
whose feet moved as one, 9 to 91 units over the floor, with the hips bouncing 108 units. `field_animations/baronmon.py`
writes those four slots again from its bind pose, standing on the floor: heel strike, flat sole, heel peel and a swing
on solved legs (the sole's contact points slip at most a unit or two), the pelvis as high as the leg allows with a small
bob, chest and pelvis turning against each other, the arms, robe skirt, cloak and plume following later; a 96-tick idle
with breathing, a weight shift and a look around; a 14-, 18- and 12-tick walk, condition walk and run at the field
speeds 20, 13.3 and 38. Slots 1 and 18 still share the old idle stream (they stay as they were), so it stays in the
file. `--source build/imported-model-edit/edit/228-Baronmon.MMD --out AFTER.MMD`, then
`tools/models/edit.py --from build/everything put 228 AFTER.MMD`; `PYTHONPATH=tools/models:tools python3 -m unittest
tools/test_baronmon.py` checks the floor, the loops, the speeds and the other slots.
Baronmon's skirt is lifted 30 units so the hem clears the shoes (the legs show beneath it), the swing foot flattens early
and passes under it, and the skirt pitches and rolls with the stride; no shoe vertex is inside the skirt in the idle,
walk or condition walk. The run is a brisk jog (arms bent about 45 degrees and hanging beside the body, upper arms about vertical on average and swinging 15 to 20 degrees either way, a slight lean).
Phantomon (229) played one 104-tick levitation in its idle, walk, condition walk and run, so the four looked the same.
`field_animations/phantomon.py` writes them again for a legless, hovering body: a slow idle (soft bobs, the hood
looking round, cloak and chains swaying late), a leaning glide in 24 ticks with the free right arm swinging forward and
back, a lower, bowed 28-tick condition walk and a 20-tick run leaning far forward with the cloak, hem and chains
streaming back. Hover height, root speed, loop lengths and the voice cue are the importer's; the scythe arm only sways.
The result is stored in the plain delta (`python3 -m tools.models.field_animations.phantomon --source SRC --out AFTER.MMD`,
then `tools/models/edit.py put 229 AFTER.MMD`); check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_phantomon_field`.
Candlemon (235) hovered on a steady line with its upper body frozen in the idle pose, so its four clips looked alike.
`field_animations/candlemon_hop.py` writes them again: it travels in hops on its foot (anticipation crouch, take-off
stretch, ballistic flight with the flame trailing, a squashing landing with the foot planted), walk 4 x 14 ticks at 20
units a tick, a heavy, slouched condition walk 3 x 18 at 13, a long flat run 5 x 10 at 38, and a 96-tick idle that
breathes, sways, looks both ways and flickers. Its face acts through texture moves (`candlemon_face.py`): the source
game's own blink frames, and mouth frames (half shut, shut, wide) slid from the painted mouth into four spare hand
drawings. Store with `python3 -m tools.models.field_animations.candlemon_hop --source SRC.MMD --tex SRC.TIM --out-dir
DIR`, then `tools/models/edit.py put 235 DIR/235.MMD DIR/235.TIM`; check with `tools/test_candlemon_hop.py`.

Diaboromon (237) kept the SkullGreymon transfer with a flat-hand contact pass, and its field clips jumped: the hand
pass switched the claws between curl and flat pad within one tick (up to 138 degrees), the transfer packed the donor's
strides into 16-28 tick clocks (45-70 degrees a tick on the upper arms and hips), the root stepped unevenly and the
planted feet slid. `field_animations/diaboromon_gait.py` writes the idle, walk, condition walk and run again on the
crouched stance: every hand and foot is solved each tick (planted ones keep their place on the floor), loops of 72,
48, 60 and 36 ticks at 0, 20, 13 and 38 a tick, no Euler angle changing more than 28 degrees between two ticks.
The limbs are not in lockstep: phase offsets off the quarter and half cycles, and the left limbs stay down a little
longer and lift less than the right ones. The hand pass had also laid the back of each hand on the floor (the claws
curl towards the hand's -X side, the palm), so the claws curled up; the planted hands now face palm down and grip
the floor with the claw points.
Store it with `python3 -m tools.models.field_animations.diaboromon_gait --source SRC --out AFTER.MMD`, then
`tools/models/edit.py put 237 AFTER.MMD`; check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_diaboromon_gait`.
ShellNumemon (231) kept the source's 104-tick clips in its idle, walk, condition walk and run: only the small front
flaps moved, the head and the eyes stood still and the body slid at a constant speed, so it read as a still lump.
`field_animations/shell_numemon_gait.py` writes the four clips again as a snail dragging itself: in every wave the
body rises and leans forward while it surges and the shell lags and tips back, then the shell is dragged forward and
rocks past its place; the eye stalks swing like pendulums (each joint wider and later than the one under it). The
head shares a ring of vertices with the front of the foot, so it never turns on it: the body (rear, front and head)
turns as one piece and the front pitches at most 3 degrees on the rear; no seam opens wider than on the model before.
The mouth opens and shuts through texture moves (`field_animations/shell_numemon_mouth.py`: the upper and lower teeth
slide apart over the red inside painted behind them; every clip starts by shutting it). Walk 24 ticks, condition walk
32 (head and stalks hanging), run 18 (the shell bouncing), each one wave; the idle breathes, turns, looks round with
each stalk, dips both once, chomps twice and yawns. Root speeds (19.25, 12.84, 35) and the movement cue are the
importer's; the body's world speed never drops below zero, the belly stays on the floor and no scale changes. The
result is stored in the plain deltas (`python3 -m tools.models.field_animations.shell_numemon_gait --source SRC.MMD
--tex SRC.TIM --out AFTER.MMD --out-tex AFTER.TIM`, then `tools/models/edit.py put 231 AFTER.MMD AFTER.TIM`); check
with `PYTHONPATH=tools/models:tools python3 -W ignore -m unittest tools/test_shell_numemon_gait.py`.

BlackKingNumemon (307): `field_animations/black_king_numemon.py` gives the two front pads (the little front legs, bones 2/3 and 4/5) a
traction stroke in the walk, tired walk and run (slots 2, 3, 4); every other bone and slot stays byte for byte (build with
`paddle=False, face=False` for the earlier clips). The eyes are rubbery: every stalk joint (bones 7, 8, 10, 11 and the eyeballs 9, 12) follows the body's bob and roll through a chain of three damped springs, so each joint lags and overshoots more than the one under it; the two eyes have their own stiffness and delay and roll opposite ways (a see-saw); the lower stalk stretches and thins with the bob. The idle sways at a different rate for each eye (the clip is re-encoded losslessly, so every other bone keeps its keys; slots 0, 1 and 18 share it); the run swings widest; in the tired walk the swing is slow, the head and stalks sag and the brows (13, 14) droop; in the run the brows set. The eyes never close. Per tick no joint turns more than 130 units or scales more than 300. The mouth is painted on the head's texture: opening it would need texture moves and a texture delta, as `shell_numemon_mouth.py` does. Each pad reaches forward, plants (the sole moves back in the body's frame at the clip's
root speed, so it does not slip: mean 8 to 14 percent, at most 40), pushes off with a short recoil, lifts and eases forward again;
the hip yaw and height are solved per tick, the outer pad's yaw is countered, and the right pad lags the left (2, 3 and 1 ticks),
so the stroke alternates and is slower and shorter when tired and quicker and flatter in the run. Check with
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_black_king_numemon_paddle`.

`field_animations/star_gait_refine.py` (Starmon 243): legs spread so the oversized boots no longer cross, run lean limited to the walk's, and the four ribbon bones hanging with a light damped lag. It is written over a bone map (`RIG`), so SuperStarmon (same 20-bone parent list plus fringe bones 20 to 26) needs only its own rig and profile values. Tested by `tools/test_starmon_gait.py`.
`field_animations/superstar_gait.py` (SuperStarmon 244): Starmon's refined clips (above) on its 1.75 times larger body, bone for bone (translations times 1.75), the walk, tired walk and run stretched to 22, 28 and 25 ticks so the root keeps about 19.5, 13.5 and 37.9 units a tick with the feet still planted, the idle with the arms hanging instead of the guard. The fringe blades and the back plate hold their rest orientation. `edit.py get 244` and `get 243` (refined), then `python3 -m tools.models.field_animations.superstar_gait --source 244.MMD --starmon 243.MMD --out AFTER.MMD` and `edit.py put 244 AFTER.MMD`; checked by `tools/test_superstarmon_gait.py`.

`field_animations/okuwamon_limbs.py` (Okuwamon 259): an offline model delta over the baked model. The idle (slot 0, 34 ticks) stays as the first pass left it, byte for byte (the two front hips turned a little, the wings and elytra as closed-loop spring followers). The tired rest, walk, tired walk and run (slots 1 to 4) are written new as a four-legged gait: legs 16/17 and 18/19 in front, 20/21 and 22/23 behind, diagonal pairs, each foot planted flat for a stance (it slides at most 25% of the root speed, measured on the sole's centre) and carried forward in an arc. Each leg is solved on its two bones (damped Gauss-Newton, no clamping; a target out of reach stops the build), the pelvis bobs (quick squash on landing, slower rise) and waddles: it shifts 20-24 units to the side of the standing pair, rolls 5-6 degrees toward it and turns 3-4.5 degrees the other way, the chest leans less and a little late, the pincers swing sideways against the body (the legs are solved over the swaying pelvis, so the feet stay planted); the pincers (arms 7 to 12) are carried forward and swing late, the wings flutter as the idle's do. The feet are 250 units across, so the steps are short: cycles of 10 (walk), 12 (tired walk), 8 (run) and 20 (tired rest) ticks, root speeds 15, 10 and 36 units a tick (the originals were 21-tick cycles; both are inside the native ranges). The build checks every clip: a loop that closes, no limb vertex inside another part, feet on the floor, slip, no joint turning past 2.7 times its median in a tick. It runs in about 15 s. `edit.py get 259`, then `python3 -m tools.models.field_animations.okuwamon_limbs --source 259-Okuwamon.MMD --out AFTER.MMD` and `edit.py put 259 AFTER.MMD`; checked by `tools/test_okuwamon_limbs.py`.

Raremon (264): `field_animations/raremon_drag.py` rewrites slots 2, 3 and 4 (walk, tired walk, run; slot 0 is shared with 33 and slot 1 with 14-18 and 34, so they are untouched). Raremon drags itself on its arms: each hand is a rigid flat plate planted on the floor for a stance (it slides at most about 12% of the root speed), then lifted and thrown forward in an arc while the other hand pulls; the arm is solved on shoulder and elbow by analytic two-bone IK with a pole vector and asserts reach each tick (nothing is clamped), the fingers only curl a little. The hump surges forward during each pull (a burst of body speed whose mean is the root speed), the lower body and tail lie flat on the floor as lagging springs, the hump sinks into the lower body to keep the arms in reach, and head and jaw follow late on closed spring loops. Cycles 16, 24 and 12 ticks, root speeds 15, 10 and 35 units a tick. The mesh pieces already overlap at rest, so the build checks penetration against the idle; a few vertices of a swinging hand graze the hump in the run. `edit.py get 264`, then `python3 -m tools.models.field_animations.raremon_drag --source 264-Raremon.MMD --out AFTER.MMD` and `edit.py put 264 AFTER.MMD --species-pins`; checked by `tools/test_raremon_drag.py`.
SkullMammothmon (268): `field_animations/skullmammothmon_clash.py` is an offline model delta that keeps the front legs out of the head
(neck, skull, trunk, jaw, ears and the tusks that hang to the floor). Slots 2, 3, 4 and 36 (35 plays slot 2's program) changed; the idle
was already clean. Per tick it turns the neck (pitch, lift) and, where a leg still crossed, that leg's shoulder, knee and ankle; the table
is fitted offline by `fit`, constant data in the module. Everything else is the source's: the other bones, the timing, the root, the other
programs. `python3 -m tools.models.field_animations.skullmammothmon_clash --source BEFORE.MMD --out AFTER.MMD` on the model before this
change (`edit.py get 268`), then `edit.py put 268 AFTER.MMD`; check with `tools.test_skullmammothmon_clash`. The resident buffer has 12 B
to spare, so a change that adds keys to those clips will not fit.
`field_animations/octomon_scuttle.py` (Octomon 278): an offline model delta over the import. The six tentacle legs are walked by damped least squares IK with planted tips (tripod gait, Hermite swings), the body rises, falls and sways, and the two arms and the idle tentacles follow with a delay. Idle 64 ticks (slots 1, 18 and 33 share it), walk 16 ticks at 15 u/tick, tired walk 20 at 10, run 10 at 35. `python3 -m tools.models.field_animations.octomon_scuttle --source <import MMD> --out <MMD>` rebuilds it; register with `tools/models/edit.py put 278`; check with `tools.test_octomon_scuttle`.

Kokuwamon (247): `field_animations/kokuwamon_arm.py` runs after the field pace pass (`after_generator` in
`content/models/imports/pace.json`). The source clips left the arm chain 13/14/15/16 stiff; its shoulder 13, forearm 14
and cover 12 now swing in the idle, walk, condition walk and run, alternating with the other arm. Everything else stays exact.
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_kokuwamon_arm` (after `edit.py get 247`).

Thundermon (252): `field_animations/thundermon_gait.py` writes its idle, walk, condition walk and run on its own 13 bones (ball body that
bobs, boots a boot's width apart that plant and swing, arms on damped springs, bolt lag); `python3 -m tools.models.field_animations.thundermon_gait
--source BEFORE.MMD --out AFTER.MMD` on the model before this change (`edit.py get 252`), then `edit.py put 252 AFTER.MMD`; `field_animations/thundermon_face.py` makes the eyes blink by texture moves over the painted eye disc (frames in unsampled texels, every clip starts and ends
with open eyes); add `--tim-out AFTER.TIM` and `edit.py put 252 AFTER.MMD AFTER.TIM`; check with `tools.test_thundermon_gait`.

Floramon (273): `field_animations/floramon_gait.py` is an `after_generator` row of `content/models/imports/pace.json`, run on the
paced model (the delta MMD and its texture are unchanged: the native eye frames are used). The idle (slot 0, a new 180-tick
program, so slot 33 keeps the old one) is a calm 9 s loop of four breaths with a closed loop; the walk (slot 2) is rewritten
as a bouncy skip (slot 2: 26 ticks, two hops of 13 ticks against the run's 10, a pelvis rise of about 34 units against the run's 61, 16 units a tick; planted-foot IK, slip 73 % to 13 %); the torso crouches on landing, pitches, twists against the hips and sways, and the head rocks side to side (about 27 degrees peak to peak, one side per skip) a little after the trunk, and petals and tail lag behind it; the run (slot 4, shared with slot 36) keeps its bones and
root and only gains a blink (three loops long); the condition walk (slot 3) keeps its legs, arms and root, and the chest leans and the head hangs about 25 degrees lower, bobbing slowly, with the blink. Blinks are `tex` events copying the native eye frames (open, half, shut) over the painted eye, every clip starts and
ends open. Check with `tools.test_floramon_gait` (needs `edit.py get 273`); re-pin 273 in `species-pins.json` after any change.

Tuskmon (253): `field_animations/tuskmon_lift.py` raises the body of the field clips over the strides `tuskmon.py` made (legs re-solved to the same
ankles) and makes the horns rigid on the chest; `python3 -m tools.models.field_animations.tuskmon_lift --out AFTER.MMD` on the model before this
change (`edit.py get 253`), then `edit.py put 253 AFTER.MMD`; check with `tools.test_tuskmon_lift`.

Triceramon (257): `field_animations/triceramon_gait.py` writes four clips from scratch over the imported model (idle, walk,
tired walk and run; the battle idle, the care and the technique clips keep the old ones). The legs are two-bone solves onto
stance points that move back by exactly the root speed, so the planted foot does not slide; the body, head, tail and arms
are authored around them with spring followers that close their loops; `python3 -m tools.models.field_animations.triceramon_gait
--source build/imported-model-edit/edit/257-Triceramon.MMD --out AFTER.MMD` on the model before this change, then
`edit.py put 257 AFTER.MMD`; check with `tools.test_triceramon_gait`.

SaberLeomon (258): `field_animations/saberleomon_gait.py` runs after the field pace pass (`after_generator`). The imported clips
were a trot (walk) and a pace (run) with no flight phase, the head and neck still, the tail replaying the idle's swish, and
the forelegs went through the mane's lower tufts. Now every leg keeps its own foot path but is re-timed with a two-bone IK:
the walks are a lateral-sequence walk and the run is a bounding gallop with about 3 of 14 ticks airborne. The spine flexes
(chest pitch against hip pitch, chest rising with the support), the head follows later with a bob, the tail is carried up in
the run and trails the body on closed lags, the forelegs sit 25 units further back, and the head is carried by a per-tick
table (`HEAD_TABLE`) that `fit()` found offline as the smallest smoothed carriage with no leg-against-mane/jaw triangle
crossing. Re-run `fit()` if the mesh, the gait timing or the profile changes (the resident buffer has little room left).
`tools/models/field_animations/meshclash.py` counts triangle crossings between two bone groups (numpy).
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_saberleomon_gait` (after `edit.py get 258`).

DarkTyrannomon (265): `field_animations/darktyrannomon_idle.py` replaces only the field idle (slot 0). The import's was the
donor's 21-tick fidget as a loop (head 38 degrees, torso 30, jaw 40, tail 42 degrees every 0.7 s, bones turning up to 8
degrees a tick, feet hopping 35 units); the new one is 96 ticks of two swelling breaths, a slow glance to one side and a
shorter one to the other, two yawns a loop, a small and a wide one (the mouth shuts between them), a tail (bones 3-5) that sweeps with a trailing tip, a head (bone 20) that nods and glances,
the lower jaw (bone 21, pitch only: the chin goes straight down, never sideways) and above all the arms (bones 12-15 and 16-19, the big outer limbs: shoulders, elbows, hands and claws swing free with a
lag, each with its own phase), all on springs (`follow`, periodic steady state). The feet (bones 6-8 and 9-11) and the
pelvis are solved onto the floor once and are bit for bit the same in every tick.
Slot 33 (the battle idle) shared the old program and keeps it; the walk, tired walk and run are untouched. Stored in the
plain delta: `edit.py get 265` on the commit before this change, `python3 -m tools.models.field_animations.darktyrannomon_idle
--source THAT.MMD --out AFTER.MMD`, `edit.py put 265 AFTER.MMD`. Check with
`PYTHONPATH=tools python3 -W ignore -m unittest tools.test_darktyrannomon_idle` (`DARKTYRANNOMON_MODEL=` names the model before).

Pumpkinmon (280): `field_animations/pumpkinmon_idle.py` replaces only the field idle (slot 0): the import's 27-tick hop
with the legs (bones 11-14) attenuated to a third of their motion (each channel scaled from the standing pose, tick 0) and
the hips lowered in the pelvis' frame so the soles rise a third as much (33 to about 14 units, leg turns 45 to 15 degrees).
Every other bone, the timing, the loop and the blink events stay as imported. Slot 33 (the battle idle) shared the old
program and keeps it; the walk, tired walk and run are untouched. `edit.py get 280` on the commit before this change,
`python3 -m tools.models.field_animations.pumpkinmon_idle --source THAT.MMD --out AFTER.MMD`, `edit.py put 280 AFTER.MMD`.
Check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_pumpkinmon_idle` (`PUMPKINMON_MODEL=` names the model before).

`field_animations/syakomon_hop.py` (Syakomon 283): an offline model delta over the import, which had one 43-tick pose cycle in all four clips (the shell sliding at 99-135 % of the root). Bone 1 is the lower shell (the body), bone 6 the upper shell with the eyes and teeth, bone 2 the tail fin, all hinged at the back; bones 3-5 are tiny hidden pieces. Walk is a planted hop (28 ticks, 2 hops at 16 u/tick, about 34 units high), tired walk a low dragging shuffle (36 ticks, 11, hops of 14), run long bounds (27 ticks, 3 hops at 38, about 52 high), idle three slow breaths (96 ticks); the mouth and the fin follow the body through damped springs, and the shell's lowest point is solved onto the floor every tick (clear of it in flight). The fin never yaws (a yawed fan cuts the shell deeper than the import does). Slots 1, 18 and 33 share the idle. `python3 -m tools.models.field_animations.syakomon_hop --source <import MMD> --out <MMD>` rebuilds it; register with `tools/models/edit.py put 283`; check with `tools.test_syakomon_hop`.
Deramon's (286) imported idle, walk, tired walk and run (32/23/22/21 ticks, root speeds 20/11/38) pitched the two
feet about their ankles by 45 to 70 degrees without lifting them, so the grey sole texture faced the camera (the same
render with and without back-face culling shows it: a sole face, not a back face or a texture defect), the feet slid at
79 to 100 % of the body's speed, and the shell never moved against the body because bone 1, the shell, is the parent of
the other seven bones. A native binding was not used: the natives nearest to a bird (Biyomon, Kokatorimon, Birdramon)
have 21 to 24 bones with legs, Deramon has eight and its feet are single rigid pieces. `field_animations/deramon_gait.py`
writes each pose in the world and derives the local values from the (rounded) shell bone: idle 120 ticks (slow breath,
looking about, wings hanging with lag, the original blink twice; slot 33 shares it), walk 16 ticks at 16 (a waddle),
tired walk 20 at 10 (lower lean, hanging head and wings), run 10 at 38 (forward lean, wings out, a flight phase).
Feet slip under 6 % of the root speed in stance (under 20 % worst), the shell's lowest point is kept at the floor,
and a shell spring (`spring`) delays and overshoots the body's bob, sway and roll. The idle is stored at tolerance 0
because the rounding of one-unit steps otherwise shows as ticks. Stored in the plain delta
(`edit.py get 286`, `python3 -m tools.models.field_animations.deramon_gait --source THAT.MMD --out AFTER.MMD`,
`edit.py put 286 AFTER.MMD`); check with `PYTHONPATH=tools python3 -W ignore -m unittest tools.test_deramon_gait`.
The pace row and `deramon-pace` overlay are dormant records (the scale lock still names them).
Dragomon (291): `field_animations/dragomon_gait.py` writes its idle, walk, condition walk and run (slots 0, 2, 3, 4) on its own 20 bones
(head-rooted, two-bone legs whose shin is rigid with a flat foot, one plate per wing, a long blade on the left arm, no tail) with planted-foot IK:
`python3 -m tools.models.field_animations.dragomon_gait --source BEFORE.MMD --out AFTER.MMD --tim-out AFTER.TIM` on the model before this change
(`edit.py get 291`), then `edit.py put 291 AFTER.MMD AFTER.TIM`; check with `tools.test_dragomon_gait`. The programs are replaced in place, so slot 33
(battle idle) follows the idle and slot 36 (battle movement) follows the run; the poor and sick idles (slots 1, 14-18, 34) are untouched.

Species 294 (Datamon): `field_animations/datamon_gait.py` writes slots 0, 2, 3 and 4 again (a 72-tick idle, a 36-tick walk,
a 28-tick tired walk and a 21-tick run at 15, 11 and 36 units a tick, slow 12, 14 and 7 tick strides) on the importer's
model: each boot sole is planted in stance and swings through the air on an arc that leaves and meets the ground's speed,
the leg chain is placed by inverse kinematics, and the two big arms hang level with the torso and trail it as lagged pendulums.
`python3 -m tools.models.field_animations.datamon_gait --source SRC.MMD --out-dir DIR` (SRC from `edit.py get 294` before the
change), then `edit.py put 294 DIR/294-Datamon.MMD`. Test: `tools.test_datamon_gait` (`DATAMON_MODEL`).
SlashAngemon (300): `field_animations/slashangemon_gait.py` rewrites only the walk (slot 2, 16 ticks and the closing frame, 20 units a tick) on its 31 bones
with planted-foot IK; the idle, tired walk, run and every other program stay the import's byte for byte (`tools.test_slashangemon_gait` checks a hash of them):
`python3 -m tools.models.field_animations.slashangemon_gait --source BEFORE.MMD --out AFTER.MMD` on the model before this change (`edit.py get 300`),
then `edit.py put 300 AFTER.MMD`. The slot has no aliases, so nothing else follows it. The upper body is authored per part as world rotations on top of the planted legs (a chest counter-turn, arm and blade pendulums, wing breathing, a trailing skirt); `upper_motion` measures it.

Taomon (315): `field_animations/taomon_arms.py` is a post-chibi stage (`post_generator` in `content/models/imports/chibi.json` row 315): it turns only the two
sleeves' first bones (20, 25; rotation) tick by tick in slots 0 (and 33), 2, 3 and 4 so no sleeve piece goes through a leg, an apron or the tail. The turns are
stored in `content/models/imports/taomon-arms.json`, found offline with `python3 -m tools.models.field_animations.taomon_arms --source CHIBI_OUTPUT.MMD
--search content/models/imports/taomon-arms.json` (about two minutes) and applied by every build (`--out AFTER.MMD` applies them to a file). It refuses any input
but the chibi output it was reviewed on. Because it sits after the chibi overlay, the importer delta and the chibi/animation-repair pins do not move; only
`tools/derive/recipes/species-pins.json` `imports["315"]` does. `tools.test_taomon_arms` (needs `edit.py get 315`) bounds the sleeve-against-leg,
apron and tail clash on every tick of the four clips and checks that only the two bones' rotation changed.

Sakuyamon (316): `field_animations/sakuyamon_gait.py` re-solves only the legs (thigh, shin, ankle rotations and the body's height by a few units) of the walk, tired walk and run (slots 2, 3, 4)
onto two steady lanes with a toe-out, keeping the import's ankle heights and fore-aft positions, root motion and every other channel (`tools.test_sakuyamon_gait` hashes the other programs and bounds the per-tick
lane gaps): `python3 -m tools.models.field_animations.sakuyamon_gait --source BEFORE.MMD --out AFTER.MMD` on the model before this change (`edit.py get 316`), then `edit.py put 316 AFTER.MMD`.
`lane_gaps` measures the sideways gap of the thigh, shin, foot and toe meshes, the knee and ankle distance and the leg-on-leg penetration per tick.
Its run is stood up by a second step, `field_animations/sakuyamon_posture.py` (the chest's forward lean cut to 30 %, the pelvis and head turned back by the same so the legs keep their pose; `edit.py get 316`, `python3 -m tools.models.field_animations.sakuyamon_posture --source BEFORE.MMD --out AFTER.MMD`). Its hair is a third step, `field_animations/sakuyamon_hair.py`, on the posture step's output (`edit.py get 316` on the commit before, then `python3 -m tools.models.field_animations.sakuyamon_hair --source BEFORE.MMD --out AFTER.MMD` and `edit.py put 316 AFTER.MMD`): bones 15-18 only (the root of 16 shifted back along the chest's back and 16, 17, 18 turned back, per tick, the least that clears the chest, pelvis, legs, arms and staff, softened over the loop; the hair in the run needs only a shift and a few degrees), the idle included. `hair.measure` counts the hair's vertices inside each part group per tick, and `tools.test_sakuyamon_gait` bounds them and pins the leg gait.
Species 323 (Lynxmon): `field_animations/lynxmon_gait.py` writes slots 2, 3 and 4 again (a 36-tick walk, a 48-tick tired walk and a
32-tick run at 26, 15 and 46 units a tick, each two different cycles) with `quadruped.py` on the model's own four legs, so that the legs
read as four legs on a texture that paints legs and body alike: planted paws, a low swing under the belly, a stance about as wide as the rest pose, a lateral-sequence
walk and a rotary lope, springs on neck, head, jaw and tail. `python3 -m tools.models.field_animations.lynxmon_gait --source SRC.MMD --out
AFTER.MMD` (SRC from `edit.py get 323` before the change), then `edit.py put 323 AFTER.MMD`. Test: `tools.test_lynxmon_gait` (`LYNXMON_MODEL`).
Musyamon (325): `field_animations/musyamon_posture.py` turns the chest back and gives the head the inverse turn in the walk, tired walk and run (slots 2, 3, 4), the pelvis and the cape bones keeping their world orientation; `field_animations/musyamon_hair.py` then moves the mane (bone 24) per tick off the cape and back in the idle and those three, softened over the loop (about 8 minutes). `edit.py get 325` on the commit before this change, `python3 -m tools.models.field_animations.musyamon_posture --source BEFORE.MMD --out MID.MMD`, `python3 -m tools.models.field_animations.musyamon_hair --source MID.MMD --out AFTER.MMD`, then `edit.py put 325 AFTER.MMD`. `tools.test_musyamon_gait` hashes everything else and bounds the lean and the mane's crossings per tick.

Species 336 (Raidenmon): `field_animations/raidenmon_gait.py` writes slots 2, 3 and 4 again (a 24-tick walk, a 30-tick tired walk and a
14-tick run at 17, 11 and 40 units a tick) and raises the idle's pelvis on the few ticks where its soles sank 5 units. The imported clips
turned the foot blocks up to 50 degrees about their floor point instead of bending the legs, so the soles went 88, 81 and 183 units under
the floor and slid; now `quadruped.py` plants both feet (hip and knee solves, the foot block flat and still in stance). The trunk, head,
tail, arms and claws stay the donor's own channels, kept as the first three harmonics of its loop (no sawtooth sweeps, no tick-to-tick
noise) with the arm and body swing eased, a closed-loop lift of any arm that would hang under the floor, and the run's arms turned a
little outward. `python3 -m tools.models.field_animations.raidenmon_gait --source SRC.MMD --out AFTER.MMD` (SRC from `edit.py get 336`
before the change), then `edit.py put 336 AFTER.MMD`. Test: `tools.test_raidenmon_gait` (`RAIDENMON_MODEL`).


Bearmon (353): `field_animations/bearmon_gait.py` is an offline model delta for the idle (slots 0 and 33), walk, tired walk and run (slots 2, 3, 4). It builds them with `quadruped.py` plus a body hook that moves the whole body from one gait phase: hips
against chest, chest roll and shift over the stance foot, hands against the legs on their sides, head, jaw and tail on springs,
and two eased cycles per clip, with a happy hop in one cycle, a stumble wobble in the other and a yawn in the tired walk. The idle (96 ticks, import legs kept) breathes, looks round, flicks an ear, wags the tail and waves a paw. Walk 20 ticks at 16 units, tired walk 28 at 10, run 16 at 36; resident buffer 81,800 of 100,352
bytes. Regenerate with `edit.py get 353`, `python3 -m tools.models.field_animations.bearmon_gait --source BEFORE.MMD --out AFTER.MMD`
and `edit.py put 353 AFTER.MMD`; `tools/test_bearmon_gait.py` covers it.


Species 333 (Raijinmon): a native binding (Ogremon donor) whose recipe asks for the stage `field_animations/raijinmon_gait.py`
(`"gait": "raijinmon_gait"` in `content/models/imports/native-bindings.json`), which writes slots 0, 2, 3 and 4 again with planted legs
under the donor's own trunk and arms (`quadruped.py`). It runs in the build; offline:
`python -m tools.models.field_animations.raijinmon_gait --source BOUND.MMD --rig 333-report.json --out OUT.MMD`. After changing it,
`edit.py check 333 --species-pins` prints the new provider pin for `tools/derive/recipes/species-pins.json`. Test: `tools.test_raijinmon_gait`
(`RAIJINMON_MODELS`).
