# MagnaAngemon on Angemon's native rig

MagnaAngemon uses native Angemon's 26-bone hierarchy and animation programs for
field movement, idles, attacks, reactions, fainting and care. The DCB 142 mesh is
bound to those bones. No gait, wing cycle, joint-angle curve or secondary motion
is authored. Bone translations are uniformly converted by 1.25 to retain the
Ultimate model's proportions; native angles, scales, key times, loop controls
and sound events are preserved. The model remains height 608 and radius 187,
with the same texture, voice banks, attribute, specialties and techniques.

The binding spec is `content/imports/specs/MagnaAngemon.json`. It identifies
Angemon (20), `ANGE.MMD`, the geometry source, the anatomical bone map and native
technique-slot choices. The original geometry import is frozen separately in
`MagnaAngemon-mesh.json`. Its donor motion never reaches the final model.

Each complete four-piece wing assembly shares one native wing hinge (14/16),
attached at the shoulders. The left assembly mirrors the right, including
polygon winding and normals. Feather pieces retain fixed positions relative to
one another. The remaining wing bones retain Angemon's hierarchy and animation
but carry no mesh. Armor and limbs are bound to the corresponding native joints;
shin armor and soles fit the donor's limb/foot envelope. Head ornaments and hair
share the head bone. All these changes are static mesh binding.

Technique slots retain their species order and select unchanged native Angemon
performances. Training slot 60 selects Angemon's kick. The registry's
`native_animation_donor` prevents the generic Buster Dive repair from replacing
native root motion. Angemon's texture-copy events are omitted because its blink
rectangles do not belong to MagnaAngemon's texture page. Sound routing remains
battle bank 18 and care bank 11. Effect origins follow the native bone indices,
with offsets scaled for the larger rig.

The stored plain delta names both the DCB geometry import and native `ANGE.MMD`
as sources; their hashes are checked before decoding. This avoids storing the
native animation set as a new binary asset. Authoring is developer-only:

```sh
PYTHONPATH=tools .venv/bin/python -m tools.models.rig_angemon MESH.MMD OUT.MMD
python3 tools/models/edit.py --from DERIVE_OUT put 206 OUT.MMD
python3 tools/models/edit.py --from DERIVE_OUT check 206 --species-pins
```

`MESH.MMD` is the pinned geometry import obtained with `edit.py sources`, not
an already rebound model. The helper also writes the compact object's skeleton
as `OUT.rig.json`. The species record must use that skeleton before `put`.

The focused integration proof compares every resulting program with its native
Angemon source and checks hierarchy, complete wing assemblies, identity,
additional donor provenance and resident/cold storage:

```sh
DW_NATIVE_ANGEL_MODEL=OUT.MMD PYTHONPATH=tools \
  python3 -m unittest tools.test_native_angemon_rig
```

Review uses culled front and three-quarter frame sheets of every distinct clip,
plus front/side/three-quarter videos beside native Angemon for walk, run, idle,
attack and fainting. The native-motion proof supplements visual mesh review.
