# Model formats and editing tools

For editing an imported or record-original model, use
[model tools](../../tools/models/README.md) and `tools/models/edit.py`.
For species records, skeletons and model selection, see [species](species.md).
The [source build](../building.md) replays imports from the player's discs through
`tools/derive/importers`, then applies the committed deltas. It does not require
sibling extraction projects or private converted models.

This page describes the original USA model formats and `tools/mmd.py` for
inspection, glTF exchange and original-model editing. Addresses and source
locations below refer to the unmodified decompilation. Imported species use
`DIGI.DAT` rather than the original executable's fixed species tables.

## 1. How the game loads a model

`loadMMD(type, class)` (`model.c:3342-3439`), with class 0 = NPC/wild,
2 = tamer, 3 = partner:

1. **Texture**: `loadDigimonTexture` (`model.c:3271-3291`) does
   `malloc3(0x4800)`, `readFileSectors("ALLTIM.TIM", buf, type·9, 9)` (entry
   `type` is 9 sectors = 0x4800 bytes) and `uploadModelTexture`
   (`model.c:3543-3564`) uploads the pixels and CLUT **to the coordinates of
   the VRAM slot**, not to the ones in the TIM header (which say (320,0) and
   (0,488)).
2. **File**: the path is built as `"CHDAT\MMD0\" + name + ".MMD"` with
   `path[9] = '0' + type/30` (`model.c:3395-3398`), but `lookupFileTable`
   keeps only the base name and looks it up in `FILE_OFFSET_TABLE`
   (`file_table_us.c`): the directory is cosmetic. The 4-letter names
   (`AGUM`, `GABU`…) are the table of 180 `char[8]` at `0x80133B44`.
   The NPC goes to `malloc3((size + 0x7FF) & ~0x7FF)` from the *heap*; the
   tamer to `TAMER_MODEL_BUFFER` and the partner to `PARTNER_MODEL_BUFFER`
   (0x18800 bytes in the original; `PARTNER_MMD_MAX`, default 0x20000, in the mod's builds). `readFile` (`file.c:80-96`) reads
   `⌈table_size/2048⌉` whole sectors.
3. **Linking**: `modelPtr = mmd + u32[0]` (the TMD), `animTablePtr = mmd +
   u32[1]`, `GsMapModelingData(&tmd->flags)` converts the TMD offsets into
   pointers in place (which is why `flags` must be 0 in the file) and
   `updateTMDTextureData` (`graphics.c:156-194`) relocates the texture
   coordinates into the slot (see § 3).
4. **Entity**: `initializeDigimonObject` (`model.c:2786-2865`) walks the
   `boneCount` bones of `DIGIMON_SKELETONS[type]`: if `objIndex ≠ −1`,
   `GsLinkObject4(tmd, &pos->obj, objIndex)`; it links the bone's
   `GsCOORDINATE2` to the parent's (`parentIndex`, −1 = root); it reads the
   initial pose from animation 0 and starts `startAnimation(entity, 0)`.
   `renderDigimon` (`2867-2929`) draws each bone with `GsGetLws` +
   `GsSortObject4`.

Digivolution (`evl.c:358`, `loadMMDAsync`/`applyMMD`,
`model.c:3566-3717`) reads the `ALLTIM` entry and the MMD to `0x80020000`
(general loading area) and then copies the MMD to `PARTNER_MODEL_BUFFER`;
reincarnation (`dooa.c:1030`) does the same. `applyMMD` with class 0 reads
the TMD and the animations from separate files `CHDAT\TMD0\*.TMD` and
`CHDAT\MTN0\*.MTN` that do not exist on the disc: leftovers from when they
were separate.

**The partner is not reloaded when changing screens**: its model is read when
creating the game, when continuing, when evolving or reincarnating. NPCs are
read on every screen.

## 2. The `.MMD` format

*Little-endian* integers. All TMD offsets are relative to the start of its
object table (`mmd + 8 + 12`), the animation ones to the start of the
animation table.

```
0x00  u32 off_tmd      always 8
0x04  u32 off_anim     = 8 + TMD size (there is no gap in any of the 178 files)
0x08  TMD              header + objects + primitives + vertices + normals
off_anim              animation table + animations
```

### 2.1 TMD

```
u32 id = 0x41   u32 flags = 0   u32 nobj
nobj × { u32 vert_top, n_vert, normal_top, n_normal, primitive_top, n_primitive; i32 scale (= 0) }
primitives of all objects (in object order)
vertices of all objects   {i16 x, y, z, pad=0}
normals of all objects    {i16 x, y, z, pad=0} in 4.12 (4096 = 1.0)
```

That order (primitives, vertices, normals) holds in all 178 files. One TMD
object = one rigid piece, in the local space of its bone. Oddities:
`TANE.MMD` (Tanemon) declares 22 normals in objects 0 and 1 but its
primitives use larger indices, which fall into the normals of the next
object (the GTE reads `normal_top + 8·index` without looking at the count);
`HYOG`, `JIJI` and `HAGU` have normals that no primitive uses.

**Primitives used** (header `u8 olen, u8 ilen, u8 flag, u8 mode`, then
`ilen` words; `mode`: bit 0 no shine, bit 1 semi-transparent, bit 2
textured, bit 3 quad, bit 4 Gouraud, bits 5-7 = 1 polygon; `flag`: bit 0
unlit, bit 1 double-sided, bit 2 gradient). Count over the 178:

| mode/flag | What it is | ilen | Words | Count |
|---|---|---|---|---|
| 0x3C/0 | textured Gouraud quad | 8 | 4 UV, (n0 v0)(n1 v1)(n2 v2)(n3 v3) | 38 346 |
| 0x34/0 | textured Gouraud triangle | 6 | 3 UV, (n0 v0)(n1 v1)(n2 v2) | 30 450 |
| 0x2C/0 | textured flat quad | 7 | 4 UV, (n0 v0)(v1 v2)(v3 0) | 561 |
| 0x3E, 0x36, 0x2E, 0x26 /0 | the same, semi-transparent | 8/6/7/5 | | 838/442/359/98 |
| 0x24/0 | textured flat triangle | 5 | 3 UV, (n0 v0)(v1 v2) | 132 |
| 0x25/1, 0x2D/1 | unlit textured tri./quad | 6/7 | 3/4 UV, RGB color (code 0), (v0 v1)(v2 v3·) | 36/10 |
| 0x38/0 | **untextured** Gouraud quad | 5 | RGB color+code 0x38, (n0 v0)…(n3 v3) | 16 |

UV words: the first carries `CBA` (CLUT) in its upper half, the second
`TSB` (page and blend mode), the rest 0. There are no lines, *sprites*,
gradients or double-sided faces. `olen` (GPU packet size) depends on the
type: 7, 9 or 12 when textured, 8 for 0x38.

**Engine restriction**: within each object, all textured primitives must
come **before** the untextured ones: `updateTMDTextureData`
(`graphics.c:177-183`) leaves the loop at the first untextured one, and those
after it would keep the page and CLUT from the file. This holds in all 178.

### 2.2 Animations

**Table**: one `u32` per *slot*, offset from the start of the table
(0 = the animation does not exist). The size of the table is not stored: it
is the smallest non-zero offset / 4 (between 5 and 62 *slots*; 54 for
Agumon). Several *slots* can point to the same animation (Agumon: 44 used,
35 distinct). Some *slots*: 0 idle, 2 walk, 0x2E+i technique i.

**Animation** (stream of `i16`, `startAnimation`, `anim.c:201-274`):

```
u16 frameCount | 0x8000 if the initial pose includes scale
(boneCount − 1) × [sx sy sz] rx ry rz tx ty tz     initial pose of bones 1..n−1
instructions...
0x0000                                             end (frame 0 is never reached)
[0xCDCD]                                           optional padding (compiler garbage)
```

Rotations in 1/4096 of a turn, scale in 4.12, translation in model units.
Each bone's matrix is `RotMatrix` (= Rx·Ry·Rz) · `ScaleMatrix` with the
translation (`anim.c:119-128`). Bone 0 has no pose: it is the entity (its
scale/rotation/position in the world). `initializeDigimonObject` reads the
pose of animation 0 **assuming it has no scale**; 8 models (NUME, DIGI,
GERE, TENT, TONO, ENUM, EDIG, EVAN) do have it, but the immediate
`startAnimation(0)` corrects it.

**Instructions** (`tickAnimation`, `anim.c:276-357`). Each one starts with a
word `code << 12 | frame` (12 bits) and runs when the frame counter (starts
at 1, 20 per second) reaches that value:

| Code | Words | What it does |
|---|---|---|
| `0x0` *keyframe* | `F`, then one or more blocks `0x8000 | mask<<6 | bone`, `divisor`, one `i16` per active channel | sets the speed of each channel: `delta/divisor` per frame with the remainder spread out (`animReadMomentumInstruction`, `398-418`). Mask: bit 14 scale x … bit 6 translation z (9 channels). Bit 15 of the next word chains another bone. The speed keeps being applied until the channel's next *keyframe* |
| `0x1` loop start | `0x1000 | repetitions` (0xFF = infinite) | stores the return point |
| `0x2` loop end | `0x2000 | F`, `return_frame` | subtracts one repetition; if any remain, goes back to the start and sets the counter to `return_frame` |
| `0x3` texture | `0x3000 | F`, `x<<8 | y`, `w<<8 | h`, `x'<<8 | y'` | `MoveImage` within the model's VRAM slot (x and w in 16-bit words = 4 pixels): eye blinks, mouths. Copies the first rectangle to the destination |
| `0x4` sound | `0x4000 | F`, `bank<<8 | note` | `playSound(bank, note)` if the entity is on screen; bank 4 is replaced by the entity's `vabId` (its voice) (`anim.c:335-346`) |

Interpreter quirks that matter when writing animations (all handled by
`import-anim`):

- **The first instruction always runs on tick 1**, whatever its frame:
  `startAnimation` sets `loopEndFrame = 1`. The originals always start with
  a (possibly empty) keyframe at frame 1; a stream whose first key is at
  frame 2 plays one tick early.
- Timing: on each tick the momentum is applied first and then the
  instructions of the current frame run, so a keyframe at frame F moves the
  pose from tick F+1 on. If S[i] is the pose after tick i+1 (S[0] = the
  initial pose), a keyframe at frame a+1 with `(val, div)` takes S[a] to
  S[a+div], and after k ticks it has added exactly `trunc(k·val/div)` (the
  counter starts at `div` and is decremented by `|val % div|`).
- A speed keeps running until the channel's next keyframe; channels not
  named in a keyframe keep theirs. A keyframe can name the same bone twice
  (two blocks with different divisors); the originals never do.
- **Loops**: there is a single loop register. The loop start is normally
  taken by the pre-check at the start of a tick, so it must be the pending
  instruction when the tick begins (after the last instruction of the
  previous frame, before those of the jump frame). The loop end (counter is
  a `u8`: 0xFF is infinite and 0 also becomes infinite, since 0−1 = 0xFF)
  sets the frame to J and **re-runs the instructions of frame J in the same
  tick**; the pose is not reset, so what repeats is the motion: tick N+k
  moves like tick T_J+k, where N is the tick of the loop end and T_J the one
  that ran frame J (true for all 1242 infinite loops of the 178 files). For
  a seamless loop the pose at the loop end must equal the one at T_J, and
  every speed has to be set again at frame J.
- `frameCount` = the frame of the loop end in looping animations (923
  cases) or later; the animation stops after the tick whose frame equals
  it. The frame field has 12 bits: one pass can last 4095 ticks at most
  (GREY's slot 0x1B plays 225 × 20 ticks with a finite loop).

Details: root motion (translation of bone 0) is not added to the pose; it is
transformed by the entity's matrix and accumulated into its position
(`applyRootMomentum`, `434-499`); in *slots* 0x23/0x24 the X is cancelled.
On reaching `frameCount` the animation stops (bit 0 of `animFlag`). Before
the instruction loop the game checks `instruction & 0x1000`, which is also
true for code 3: a texture instruction pending for a later frame would be
taken as a loop start. This never happens in the data (texture ones always
come in the same frame as the previous one), but a new animator has to
respect it. Besides code 3, `animateEntityTexture` (`anim.c:76-117`) cycles
texture rows every 2 frames for nine fixed types (flames).

Totals over the 178: 79 905 *keyframes*, 13 897 texture, 4 918 sound,
1 310 loops.

### 2.3 Skeleton (in the executable)

`DIGIMON_SKELETONS[180]` (`model.c:2305`, RAM `0x8011CE60`) points, per type,
to an array `{s8 objIndex, s8 parentIndex}` of `boneCount` entries
(`SKELETON_*`, `model.c:72-2304`). `objIndex = −1` is a bone without a mesh
(joint), `parentIndex = −1` the root. Bone 0 is always `{−1,−1}`.
Agumon: 22 bones, 16 TMD objects, 6 empty bones. There are 79 distinct
skeletons for the 180 types and 56 are shared by several types
(`python3 tools/mmd.py info` shows the pointer); the partner has room for 34
bones (`PARTNER_POSITION_DATA[34]`, `main.c:3279`) and the tamer for 22; the
maximum used is 32 (Machinedramon).

## 3. The texture: `ALLTIM.TIM` and the VRAM slots

Entry `type` = bytes `type·0x4800 … +0x4800`: 4 bpp TIM (`flag 8`), CLUT of
16×N (N = 16 in 168 entries, fewer in 12), image 64×128 words = 256×128
pixels (174 entries; ANLG is 248×120, TENS and BRIK 256×88, TONO 256×112,
JURE 256×96, HAGU 256×104: the glTF UVs are normalized by the real size). Color 0x0000 = transparent; opaque black is 0x8000.

| Who | Page (`pixelPage`) | Image in VRAM | CLUT (16×16) |
|---|---|---|---|
| tamer | 0x15 | (320, 256) | (0, 488) |
| partner | 0x15 + v offset 0x80 | (320, 384) | (16, 488) |
| NPC slot k = 0..4 | 0x16 + k/2, v (k%2)·0x80 | (384+64·(k/2), 256+128·(k%2)) | ((k+2)·16, 488) |

(`model.c:3385-3390`, `3411-3425`.) The primitives in the file carry
coordinates **relative to the slot**: `u` 0..255, `v` 0..127, `TSB = 5 |
blend_mode<<5` (0x05, 0x25, 0x65) and `CBA = 0x7A00 + (row<<6)` (an add, not an
or: row 8 is 0x7C00, since 488 has bit 3 set), i.e. the
CLUT at (0, 488 + row) with row 0..14. `updateTMDTextureData`
(`graphics.c:156-194`; the names of its parameters are swapped in the
decompilation) adds to every textured primitive: to the `CBA` the x index of
the slot's CLUT, to the `TSB` the page (clearing its low 5 bits) and to each
UV the offset `(offY<<8)+offX` (v + 0x80 for the partner and for odd NPCs).
Consequences:

- Each **face** picks one of up to 16 palettes of 16 colors (CLUT row);
  a texture can thus have up to 256 distinct colors, but each pixel only
  makes sense with the palette of the faces that use it.
- Row 15 is used by the flat *sprite* (`renderFlatDigimon`,
  `model.c:2722-2774`: `clut + 0x3C0`, four 15×15 frames at u 0xE0/0xF0,
  v 0x60/0x70 of the texture), which the tournament shows instead of the
  model.
- Texture animations (code 3) copy rectangles of the texture itself: the
  alternative frames (closed eyes, etc.) have to stay in the same place, or
  the instructions must be changed too.

## 4. `tools/mmd.py`

Standard library only (own PNG code). It reads names, `boneCount` and
skeletons from `extracted/SLUS_010.32`; the type comes from the file name
(`--type` if it is renamed).

```bash
python3 tools/mmd.py info extracted/CHDAT/MMD0/AGUM.MMD          # objects, primitives, skeleton, slots
python3 tools/mmd.py roundtrip                                   # all 178: raw and normalised
python3 tools/mmd.py gltf extracted/CHDAT/MMD0/AGUM.MMD build/models/AGUM.gltf   # .gltf + .bin + .png
python3 tools/mmd.py preview extracted/CHDAT/MMD0/AGUM.MMD a.png --anim 0x2E --tick 12 --yaw 0 90
python3 tools/mmd.py import-gltf extracted/CHDAT/MMD0/AGUM.MMD AGUM-editado.gltf AGUM.MMD
python3 tools/mmd.py import-anim extracted/CHDAT/MMD0/AGUM.MMD new-anims.gltf AGUM.MMD --map Spin=0 --keep-tex
python3 tools/mmd.py anim-roundtrip                              # all 178: export → import-anim → compare per tick
python3 tools/mmd.py transplant extracted/CHDAT/MMD0/GABU.MMD extracted/CHDAT/MMD0/AGUM.MMD AGUM.MMD
python3 tools/mmd.py transform extracted/CHDAT/MMD0/AGUM.MMD AGUM.MMD --bone-scale 3=1.6
python3 tools/mmd.py tex-export 3 agumon.png        # 256×128 RGBA PNG with each face's palette
python3 tools/mmd.py tex-import 3 agumon.png ALLTIM.TIM
python3 tools/mmd.py recolor 3 ALLTIM.TIM --hue 200     # or --swap bgr
python3 tools/mmd.py copy-tex 0x11 3 ALLTIM.TIM         # Gabumon's texture into Agumon's entry
```

**Data model.** `MMD.parse` stores each primitive raw (it is decoded into
fields with `Prim.decode`/`Prim.encode`), vertices and normals as two
*pools* with `(start, count)` per object (this absorbs the TANE case) and
the animations already interpreted (instructions as dictionaries; whatever
follows the `0x0000` is kept as a tail). `MMD.build()` writes it back:
**178/178 identical**, and also 178/178 if every primitive is decoded and
re-encoded first (animations are always re-encoded).

**glTF.** One node per bone (`bone00`…, with `extras.dw_bone/dw_obj/
dw_parent`) hanging from a `dw_root_flip` node that rotates 180° around X
(the PS1 has Y pointing down); each TMD object's mesh is **rigid** and sits
on its bone's node (as the game does it; there is no *skinning*), with the
pose of animation 0 as the rest pose. Materials `dw_m<mode>_f<flag>_p<row>_t<TSB>`
(the name is the primitive's specification: type, palette, blending),
256×128 RGBA PNG texture (each pixel with the palette of the faces that use
it; whatever no face covers takes the majority palette of its 8×8 block, and
the texture-animation frames take that of their destination).
Animations: the game is simulated frame by frame exactly like `anim.c`
(`AnimPlayer`: integer momentum with its remainder counters, `int16`
rotations, the loop pre-check, `u8` loop counter) and one sample per tick is
exported (20 fps, linear interpolation; finite loops expanded); infinite
loops are run once, and `extras` holds the return point (`loop_sample`: the
sample whose motion follows the last one), the sounds and the texture moves
(`tick` = sample index). Bone 0 has no rest pose; the translation of
`bone00` is the root motion accumulated through bone 0's R·S (the
displacement of the entity, not part of the pose). Custom attributes `_DW_VERT`/`_DW_NORM` and primitive/mesh
`extras` store the TMD indices, the order and the quads so that importing a
glTF without topology changes gives the same file: **177/178 identical**
(not TANE, because of the overlapping normals; the result is equivalent).
Validated with the official Khronos validator (`gltf-validator`): 0 errors.

**Import (route a).** `import-gltf BASE.MMD x.gltf output.MMD`
rebuilds the TMD from the meshes of the `boneNN` nodes (in the bone's local
space), quantises positions to `i16`, normals to 4.12 and UVs to
0..255/0..127, takes type, palette and mode from the material name, pairs
consecutive triangles `(c2,c1,c0)(c1,c2,c3)` into quads (or uses the hints
from the export) and **keeps BASE's animation section intact**. It serves to
move, scale, deform or replace the geometry of each piece while keeping the
skeleton. If the mesh is remade in Blender: one mesh per bone, no weights
(if there is *skinning* it has to be split by bone), materials named
`dw_…` (copy the name from an exported one).

**Animations (route d).** `import-anim BASE.MMD x.gltf out.MMD` encodes
the animations of a glTF with BASE's skeleton (nodes `bone00`… found by
`extras.dw_bone` or by name) into slots of BASE and keeps everything else
(TMD, the other slots; slots that shared the replaced animation keep the
old one; animations no slot uses any more are dropped, identical ones are
shared). How:

1. **Slot**: `--map NAME=SLOT` (repeatable; with `--map` only the mapped
   animations are imported), else `extras.dw_slot` or the name `animNN`
   (decimal, as the export writes it). A slot beyond the table grows it.
2. **Sampling**: each glTF animation is evaluated once per game tick
   (glTF time t → tick t·`--fps`, 20 = real time; `--fps 10` plays it
   twice as slow) with its own interpolation (LINEAR with slerp, STEP,
   CUBICSPLINE); channels it does not animate take the node's rest value.
   Rotation (a quaternion, the only form glTF has; Blender converts its
   Euler curves) becomes the engine's Euler angles (M = Rx·Ry·Rz, 4096 =
   360°) **unwrapped against the previous tick**: of the two equivalent
   solutions and their whole-turn shifts the closest one is taken, so a spin
   keeps adding up (several turns are fine as long as consecutive ticks
   differ by less than half a turn). In gimbal lock (ry = ±90°) rx is taken
   halfway between the neighbouring ticks. Scale ×4096, translation in game
   units (rounded). For `bone00` the translation track is the root motion:
   it is differentiated per tick and brought back through bone 0's R·S.
3. **Keyframes**: per bone, the channels that move are split greedily into
   the longest segments the engine reproduces within `--tol` units at every
   tick (the engine adds `trunc(k·val/div)`, so the check is exact; default
   1, `anim-roundtrip` uses 0; for root motion it bounds the accumulated
   displacement, so the per-tick step can differ by 2); segment ends land exactly on the samples, so
   the error does not accumulate. Two encodings are tried per bone, one
   segmentation shared by all its channels (one block per keyframe, like the
   originals) and one per channel, and the smaller wins; keys that would not
   change a running whole-number speed are omitted. Segments are split at
   |val| > 32767.
4. **Loops**: infinite if the animation says so (`extras.loop_sample` of
   our export), if its name ends in `_loop`, with `--loop NAME[=SECONDS]`
   (restart point), or if the replaced slot of BASE loops (then from the
   start; `--no-loop NAME` prevents it). The loop start goes before the
   frame of the restart sample, which gets a keyframe for every channel that
   moves, and the loop end goes on the frame after the last sample. Since
   the loop repeats deltas, the last sample should be the restart pose (a
   Blender cycle whose last key equals the first does that); if both poses
   are the same rotation the last one is written in the restart's Euler
   solution. **Repeated motion** (the same per-tick motion and events, p
   ticks, R ≥ 2 times) is also tried as finite loops and kept if smaller:
   this is what brings back the originals' finite loops (and GREY's 4501
   ticks) and keeps every re-encoded file within its sectors.
5. **Sounds and texture moves**: `--keep-sounds`/`--keep-tex` keep those of
   the replaced slot (blinks: Agumon's idle blinks through code 3),
   `--gltf-events` takes them from the animation extras (our export,
   possibly of another Digimon: careful, texture moves belong to its texture
   layout and bank 4 is the voice of whoever plays it). Those after the end
   are dropped. A keyframe (empty if needed) always precedes a texture
   instruction in its frame (the 0x1000 pre-check), and frame 1 always has
   one.

`anim-roundtrip [MMD ...]` exports every MMD to glTF (temporary folder),
imports all its animations back with `--tol 0 --gltf-events`, and plays the
original and the new slot side by side with `AnimPlayer`, three passes of
infinite loops: pose of every bone (rotation compared modulo whole turns and
the equivalent Euler solution, then as matrices), root motion per tick, stop
tick, sounds and texture moves. Result for the 178: **4843 slots, 4832
identical on every tick and 11 within 1 unit of angle** (gimbal-lock ticks
where only rx ± rz is defined: AIRD/EAIR 0x29, MONZ 0x2/0x23/0x3A, VEDA
0x21, ANDR 0x3A, KUNE/EKUN/DOKU 0x2A, PICC 0x5); no re-encoded file grows
beyond its sectors (most shrink: Agumon 72 012 → 70 922 with every slot
re-encoded exactly, 70 448 with `--tol 1`). About 9 s on 16 cores.

**Retarget (route e): `tools/retarget.py`.** Moves animations between
**different** skeletons with an explicit bone map, e.g. Vegiemon's vines onto
Cherrymon's branch arms:

```bash
python3 tools/retarget.py extracted/CHDAT/MMD0/VEGI.MMD build/models/JURE-partner.MMD out.MMD --tgt-type 121 \
        --slot 0x30 --map 9=8:10 --map 10=10:12@0.8 --map 11=12@0.7 --map 2=3@0.3 --hips '1=1*1.2' --sounds
```

Both models face −Z with Y down, so motion is carried in model space. For each
tick, a mapped source bone S gives its world rotation delta from the source's
reference pose (slot 0, first tick): `D = Wsrc(t)·Wsrc_ref^T`. The target bone T
is posed with world rotation `D·Wtgt_rest`, so it turns the way S turned from
its own rest orientation. Its local rotation is solved under its posed parents.
This makes rest-pose differences and different local axes irrelevant.

- `T=S1:S2` carries a direction instead of a rotation: the chord from joint S1
  to joint S2 (several pieces of a 6-piece vine at once onto one arm piece),
  turned by the smallest rotation, with no twist.
- `@W` scales the delta's angle (damping or exaggerating).
- `--hips T=S*K` moves T by K times S's offset from its reference position (hops,
  squats). Root motion is scaled by `--root-scale`.
- Sounds can be copied (`--sounds`). Texture moves are not.
- The library function `transfer()` returns per-tick local rotations so a caller
  can layer more motion on top (`content/models/cherrymon/anims.py`).

Limits: an unmapped target bone keeps its rest (or layered) rotation, so its
children move with that underneath; mirrored limbs need their own source bones;
scale is not carried. Do not retarget a biped onto a quadruped or a tree. The
structure has to match: a chain onto a chain.

**Contact sheets: `tools/animsheet.py`.** It renders any slots of an MMD as rows
of frames with **one fixed camera**. `mmd.py preview` refits the view to every
pose, so hops and lunges cannot be seen there. The sheet applies root motion and
bone 0's facing, draws the ground line, and puts a small bar code of the slot
number at the left of each row. `--list` prints the length, loop sample, root
motion and sounds of each row.

```bash
python3 tools/animsheet.py build/models/JURE-partner.MMD s.png --type 121 --slots 2 4 0x36 --every 2 --size 200 --yaw 60 --pitch 10 [--no-root]
```

**Transplant (route b).** `transplant MESH.MMD ANIM.MMD output.MMD`: the TMD
of one and the animations of the other; it requires the same
`DIGIMON_SKELETONS` (or at least the same bone → object assignment). The
mesh uses the palettes of its own texture, so the `ALLTIM` entry has to be
copied too (`copy-tex`). Careful: ANIM's texture instructions (code 3) keep
moving the rectangles of **its** texture (Agumon's eyes) over MESH's; if the
two do not have the same layout, the blinks paint the wrong pieces (those
instructions would have to be removed or adapted).

**Textures (route c).** `tex-export`/`tex-import` convert an `ALLTIM` entry
to PNG and back: for each CLUT row the pixels that belong to it are
gathered, its 16 colors are recomputed (exact if they fit, otherwise
*median cut*; alpha < 128 becomes 0x0000) and the indices are reassigned.
Exporting and importing without changes gives the same image (0 differing
pixels). `recolor` rotates the hue or swaps channels of all the CLUTs
without touching the pixels. Limitation: a pixel shared by faces with
different palettes is only fitted to one of them.

## Editing and rebuilding

Keep generated MMD, TIM and glTF files under `build/`. Do not commit the player's
model data. `tools/models/edit.py get` creates an editable model from disc replay;
`put` validates an edit and writes our plain delta. Use its `check` command before
building the integrated disc. See the model-delta guide for source-disc arguments.

Original-model generators live in `content/models/`. A generator reads the
player's original model and records our edits as source code or specifications.
The derive models step runs these generators. Add or change a generator through
that step rather than manually replacing files in a release image.

The standalone converters (`tools/dcb2mmd.py`, `tools/dw2mmd.py`,
`tools/dw3mmd.py`) and `tools/import_batch.py` remain developer tools for authoring
conversion specs. Their sibling-project settings are not player prerequisites.
Published replay uses frozen specs in `content/imports/specs/`, bundled readers,
and source/output pins. See [import internals](../reference/imported-species.md).

Use the [story language](story-language.md) to place an NPC or change its presence.
The compiler updates script setup and map slots together and checks model heap
use. Build and test through [building.md](../building.md); release checks are
orchestrated by [the release pipeline](../patcher.md#release-pipeline).

## Model budgets

Keep the original PlayStation's 2 MB as the acceptance target. File size alone
is insufficient: skeletons, primitive buffers, animation tracks, textures and
simultaneously visible models all consume constrained storage. Validate the
species record and the final screen's heap, VRAM and SPU use with `tools/species.py`,
`tools/heapcheck.py` and `tools/membudget.py`. See [memory](../reference/memory.md).
Optional larger emulator buffers do not establish console compatibility.

Rebuild from a memory-card save when testing a changed disc. Check field motion,
battles, evolution and transitions on the actual integrated image; a successful
glTF export or model round trip does not establish runtime correctness.
