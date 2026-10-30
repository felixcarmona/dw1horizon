# Compiler: the GCC build of the decompilation

The mod's executable is the decompilation compiled with GCC (a non-matching build), not with MWCC, the original compiler.
C that only worked because of MWCC's data layout or code generation behaves differently under GCC; this page lists each
divergence found, its root cause and the patch that handles it, then the original game's own bugs found the same way,
and the classes of bug to watch for when changing code.

## The toolchain

The decompilation (`decomp/`, see [../building.md](../building.md)) builds with `TOOLCHAIN=mwcc` (the matching build) or
`TOOLCHAIN=gcc`. The mod uses GCC, `mipsel-linux-gnu-gcc`, with the flags of `decomp/mk/toolchain/gcc.mk` and
`decomp/mk/platform/psx.mk`: `-Os -G8 -march=r3000 -msoft-float -fno-pic -mno-abicalls`, `-ffunction-sections
-fdata-sections -fno-common`, `-fno-zero-initialized-in-bss -fno-builtin -fno-strict-aliasing -fwrapv
-fno-tree-switch-conversion`, Shift-JIS (`CP932`) as execution charset, and `--gc-sections` at the link. Our series adds:

| Flag | Patch | Why |
|---|---|---|
| `-fno-delete-null-pointer-checks` | 0001 | `clearMapDigimon` writes through a null `Entity *` (`->isOnMap`). GCC treats that as undefined and emits a trap; MWCC emits the store, and the original runs on |
| `-mno-check-zero-division` | 0022 | GCC guards every `div` with `break 7`; MWCC emits no guard, so a division by zero in the original just gives an undefined quotient. The `break 7`s that remain are the Psy-Q library's, as in the original |

MWCC keeps the declaration order of a file's globals as the `*_bss_order`, `*_sbss_order` and `*_functions` anchor arrays
force. GCC with `-fdata-sections` places each variable in its own section and the linker orders them differently.
`-fno-toplevel-reorder` would keep declaration order, but it changes the layout of the whole executable and keeps every
unused anchor array, so each overrun is fixed where it is instead. Each fix keeps the original declaration under
`#ifdef __MWERKS__`, so the matching build is unchanged.

## Divergences

| # | Symptom under GCC | Cause | Fix |
|---|---|---|---|
| 1 | trap in `clearMapDigimon` | null pointer write, see above | 0001 |
| 2 | new game: the tamer is missing in the File City intro (screen 238) and the scene never ends | `TAMER_MODEL_BUFFER` overflow | 0002 |
| 3 | the first battle hangs: no banner or HUD, the CPU spins in `CdControl` | unterminated `EFEDAT.EFE` path | 0003 |
| 4 | none visible (latent) | `MAPHEAD.SCN` read as whole sectors into a smaller buffer | 0004 |
| 5 | winning an arena or VS match hangs or traps during the win camera | spline tables overrun | 0021 |
| 6 | a division by zero stops the console | GCC's divide guard, see above | 0022 |
| 7 | the Tech tab's help (square button in the technique grid) shows an empty screen and the menu stops answering | `STATUS_VIEW_LABELS` read past its end | 0094 |
| 8 | latent: 15 stores past the end of `EAB_REL` | `EAB_initializeRings` overrun | 0094 |

### 2. Tamer model buffer

The tamer model `CHDAT/MMD0/BOYS.MMD` is 57 036 bytes (0xDECC) but `main.c` declares `TAMER_MODEL_BUFFER[0x7800]`. In the
original layout `MAIN_D_801A8B98[0x6800]` follows it (0x801A1398 + 0x7800), giving 0xE000 bytes in all, and the game
relies on the model spilling into it. Under GCC, `TAMER_POSITION_DATA`, `TAMER_MOMENTUM_DATA` and `PARTNER_MODEL_BUFFER`
follow instead: loading BOYS.MMD overwrites the tamer's own position data (so it is not drawn), and loading the partner
model overwrites the tail of the tamer model where its later animations are. Animation 18, played by the intro, then
reads an instruction word no case of `tickAnimation` handles and the loop never advances.

Fix: `TAMER_MODEL_BUFFER` is 0xE000 bytes and `MAIN_D_801A8B98` is an assembler alias of its second half. The symbol is
kept because VS mode uses it on its own (`vs_hud.c`), and VS also loads its stage model into `TAMER_MODEL_BUFFER`.

### 3. The EFEDAT.EFE path

`findEFEDATFile` builds the CD path with `strcpy` from `MAIN_D_8012342C`, declared `char[16]` and initialised with a
16-character path: no terminator. In the original, `EFEDAT_CD_LOCATION` (still 0 at that point) follows and terminates
it. Under GCC, `CLOUD_FX_COLOR` follows, the name gets garbage appended, `CdSearchFile` fails (it returns 0; the caller
only retries on -1), `EFEDAT_CD_LOCATION` is filled from uninitialised stack, and the file queue retries a `CdlSetloc`
with a non-BCD minute forever while `LOAD_EFE_STATE` stays 1.

Fix: an unsized, terminated string. It is the only `char` array in `decomp/src/` initialised with a string as long as
the array and used as a string. The same patch hardens two latent bugs on that path:

- `getEFEDATEntry` is defined `void`, but the `*_loadNextEFEFile` functions of BTL, STD and VS declare it as returning
  `CdlLOC *` and copy through the result (in the original, a pointer to a dead stack local left in `v0`). It now
  returns static storage.
- Those three functions pass a never-written `path[32]` to `addFileReadRequest`, which rejects a request with no NUL in
  its first 29 bytes. It is now set to an empty string.

### 4. MAPHEAD buffer

`initializeScripts` calls `readFile("MAPHEAD.SCN", MAPHEAD_SCRIPT_BUFFER)`. `readFile` reads `(size + 0x7FF) & ~0x7FF`
bytes: 0x606E rounds to 0x6800, into a 0x61A8 buffer. In the original the spill lands in `SCRIPT_OFFSET_TABLE`, which is
read from `DG.SCN` right after; under GCC it lands in `GLYPH_DRAWING_AREAS` (`font.c`), glyph scratch rewritten before
use. Patch 0004 makes the buffer 0x6800; patch 0091 later makes it 0x8000 ([memory.md](memory.md)).

### 5. Arena and VS win camera

`STD_startCameraIntro` fills 22 entries of `STD_D_8007B9EC` and `STD_D_8007BA9C`, which are declared with 4, relying on
`STD_D_8007B9FC` and `STD_D_8007BAAC` following them. GCC orders the pairs the other way, so the writes corrupt the camera
target pointer (`STD_D_8007B9D0`) and the win camera hangs on a garbage pointer in `calculateBoneMatrix` or divides by
zero. The tick also reads one word past `STD_D_8007B9BC`, which in the original layout is `STD_D_8007B9D0.target`.
`VS_tickCameraIntro` has the same code. Fix: each pair is one 22-entry array with the tail aliased, and the target is read
as the field it is (`VS_D_80071A18[0]` in VS).

### 7. Tech help labels

`drawMoveViewHelpStrings` (`game_menu.c`) draws one help line per frame as `STATUS_VIEW_LABELS[MENU_SUB_STATE + 9]` of an
8-entry array. In every release `TECH_VIEW_LABELS` sits at `STATUS_VIEW_LABELS + 0x20`, so indexes 9..16 are
`TECH_VIEW_LABELS[1..8]`; GCC places `TECH_VIEW_LABELS` before it and the help passed arbitrary words to `drawString` as
string pointers. Fix: `TECH_VIEW_LABELS[MENU_SUB_STATE + 1]`, the same address in the original's layout.

### 8. EAB rings

`EAB_initializeRings` (the final boss's appearance, script opcode 0x28) clears the `timer` of 18 rings of the 3-entry
`EAB_D_800617D0` (8-byte stride). The original writes -1 over the variables that follow (appearance state, flash buffer);
under GCC the array is the last data of `EAB_REL` and 15 stores went past the overlay's end. The loop now stops at 3.

## Audits

### Fixed buffers against the files they receive

Files are read in whole 0x800-byte sectors (`readFile`, `CdRead`), so a buffer must hold the file size rounded up.

| Buffer | Size | Largest file, rounded | Result |
|---|---|---|---|
| `MAPHEAD_SCRIPT_BUFFER` | 0x61A8 | MAPHEAD.SCN, 0x6800 | overflow, case 4 |
| `MAP_SCRIPT_BUFFER` | 0x4000 | DG.SCN entries 200-202 and 214, 0x3800 (entry 0 is never loaded) | fits |
| `GENERAL_MESH_BUFFER[4][0x800]` | 0x2000 | GAND.TMD 0x1800 into `[0]` | spills into `[1]`/`[2]` of the same array in both builds: fine |
| `CHEST_MESH_BUFFER`, `MEDAL_MESH`, `POOP_MODEL_BUFFER` | 0x800 each | TAKA.TMD, MEDAL.TMD, UNTI.TMD, 0x800 | fits |
| `DOO2_D_80071EE4` | 0x9808 | TAMA.TMD 0x9800 | fits |
| `KAR_D_8005BFCC` | 0x7800 | KARRING.TMD 0x7000 | fits |
| `MAP_COLLISION_DATA` | 0x2800 | B_/E_TOGI.ATR 0x2800 | fits |
| `STD_RESULT_TMD_BUFFER` | 0x2800 | CHAMP.TMD 0x2800 | fits |
| `MAIN_D_801A8B98` (VS 1P2PWIN.TMD) | 0x6800 | 0x2000 | fits |
| `TAMER_MODEL_BUFFER` (VS stage) | 0xE000 | B_TOGI.TMD 0x6800 | fits |
| `PARTNER_MODEL_BUFFER` | 0x18800 (original) | ETEM.MMD, 97 812 bytes | fits; sized by the build since patch 0064 ([memory.md](memory.md)) |

`GENERAL_BUFFER`, `STD_TMD_BUFFER`/`VS_TMD_BUFFER` (0x80038000), `TEXTURE_BUFFER` and `BOSS_EFE_TMD_BUFFER` are fixed
addresses, not variables, so GCC's ordering does not move them; every GCC overlay is smaller than the original at the
same load address. `STD_ARENA_MODEL` is allocated with the rounded file size.

### Indexes past a declared size

Every global array was scanned for constant indexes past its size, `NAME[expr + K]` against the range of `expr`, loops with
a literal bound over a smaller array, and `memcpy`/`memset`/`strcpy` lengths. Besides cases 5, 7 and 8:

| Where | What | Result |
|---|---|---|
| `battle_effect.c`, `BTL_BUFF_TRAILS[1]` written for `i < 8` | marked as a bug in the source; the extra writes hit nothing used | left |
| `model.c`, `NPC_MODEL_TAKEN[k] != 0 && k < 5` (two places) | reads `[5]` before testing the bound; the value is unused | benign |
| `item.c`, `EVOLUTION_ITEM_TARGET[item - 0x47]` (44 entries) | only items 0x47..0x72 reach `handleEvoItems` | in range |

Checked and in range: `PLAYER_VIEW_LABELS[MENU_SUB_STATE + 1]`, `HEALING_VALUES` and `HEAL_EFFECT_VARIANT[idx - 4]`,
`STD_LOSE_TILT`, the STD/VS win and result tables, `STD_CHAMPION_ORBIT_ANGLES[i + 0x28]`, `CAMERA_PRESETS[rand(3) + 6]`,
`BRAIN_TO_COMMAND_MAP[brains / 100]` (guarded below 500), `SIN_LOOKUP_TABLE[256 - x]`,
`STAT_GAIN_ENEMY_FACTORS[ENEMY_COUNT - 1]`. Not covered by the scan: indexes taken from game data, arrays inside structs,
and casts such as `*(T *)&ARRAY[...]`.

### Latent mismatches that work by chance

- `tickCameraMoveTo` (`map.c`) is defined `void`, but `script_interp.c` and `kar.c` declare it `int32_t` and use the
  result. Both compilers end it with a tail jump to `checkCameraMovement`, so `v0` holds that function's result. A
  clean fix returns it explicitly. A cross-file scan found no other such function besides `getEFEDATEntry` (case 3).
- `tickEntityMoveTo` and `tickEntityMoveToAxis` are K&R definitions with `int8_t`/`int16_t` parameters and no
  prototype; GCC converts the promoted `int` in the callee, truncating as the original does.
- `anim.c` passes `*(*instrPtrPtr)++` among `MoveImage`'s arguments (`-Wsequence-point`); the generated code reads the
  right words.
- Functions that fall off the end without a return (`getEntityFromScriptId` when nothing is found, `popScriptStack`...)
  have callers that ignore the result in that case.
- `drawString2` (`script_textbox.c`) never sets the advance before a row's first glyph, and in the original a space
  advances by the previous glyph's width. A row that starts with a space therefore advances by whatever the register
  holds; it is 0 in both builds. Patch 0025 makes a space advance a fixed 8 px, and patch 0108 gives rows cut into
  pieces their own rule, so nothing depends on the uninitialised value ([../mods/font.md](../mods/font.md)).

A play-test comparing the GCC build with the original executable through the same steps from the same card (wild
battle, save and cross-load, evolution, items and shops, map transitions, toilet, day and night, sleep, training) gave
the same RAM and screens apart from timing and random numbers. Testing tools are in [../developing.md](../developing.md).

## Original game bugs found the same way

These happen on the retail disc too; the patches fix them for every build.

| Patch | Bug | Fix |
|---|---|---|
| 0023 | After a cup, `startTournament` (called from `tickScript` inside a `gameLoop` frame) returns with the ordering table the STD overlay already filled and sent. `gameLoop`'s `applyDrawOffset` then adds `DR_OFFSETS[n]` to the slot that already holds it, making a primitive tag that links to itself, and `GsDrawOt` sends an endless list. On a console this should cost a libgpu `DrawSync` timeout (a stall and a lost frame); PCSX-Redux flags a DMA bus error and hangs in `loadMapSounds` | after `thunkReinitializeAfterTournament`, start a fresh frame (active buffer, work base, clear and select its ordering table), as `tamerTickBattle` already does after a battle. No `DrawSync` is needed: STD's last frame already waited for the list of the buffer that becomes active. Other overlays started from a script with their own render loop (`dooa`, `kar`, `evl`) have the same frame shape |
| 0050 | The save title's name fields are filled with `_strncpy`, which stops at the source's NUL and never writes one, so a short name leaves the tail of the previous title (a one-letter tamer name showed the rest of the default name) | clear the two fields (title+0x0E, 14 bytes; title+0x1C, 18 bytes) before copying; `_strncpy` itself is unchanged because the slot label copy relies on it |
| 0094 | A battle that raises Brains to 700, 800, 900 or 999 appends the MP bonus message to the result box and the battle never ends. `BTL_appendMPBonusText` adds 4 to the line count (the rows of the Japanese message) while the US text has one row end; and `BTL_drawBattleEndText` stops at the byte 0x30 (a digit zero never occurs there in the Japanese two-byte text) instead of the terminator | count the rows the appended text really has (`BTL_countEndTextRows`) and stop at the terminator |

More original-game fixes are listed in [engine-patches.md](engine-patches.md).

## What to watch for

- **Adjacent globals.** In any file with an anchor array, GCC orders globals differently from the original. Code that
  writes past the end of a global array (CD reads into fixed buffers, `memset`/`memcpy` across several variables) can
  break. Compare buffers with file sizes rounded up to 0x800.
- **Strings without a terminator.** `char x[N] = "..."` with exactly N characters is legal C and has no NUL.
- **Return types that differ between definition and declaration** across files: the result is whatever is in `v0`.
