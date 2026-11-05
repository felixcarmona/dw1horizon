# Model tools

`delta.py` owns the plain model delta codec. Source-game imports and their
reviewed field overlays remain in derive; immutable recipes remain under
`content/imports/` and `content/modeldelta/`.

Run developer tools from the repository root:

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

Angewomon (190) uses the same binding path with Angemon's complete native
partner rig. Her height/radius metadata matches Angemon (400/150), and the
rest mesh is approximately 416 units tall including the helmet ornaments.
The mesh retains its own bow, hair, feather fans and imported texture.
Angemon supplies distinct care and condition programs as well as locomotion;
the native Myotismon model lacks several of these partner programs. The
provider's final Buster Dive reach pass remains active. Run `get 190` too
before the binding tests, and `check 190 236 --species-pins` for both outputs.

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
