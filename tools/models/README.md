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
