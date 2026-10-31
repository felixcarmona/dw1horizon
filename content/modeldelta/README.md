# Model edits

These deltas contain our edits to imported models. They contain no complete game
models or textures. The source models, textures and donor animations are rebuilt
from the player's discs using `content/imports/specs` and the bundled converters.

`models.json` pins each source, delta and result by SHA-256 and size. Each plain
MD3 delta stores references to source ranges and additions representing our edits.
`tools/modeldelta.py` accepts only plain mode and verifies the reconstructed
result. The structured prototype is unsupported because it could retain original
source data. `import-batches.json` pins the frozen converter specs;
`import-sizes.json` records geometry scaling. The other manifests record source
provenance and reproducibility checks.

## Editing an animation

Prepare the three source discs once, as described in
[building](../../docs/building.md). Then:

```sh
python3 tools/v61edit.py --source-disc 'dcb=/path/Card Battle.bin' \
  --source-disc 'dw2=/path/World 2.bin' \
  --source-disc 'dw2003=/path/World 2003.bin' check 183
python3 tools/v61edit.py get 183
# Edit build/v61edit-work/edit/183-Wormmon.MMD with tools/animstudio.py.
python3 tools/v61edit.py put 183 build/v61edit-work/edit/183-Wormmon.MMD
python3 tools/v61edit.py check 183 --species-pins
```

`--from DERIVE_OUT` uses an existing derive output's `source-games` directory.
`put` updates the delta, its manifest pins and the species pins, including field
overlays. Re-encoding an unchanged model preserves its committed delta.

When changing the importer, preserve the final models: write old sources with
`v61edit.py sources OLD`, write new sources with `sources --unchecked NEW`, then
run `v61edit.py rebase OLD NEW`. This updates source pins and deltas while checking
that the target bytes remain unchanged.

A spec's donor is an original DW1 species: its motion is read from the player's
DW1 extraction during import. Changing donors requires rebuilding and rebasing
the import before editing the model. Donor motion belongs in the regenerated
source, rather than as additions inside an edit delta.

## Nefertimon front legs

Nefertimon (198) uses Monochromon's three-joint front legs. The reviewed import
spec maps right upper leg/shin/paw `4,5,6` to donor `7,8,9`, and left
`7,8,9` to donor `10,11,12`. The former right upper/shin assignments were
reversed; the missing left paw assignment layered native idle movement onto
that paw during field locomotion. This was a mapping defect, not a missing
animation in the source disc.

The corrected spec is pinned in `import-batches.json`. Its regenerated source
was rebased with `tools/models/edit.py sources --unchecked` and `rebase`, then
stored with `put`. The final delta preserves the reviewed native idle in slots
0 and 0x21 and the existing technique aliases. Mesh, texture, native hit clips,
root motion and slot durations are unchanged. Unreferenced animation streams
and parse tails were removed with `share_identical_streams`; only identical
referenced programs are shared.

Review with `tools/animstudio.py` using the regenerated species 198 model and
`extracted/CHDAT/MMD1/MONO.MMD:47`, especially slots 0, 2, 3, 4, 0x21 and
0x24. Select front paws 6 and 9 explicitly when calling its `metrics()` helper:
the CLI's two lowest joints include a hind leg on this rig. Paw joint positions
do not measure paw rotation, so also compare the paw's local rotation ranges
and world rotation swing. A mapped paw can turn without moving its own joint.
