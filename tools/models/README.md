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
