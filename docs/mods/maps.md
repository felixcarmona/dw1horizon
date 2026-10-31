# Map formats and low-level inspection

For creating or changing playable screens, follow [new-map authoring](new-maps.md)
and [tools/maps](../../tools/maps/README.md). That workflow covers full-resolution
SAM foreground masks, exact palette packing, collision review, arrival reachability
and original-2-MB acceptance. Use the [story language](story-language.md) for NPCs
and events, and the [derive recipe](../derive.md) to register build outputs.

This page describes the original USA `.MAP` and `.TFS` formats and `tools/dwmap.py`.
Source locations and addresses refer to the unmodified decompilation unless stated.
Generated map JSON, MAP, TFS and TIM exports contain player-disc data and belong
under ignored `build/`, not in published content.

## How a screen is loaded (summary of the chain)

1. `changeMap(id, exit)` (`map.c:5458`) → `runMapHeadScript(id)`: runs section
   `id` of `MAPHEAD.SCN` (loaded whole at boot into `MAPHEAD_SCRIPT_BUFFER`
   `0x801B1D30`, 0x61A8 bytes, `script_interp.c:2114`).
2. That section starts with `FB 00 <script u16> <screen u16>` (`script_interp.c:2763`):
   it stores `CURRENT_SCRIPT_ID`/`CURRENT_SCREEN_ID`, pushes "reload the TFS" and calls
   `loadMap(screen)` (`map.c:4147`), which reads the whole `.MAP` into `GENERAL_BUFFER`
   (`0x80010000`) and distributes it. The rest of the section (e.g. `1E 00 F5 xx` = pstat 0xF5,
   `5D xx` = music) is executed and ends with `FE 00`.
3. `returnFromScriptFile` (`script_interp.c:2603`) reads the `.TFS` into the same
   `GENERAL_BUFFER` (overwriting the `.MAP`, which is no longer needed), calls `setupMap`
   (`map.c:4352`) and jumps to section `0xFE` (initialization) of script
   `CURRENT_SCRIPT_ID` in `DG.SCN` (`getScript`, `script_interp.c:571`).
4. The background tiles **stay in RAM** (`MapTileData.imagePtr` points into the
   TFS) and are uploaded to VRAM in windows of 4×3 tiles as the camera moves
   (`uploadMapTileImages` `map.c:4525`, `handleTileUpdate` `map.c:4786`). That is why the
   TFS cannot be overwritten while on the screen, and it is read again after a battle.
   With the mod executable's background streaming only the header and an 8-tile ring stay
   resident and the tiles are read from the CD as the window moves; the file format is unchanged and it no longer has to fit in the load area
   (still at most 35 tiles).

Files are looked up **by name only** (no directory): `buildMapPath`
(`map.c:4228`) builds `\MAP\MAP<id/15+1>\<NAME>.MAP`, but `lookupFileTable`
(`file.c:16`) keeps what follows the last `\` and looks that name up in
`FILE_OFFSET_TABLE` (`{i32 sector, i32 size, char *name}`, 819 entries,
`0x8011FE1C`). `readFile` (`file.c:80`) reads `⌈size/2048⌉` sectors starting at that sector:
**the size and sector that count are the executable's, not the ISO's.**

## `.MAP`

Little-endian. It starts with a **table of u32 offsets** (relative to the start of the
file); its size is the first offset. `loadMap` (`map.c:4147-4226`) walks it in this
order:

| # | Section | When it exists | Who reads it |
|---|---|---|---|
| 0 | setup (camera, lights, tiles) | always | `loadMapSetup` `map.c:4270` |
| 1..n8 | 8 bpp TIMs (map sprites) | `MAP_ENTRIES[id].num8bppImages` | `loadMapImage1` `overworld.c:351` |
| .. n4 | 4 bpp TIMs | `MAP_ENTRIES[id].num4bppImages` | `loadMapImage2` `overworld.c:365` |
| | sprites (definitions + instances) | only if n8 + n4 > 0 | `loadMapObjects` `overworld.c:302` |
| | entities (exits + placed Digimon) | always | `loadMapEntities` `tamer.c:350`, `loadMapDigimon` `overworld.c:994` |
| last | collision (10 000 bytes) | always | `loadMapCollisionData` `map_collision.c:23` |

**Important**: how many TIMs there are is **not in the `.MAP`** but in `MAP_ENTRIES` (n8, n4),
and the same goes for whether the Digimon list is read (`flags & 0x80`). Removing or adding TIMs requires
changing that row of the executable. `dwmap.py` deduces the sections from the offset table
(size = 4 × number of sections), so it also reads a `.MAP` file without a row (MGEN17).
Across the 242 files there are no gaps between sections except 40 bytes after the entities of
YAKA22 (count 63 without `flags & 0x80`); `dwmap.py` keeps those leftovers as they are.

### Setup section (all `s32`)

| Word | Field | Use |
|---|---|---|
| 0–2 | `vpx, vpy, vpz` | camera position; the game does `<<1` (`GS_VIEWPOINT`, `map.c:4282`) |
| 3–5 | `vrx, vry, vrz` | look-at point, also `<<1`; `GsSetRefView2` (roll `rz` is not touched) |
| 6–23 | 3 lights × `vx, vy, vz, r, g, b` | `GsSetFlatLight`; copy in `MAP_LIGHTS`; in the evening they are scaled ×1/0.7/0.7 and at night ×0.5 (`updateTimeOfDay`, `map.c:4428`) |
| 24–26 | ambient r, g, b | read and **ignored** (`GsSetAmbient(0x800,0x800,0x800)` fixed) |
| 27 | projection | `GsSetProjection(VIEWPORT_DISTANCE)`: focal length in pixels |
| 28–31 | region A ×4 | if any = `RAISE_DATA[partner].favoredRegion` → `partnerAreaResponse = 1` |
| 32–35 | region B ×4 | likewise → 2 (partner reactions to the area) |
| 36, 37 | width, height | in 128 px tiles (`MAP_TILE_DATA.width/height`, `int8`) |
| 38… | width×height values | `MAP_TILES[]` (`int8`, 35 at most): −1 = empty tile (black, not in the TFS); any other = the next tile of the TFS. **The value is not used as an index**: the TFS is consumed in order (`setupMap`), although in the files it is always 0, 1, 2… |

The function returns the next word, which nobody uses: the section ends there.

### Sprite TIMs

Standard TIM (`10 00 00 00`, flag, optional CLUT block, image block). It is uploaded to the
VRAM coordinates in its own header (`LoadImage`); across the 242 maps always at
**x = 384…767, y = 0…255** (412 8 bpp TIMs and 168 4 bpp ones).
- 8 bpp: the CLUT is uploaded unless its row is 480 (`loadMapImage1`): sprites
  cut out of the background itself use the background palette and change with the time of day.
- 4 bpp: only the **first** 4 bpp TIM uploads its CLUT, and splits it into rows of 16
  colors at (16·i, 486) (`loadMapImage2`).

### Sprite section (all `s16`)

```
s16 nDefinitions                          (LOCAL_MAP_OBJECTS[180]; one map has 186 and overflows)
nDefinitions × { texX, texY, width, height, x, y, z, clut, transparency }   9 × s16
s16 nInstances                            (MAP_TILE_DATA.objects[188])
nInstances × { frames[8], times[8], x, y, flag }                            19 × s16
```

- **Definition** (`LocalMapObject`): texture rectangle and a 3D point `(x, y, z)` that
  is only used for depth sorting (`calcMapObjectOrder`, `overworld.c:388`:
  `otz >> 2`, minimum 0x23; `y = 10000` → all the way at the back, 0xFFE). `clut = −1`: 8 bpp with
  the background palette (0,480); `0–15`: 4 bpp with CLUT (16·clut, 486); `≥ 16`: 8 bpp with CLUT
  in row `clut + 468`. The page is `384 + (texX/256)·128` (8 bpp) or `·64` (4 bpp);
  `texY` 0–255. `transparency = 4`: opaque; 0–3: GPU semi-transparency mode
  (`buildMapOverlayPrim`, `overworld.c:700`).
- **Instance**: position `(x, y)` **in pixels of the full background**; animation of up to
  8 frames (definition index; −1 ends, −2 = invisible frame) with their
  duration in game frames. `flag = 1` is not drawn; `flag & 0x80` = snowflake
  (random position). They are, above all, **pieces of the background that must cover the
  characters** (treetops, roofs) and animations (water, smoke, flowers).
- Special cases by id: screens 0x58–0x60 and 0x84–0x87 scatter instances
  0x14–0x22 at random (snow, `overworld.c:330`); fog on 115–119, 121, 163, 220
  (`renderMapOverlays`, `overworld.c:436`).

A background retouch must also update overlapping foreground cutouts. Coela Point
(`MAYO05`, screen 5) adds stairs to the TFS, beneath the original cliff sprite.
Its recipe copies the changed background indices into the existing cliff TIM so
that the donor cliff does not hide the entrance up to a rectangular sprite edge.
The copy keeps existing transparent texels, testing all three CLUTs: index 1 is
transparent by day but coloured at dusk and night. It changes no palette, sprite
geometry or VRAM allocation. The beach turning grey-green at night is the
original TFS palette, shared by the background and cutouts.

### Entity section (all `s16`)

```
MapWarps (120 bytes): spawnX[10], spawnY[10], spawnZ[10], rotation[10], targetMap[10], targetExit[10]
s16 nDigimon
if MAP_ENTRIES[id].flags & 0x80, nDigimon × {
    33 × s16: type, followMode, posX, posY, posZ, rotX, rotY, rotZ, trackingRange, unk2,
              scriptId, hp, mp, currentHp, currentMp, off, def, speed, brain, bits,
              chargeMode, unk1, tech[4], priority[4], fleeX, fleeY, fleeZ
    s16 nWaypoints (≤ 8)
    s16 aiSections[8]          (0 wait waypoint.x frames, 1 walk, 2 run, −1 restart)
    nWaypoints × { x, y, z }
}
```

- Exit *i*: spawn point (x, y, z, heading 0–0xFFF) when **arriving** through it, and
  destination `(targetMap, targetExit)` when **stepping** on a tile of value `110 + i`
  (`checkMapInteraction`, `tamer.c:655`). −1 = no destination (used by scripts). The
  partner appears 200 units in front of the player (`tamer.c:368-379`).
- Placed Digimon: up to 8 (slot *n* = `ENTITY_TABLE[n+2]`). They only exist if the screen's
  script creates them (`LOAD_DIGIMON`/`SET_DIGIMON`, which fails if the type does not match
  the one in the `.MAP`). The battle stats, the reward (`bits`) and the script section
  run on talking/touching (`scriptId`) are these, not those in `DIGIMON_DATA`.

### Collision (10 000 bytes)

100×100 grid, row = Z tile, column = X tile; tiles of 100 units,
`tx = x/100 + 50`, `tz = 50 − z/100` (with sign correction, `getModelTile`
`map_collision.c:146`). Values: 0 free, **bit 7 = wall** (`checkMapCollisionX/Z`), 110–119
exit, 120 toilet, 51–79 script section on stepping, 80–109 script section on pressing ✕.
Scripts can block tiles at run time (`7C`, chests).

## `.TFS`

Read by `setupMap` (`map.c:4352-4426`); the format is trivial and uncompressed:

```
u16 width, u16 height        NOT read (data++). In 13 files they do not match the .MAP
u32 nCLUT                    1 (interiors, flags & 0x40), 3 (day, evening, night); 4–5 in MIST02, TWNA02, MAYO01_2
nCLUT × 256 × u16            BGR555 palettes → VRAM (0, 481+i); the active one is copied to (0,480)
for each non-empty tile of the .MAP, in order:
    u32                      source position (u16 x = column·64, u16 y = row·128): NOT read,
                             but it always matches the .MAP grid
    128 × 128 bytes          8 bpp pixels, row by row (LoadImage of 64×128 words)
```

- VRAM window: tile (col, row) goes to `(768 + 64·(col%4), 128·(row%3))`, 8 bpp
  page, CLUT (0,480) (`fillTileData`, `map.c:4469`).
- `MAP_CLUTS` has only 3 pointers: with 4–5 CLUTs the game writes past the array. For
  new maps: **exactly 1 (with `flags & 0x40`) or 3**.
- Color `0x0000` is transparent on the PS1 (the black behind shows through); for a "real"
  black in a new palette `dwmap.py` uses `0x8000`.

## Camera and projection (for rendering new backgrounds)

`dwmap.py` projects with this formula and the overlay matches the game (a clearing
painted in MAYO01 lines up with where one can walk):

- Eye `E = 2·(vpx, vpy, vpz)`, target `T = 2·(vrx, vry, vrz)`, no roll.
- Camera axes (PS1 convention, **Y pointing down**): `z = norm(T − E)`,
  `x = norm((0,1,0) × z)`, `y = z × x`.
- A world point `P` falls on the pixel of the **full background** (`width·128 × height·128`):
  `u = width·64 + f·(x·(P−E))/(z·(P−E))`, `v = height·64 + f·(y·(P−E))/(z·(P−E))` with
  `f` = word 27 (projection). The look-at point falls at the center of the background
  (`setupMap` + `initializeDrawingOffsets`, `map.c:4482`).
- The ground is `y = 0`; models grow towards −Y. A tile is 100 units; the
  world spans −5000 to +5000 in X and Z.

**Blender** (Z up): game world `(x, y, z)` → Blender `(x, z, −y)` (a proper
rotation, it preserves orientation). Camera at `E`, *Track To* constraint towards `T` (up
axis Blender +Z), no roll. Resolution `width·128 × height·128`, aspect 1,
horizontal *sensor fit* with **sensor = width·128 mm and focal length = f mm** (horizontal FOV
`2·atan(width·64/f)`), *shift* 0. That way the render covers the background exactly and each pixel
matches the GTE projection (the GTE truncates to integers: ±1 px).

## `tools/dwmap.py`

Python 3 with no dependencies (PNG via `zlib`). Classes `MapFile`, `TfsFile`, `TIM` with
`build()` for rewriting; lossless `MapFile.to_json()/from_json()`. Every editing command
validates its input, rebuilds the file and checks it parses back identically, and prints
the new size against the original.

| Command | What it does |
|---|---|
| `describe X.MAP [--screen N] [--maphead F]` | everything in the map in readable form: MAP_ENTRIES row, camera (world units, angles, FOV), lights, TIMs, sprite instances, each exit (spawn in world/tile/pixel, heading, target, which tiles trigger it), the exits of other maps that lead here, each placed Digimon (name, position, AI, path, stats, script section, whether MAPHEAD spawns it), collision as rectangles per value, and the sections of the screen's DG.SCN script |
| `coords X.MAP --world X Z \| --tile TX TZ \| --pixel U V \| --screen-px SX SY [--live]` | converts between world units, collision tile, background pixel and screen pixel (`--live` reads the 2D camera from the running emulator) |
| `edit IN.MAP OUT.MAP ops…` | all `.MAP` edits, applied in order (table below); `--maphead OUT.SCN` also rewrites MAPHEAD for added/removed/retyped Digimon; `--overlay OUT.png` renders the result |
| `bg X.MAP X.TFS OUT.TFS ops…` | background region edits keeping the palette: `--paste PNG X Y` (RGB, RGBA or indexed), `--text X Y TEXT` (5×7 font, `--scale --color --box`), `--fill X0 Y0 X1 Y1 RGB`, `--fill-tiles TX0 TZ0 TX1 TZ1 RGB` (the ground under collision tiles); `--at-world` takes world x z for paste/text |
| `overlay X.MAP OUT.png [--tfs F] [--clut 0/1/2] [--no-collision]` | the map seen without the emulator: background + collision (red wall, blue exit, yellow step script, green ✕ script, brown toilet), `S<k>><map>.<exit>` spawn points with heading, `D<slot>` Digimon with their path, `I<n>` sprite instances (dashed = hidden) |
| `tim-import X.MAP K sprite.png OUT.MAP` | replaces the pixels of sprite TIM K (same size; requantized to the CLUT it is drawn with) |
| `entry SLUS ID [FIELD=VALUE…] -o OUT` | shows/changes a `MAP_ENTRIES` row: `name n8 n4 flags sound daynight digimon doors toilet label` (`--map` for a GCC/mods executable's linker map) |
| `doors SLUS [ENTRY] [--set K MODEL X Y Z ROT] -o OUT` | `DOOR_MAPDATA` (24 entries × 6 door models) |
| `toilet SLUS [ENTRY] [--set X1 Z1 X2 Z2] -o OUT` | `TOILET_DATA` (10 entries) |
| `roundtrip [DIR]` | parse → build of every `.MAP`/`.TFS`, `.MAP` → JSON → `.MAP`, background → indexed PNG → TFS (all 242; also RGB for 1 in 10), 580 sprite TIMs → PNG → `tim-import`, collision → PNG → `.MAP`: **all identical** (11 s) |
| `info X.MAP` | short summary |
| `dump X.MAP x.json` / `build x.json X.MAP` | the whole `.MAP` as editable JSON (collision as 100 hex rows, TIMs in base64) |
| `export X.MAP DIR` | `-background-day/evening/night.png` (indexed), `-overlay.png`, `-collision.png` (100×100 indexed: index = tile value), `-collision-x4.png`, `-timN-*.png`, `X.json` |
| `import-png X.MAP X.TFS background.png new.TFS [--new-palette]` | whole background PNG → TFS. Indexed with the same palette: copies the indices; RGB: unchanged pixels keep their index, the rest get the closest day colour. `--new-palette`: new 255-colour palette, evening/night derived |
| `collision-import X.MAP collision.png new.MAP` | painted grid (100×100 indexed PNG) → `.MAP` |
| `set-tiles X.MAP new.MAP TX0 TZ0 TX1 TZ1 VALUE` | fills a rectangle of tiles (same as `edit --paint`) |
| `map-entry NAME N8 N4 FLAGS DOORS TOILET LABEL` | the 16 bytes of a `MAP_ENTRIES` row (to poke into RAM) |
| `patch-exe SLUS SLUS.new ID NAME N8 N4 FLAGS DOORS TOILET LABEL` | writes row ID of `MAP_ENTRIES` into a copy of the original executable (file `0x992D4 + 16·ID`) |
| `file-entry SLUS SLUS.new NAME SECTOR SIZE` | repoints an entry of `FILE_OFFSET_TABLE` (file `0x8FE1C + 12·i`) |
| `mmm MMM.new FILE…` | copy of `MMM.DAT` with the files inside (sector-aligned); prints their absolute sector |

### What a screen contains and how each part is edited

| Part | Lives in | Command |
|---|---|---|
| camera eye/target, projection | `.MAP` setup | `edit --camera EX EY EZ TX TY TZ` (world units; the file keeps half), `--projection F`. The background is prerendered: moving the camera moves the 3D models (player, NPCs) against it, so only small changes look right unless the background is re-rendered |
| 3 flat lights | `.MAP` setup | `edit --light I VX VY VZ R G B` (tints every model on the screen) |
| partner area regions | `.MAP` setup | `edit --regions A0 A1 A2 A3 B0 B1 B2 B3` |
| background tile layout (width, height, tile list) | `.MAP` setup | `dump`/`build` JSON (and a TFS with that layout: `import-png`) |
| background pixels and palettes | `.TFS` | `bg --paste/--text/--fill/--fill-tiles` (regions), `import-png` (whole image, `--new-palette`) |
| sprite TIMs (foreground pieces, animations) | `.MAP` | `tim-import` / `edit --tim K PNG`; how many there are is in `MAP_ENTRIES` (n8, n4) |
| sprite definitions / instances | `.MAP` sprites | `edit --sprite I key=value`, `--instance I hide\|show\|X,Y` |
| collision: walls, exits, toilet, script triggers | `.MAP` collision | `edit --paint`, `--paint-world`, `--replace-value`; `collision-import` for a painted PNG |
| exits: spawn point, heading, target screen/exit | `.MAP` entities | `edit --set-exit`, `--spawn`, `--target`, `--clear-exit` |
| placed Digimon: type, position, AI, path, stats, bits, script section, flee point | `.MAP` entities | `edit --add-digimon`, `--remove-digimon`, `--move-digimon`, `--set-digimon`, `--path` |
| which placed Digimon appear (and when) | `MAPHEAD.SCN` section of the screen (`LOAD_DIGIMON`/`SET_DIGIMON`) | written by `edit … --maphead OUT.SCN` for add/remove/type changes; presence conditions in the Python story language |
| what touching a Digimon or stepping on a trigger does | the screen's `DG.SCN` script, section = `scriptId` or tile value | Python story handlers (`tools/dws.py`); `describe` lists which sections exist |
| chests, boulder, doors opening, tiles blocked at run time | script opcodes `75`, `76–78`, `7C` (DG.SCN) | story handlers (not in the `.MAP`) |
| name, sound bank, day/night, Digimon list on/off, doors, toilet, caption | `MAP_ENTRIES` row (executable) | `entry SLUS ID field=value -o OUT` |
| door models and positions | `DOOR_MAPDATA` (executable) | `doors` |
| toilet walk points | `TOILET_DATA` (executable) | `toilet` |
| crystals, fishing, curling, shops, arenas, snow, fog | C code by screen id | not data: avoid those ids (Limits) |

Not covered by commands (rare, use `dump`/`build` or the `MapFile` class): changing the
background grid size, adding/removing TIMs (needs `MAP_ENTRIES` n8/n4 too), the
`ambient` words (ignored by the game).

## New screens and disc layout

The mod stores screens 255 and above in `SCRN.DAT`, generated from screen JSON
by `tools/screens.py`. The derive screens and plan steps register the screen's
setup, map files and file-table names. The disc builder allocates sectors and
rewrites the executable's file table during `--relayout`. Manual sector assignment,
embedding files in MMM.DAT and repurposing original screen rows are unnecessary
for this workflow. See [new maps](new-maps.md) for the complete recipe.

A screen's TIM counts must match its map sections. Foreground sprites must use
valid texture pages, palette rows and world depth anchors. Collision must match
the visible geometry and connect the actual arrivals with the engine's body radius.
Use `tools/maps/cutout.py check`, `tools/maps/reach.py` and the final build's
memory checks, then verify walking and transitions at the original 2 MB.

`tools/dwmap.py roundtrip` checks parse/build and image-import preservation against
the extracted maps. This format check complements the geometric and runtime checks;
it does not prove that a newly authored screen is playable.
