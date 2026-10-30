# File formats

Every data format on the Digimon World (USA) disc, at field level, and which files use it. Where one of our
tool docs already describes a format in full (maps, models, sound, scripts), this page gives the outline and links
there. All integers are little-endian. Which file is where on the disc: [disc.md](disc.md); how the engine loads
each format: [engine.md](engine.md).

## Overview

| Format | Files | Section |
|---|---|---|
| TIM | `ETCDAT/*.TIM`, `ETCHI/*.TIM`, `ETCNA/*.TIM`, `STDDAT/**.TIM` | [TIM](#tim) |
| TIM containers | `CHDAT/ALLTIM.TIM`, `CARD/CARD.ALL`, `ETCDAT/ETCTIM.BIN`, `STDDAT/STDTIM.BIN` | [TIM containers](#tim-containers) |
| TMD | `DOOR/*.TMD`, `ETC*/*.TMD`, `STDDAT/*.TMD` | [TMD](#tmd) |
| MMD | `CHDAT/MMD0..MMD5/*.MMD` (178) | [MMD](#mmd-digimon-models) |
| MAP + TFS | `MAP/MAP1..MAP17/*.MAP`, `*.TFS` (242 pairs) | [MAP and TFS](#map-and-tfs-screens) |
| SCN | `SCN/DG.SCN`, `SCN/MAPHEAD.SCN` | [SCN](#scn-scripts) |
| VHB (VAB + SEQ) | `SOUND/VHB/*.VHB` (7) | [VHB](#vhb-sound-banks) |
| EFE | `ETCHI/EFEDAT.EFE` | [EFE](#efe-battle-effects) |
| STR | `MOVIE/*.STR` (4) | [STR](#str-movies) |
| ATR | `STDDAT/B_TOGI.ATR`, `E_TOGI.ATR` | [ATR](#atr-arena-floor) |
| `MWo1` overlay | `*_REL.BIN` (16) | [executable.md](executable.md#mwo1-header) |
| PS-X EXE | `SLUS_010.32` | [executable.md](executable.md#slus_01032-ps-x-exe) |

## TIM

The standard Psy-Q texture format.

```
u32 id = 0x10
u32 flags        bits 0-1 pixel mode: 0 = 4 bpp, 1 = 8 bpp, 2 = 16 bpp; bit 3 = has a CLUT block
[CLUT block]     u32 length (incl. this header), u16 x, u16 y, u16 w, u16 h, w×h u16 colours (BGR555, bit 15 STP)
pixel block      u32 length, u16 x, u16 y, u16 w, u16 h, w×h u16 words
```

`x` and `w` are in 16-bit VRAM units: a 4 bpp image is `w×4` pixels wide, an 8 bpp one `w×2`. Colour `0x0000` is
transparent on the PS1; an opaque black is `0x8000`. The VRAM position in the header is where `LoadImage` puts the
image when the game honours it; several loaders ignore it and use a slot of their own (models, effects, the card
viewer): the VRAM map is in [engine.md](engine.md#graphics).

Loose TIMs of note: `TITLE256.TIM`/`TITLE2.TIM` (8 bpp, 320 px: title and menu background), `SBOY.TIM`,
`SYSTEM_W.TIM` (box borders, cursor), `SPOT256.TIM` (round shadow), `FI_INFO.TIM` (clock and HUD), `ITEM.TIM` (item
icons), `FISHING*.TIM`, `SLOT.TIM` (training slot machine), `LIFE.TIM` (death), `OP.TIM` (ending), the arena's
`*_TOGI.TIM`, `TAISEN*.TIM`, `TIME.TIM`, and `STDDAT/GRADE/*.TIM`, one per tournament cup (23, nearly all 33 312
bytes: 8 bpp with CLUT).

## TIM containers

| File | Layout |
|---|---|
| `CHDAT/ALLTIM.TIM` | 180 entries of **0x4800 bytes** (9 sectors), one per Digimon type in `DIGIMON_DATA` order. Each holds one 4 bpp TIM of 64 words × 128 lines (256 × 128 pixels) with a CLUT of 16 × 8 or 16 × 16 entries, padded to 0x4800. The headers say pixels at (320,0) and CLUT at (0,488); the model loader ignores both and uploads to the type's VRAM slot ([../mods/models.md](../mods/models.md) §3). Entry `type` starts at sector `type × 9`. |
| `CARD/CARD.ALL` | 66 entries of **0x7000 bytes** (14 sectors), one per card: an 8 bpp TIM (CLUT at (448,511)) padded with zeros. The card viewer reads entry `id` at sector `id × 14` into `TEXTURE_BUFFER` and uploads it to (576,256). |
| `ETCDAT/ETCTIM.BIN` | 9 TIMs back to back, walked by `loadStackedTIMFile` at boot; they are copies of the loose `ETCDAT` TIMs: #0 `BI_IN`, #1 `BTLCOMND`, #2 `DEFEFF`, #3 `FEEL_EF`, #4 `FI_INFO`, #5 `SBOY`, #6 `ITEM`, #7 `SPOT256`, #8 `SYSTEM_W`. |
| `STDDAT/STDTIM.BIN` | 6 TIMs back to back (arena HUD). |

A TIM container is found by walking: each TIM's size follows from its block lengths.

## TMD

The standard Psy-Q model format: `u32 id = 0x41`, `u32 flags`, `u32 nobj`, then `nobj` object headers of 7 `u32`
(`vert_top, n_vert, normal_top, n_normal, primitive_top, n_primitive, scale`), then primitives, vertices and normals.
Used for the 33 doors (`DOOR/DOOR00..32.TMD`), props (`ETCNA`: boxes, rocks, the warp, the medal, `UNTI.TMD` the
poop), effect meshes (`ETCHI/BOSS_EFE.TMD`, `MAHI.TMD`), minigame meshes (`KARRING.TMD`, `TAMA.TMD`, `SEA.TMD`),
arena sets (`STDDAT/*_TOGI.TMD`, `*_DAI.TMD`, `WIN_LOSE.TMD`, `CHAMP.TMD`, `DRAW.TMD`) and inside every MMD.

The primitive types the game uses, the engine's rule that textured primitives come first in each object, and how UVs
are made relative to a VRAM slot: [../mods/models.md](../mods/models.md) §2.1 and [engine.md](engine.md#graphics).

## MMD: Digimon models

One file per Digimon (178, in `CHDAT/MMD0..MMD5`; the tamer is `BOYS.MMD`):

```
0x00  u32 off_tmd     always 8
0x04  u32 off_anim    = 8 + size of the TMD
0x08  TMD             one object per bone that has a mesh
off_anim              animation table (u32 offsets per slot, 0 = none) + animations (i16 streams)
```

The TMD's `nobj` counts mesh pieces; the skeleton (`DIGIMON_SKELETONS` in the executable) also has joints without a
mesh, so `DIGIMON_DATA.boneCount` is larger (Agumon: 22 bones, 16 objects). The animation stream (keyframe blocks,
loops, texture moves, sounds), the skeleton and the texture slot are documented in full in
[../mods/models.md](../mods/models.md) §2–3; the engine's playback in [engine.md](engine.md#models-and-animation).
Strings like `CHDAT\TMD0\` and `CHDAT\MTN0\` in the executable are leftovers of an earlier layout with model and
motions in separate files.

## MAP and TFS: screens

Each screen is a pair of files named in `MAP_ENTRIES` (see [world.md](world.md)).

- **`.MAP`**: a table of `u32` section offsets (the first entry equals the table's own size), then the sections in
  this order: setup (camera, three lights, projection, partner region ids, the tile grid of the background), the map
  sprite TIMs (how many 8 bpp and 4 bpp ones is in `MAP_ENTRIES`, not in the file), sprite definitions and instances,
  entities (10 exits with spawn points and destinations, then up to 8 placed Digimon with stats, techniques, AI
  waypoints and script section), and a 100 × 100 collision grid of 10 000 bytes. Uncompressed.
- **`.TFS`**: the pre-rendered background, **uncompressed**: `u16 width, u16 height` (not read), `u32 nCLUT` (1 for
  interiors, 3 for day / evening / night), the 256-colour palettes, then for each non-empty tile of the `.MAP` grid a
  `u32` source position and 128 × 128 bytes of 8 bpp pixels. Its high entropy is just colour indices.

Every field, the collision values, the camera and projection, and `tools/dwmap.py`:
[../mods/maps.md](../mods/maps.md).

## SCN: scripts

**`DG.SCN`** is a container: a table of `u32` offsets (223 entries), each entry aligned to 0x800. Entry 0 is a
copy of `MAPHEAD.SCN` with 0x6800 bytes reserved; entries 1–222 are the screens' scripts. Each entry is padded up to
its sector with leftovers of earlier builds (old script copies and file names such as `\SCN\MAP133.SCN`: during
development each script was its own file). An entry:

```
u16 table size, then pairs (u16 section id, u16 offset) ... until id = 0xFFFF
sections of bytecode; one-byte opcodes, loosely aligned arguments, offsets relative to the start of the script;
section 254 is usually the initialisation; a script ends with FE 00 FF 00
```

**`MAPHEAD.SCN`** uses the same format (282 sections) and holds each screen's header script: its first command
names the `DG.SCN` script and the screen to load, the rest sets per-screen state (pstats, music) before the map
loads. It is loaded whole at boot.

Text inside the bytecode is full-width Shift-JIS (two bytes per character) terminated by `00 00`, with in-line
control codes: `0D 00` line break, `01 07 … 01 01` coloured name, `01 06 05 00 01 01` the player's name,
`01 0A 06 00 01 01` the partner's name. A text box holds 3 lines of about 31 characters. Our mod executable adds a
one-byte text form (patch 0145).

The opcode set is in `decomp/include/dw/script.h` and is interpreted by `decomp/src/main/script_interp.c`. Opcode operand layouts are defined in `tools/dws/bytecode/__init__.py`.
[Bytecode and scnasm](../mods/scripts.md) covers containers, text controls, growth
and round-trip checks; [the interpreter reference](scripts.md) explains execution.

## VHB: sound banks

Concatenated chunks aligned to 2048 bytes; each chunk is

```
0x00  u32 vh_off = 0x0C   (VhbFileHeader in decomp/include/dw/sound.h)
0x04  u32 vb_off          end of the VAB header (VH: header + 128 programs + tone attributes)
0x08  u32 end             end of the body (VB: SPU ADPCM samples)
0x0C  "pBAV" ...          standard Psy-Q VAB header
vb_off                    VAB body
```

| File | Chunks | What it holds |
|---|---|---|
| `SS.VHB`, `SL.VHB` | 1 each | system and menu sounds (banks 0 and 1) |
| `FAALL.VHB` | 33 | music: each chunk is a VAB plus a SEQ block (four `u32`: VH, VB, SEQ, end), 39 sectors apart |
| `VLALL.VHB` | 16 | partner long voices, 15 sectors apart |
| `VBALL.VHB` | 71 | Digimon voices, 7 sectors apart |
| `ESALL.VHB` | 22 | sound effects per map region (`MAP_SOUND_PARA`) |
| `SB.VHB` | 1 | battle sound effects |

The game's SEQ variant (meta events without a length byte, NRPN loops, `0xCD` padding), the strides, the SPU layout
and `tools/sound.py`: [../mods/sound.md](../mods/sound.md).

## EFE: battle effects

`ETCHI/EFEDAT.EFE` is a sequence of fixed **0x5000-byte blocks** (10 sectors), one per effect. Effect `id` (from
0x100) is at sector `start + (id − 0x100) × 10`. The file has 122 blocks: ids 0x100..0x178 plus an empty one filled
with `0xCD`; block 110 carries `effectId` 0x158 instead of 0x16E. In total the file contains 1 050 TIMs and 94 TMDs.

Each block starts with an `EfeFileHeader` (`decomp/include/dw/efe.h`, 0x34 bytes), all fields `u32` offsets within the
block except the last three:

| Off. | Field | Meaning |
|---|---|---|
| 0x00 | `startScript` | effect script entry |
| 0x04 | `initScript` | initialisation script |
| 0x08 / 0x0C | `uvAnims` / `uvAnimsEnd` | UV animation records |
| 0x10 | `subEffects` | sub-effect table |
| 0x14 / 0x18 | `tmdStart` / `tmdEnd` | the effect's TMD |
| 0x1C / 0x20 | `timStart` / `timEnd` | the effect's TIM |
| 0x24 | `dataEnd` | end of the used data |
| 0x28 | `unk28` | |
| 0x2C | `numSubEffects` | |
| 0x30 | `effectId` | must equal the requested id, or the load is rejected |

The scripts are bytecode for the effect stack machine in `BTL_REL`. Loading and residency: [engine.md](engine.md#effects-efedatefe).

## STR: movies

`MOVIE/OP1.STR`, `OP2.STR`, `ED2.STR`, `EDR.STR`: MDEC video at 320 × 176, 15 frames per second, interleaved with XA
ADPCM audio at 37 800 Hz stereo. These are the only files with Mode 2 Form 2 sectors (video and audio sectors mixed),
so they must be copied as raw 2352-byte sectors; ffmpeg and jPSXdec decode them from the raw sectors. Playback:
[engine.md](engine.md#video-mov_rel).

## ATR: arena floor

`STDDAT/B_TOGI.ATR` and `E_TOGI.ATR` (10 000 bytes each): a 100 × 100 grid of floor attributes for two of the arena
stages, the same shape as a `.MAP` collision grid.

## Plain files

- `SYSTEM.CNF`: `BOOT = cdrom:\SLUS_010.32;1`, `TCB = 4`, `EVENT = 16`, `STACK = 801FFFF0`.
- `MMM.DAT`: 27 648 000 bytes of zeros ([disc.md](disc.md#mmmdat)).
