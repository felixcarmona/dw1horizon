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

DemiDevimon (236) binds its imported mesh to Birdramon's native skeleton and
programs through `field_animations/native_binding.py`. The recipe in
`content/models/imports/native-bindings.json` assigns every rigid piece, fits
the wing spars and trailing web, and scales native translations once. Native
timing, rotations, scales and controls remain intact. Texture-copy commands
are removed because the imported atlas has another layout; effect origins
use the scaled native joints. The imported delta and texture remain pinned.

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

Vilemon's slow walk keeps its existing footwork, body, wrist poses and mesh.
The `vilemon` pass after field pace transfers native Ogremon's shoulder and
elbow motion over each 15-tick stride; every other program, including the run,
remains exact. `VILEMON_MODEL=MODEL PYTHONPATH=tools python3 -m unittest
 tools.test_vilemon_walk` checks the complete provider layer against its input.

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
`field_animations/valkyrimon.py`; player builds replay the plain delta.
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
