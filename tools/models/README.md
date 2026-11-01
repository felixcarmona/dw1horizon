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
```

The editor can extract the three source games with repeated `--source-disc`
arguments. `--from DERIVE_OUT` reuses their extracted inputs. Its cache lives in
`build/imported-model-edit/`; accepted models still have to pass every
source, delta, target and species pin. Rejected edits leave deltas and pins intact.
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

Measure final field speeds and voice-note coverage with:

```sh
python3 tools/models/audit_field.py --from build/dev-everything --out build/field-audit.json
PYTHONPATH=tools python3 -m unittest tools.test_field_audit tools.test_model_provider
```

The audit uses each overlay report's generated skeleton. Its JSON includes
walk/condition/run durations, root travel per tick, bank-4 notes and missing
voice tones. Long programs (40 ticks or more) need an in-game switch-latency
measurement as well as an offline speed measurement.
