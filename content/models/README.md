# content/models/

Scripts and specs that build native and imported partner models. The derive models step owns generator order; imported models and field overlays have their own derive steps.

| folder | builds |
|---|---|
| `master-tyrannomon/`, `cherrymon/` | MasterTyrannomon 124 and Cherrymon 121 from existing models (`make-model.py`; Cherrymon also has `clips.py`/`anims.py`, a small animation toolkit) |
| `partners/` | KingSukamon, Icemon, Meteormon, WaruMonzaemon, Myotismon, ShogunGekomon, Machinedramon, Jijimon and Analogman; see [partner models](../../docs/mods/features/partner-models.md) |
| `dcb-import/` | JSON specs for the Veemon, Puppetmon and Kimeramon imports (`tools/dcb2mmd.py`, `tools/dw2mmd.py`) |
| `mega/` | the demo Mega WarGreymon's model (`make-model.py`); its species file is `content/species/373-wargreymon.json` |
| `imports/` | the imported provider of the 175 imports (`species.py`, `models.json`: each id's model and its reviewed field overlay, `tools/models/field_animations/*.py`), run by tools/derive's overlays and species steps on the models its imports step makes from the player's discs (`content/imports/`, `content/modeldelta/`) |

`imports/` supplies imported-species records backed by disc replay and our deltas.
The everything build uses this provider instead of the standalone demo converters.
Generated models belong under `build/`. `REUSE_MODELS=1` retains existing original
model outputs; rebuild those outputs after changing a generator.
