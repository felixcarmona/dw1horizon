# MagnaAngemon on Angemon's native rig

The World 2003 HANG mesh replaces the Card Battle mesh. Culled front, side and
three-quarter comparison of DCB 142, World 2 HANG and World 2003 HANG selected
World 2003 for its upright silhouette, smaller helmet and clearer limbs. World 2
shares the Card Battle model's oversized helmet and compact body. HANG's file is
byte-identical across the supported PAL, Japanese and USA World 3 discs.

The final model uses Angemon (20), `ANGE.MMD`, its 26-bone hierarchy and native
animation programs for every clip. Uniform 1.5 translation scaling preserves the
Ultimate size. Angles, scales, timing, loops and sound events remain native.
Angemon's blink texture copies are omitted because their rectangles belong to
its own texture. Technique order, voice banks 18/11, level, height 608 and radius
187 remain unchanged. The generic Buster Dive adjustment is disabled for this
native animation donor.

Static mesh binding fits the torso, neck, helmet and limbs to the donor. The
collar is lowered and the sashes shortened; the hip skirt is compact and rigidly
bound to bone 18. Each wing consists of two broad World 3 fans sharing a shoulder
hinge, 10/12. One assembly mirrors the other, including polygon winding and
normals. The redundant upper wing pair is omitted to clear the helmet. Fan size
is reduced toward Angemon's silhouette so the native wing stroke remains calm.
No motion curves are authored or retargeted.

Angemon's staff is held by bone 9, as in its native performances. Only its staff
faces are copied, with the original small texture strip and palette packed into
unused World 3 atlas space. Palette row 15 remains reserved for the flat sprite.

`MagnaAngemon.json` records the binding and native clip choices.
`MagnaAngemon-dw3-mesh.json` freezes the source mesh and first pose; the normal
import replay's `mesh_only` path generates that source using the standard library.
The plain model delta borrows both that mesh and native `ANGE.MMD`; the texture
delta adds the staff strip to the source texture. Hashes verify every input and
output. The old DCB import spec remains a frozen historical input.

Developer authoring uses NumPy only for static mesh calculations:

```sh
PYTHONPATH=tools .venv/bin/python -m tools.models.rig_angemon MESH.MMD OUT.MMD
python3 tools/models/edit.py --games SOURCE_GAMES put 206 OUT.MMD OUT.TIM
python3 tools/models/edit.py --games SOURCE_GAMES check 206 --species-pins
DW_NATIVE_ANGEL_MODEL=OUT.MMD PYTHONPATH=tools \
  python3 -m unittest tools.test_native_angemon_rig
```

`MESH.MMD` and its TIM are the frozen World 3 source from `edit.py sources`, not
an already bound model. The helper writes the model, texture and compact skeleton
as `OUT.rig.json`; the species record must use that skeleton before `put`.

The focused proof checks native programs, hierarchy, shoulder wing assemblies,
hip-skirt assignment, staff texture/hand binding, identity, provenance and
resident/cold storage. Visual review uses every frame of idle, walk, run, attacks
and fainting beside Angemon, then the remaining care and reaction clips. Front,
side and three-quarter culled videos supplement the frame sheets.
