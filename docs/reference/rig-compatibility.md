# Import animation rig compatibility

A native binding replaces the source model's skeleton. Its mesh fitting and
source battle retargeting must agree about both the hierarchy and the final
joint dimensions. A clip with the correct number of bones can still unfold the
wrong rig if it restores translations from before a geometry reshape.

`native_binding.bind` fits the mesh and captures its rotation basis first. A
chibi pass then changes local mesh geometry and joint offsets. After that pass,
`clip_rig.fit_context` carries the final offsets and scales into the battle
context through the shared `clip_rig.fit` transform and recomputes its body reference position and body-motion scale. It
keeps the original rotation constants: taking them from an animated field idle
would incorrectly include arm pumping and other field posing in the mesh basis.
The generated binding report records the actual battle reference in `battle_rig`.

Every import still finishes at the shared `clip_rig.conform` provider boundary,
including source, donor and authored clips. `clip_repair.fit_rig` remains an alias
of `clip_rig.fit`. Size bounds stay at 0.92–1.08; anatomical proportions stay
within 0.08 at the first tick and 0.12 across the clip. Correcting the authoring
context does not replace those final encoded-program checks.

SkullSatamon exposed this ordering error. Its source has 25 bones and its bound
Ogremon rig has 18; that conversion is intentional and performed explicitly.
The defect was using a neck offset of `(118,2,1)` instead of `(134,2,1)`, a head
offset of `(-17,-58,-7)` instead of `(-26,-106,-13)`, and a shin offset of
`(95,27,-9)` instead of `(77,22,-7)`. Assaultmon and Maildramon had the same
post-binding reshape. Their meshes, proportions and field programs are preserved
by the correction.

Historical replays from the SkullSatamon native binding through main found no
field regression: all five field clips have identical poses at every tick and
bone. Restored battle clips first acquire the stale dimensions in `2ce18e19`,
merged on the first-parent path as `74ec313a` (#439).

## Checking a build

Use decoded importer models from the same revision, including imported donors:

```sh
python tools/models/rig_qa.py --models build/imported-models --out build/rig-qa
python -m unittest tools.test_rig_qa tools.test_native_battle tools.test_clip_repair
```

The tool runs provider builders and overlays before inspection. Every occupied
program is checked for bone count and index bounds. Imports preserving their
source skeleton compare its ordered object and parent assignments with the
written hierarchy. Native retargeting additionally captures its actual target
context and checks its joint dimensions against the written model. The JSON
records slots and differences per bone. A nonzero exit reports mismatches or
inputs that could not be replayed. `--resume` explicitly reuses completed exports;
use a new output directory after changing inputs or generators.

`reference_pose_changes` preserves differences in rotations and carrier
placement for inspection. These are animated poses, not automatically rig
faults: a field idle may pump its arms or plant its body at a different height.
The audit does not infer anatomical bone names or historical authorship from
MMD bytecode, which stores neither skeletons nor bind matrices. Reference-pose
checks require an authoring context; source-preserving deltas receive structural
checks. Bone-count guards also run at the shared source-rig fitting and native
retarget boundaries, before any channels are copied.

## Reviewing restored clips

Run `battle_qa_native.py` on the final provider model and the recipe's restored
slots, and compare care QA with the same main model. A clip approved against old
dimensions must be reviewed again after correcting those dimensions. Keep source
clips that pass; retain the fitted native clip where the source motion no longer
fits the proportions cleanly. Store reviewed clearance turns with
`native_recipe.py ID SLOT --clearance OPERATIONS.json --reason REASON`, where the
file maps each slot to its final shared-fit operations. These keep the source
motion and the existing fidelity limits. Withdraw a failed source clip through the recipe
tool, one species per invocation:

```sh
python tools/models/native_recipe.py ID SLOT --reason 'Measured reason'
python tools/models/edit.py --from BUILD put ID DECODED.MMD --force
```

This removes its obsolete repairs, timing override, dependent source aliases and
source-specific final clearance placements.
The native program remains in the generator's table and receives the geometry
reshape normally. `edit.py put` updates the provider pin without changing the
source delta. Validate field program bytes, mesh bytes, resident storage and
approved chibi proportions before accepting the result.
