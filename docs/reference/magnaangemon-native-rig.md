# MagnaAngemon on Angemon's native rig

The mesh is Card Battle's (DCB 142), the importer's own output after the size
pass. Two World 2003 HANG pieces are grafted on: the shoulder shield on the black
upper arm, recoloured to the helmet's purple, and the bracelet with the blue gem
on the white forearm, fitted round it with the gem facing out.

The final model uses Angemon (20), `ANGE.MMD`, its 26-bone hierarchy and native
animation programs for every field and care clip. Uniform 1.1825 translation
scaling preserves the Ultimate size. Angles, scales, timing, loops and sound
events remain native. Angemon's blink texture copies are omitted because their
rectangles belong to its own texture. Technique order, voice banks 18/11, level,
height 608 and radius 187 remain unchanged.

## Binding

`tools/models/rig_angemon.py` binds the mesh offline (`MagnaAngemon.json`):

- The Card Battle rest is its zero pose (arms down, symmetric), but for the wing
  bones (`posed`), which keep their first-frame spread.
- Limb segments (`segments`) are swung and stretched onto Angemon's; hands and
  feet (`ends`) turn with their segment without stretching; every other piece
  moves with the body's least-squares offset.
- The wings and the back cloth (`pivots`) turn about their own Card Battle
  joints: the Angemon bones they ride are moved there, in every program's pose
  (no translation keys ride those bones). The cloth rides Angemon's own cloth
  bone 25, so it swings with the clips.
- The grafts' faces are packed into free texels and palettes of the Card Battle
  texture (the shield at half resolution).

## Battle clips from Card Battle

The overlay `magnaangemon-battle` (`tools/models/field_animations/bound_battle.py`,
row 206 of `content/models/imports/bound-battle.json`) plays the Card Battle
source's own clips on the bound rig (`battle_source`: the same importer output,
written by the imports step as `imported-models/206.battle.MMD`). Each bone
follows the pieces it carries, fitted from their vertices. Only the slots that
pass `tools/models/battle_qa_native.py` are listed: 0x21, 0x28, 0x29, 0x2B,
0x37, 0x3B and 0x3C (29 ticks, `ticks`). 0x2A (crossings), 0x2C (the source
sinks under the floor), 0x34 (retime) and every slot the source lacks (0x2E-0x33)
stay Angemon's. The row's `drop_npc_slots` and the exact compaction keep the
resident clips at 95,808 of 100,352 bytes.

The final provider pass `mesh_stability` reorders the vertex pool, so the QA
reads the model before it (the animation is the same):

```sh
python3 tools/models/battle_qa_native.py check 206 FINAL.MMD imported-models/206.battle.MMD MAIN.MMD
DW_BOUND_BATTLE_MODELS=build/everything/imported-models python3 -m unittest tools.test_bound_battle
```

## Authoring

The model delta borrows the Card Battle mesh, native `ANGE.MMD` and the World 2003
mesh (`MagnaAngemon-dw3-mesh.json`, made by the import replay's `mesh_only`
path); the texture delta borrows the Card Battle texture and the World 2003 one.
Hashes verify every input and output. Developer authoring uses NumPy only for
static mesh calculations:

```sh
python3 tools/models/edit.py --games SOURCE_GAMES sources SOURCES 206
PYTHONPATH=tools .venv/bin/python -m tools.models.rig_angemon SOURCES OUT.MMD
python3 tools/models/edit.py --games SOURCE_GAMES put 206 OUT.MMD OUT.TIM
python3 tools/models/edit.py --games SOURCE_GAMES check 206 --species-pins
DW_NATIVE_ANGEL_MODEL=OUT.MMD PYTHONPATH=tools python3 -m unittest tools.test_native_angemon_rig
```

The helper writes the model, texture and compact skeleton as `OUT.rig.json`; the
species record must use that skeleton, and `bound-battle.json` must pin the
model (`source_sha256`, `edit.py repin` moves it), before `put`.

The focused proof checks native programs, the pivot joints, hierarchy, every
Card Battle vertex on its bone plus the grafts, identity, provenance and
resident storage.
