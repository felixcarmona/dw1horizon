# Digimon World 2 technique effects

This page explains how Digimon World 2 (USA) stores and plays a technique's visual effect. It also covers
what carrying one into this game's effect engine would take. Everything here is read from the player's own
DW2 disc with `tools/dw2effect.py`. Nothing from that disc is kept in the repository.

## Where a technique's effect lives

Every disc file is addressed by a number, its *file id*. The DW2 boot executable (`SLUS_011.93`) holds a
table of 0xE5B files: the start sector of each id (i32 at 0x33F94) and its sector count (u16 at 0x37900).

The skill table is file 0x25B. Each record is 0x44 bytes, starting at the offset in the file's first word.

| Offset | Field |
|---|---|
| 0x00 | u16 skill id; bits 16-17 select the caster's clip (file F, G or H of the Digimon's animations), bits 18-19 the kind (3 = support), bits 20-23 the target |
| 0x04 | u8 MP, u8 voice channel, i16 voice XA file |
| 0x08 | i16 power |
| 0x0C | skill-name banner (file << 16 \| entry), a 2D sign, not part of the effect |
| 0x24 | offset of the name |
| 0x2C | `fxFiles[4][3]` (i16): three cast models, three cast animations, three hit models, three hit animations; 0 = none |

The Digimon data files are 0xCB9 (ids below 300), 0xCBB (400 to 500) and 0xCBA (the rest). Their records are
0x28 bytes and give each Digimon's model, its eleven animation files (A to K) and where effects attach:

- +0x1E is the head height.
- +0x20 is the hit point height.
- +0x22, +0x24 and +0x26 are three rows of launch points, one per caster clip, stored in the file's second
  entry.

The base data, file 0xC6C (records of 0x12 bytes), names the skill each Digimon learns.

## An effect object is a small animated model

Each slot of `fxFiles` is an *effect object*: a pair of files.

- The **M** file is a model in exactly the format of a DW2 Digimon model:
  - a bone count;
  - per bone: a vertex list, a normal list, a primitive list and a depth (the parent is the last bone of a
    lower depth);
  - a 4-bit 128x256 texture whose palettes sit inside the image itself (a palette is 16 halfwords on one row).
- The primitive list has four sections: semi-transparent quads, opaque quads, semi-transparent triangles,
  opaque triangles.
  - Each primitive carries vertex indices, UVs, a palette and a texture page.
  - Bits 5-6 of the texture page choose the blend: 0 = half back + half effect, 1 = back + effect (additive),
    2 = back - effect, 3 = back + a quarter of the effect.
  - Only texels with the top bit set blend; colour 0 is transparent.
- The **A** file is an ordinary DW2 animation bank holding one 60-frame clip:
  - one key table per bone, with keys of 0x18 bytes (a 3x3 matrix at 4096 = 1.0, then a translation);
  - then a key index per bone for every frame.
  - A key matrix can scale, which the effects use to grow, flatten and hide parts. A hidden part has a zero
    scale.
  - The key tables of different bones may overlap, so a reader takes only the keys the frames use.
- After the bone tables, the M file can list texture-animation parts: rectangles copied inside the texture
  every tick (x and widths in halfwords).
  - The first two slots are blink slots that effects do not use.
  - Then come 3-frame cycles, 8 ticks a frame.
  - After a 0xFE byte come timed flipbooks of 0x2A bytes: destination, size, period, timer and up to eight
    source positions.
  - The flipbook decoding is unconfirmed: on the one sample checked, all its frames came out at the same spot.

An object lives a fixed time: a cast object 120 ticks at 60 Hz (its whole clip, one frame every two ticks), a
hit object 60 ticks (the first 30 frames).

## How a battle places them

DW2's battles are turn-based. The two rows of fighters stand 0x2800 units apart, facing each other.

1. The camera looks at the caster, the skill's banner shows and the voice line plays (an XA stream, the
   record's file and channel).
2. The caster plays its cast clip and the three cast objects start:
   - slot 0 above the head (y = -0x280 - head height);
   - slot 1 at the launch point of the clip's row (x, -y, -(0x100 + z) in the caster's space, where -z points
     at the target);
   - slot 2 at the feet.
3. After 150 ticks the camera cuts to the target. The damage number shows and the three hit objects start on
   the target: slot 0 above the head, slot 1 at the hit point height, slot 2 at the feet.

There is no projectile code. A breath or a beam travels inside the cast object's own clip: its parts reach
7,700 to 9,000 units forward, almost the whole gap between the rows.

`tools/dw2effect.py render` draws this from a fixed side camera, both objects' timelines together, with the
PlayStation's blending:

```
python3 tools/dw2effect.py --disc DW2.bin skill "Hyper Heat"
python3 tools/dw2effect.py --disc DW2.bin render "Hyper Heat" --caster Cyclonemon --out hyperheat.png
```

## Carrying one into this game's effect engine

This game's techniques are 0x5000-byte chunks of `ETCHI/EFEDAT.EFE`, explained in [the engine
notes](engine.md). `tools/efescript.py` prints a chunk's header and its scripts.

The engine can draw a DW2 effect object:

- Effect op `drawTMD` draws one object of the chunk's own TMD with the running instance's position, Euler
  rotation and a per-axis scale.
- Every pose in the DW2 effects checked is exactly a rotation times a positive per-axis scale: no shear and no
  mirroring. A flattened axis (zero scale) takes its direction from the other two.
- So a converter can turn each drawn bone into a TMD object and each distinct pose into an 18-byte record, then
  write a script that picks the pose of the current frame from a table, turns it by the caster's facing and draws
  it.

What the converter has to rebuild around the drawing, shown on Mega Flame (chunk 63), the ranged fire that
SkullMeramon and Cyclonemon use in this game:

- Mega Flame has no TMD at all: it draws sprites. Its scripts face the target, play two sounds and, from frame
  20 to 38, release one flame puff a frame.
- Each puff flies forward for 23 frames, about 40 to 50 units a frame, growing from a size table. In its first
  20 frames it hits whatever its box touches. So the damage reaches about 1,000 units.
- Its 23 sub-effect slots are exactly the 1 + 4 + 18 instances its scripts start, and its UV-animation area is
  empty.
- Adding a TMD means laying the chunk out again:
  - the loader clears a 32-byte UV-animation record per TMD object, so that area must grow;
  - the sub-effect table needs more slots for the pose drawers;
  - the TMD must come after the sub-effect table, because the engine stops looking for free slots where the TMD
    starts.
- The clean graft keeps the puffs as invisible hitboxes (their drawing script returns at once) and adds
  sub-effects that draw the DW2 poses. The converter must scale the DW2 travel so the picture reaches as far as
  the puffs, about 1,000 units here against about 9,000 in DW2. Otherwise the picture and the damage disagree.

The limits come from the chunk, not the engine:

| Limit | Room in one chunk | Metal Fireball (SkullMeramon) | Hyper Heat (Cyclonemon) |
|---|---|---|---|
| Chunk size | 20,480 bytes | about 16,600 | about 31,300 |
| Kept in battle memory (scripts, tables, TMD) | inside the battle's effect area | about 12,300 | about 26,800 |
| Texture | one strip of 256x32 texels | blocks 344 texels wide, one 40 rows tall | 19,488 texels |
| Palettes | 6 | 6 | 11 |
| Texture animation | scrolling UVs only | one 3-frame flipbook | two flipbooks |

`tools/dw2effect.py budget SKILL` prints these figures for any skill. The figures are estimates of what a
converter would write. The texture check packs every UV block (overlapping prims kept together, and every
flipbook frame, because a flipbook becomes UV switching) into the strip.

- Metal Fireball fits in size and palettes, but its texture does not fit one strip. It fits if the hit texture
  is halved and the cast's 40-row block is cut in two, with the rows the prims share copied into both halves.
  Or it fits with an engine change that gives an effect two strips.
- Large effects such as Hyper Heat need that engine change, more palette rows and a bigger chunk. Or their
  parts must be cut down.
- Swapping a chunk's content changes the technique for every Digimon that uses it. A per-species effect needs
  new chunk ids and a species check where the battle picks the chunk.
- The effect engine's tick rate against DW2's 60 Hz has not been measured. The pose table should be stepped by
  the engine's own frame counter once it is.
