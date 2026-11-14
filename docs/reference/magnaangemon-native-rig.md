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
The bound model itself has no authored or retargeted motion curves.

Angemon's staff is held by bone 9, as in its native performances. Only its staff
faces are copied, with the original small texture strip and palette packed into
unused World 3 atlas space. Palette row 15 remains reserved for the flat sprite.

## Battle clips from World 2003

`MagnaAngemon-dw3-battle.json` (format `native-battle-source-v1`) freezes the
clip choices the World 3 importer makes (`import_batch.analyse_clips_dw3`) on the
same mesh; its import-batches recipe (`battle_source`) makes it on the player's
discs, and the imports step writes it as `imported-models/206.battle.MMD`. The
overlay `magnaangemon-battle` (`tools/models/field_animations/bound_battle.py`,
row 206 of `content/models/imports/bound-battle.json`) plays its clips on the
bound rig with `native_battle.py`'s retarget: the pieces of each bone are fitted
from their vertices, the mirrored left wing from the right wing's, the hips
follow the body and not the sash. Only the slots that pass
`tools/models/battle_qa_native.py` on the final model are listed (0x21, 0x28,
0x29, 0x2B, 0x2C, 0x2E-0x34); the hits keep Angemon's impact sounds, and the
battle and technique slots are compacted exactly for room. The row's
`drop_npc_slots` leaves out Angemon's clips of the slots only the tamer, the NPCs
and the kart race play (0x1C and 0x1D here), which no partner starts: 97,600 of
100,352 bytes. Field and care slots stay Angemon's byte for byte. The get-up
(0x2C) is the source's clip with `repairs` (tools/models/clip_repair.py): while
it lies on the floor one thigh turns 15 degrees and its knee 6, so the foot
follows the source's, and the body is lifted 40 units where it sank under the
floor. The faint (0x2B) plays the source's 54 ticks at 34 (`ticks`, 1.59; the
slot's own 31 would be 1.74), with the body lifted 60 units from tick 18, where
it sank (under the floor 0.224 heights, was 0.323), and the right knee turned 10
degrees over the last ticks (tip of the foot 0.150 heights, was 0.155; Angemon's
clip 0.719). The rest of its tip error is the rig's proportions (Angemon's thigh
is shorter than the source's), not a turn.

```sh
python3 tools/models/battle_qa_native.py check 206 FINAL.MMD imported-models/206.battle.MMD MAIN.MMD
DW_BOUND_BATTLE_MODELS=build/everything/imported-models python3 -m unittest tools.test_bound_battle
```

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
