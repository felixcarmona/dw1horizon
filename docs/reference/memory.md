# Memory

How the 2 MB of main RAM, the 1 MB of VRAM and the 512 KB of SPU RAM of the PS1 are shared out by the game and by our
patch series: the layout, the fixed buffers, the `malloc3` heap and its budget, and every patch that moves bytes around.
Addresses are those of the USA executable. For the addresses of individual game-state variables see
[ram-map.md](ram-map.md); for the executable's sections and overlays as files see [executable.md](executable.md).

## In short

- A normal PS1 has no spare RAM. The only elastic resource is the `malloc3` **heap**: what the main executable leaves
  between the end of its bss and the bottom of the stack. It holds the current screen's NPC and wild Digimon models,
  nothing else on world screens.
- **Every byte the main executable gains comes off the heap** (code, strings, tables, data, bss, file-table entries).
  A screen whose models no longer fit never finishes loading. The build measures this and stops ("The heap budget
  rule" below).
- The series makes room by moving data and code out of the resident executable: the map background is streamed
  instead of resident, NPC models drop animations NPCs never play, the stack is trimmed, code that only one overlay
  calls lives in that overlay, the title/card menus are an overlay of their own, and the save extensions live in the
  load area instead of the bss.
- New content that must run on a console goes where the game itself puts things: overlays and data read from the CD on
  demand. There is plenty of disc space.
- VRAM and SPU RAM are almost entirely allocated by design.

## Main RAM (2 MB)

Original executable (Metrowerks build), as linked:

| Range | Size | What is there |
|---|---|---|
| `0x80000000–0x8000FFFF` | 64 KB | BIOS kernel (vectors, tables, kernel heap). Never touched; its apparent gaps depend on the BIOS |
| `0x80010000–0x8008FFFF` | 512 KB | **load area** (`GENERAL_BUFFER`): overlays, the map background, the battle effects heap; see the next section |
| `0x80090000–0x800907FF` | 2 KB | PS-X EXE header (dead after loading) |
| `0x80090800–0x80113A5F` | 525 KB | code (game and Psy-Q libraries) |
| `0x80113A60–0x80134C4B` | 133 KB | rodata, data, sdata (tables, strings, font) |
| `0x80134C4C–0x801BFB63` | 556 KB | sbss + bss: game state, the partner and tamer model buffers, ordering tables and GPU packet buffers, VAB headers, SEQ, the resident scripts |
| `0x801BFB70–0x801EFEFF` | 193 KB | `malloc3` heap |
| `0x801EFF00–0x801FFEFF` | 64 KB | stack (`_stack_addr` 0x801FFF00, `_stack_size` 0x40 KB) |
| `0x801FFF00–0x801FFFFF` | 256 B | above the stack top |

In our builds (GCC, [compiler.md](compiler.md)) the executable still starts at 0x80090000 and the stack top is still
0x801FFF00; what moves is `_end` (`main_BSS_END`) and the stack size, and the heap is everything between them.

`initializeHeap` computes the heap at run time from linker words: it starts at `(_end & ~15) + 16` and ends at
`_stack_addr − _stack_size · 1024`. Changing either word changes the heap without touching code.

### Rules the layout imposes

- The executable cannot grow downward: it starts right above the load area, whose highest user (TRN/TRN2) ends at
  0x8008F800.
- It grows upward only into the heap.
- The GCC bss is generated from the decompilation's symbol list (`decomp/tools/gen_bss.py`): its variables can be moved,
  not shrunk, without rewriting the code that uses them.
- `__start` does not zero the bss in the GCC build (the BIOS loader does it from the header's `b_addr/b_size`); a new
  section outside the bss has to be initialised in code.
- Two bss arrays of the original rely on the next array to absorb an overflow. GCC orders bss differently, so the
  series sizes them for their real contents: `TAMER_MODEL_BUFFER` 0xE000 (`BOYS.MMD` is 0xDECC; the original's 0x7800
  spilled into the following 0x6800 array; patch 0002) and the MAPHEAD script buffer (patch 0004, later 0091; below).

## The load area (`0x80010000–0x80090000`)

512 KB that every mode reuses. Nothing kept in it outlives the next mode change, which is why it is never heap.

| Mode | What occupies it |
|---|---|
| intro, movies | `MOV_REL` with its MDEC buffers, from 0x80010000 (to 0x80085C54 since patch 0098; below `OVL_TRN_BASE`) |
| title | the title's TIMs (`ETCTIM.BIN`, 0x80010000–0x8002F000) |
| world | the map background (`.TFS`; the `.MAP` is read there first and processed). Original: the whole TFS stays resident, up to 0x78800 bytes, ending at 0x80088800. With the series: a 4 KB header and an 8-tile ring, 0x80010000–0x80035000, and the rest is world scratch (below) |
| training | `TRN_REL`/`TRN2_REL` at 0x80088800–0x8008F800 |
| menus, fishing, death | `DOO2` and `FISH` at 0x80070000, `MURD` at 0x8007C000, `DOOA` at 0x80080000, `DGET` at 0x80080800; the map is reread on return |
| curling | `KAR` at 0x80053800, alongside the screen's map |
| evolution, ending | `EVL`, `ENDI`, `EAB` at 0x80060000; the evolving model at `EVO_MMD_ADDR` 0x80020000 |
| battle | the EFE engine from 0x80010000 (16 slots and an effects heap of 0x41000), `BTL_REL` (TIM and TMD prefix, then code) from 0x80052AE0. The background is reread on exit |
| tournament, VS | `STD_REL` / `VS_REL` from 0x80052AE0 (STD ends at 0x8007D0DC; BTL and VS are kept at or below it by link asserts), arena model at 0x80038000 |
| title card menus, save machine, sleep save | `MENU_REL` at 0x80052AE0 (patch 0211) |
| always | `TEXTURE_BUFFER` at 0x80088800 (0x7800: temporary TIMs, the card image, script arrays); DOOA/MURD ordering tables at 0x8008C000 and 0x8008E000 |

The top 2 KB, 0x8008F800–0x8008FFFF, are reached by nothing.

### `include/dw/memmap.h`

Patch 0013 names the fixed memory map in one header that both C and the linker scripts include (it holds plain
`#define`s only, since `psx.mk` runs every `.ld` file through the preprocessor). The link asserts below are written
against it.

| Name | Value | Meaning |
|---|---|---|
| `LOAD_AREA_START` / `_END` | 0x80010000 / 0x80090000 | the load area |
| `EXE_HEADER_ADDR` | 0x80090000 | PS-X EXE header, then the executable |
| `STACK_ADDR` | 0x801FFF00 | stack top |
| `STACK_SIZE_KB` | 0x10 | 16 KB (0x40 originally) |
| `STACK_MEASURED_MAX` | 0xF78 | deepest measured use; the link asserts the stack is at least 4× this |
| `MIN_HEAP` | 0x26800 | the link fails if the heap is smaller |
| `OVL_MOV_BASE` | 0x80010000 | movies |
| `OVL_BTL_BASE` | 0x80052AE0 | BTL, STD, VS, and the menu overlay |
| `OVL_KAR_BASE` | 0x80053800 | curling |
| `OVL_EVL_BASE` | 0x80060000 | EVL, ENDI, EAB |
| `OVL_FISH_BASE` | 0x80070000 | FISH, DOO2 |
| `OVL_MURD_BASE` | 0x8007C000 | death |
| `OVL_DOOA_BASE` | 0x80080000 | DOOA |
| `OVL_SHOP_BASE` | 0x80080800 | DGET (and the unused shop overlay's slot) |
| `OVL_TRN_BASE` / `OVL_TRN_MAX_END` | 0x80088800 / 0x8008F800 | TRN, TRN2 |
| `GENERAL_BUFFER_ADDR` | 0x80010000 | `.MAP` then `.TFS`, sound bank staging, EFE base |
| `DOOA_WORK_OFFSET` | 0x4B000 | DOOA's work area, from `GENERAL_BUFFER` |
| `TFS_HEADER_ADDR` / `_SIZE` | 0x80010000 / 0x1000 | streamed background: the TFS header |
| `TFS_RING_ADDR`, `TFS_SLOT_SIZE`, `TFS_RING_SLOTS`, `TFS_RING_END` | 0x80011000, 0x4800, 8, 0x80035000 | the tile ring |
| `WORLD_SCRATCH_START` / `_END` | 0x80035000 / 0x80053800 | free on every world screen |
| `SAVE_EXT_ADDR` / `SAVE_EXT_MAX` | 0x8004E000 / 0x4000 | save-file extensions during a card operation |
| `SOUND_STAGING_MAX` | 0x3E000 | the most a sound bank staged at `GENERAL_BUFFER` may take |
| `TEXTURE_BUFFER_ADDR` / `_SIZE` | 0x80088800 / 0x7800 | temporary TIMs, card image, script arrays |
| `BOSS_EFE_TMD_BUFFER_ADDR` | 0x80058000 | boss effect model |
| `ARENA_TMD_ADDR` | 0x80038000 | STD/VS arena model |
| `EVO_MMD_ADDR` | 0x80020000 | the evolving model (EVL, DOOA) |
| `DOOA_SHARD_ADDR` / `_SIZE` | 0x80044800 / 0x5DC0 | reincarnation shard scratch |
| `OVL_OT_0_ADDR` / `_1_` | 0x8008C000 / 0x8008E000 | DOOA and MURD ordering tables |
| `BATTLE_FINISHER_TIM_ADDR` … `BATTLE_BUFF_MODEL_ADDR` | 0x80052AE0 … 0x80055328 | the TIM and TMDs at the start of every battle overlay |
| `PARTNER_MMD_MAX` | from the build (generated `partner_mmd_max.h`) | partner model buffer |
| `TAMER_MMD_MAX` | 0xE000 | tamer model buffer |
| `MAP_SCRIPT_MAX` | 0x4000 | one `DG.SCN` entry (largest original 0x3800) |
| `SCRIPT_OFFSET_TABLE_SIZE` | 0x800 | `DG.SCN`'s offset table |
| `MAPHEAD_SCRIPT_MAX` | 0x8000 | resident `MAPHEAD.SCN` |
| `SEQ_BUFFER_SIZE` | 0x8000 | SEQ block of the current music font (0x5800 originally) |
| `SPU_BANKS_START` / `SPU_REVERB_START` | 0x1010 / 0x7B7C0 | SPU range the sound banks may use |

## Fixed buffers in the main bss

These are static arrays: they cost heap whether or not they are full.

| Buffer | Size | Holds |
|---|---|---|
| `PARTNER_MODEL_BUFFER` | `PARTNER_MMD_MAX` (0x18800 by default) | the partner's MMD: mesh and resident animations |
| `TAMER_MODEL_BUFFER` | 0xE000 | `BOYS.MMD` |
| `MAPHEAD_SCRIPT_BUFFER` | 0x8000 | `MAPHEAD.SCN`, resident from boot |
| `SCRIPT_OFFSET_TABLE` | 0x800 | `DG.SCN`'s offset table |
| the screen script | 0x4000 | the current `DG.SCN` entry |
| SEQ buffer | 0x8000 | every track of the current music font |
| `COLD_ANIM_BUFFER` | 0x2000 | a partner animation read from the disc when it starts (patch 0113) |
| `SAVE_FILE` | 0x2000 | the v1 save file; its battle registrations are game state between card operations |
| `GS_WORK_BASES` | 2 × 0x14000 | GPU packet buffers (one per frame buffer) |
| ordering tables | 2 × 0x4000 | |
| `MOD_TFS_CLUTS` | 1.5 KB | resident copy of the map's first three palettes (patch 0159) |

### Partner model buffer (patches 0064, 0176)

The partner is never reloaded on a screen change and battle, menus and training all use its model, so it lives in a
fixed array, not the heap. The original's is 0x18800 (100 352 bytes; the biggest original MMD, Etemon, is 97 812).

- `PARTNER_MMD_MAX` sizes the array. It is a Makefile variable passed through a generated header (default 0x18800);
  the link fails when it leaves less than `MIN_HEAP`. `tools/build-full.sh` sets it to the biggest partner model on
  the disc, never below 0x18800, so a disc without big models keeps all its heap. Every byte over 0x18800 is a byte
  less of heap on every screen. The model converters read the same environment variable.
- With the default buffer the heap has roughly 26 KB over `MIN_HEAP`, so a disc's biggest model can be up to about
  0x1E000 before the link fails.
- **Why a fixed buffer and not a heap block sized to the model.** The bytes are the same either way (the worst screen
  setup plus the partner has to fit in the same RAM), and a heap block would fragment the heap: an evolution frees the
  old partner and allocates a bigger one while the screen's NPCs sit between them. The heap is one block today, which
  is what makes per-screen budgeting possible.
- **Guards.** A model bigger than the buffer (a `DIGI.DAT` built for another executable) never overwrites what follows:
  `loadMMD`, `loadMMDAsync` and `applyMMD` refuse it as a partner, natural evolution skips it as a target
  (`isPartnerModelFit`), the lab menu reports it. Evolution and reincarnation first read the model at `EVO_MMD_ADDR`
  (0x80020000 in the load area): a 0x4800 texture plus the model end at 0x80048800 at the biggest buffer the heap
  allows, below `SAVE_EXT_ADDR` (link assert), the battle prefix and the EVL overlay.

### Cold animations (patch 0113)

Animations are most of a model (an imported model averages 27 KB of mesh and 64 KB of animations). `tools/coldsplit.py`
cuts a partner model in two: the resident MMD and a cold part that follows it in `DIGI.DAT` from the next sector. For
each cold slot the resident animation table holds `0x80000000 | (length in words << 16) | offset in words`.
`startAnimation` reads such an animation into `COLD_ANIM_BUFFER` (whole sectors, 8 KB; the longest cold animation is
under 5 KB) with `readFileSectors` and plays it from there (`loadColdAnimation`). Only the partner has cold entries;
any other entity asking for one starts nothing, as with an empty slot.

The species record's `modelSize` is the resident size, so every fit check sees only the resident part. `species.py
build` with `COLD=1` (the default of `tools/build-full.sh`) cuts the slots in `coldsplit.py`'s `COLD_SLOTS` (5 and 7–13:
reactions, eating, pooping) of partner species ≥ 180; `species.py check` joins them back and compares. Over the imports
this moves about 15 KB per model out of the buffer. Techniques are not cold: an enemy of the same species plays them
in battle. On a real drive the first eating clip may stall briefly for the seek.

### MAPHEAD buffer (patches 0004, 0091)

`MAPHEAD.SCN` (every screen's setup section and the sections the C code calls: shopkeepers, the new-game questions,
cards, the tournament) is read once at boot by `initializeScripts` into `MAPHEAD_SCRIPT_BUFFER` and stays resident.
Its text is what a translation grows ([../mods/translating.md](../mods/translating.md)).

| | original | patch 0004 | patch 0091 |
|---|---|---|---|
| `MAPHEAD_SCRIPT_BUFFER` | 0x61A8 (the whole-sector read spills into the next array) | 0x6800 | **0x8000** |
| `SCRIPT_OFFSET_TABLE` | 0x2000 | 0x2000 | **0x800** |
| together | | 0x8800 | 0x8800: the bss does not grow |

Where the 6 KB come from: `DG.SCN`'s offset table is its first sector (u32 offsets; entry 0 starts at 0x800, so at most
511 entries plus the end). The original read 0x2000 bytes at boot; the other 0x1800 were the start of entry 0, a copy of
`MAPHEAD.SCN` that nothing reads (`getScript` only reads `table[id]` and `table[id + 1]`, and `getScript(0)` uses the
resident MAPHEAD). The boot read is now one sector and `scnasm.py` keeps the table in it.

The compiler checks MAPHEAD against the target's buffer (`tools/dws/backend.py` `MAPHEAD_LIMITS`: 25 000 for the
original executable, 0x8000 for ours; `--maphead-max` overrides). `tools/build-full.sh` reads `MAPHEAD_SCRIPT_MAX` from
the tree it builds, passes it to the story build (keys that do not fit stay in English and are listed) and checks the
final file. The original's `MAPHEAD.SCN` is 24 686 bytes; a full Spanish one is about 25.7 KB.

### EVL shard scratch (patches 0062, 0079)

When a partner evolves away, the EVL overlay breaks its mesh into shards, written bone after bone into one scratch
array. The original's was 5 436 bytes, enough for the original partners but not for boss models or most imported
species (up to about 10 KB); running past it overwrote the bone order and particle state and left a shard object
ticking in the unloaded overlay (a crash at the next battle). Patch 0062 bounds the writes (a bone whose shards do not
fit gets none; its wireframe still fades); patch 0079 sizes the array to `EVL_SHARD_SCRATCH_SIZE` 0x3000. The overlay
then ends at 0x8006A800, and `main.ld` checks it stays below FISH (0x80070000). `tools/species.py` fails the build
when a species needs more.

## The heap

Psy-Q's `malloc3` (`InitHeap3`/`malloc3`/`free3`, libapi) is a K&R allocator: a block header `{next, size in 8-byte
units}`, a circular free list sorted by address, a size-0 sentinel at the end, and allocation from the top of the first
block that fits.

What it holds:

- on world screens, **only** the screen's NPCs and wild Digimon: each model's MMD (rounded to sectors) and per placed
  Digimon its `posData` and `momentum` (`bone_count × 0x88` and `× 0x52`, plus 8 bytes each);
- a temporary 0x4800 texture block while a model loads;
- in tournaments the arena model (`STD_ARENA_MODEL`, 26 KB) next to the opponent.

Battle data does not use `malloc3`: a wild battle leaves the heap exactly as the screen had it.

The heap stays **one block**. `unloadModel`/`removeEntity` give everything back and `free3` coalesces; chaining warps
without reloading gives exactly the per-screen free heap. That is what lets each screen be budgeted on its own.

The worst case is a screen with several different large models (the largest original MMDs are about 96 KB:
Etemon, Phoenixmon, MetalEtemon); the original maps are built never to ask for that. A mod that adds big wild Digimon
to a screen has to account for it.

### `MIN_HEAP`

`MIN_HEAP` (0x26800 = 157 696) is the worst MAPHEAD setup path of the original screens, rounded up (`membudget.py worst
--trimmed`): File City (screens 198–203: Betamon, Kunemon, Megadramon), 157 680 bytes with NPC models trimmed on load
and the loading peak of the last one. With whole models the worst would be Ogre Fortress (48), 185 304 bytes. The link
fails below it. It is a floor, not a target: the per-screen check below is the real gate.

## The stack

The original reserves 64 KB, of which it uses under 2 KB (deepest measured 1.6 KB, in battle). GCC frames are larger:
the deepest measured on our builds is 3 960 bytes (a battle against two enemies with their effects); a later
re-measurement over battles at double speed with a finisher, the triangle menu, the evolution chart, map changes, the
trade menu and a save from bed stayed under 4 352 bytes.

- Patch 0060 (from the `memreclaim` work): `STACK_SIZE_KB` 0x40 → 0x14 (20 KB). A 16-byte canary at the stack limit is
  checked once per tick (`MOD_STACK_GUARD_HITS`).
- Patch 0208: 0x14 → 0x10 (16 KB). The link asserts at least 4× `STACK_MEASURED_MAX`.

Not measured: evolution, the ending, fishing, curling. A feature that adds deep recursion or large stack arrays has to
re-measure (fill the stack below its expected floor, run the activity, read back the deepest written word).

## The heap budget rule

1. **Measure before merging.** `nm SLUS_010.32.elf | grep main_BSS_END` before and after the patch (or read `_end`
   from the map). The difference is what every screen loses.
2. **Data that is not needed every frame does not go in the main executable.** Use an overlay (battle, shop, training
   code is loaded when used), a disc file read on demand into the load area or `GENERAL_BUFFER`, or a table rebuilt
   from what the executable already has. A rule beats a table.
3. **The build checks it.** `tools/build-full.sh` runs `tools/heapcheck.py` on the executable's link map after building
   it (step `heap`, output in the build's `heap.txt`). It prints the heap, how much it shrank since the per-screen sweep
   (`docs/data/memory-budget.csv`) and the screens that would keep the least free heap. Projected free heap per screen
   is `heap_free − (heap_total of the sweep − heap now)`. It **stops the build** when a screen would be below 0
   (`HEAP_OK=1` lets it through with a warning) and warns under 8 KB. The link's `MIN_HEAP` assert is the floor under
   that. New screens and models are checked per screen by `tools/membudget.py` and the story compiler (`dws check`).
4. When the margin is used up, take bytes back before adding more ("Reserves not used" below lists what is left).

What the tightest original screens keep with a typical full build: Ogre Fortress (48) and Secret Beach Cave (143) at
noon and Mangrove Region (15) at night, each around 40 KB.

### What things cost

Measured as the change in `main_BSS_END`, i.e. heap lost on every screen.

| What | Cost |
|---|---|
| each new disc file name (`FILE_OFFSET_TABLE` entry and name; patch 0147) | about 20 bytes (24 before patch 0210): 100 new screens cost about 4 KB |
| the two-language build (the copies' file-table entries, `LANG_FILES` rows, strings padded to the longer language) | about 7 KB before patches 0209/0210, less after |
| 15 extra font glyphs (patch 0024's punctuation) | 360 bytes of rodata |
| the original font next to font b (patch 0175) | about 8 KB |
| the name keyboard's extra pages (patch 0195) | 1 496 bytes |
| the evolution chart's criteria card (patch 0176) | 4 916 bytes |
| a larger partner buffer | every byte over 0x18800 |

Code that runs every frame (the status bubbles, the camera) or in menus that run with any overlay loaded has to stay
resident; everything else is a candidate for an overlay.

## How the series reclaims memory

| Patch | Change | Gain |
|---|---|---|
| (GCC build) | GCC `-Os` instead of the original compiler | about 61 KB of text, straight to the heap |
| 0060 | map background streamed; NPC models trimmed; stack 64 → 20 KB | +44 KB of heap from the stack, 15–30 KB per partner species used as an NPC, 334 KB of the load area free in the world |
| 0091 | MAPHEAD buffer 32 KB, paid for by the dead part of the script offset table | 0 (buffer grows by 6 KB, bss does not) |
| 0092, 0093 | save extensions in the world scratch instead of the bss | 7.6 KB |
| 0098 | code that only an overlay calls moves into it; dead library code dropped | 46.6 KB |
| 0113 | rare partner animations read from the disc | about 15 KB of the partner buffer per imported model |
| 0208 | stack 20 → 16 KB | 4 KB |
| 0209 | `LANG_FILES` rows as a hash and two indices | about 4 KB on a two-language disc |
| 0210 | file names stored in the `FileEntry` | 4 bytes per file-table entry |
| 0211 | title and card menus in an overlay | 33 KB |
| 0216 | the VS mode's selection screens into `VS_REL` | 10.8 KB |

### What the GCC build gains

| Section | Original | GCC `-Os` | Difference |
|---|---|---|---|
| text | 0x83260 (525 KB) | 0x73CC0 (463 KB) | −61.4 KB |
| rodata | 0x1F94 | 0x4840 | +10.0 KB |
| data | 0x1E138 | 0x1BB54 | −9.3 KB |
| sdata | 0x1120 | 0x102C | −0.2 KB |
| sbss + bss | 0x7AC + 0x8A76C | 0x7E0 + 0x8A76C | +0.05 KB |
| `_end` | 0x801BFB64 | 0x801B07CC | −61 KB |

All of it shows up in the heap without further work (193 → 254 KB before any mod). New code in the executable is paid
from there.

### The streamed map background (patch 0060, `src/main/tfs_stream.c`)

Only the 4×3 tiles of the VRAM background window are ever visible, and VRAM already holds them; RAM only needs the
tiles about to enter the window.

- **Resident**: the TFS header (palettes) at `TFS_HEADER_ADDR` (2 sectors), then a ring of 8 slots of 9 sectors
  (0x80011000–0x80035000). A tile is 0x4004 bytes in the file and never sector-aligned, so a slot is 0x4800 and the
  pixels start at `slot + offset % 2048`. A small map never gets more slots than its whole TFS would have taken, so
  whatever the game writes just above a small TFS stays safe.
- **The window logic is the original's**: `handleTileUpdate`, `updateTileColumn/Row` and `uploadMapTileImages` are
  unchanged; only the `LoadImage` source changes (`tfsLoadTile`). Whole-window uploads (map load, curling, fishing) read
  each window row, contiguous in the file, in one `CdRead` over the ring.
- **Prefetch**: once per tick, while the game's read queue is empty, the tile the window may need soonest is read
  asynchronously, one tile per `CdRead`. "Soonest" is the camera's distance to `handleTileUpdate`'s thresholds (right at
  `cameraX ≥ 128·(wx+1)+10`, left below `128·wx+1`, down at `cameraY ≥ 128·(wy+1)`, up below `128·wy+1`), plus 96 px
  for a side the camera has not moved toward in the last 40 ticks. A ring tile is only given up for one at least 32 px
  nearer. A read only starts once the drive has finished its last command (`CD_sync`) and 3 vsyncs after the previous
  read ended; starting right after a read can stall the tick for two refreshes waiting for the drive.
- **Hysteresis**: the original's is 1 px vertically and 9 px horizontally, so walking back right after a shift needs
  the strip that just left. That strip is copied from VRAM back into the ring as it leaves (`StoreImage` before the
  replacing `LoadImage`) and never waits for the CD. Tiles already in VRAM are evicted first.
- **CD arbitration**: the read queue does not start a request while a tile read is in flight; `readFile`,
  `readFileSectors` and `readFileSection` wait for it first. A miss (a tile not in the ring when needed) is read
  synchronously and counted. Since patch 0206 every synchronous reader and every enqueue also waits for the queue's
  read in flight (`tfsStreamCheckTarget`): a second `CdRead` aborts the first, which would end with only its first
  sectors.
- **Invalidation**: a load whose target overlaps 0x80010000–0x80035000, and every battle, empty the ring. The game's
  own `readMapTFS` calls (map load, battle won, evolution, death, jukebox, script op 0x24, Toy Town's background swap)
  now only reread the header and reopen the ring.
- **Reopening is world-only** (patches 0160, 0206): `ringMayReopen` lets `tfsLoadTile`, `tfsTilePixels` and
  `tfsStageRow` reopen an invalid ring only while `GAME_STATE` is 0 and the read queue holds no request. In a battle the
  load area belongs to the EFE engine (its slot table sits at `GENERAL_BUFFER`); a reopen there wrote the TFS header over
  that table and crashed the fight's next render. A refused reopen keeps what VRAM holds, the next `readMapTFS` restores
  it, and `MOD_TFS_STATS.refused` counts it. The battle camera (`modCamBattleStep`) is clamped to the 4×3 window VRAM
  holds (`MAP_TILE_X/Y`) and asks for no tile.
- **Palettes are copied out** (patch 0159): the time of day reloads the map palettes whenever the hour changes, possibly
  long after something was staged over the header (a sound bank, a music font change). Each header read
  (`tfsStreamOpen`) now copies the first three palettes to `MOD_TFS_CLUTS` and `setupMap` points `MAP_CLUTS` there.
- **Counters**: `MOD_TFS_STATS` (opens, prefetches, hits, waits, misses, vsyncs, longest read, invalidations, reopens,
  refusals, row reads, captures).

Results: the resident TFS goes from up to 482 KB to 148 KB, warps are faster (the header is 2 sectors and the window
rows about 100 sectors instead of the whole file; leaving a battle rereads 2 sectors instead of 482 KB), and the
per-tick cost while walking across tile boundaries is unchanged. A longest tile read takes 24–30 vsyncs, a window row
16–18, and a walk across every window boundary of File City with reversals has no misses. The streaming code costs
about 5.6 KB of heap. The scripts in `tools/dev/memory/` check the ring and the window against the file.

**Rule for the load area in the world**: nothing that has to last longer than the load that brought it may be read
from the load area later. Copy it out when it arrives.

**libcd gotcha**: `CdReadSync` treats "no progress for 60 vsyncs" as a stalled read and restarts the **last** read into
its buffer, even if that read finished long ago. Polling `CdReadSync(1)` to ask whether the drive is idle therefore
rereads stale data over reused buffers. Poll it only for a read in flight; idleness comes from the queue
(`isFileReadQueueIdle`).

### World scratch

The freed part of the load area is not heap: the heap must hold the screen's NPC models through every mode they
survive, and some mode overwrites every byte of the load area while they are alive (battle, tournament, fishing, DOO2,
MURD, DOOA, DGET, TRN, `TEXTURE_BUFFER`). It is scratch instead (`WORLD_SCRATCH_START/END`):

- 0x80035000–0x80053800 (122 KB) is free on every world screen;
- up to 0x80088800 (334 KB) except on curling (KAR at 0x80053800), fishing (FISH at 0x80070000) and while a menu
  overlay is loaded.

Anything stored there is lost on every battle, menu, evolution, death and map change and must be reloadable, at the
point where `tfsStreamOpen` runs.

### NPC models without unused animations (patch 0060, `src/main/npc_anim_trim.c`)

An NPC model (`loadMMD` class 0) is read whole into the heap, but NPCs never play the partner's care animations. After
the read, `trimNpcModel` keeps the slots listed in the generated `npc_anim_keep.c` (`tools/npcanims.py gen`), packs them,
moves the model to the top of its block and frees the bottom, which joins the free block below.

Kept for every type: 0–4 (idle, alternative idle, walk, run), 0x13, 0x1C–0x20 (curling opponent, training partner,
scripted gestures) and 0x21 on (every battle animation and technique: any NPC can be fought). Per type, additionally,
every slot a script plays on an actor that resolves to that type (`PLAY_ANIMATION`, `ENTITY_WALK_TO*`, resolved through
the screens that load the script, their `.MAP` entries and `SET_DIGIMON` overrides). Script lines whose actor cannot be
resolved keep their slot for every type. Type 0 (the tamer) and types ≥ 180 (imported species) are not trimmed.

- A dropped slot points to a one-frame stub (the idle's first pose), not 0: `startAnimation` ignores a 0 slot and the
  previous animation would go on, hanging a script that waits for it to end. No original animation is one frame long,
  so stub plays are counted (`MOD_NPC_STUB_HITS`, `MOD_NPC_STUB_LAST` = type << 8 | slot).
- Effect: about 14% of all MMD bytes. Enemy models (`E*.MMD`) have no care animations (0–6 KB to drop); partner species
  used as NPCs lose 15–30 KB each.
- Loading still needs the whole file for a moment: the budget tools count the last model's full size as the peak.
- Scripts that make an NPC play a new animation need `npcanims.py gen` rerun with their `DG.SCN`/`MAPHEAD.SCN`
  (`--dg`, `--maphead`), or the NPC plays the stub. `npcanims.py report` lists every model.

### Save extensions (patches 0092, 0093, 0096)

The extensions of a save file (file offsets from 0x2000; [save-format.md](save-format.md)) used to be part of the
static `SAVE_FILE`. They are only used for the moment of a card operation: a read is followed in the same tick by the
copy into the game state, and a write is prepared from RAM in the tick that writes it. They now live at
**`SAVE_EXT_ADDR` 0x8004E000–0x80052000**, in the world scratch:

- in the world (the save machine, the sleep save) only the TFS ring sits below `WORLD_SCRATCH_START`;
- at the title (continue, new game's file, the VS mode's card read) the title's TIMs end at 0x8002F000 and the movie
  overlay is dead once `playMovie` returns;
- it is above every sound bank staged at `GENERAL_BUFFER` (the largest, an ESALL chunk of 124 sectors, ends exactly at
  0x8004E000; `SB.VHB` at 0x8004D000), the evolution model area and `DOOA_SHARD` (to 0x8004A5C0), and below the battle
  prefix (0x80052AE0). A battle's EFE heap covers it, but no card operation runs in a battle.

Link asserts: `GENERAL_BUFFER_ADDR + SOUND_STAGING_MAX ≤ SAVE_EXT_ADDR` and `EVO_MMD_ADDR + 0x4800 + PARTNER_MMD_MAX ≤
SAVE_EXT_ADDR`, and the area stays in the world scratch below the battle prefix. `tools/sound.py` refuses a bank chunk
whose staged size passes `SOUND_STAGING_MAX`, and `tools/build-full.sh` checks the disc's banks against the executable's
value ([../mods/sound.md](../mods/sound.md), "Limits"). The game-clear save, which runs while the ending's sound bank
may be loading, waits for it first.

`SAVE_FILE` keeps the v1 file (0x2000), as in the original, because its battle registrations are game state between
card operations. A multi-part file is read and written part by part in copy order, each part waited for, so a write
that stops anywhere leaves one whole copy (patch 0096).

### Code out of the executable (patch 0098)

| What | Moved to | Bytes |
|---|---|---|
| `src/vs/vs_combat.c`, `vs_intro.c` (the VS mode's battle AI, setup, results, intro) | `VS_REL` | 21 196 |
| `src/main/battle_ui.c` (end-of-battle box, bits box, move learning) | `BTL_REL` | 5 732 |
| libpress (MDEC decoder and its VLC tables), libcd streaming (`St*`, `CdRead2`, the ring callbacks), `SetDefDispEnv` | `MOV_REL` | 10 728 |
| Psy-Q functions nothing calls (mostly libgpu) | dropped by `--gc-sections` | about 9 000 |

No C file changes: the linker scripts (`config/us/overlay.ld`, `main.ld`) and the build. Each overlay keeps its
addresses; the moved code is appended after its bss. The Psy-Q libraries are assembled one section per function so
`--gc-sections` can drop dead ones and a linker script can place a function by name; libapi, libmcrd and libgte stay
one section each (code copied by address range, functions that fall through into the next).

Bigger overlays still fit: BTL and VS stay at or below STD's end (STD runs the same battle engine, so nothing in a
battle writes between their old ends and STD's), and MOV stays below `OVL_TRN_BASE` (a movie owns the whole load area);
link asserts keep both. `build-disc.py --relayout` moves the files that follow a grown overlay on the disc.

The movie's CD and MDEC callbacks are the only moved functions ever stored as callbacks; `MOV_playMovie` unhooks them
before it returns, so nothing points into MOV after a movie.

**Proving a move safe: `tools/xref.py`.** The link keeps its relocations in the ELF (`--emit-relocs`; the output bytes
are unchanged), so every reference is known: `jal`, `lui`/`addiu` pairs, `.word` entries, gp-relative accesses.
`xref.py classes ELF` walks from `__start` through the executable's own code and data and groups what it does not
reach by the overlay that reaches it, or as dead. `xref.py refs ELF NAME` lists who references a symbol. `xref.py check
ELF` lists every reference from the executable into an overlay (valid only while it is loaded) and between overlays. A
move is safe when `check` gives the same executable-to-overlay references as before (minus the moved sites) and none
between overlays.

### The menu overlay (patches 0211, 0216)

`main_menu.c` (the title's menus, new game and continue, the card screens, VS registration, the save machine, the
sleep save and the game-clear save) was 35 KB of code resident through the whole game. Patch 0211 links most of it into
`MENU_REL.BIN` (overlay id 17, a new file-table name; on the disc in `SCN/`, because the root directory's first sector
must keep `SYSTEM.CNF`), read at `OVL_BTL_BASE` by `loadMenuOverlay` where a menu opens:

| Where | Why the slot is free |
|---|---|
| `runMainMenu` (title) | nothing of the world is loaded; the title's TIMs end at 0x8002F000 |
| the sleep save | the world keeps only the TFS ring and `SAVE_EXT` below it; on the curling screen KAR shares the slot and `closeMenuOverlay` reads it again |
| `openSaveMachine` (script routine 0x30) | the same |
| `gameClearSave` (routine 0x36) | the same, after waiting for the ending's sound bank; ENDI loads at `OVL_EVL_BASE`, above the overlay's end (link assert) |

What stays resident: the entry points, the boot options (they run before any menu), `modNewGame` (evolution and
rebirth call it), the lab's helpers, `modReplayMainMenu` (the extra frame passes) and the file's data, rodata and bss,
except the moved functions' switch tables and, since patch 0283, the read-only data only the overlay reaches (2.4 KB:
card messages, labels, the save icon; found with `xref.py classes`). Data that is ever written, or that the balance
tables encode (`MOD_VS_UNLOCK`), stays resident: a reload of the overlay would undo a write. `SLOT_ACTION_TITLES` and
`SLOT_ACTION_QUESTIONS` stay resident and point into the overlay; only the overlay reads them. `config/us/overlay.ld` names the moved functions one by one, so a new
function in `main_menu.c` stays resident unless it is added there, which is always safe.

A VS battle started from the title's registration screens needs `VS_REL` in the same slot: `modMenuVsBattle`
(resident) removes the menu objects, reads VS, runs the battle, reads the menu overlay again and adds the objects back,
returning into the same `tickMainMenu` code. The overlay's strings are per-language like the executable's, with its own
Spanish copy and `LANG_FILES` row. Patch 0216 then links `vs_select.c` (battle mode, stage and fighter selection) into
`VS_REL` too: `modMenuVsBattle` reads VS before calling `VS__initialize`.

### File table entries (patches 0147, 0209, 0210)

Every disc file with a name the original never had (a new screen's `.MAP` and `.TFS`, a language copy, a new overlay)
is one more `FILE_OFFSET_TABLE` entry in the executable's data. Patch 0147 generates them from the content at build time
(`NEW_FILES`, [ids.md](ids.md)), so the link's `MIN_HEAP` assert sees them, and a build without new names costs nothing.

- Patch 0209: a `LANG_FILES` row is the name's FNV-1a hash plus the two copies' places among the new files
  (`FILE_TABLE_NEW_FIRST`, `NUM_NEW_FILES`), 8 bytes, instead of three name pointers and their strings. The generator
  stops the build when two names on the disc share a hash.
- Patch 0210: `FileEntry` is `{i32 sector, i32 size, char filename[12]}` (no NUL at 12 letters; `fileEntryIs`
  compares) instead of a pointer to an aligned string: 20 bytes an entry instead of 24. The tools that read the table
  out of an executable accept both layouts.
- Patch 0198: an overlay loaded asynchronously (`loadDynamicLibrary`) is found through `FILE_OFFSET_TABLE` like
  `readFile`, not `CdSearchFile`, which only sees the first sector of the root directory (a disc with many files
  outgrows it) and would read an overlay's English copy.

## Adding new code or data without RAM

- **A new overlay.** `loadDynamicLibrary(id, …)` reads `REL_BIN_FILES[id−1]` to the fixed address `REL_BIN_OFFSETS[id−1]`
  (enum `Overlay` in `include/dw/utils.h`; the series extends it, e.g. `MENU_REL = 17`); the file is looked up by name
  in `FILE_OFFSET_TABLE`. In the GCC build each overlay is an `OVERLAY` section in `config/us/overlay.ld`, linked
  against the executable's symbols and extracted with `objcopy`. A new mode (menu, minigame, special battle) can use the
  whole load area as BTL, DOO2 and FISH do, as long as the map is reread on exit; code that has to coexist with the
  world only has the world scratch, and only between mode changes. Every executable reference into it must be checked
  with `xref.py check`.
- **The unused shop slot.** `SHOP_REL.BIN` is still read (to 0x80080800 on shop screens and by script opcode 0x23) but
  its bytes are never used: the shop code is linked into the executable. The build writes zeros of the same size there.
- **Data on demand.** As the game does with `DG.SCN`, the sound banks and the models: a table in a disc file read into
  the heap (`malloc3` + `readFile`) or into `GENERAL_BUFFER` when needed. There is plenty of disc space (`MMM.DAT` is
  27 MB of zeros that are never read).
- **Compression** saves CD time, not resident RAM, unless the data is decompressed in chunks.

## Per-screen budget: `tools/membudget.py`

```bash
tools/membudget.py live [--vram]        # this screen in a running emulator: heap blocks by holder, buffers, VRAM, SPU
tools/membudget.py sweep                # every screen -> docs/data/memory-budget.csv (resumable)
tools/membudget.py sweep --chain --screens 0,3,143   # no state reload between warps
tools/membudget.py estimate 0 --hour 12 # static, no emulator (--trimmed: NPC models trimmed on load)
tools/membudget.py worst [--trimmed]    # static: the screen setups that need the most heap
tools/membudget.py vram-map 0           # static VRAM occupancy of a screen
```

How the live numbers are obtained (on any build; symbols through `dwsyms`, `_end`/`_stack_addr` from the map):

- **Heap**: walks every `malloc3` block from `(_end & ~15) + 16` and names it from `NPC_MODELS[].mmdPtr`,
  `ENTITY_TABLE[2..9]->posData/momentum`, `UNKNOWN_MODEL[]` and `STD_ARENA_MODEL`.
- **Fixed buffers**: what each one holds now (partner MMD, `BOYS.MMD`, `MAPHEAD.SCN`, the current `DG.SCN` entry, the SEQ
  of the current music font, the TFS, the battle EFE heap).
- **VRAM**: by what claims each area, not by reading pixels (states keep stale data): the fixed layout, the TIM headers of the screen's
  `.MAP`, `NPC_MODEL_TAKEN` and `UNKNOWN_MODEL_TAKEN`; free space as the largest free rectangles of 16×16 cells.
- **SPU**: each bank's VAB header in RAM, body (sum of VAG sizes) against the slot between `VHB_SOUNDBUFFER_START`
  entries.
- **Stack**: deepest non-zero word since boot. Note that a zero inside the bss is not free memory; truly free is only
  the heap's slack, the stack's and the tail of the load area.

**Static estimate.** `membudget.screen_budget(screen, hour=None, maphead_text=None)` (importable; `estimate` on the
command line) walks every path of the screen's MAPHEAD section (hour conditions evaluated when `hour` is given; triggers
taken both ways but kept consistent along a path; counters such as File City's recruit limit followed) and adds up,
per path, each model and each placed Digimon's `posData`/`momentum`. It returns `need`, `peak` (the 0x4800 temporary
texture counts only before the last load), `available` and `margin`. It equals the measured bytes on most screens and
is never below them. The story compiler's `check_model_heap` (`tools/dws/backend.py`) uses a fixed 170 KB for models
alone; `screen_budget` is the precise figure.

**The sweep** (`docs/data/memory-budget.csv`): one row per screen at 12:00, plus 20:00 for the screens whose setup
changes with the hour, measured on the original executable from an early-game save (the save's triggers decide which
NPCs appear). Free heap was 40.2 KB minimum, 138 KB median, 192.9 KB maximum (screens with no NPCs); NPC models 0–140 KB
(median 48); `posData` + `momentum` up to 27.8 KB (Mt. Infinity). `heapcheck.py` projects every row onto the current
executable's heap.

Tightest original screens (free heap on the original executable):

| Screen | Hour | Models | Free heap |
|---|---|---|---|
| 48 Ogre Fortress | day | Ogremon, Agumon (+ placed) | 40.2 KB |
| 143 Secret Beach Cave | day | WaruSeadramon, Gabumon, Ogremon | 41.6 KB |
| 15 Mangrove Region | night | J-Mojyamon, Tsukaimon, Betamon | 43.9 KB |
| 236/237 File City | day | Airdramon, Greymon, Jijimon | 51.4 KB |
| 167 Mt. Infinity | day | Gururumon, Piddomon | 53.1 KB |
| 80 Ancient Glacial Region | both | Yanmamon, Vermilimon | 56.2 KB |

Model trimming widens these (Ogre Fortress gains most, through its Agumon), and each heap gain in the series adds to
every row.

**Battles.** A wild battle leaves the heap untouched. `BTL_REL` (141 KB) sits at 0x80052AE0 and the EFE effects heap
starts just above 0x80012000 (a typical wild battle's techniques use about 35 KB of its 0x41000). In a cup battle the
arena model (26 KB) sits in the heap next to the opponent, and `STD_REL` is 181 KB of the load area.

## VRAM (1 MB, 1024×512 at 16 bits)

| x | y | Use |
|---|---|---|
| 0–319 | 0–479 | two 320×240 frame buffers |
| 0–319 | 480–511 | CLUTs (map, items, models, font, effects) |
| 320–383 | 0–511 | item icons, `SYSTEM_W`, tamer and partner textures |
| 384–767 | 0–255 | map sprites and objects (TIMs inside the `.MAP`; 64 to 384 wide depending on the map) |
| 384–575 | 256–511 | 5 NPC/wild Digimon texture slots (64×128 each), `SBOY.TIM` at 512 |
| 576–703 | 256–511 | 16 battle effect (EFE) texture slots |
| 704–767 | 256–511 | rendered text |
| 768–1023 | 0–383 | the 4×3 window of map background tiles (and the title) |
| 768–1023 | 384–511 | `DEFEFF`, `EX`, `SPOT256`, `BI_IN`, `FI_INFO`, `FEEL_EF`, `BTLCOMND` |

Unowned VRAM per screen is 103–343 KB (median 135 KB), almost all of it the EFE slots, which battles take, and unused
NPC slots; none of it is guaranteed free. The truly unowned space is part of the CLUT strip and, per map, whatever its
`.MAP` leaves of 384–767 × 0–255. Outside battle the EFE slots are only used briefly (the card viewer, `LIFE.TIM`,
`SLOT.TIM`, `OP.TIM`); using them for more NPC texture slots would require rereading those NPCs' textures after every
battle and every one of those viewers, since NPC textures are not kept in RAM.

## SPU RAM (512 KB)

Fixed bank addresses (`VHB_SOUNDBUFFER_START`, `sound.c`); details in [../mods/sound.md](../mods/sound.md).

| Bank | SPU range | Slot | Largest original body | Worst-case margin |
|---|---|---|---|---|
| — | `0x00000–0x0100F` | 4 KB | libspu buffers and silence block | — |
| 0 `SS` | `0x01010–0x0E7FF` | 54 KB | 0xD130 | 1.7 KB |
| 1 `SL` | `0x0E800–0x1B7FF` | 52 KB | 0xCAE0 | 1.3 KB |
| 2 `FAALL` (music) | `0x1B800–0x29FFF` | 58 KB | 0xC850 | 7.9 KB |
| 3 `VLALL` (long voice) | `0x2A000–0x317FF` | 30 KB | 0x6850 | 3.9 KB |
| 4–7 `VBALL` (voices) | `0x31800–0x3B7FF` | 4 × 10 KB | 0x2700 | 0.25 KB |
| 8 `ESALL`/`SB` (map effects) | `0x3B800–0x7B7BF` | 256 KB | 0x3CE20 | 12.5 KB |
| reverb `STUDIO_B` | `0x7B7C0–0x7FFFF` | 18 KB | work area (0x4840) | — |

The SPU is full by design: about 27 KB of slack in the worst case, spread in pieces. New sounds replace samples within
their slot, lower existing sample rates, or remove the reverb (+18 KB, changes the sound).

## Reserves not used

| Reserve | Size | Why it stays |
|---|---|---|
| `GS_WORK_BASES` (2 × 0x14000 GPU packet buffers) | up to tens of KB | peak use per frame measured 26–49 KB of 80 KB on ordinary screens and battles; a crowded screen, a big finisher or a text-heavy menu goes higher, and an overflow corrupts memory silently |
| code BTL, STD and VS all call (`efe.c`, `vecmath.c`, `aabb.c`, part of `map.c` and libgte) | about 9 KB | the same input section cannot be linked into three overlays; it would need three compilations with renamed symbols |
| dead functions in libapi and libmcrd | 2.3 KB | those files must stay whole (code copied by address range) |
| our own resident features (lab menu, portraits, condensed names) | under 10 KB | each needs a lifetime proof across world, menus and evolution, and the bubbles and camera run every frame |
| `FIT_STRIP` (long-name composition strip) | under 1 KB | used in menus, the world and battle; no load-area bytes are free in all three without auditing `TEXTURE_BUFFER`'s users |

## See also

- [ram-map.md](ram-map.md): addresses of game-state variables.
- [executable.md](executable.md): the executable and overlay files.
- [engine-patches.md](engine-patches.md): the series' engine patches by feature.
- [compiler.md](compiler.md): the GCC build.
- [save-format.md](save-format.md): the save file and its extensions.
- [../building.md](../building.md): `tools/build-full.sh` and its steps.

## Compact routes and staged models

Patches 0258–0262 keep only active-language routes resident, pack sector/size
records losslessly into eight bytes, move laboratory helpers into overlays and
stage NPC models before their final allocation. Heap acceptance uses the final
executable and DIGI.DAT, including transient loading peaks. New content must pass
all story setups within the original PlayStation's 2 MB RAM.

## City page budget

With all eight padded language banks, patch 0277 moves `main_BSS_END` from
`0x801ce958` to `0x801cf0bc`: 1,892 bytes, including 1,824 bytes of code. Heap
alignment makes the available heap fall by 1,888 bytes to 183,872 bytes.
The roster and icons live in DIGI.DAT and the chart's existing buffers and VRAM
are reused. The actual-archive story check covers 320 setups; screen 361 is
smallest at 1,840 bytes free. The general heap sweep also passes. Recheck these
figures whenever the patch series, language padding, models or story changes.

Through patch 0283 the series ends at `0x801cf040` and screen 361 keeps 1,952 bytes. A new resident patch
must fit those bytes or free its own first: `xref.py classes` lists what is left to move.

## Timed field-battle teardown

Patch 0285 adds 120 bytes to `BTL_REL.BIN` and no resident growth. Controlled English-only builds with the same
`MOD_VERSION=airdramon-test` keep `main_BSS_END` at `0x801cb9fc` before and after the change, with 197,888 bytes of
heap. The general heap projection passes, and all 320 actual-archive story setups fit; screen 361 has the smallest
margin at 15,488 bytes. These English test-bank figures are not an eight-language release measurement. The guard
uses only battle-stack locals and the existing combat state; it adds no allocation, model or effects buffer.
