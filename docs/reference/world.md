# The world: screens, entities, the city and recruitment

How the overworld is built and run: the 239 screens and their exits and placed Digimon, how a screen is entered,
player movement and collision, the camera, NPCs and wild Digimon, the partner's following, File City and its variants,
prosperity, Birdramon's transport, chests, poop and toilets. The `.MAP` and `.TFS` file formats and our map tooling are
in [../mods/maps.md](../mods/maps.md); the script side (sections, triggers, pstats) in [scripts.md](scripts.md).

Addresses are RAM addresses of the original US executable (`decomp/config/us/symbols.txt`; `tools/dwsyms.py` resolves
names for a rebuilt executable). `file.c:line` citations point into `decomp/src/main/`. `[inferred]` marks deductions.

## Summary

- The world is **239 screens** (ids 0-238, `MAP_ENTRIES[255]`), each a `.MAP` (data) and a `.TFS` (pre-rendered
  background). The current screen is one byte, `CURRENT_SCREEN`; there is no continuous world map: each screen is a
  plane of **100x100 tiles of 100 units** (X and Z from -5000 to +5000; Y is height and is 0 while walking) seen from a
  fixed camera defined in the `.MAP`. The mod executable raises the screen count (patch 0146, ids from 255 up).
- Each `.MAP` holds the camera and lights, the background image layout, animated sprites, **10 exits** (`MapWarps`:
  spawn point and target screen/exit), up to **8 placed Digimon** (type, position, battle stats, reward in bits, path)
  and the collision/trigger grid (10 000 bytes).
- Entering a screen runs MAPHEAD section *screen*, whose `FB` opcode loads the `.MAP` (`loadMap`) and the screen's
  script; that script decides which placed Digimon appear (`SET_DIGIMON`), places chests, closes doors.
- **There are no random encounters and no rate tables**: wild Digimon are fixed placements from the `.MAP` that, with a
  chasing `followMode`, walk towards the player and run their script section (usually the battle) on contact.
- There are 10 entities: `ENTITY_TABLE[0]` the player (`TAMER_ENTITY`), `[1]` the partner (`PARTNER_ENTITY`), `[2..9]`
  the 8 NPCs (`NPC_ENTITIES`).
- Recruitment lives in the scripts: each recruit sets a trigger and adds to pstat 1 (prosperity). The executable only
  reads 5 triggers to choose which of 12 upper File City variants loads (`getFileCityTopMap`) and 6 for Birdramon's
  destinations (`BIRDRA_TRANSPORT_TARGETS`).

## Source files

| File | Contents |
|---|---|
| `map.c` | `MAP_ENTRIES`, `MAP_NAME_PTR`, screen loading (`loadMap`, `loadMapSetup`, `setupMap`), screen change (`changeMap`, `scriptTickChangeMap`), 2D camera (`tickCameraFollowPlayer`, `createCameraMovement`), time of day (`updateTimeOfDay`, `tickDaytimeTransition`), entity collision and sliding (`entityCheckCollision`, `collisionGrace`), partner paths, `getFileCityTopMap`, the death map |
| `map_collision.c` | the 100x100 grid `MAP_COLLISION_DATA`: `getTileTrigger`, `checkMapCollisionX/Z`, `getModelTile`, `setImpassableRect/Square` |
| `overworld.c` | `MapDigimonEntity`/`LocalMapObject`, map sprites (`loadMapObjects`), placed Digimon (`loadMapDigimon`), `scriptSetDigimon`, NPC AI (`NPCEntityTickOverworld`), `setMovementEnabled`, fog, Ninjamon effect |
| `tamer.c` | the player: `initializeTamer`, `loadMapEntities` (reads `MapWarps`), state machine (`tamerTickOverworld`), pad movement (`tamerTickWalkingState`), interaction (`checkMapInteraction`, `checkItemPickup`, `checkChestCollision`), `startBattle`, `tamerTickChangeMap`, chests, scripted movement |
| `map_object.c` | 3D objects: doors (`loadDoors`, `tickRotateDoor`), chests (`CHEST_ARRAY`, `spawnChest`), teleport crystals, the boulder, Toy Town boxes, gear, Angemon's pedestal, dirt pile/cart, training poop, medal |
| `door_mapdata.c`, `toilet_data.c` | `DOOR_MAPDATA[24]` (up to 6 door models each), `TOILET_DATA[10]` (approach and use points) |
| `world_object.c` | `WORLD_OBJECTS[128]`: live objects (id, instance, `tick`, `render`) walked every frame |
| `aabb.c` | axis-aligned boxes (`findAABBHitEntity`, used in battle) |

## State in memory

Struct offsets computed from `entity.h`/`main.h` with the Psy-Q sizes (`GsDOBJ2` 0x10, `GsCOORDINATE2` 0x50, `MATRIX`
0x20); the totals match symbols.txt.

| Symbol | RAM | Type / size | Meaning |
|---|---|---|---|
| `CURRENT_SCREEN` | `0x80134DA8` | u8 | current screen (0xCC at boot) |
| `PREVIOUS_SCREEN` | `0x80134DA9` | u8 | previous screen; scripts use it to know where the player came from |
| `CURRENT_EXIT` | `0x80134DAA` | u8 | exit (0-9) the player **arrives** through: index into `MAP_WARPS` of the spawn point |
| `PREVIOUS_EXIT` | `0x80134DAB` | u8 | exit through which the previous screen was left |
| `CURRENT_SCREEN_ID` | `0x80134FFE` | u16 | copy written by `FB`; only scripts and `updateMapLightState` read it |
| `TARGET_MAP` | `0x80134DE0` | u8 | screen the player is about to change to (tamer state 5) |
| `DEATH_MAP` | `0x801343B0` | | deferred target set by `setDeathMap` |
| `SKIP_MAP_FILE_READ` | `0x80134DA0` | | 1 = `loadMap` reuses the buffer instead of reading the disc |
| `MAP_WARPS` | `0x80138730` | `MapWarps`, 0x78 | the 10 exits: `s16 spawnX[10]` +0, `spawnY` +0x14, `spawnZ` +0x28, `rotation` +0x3C, `targetMap` +0x50, `targetExit` +0x64; -1 = no target |
| `MAP_COLLISION_DATA` | `0x801AF398` | u8[100x100] | collision/trigger grid; row = Z tile, column = X tile |
| `ENTITY_TABLE` | `0x8012F344` | `Entity *[10]` | 0 player, 1 partner, 2-9 NPCs; NULL = empty |
| `TAMER_ENTITY` | `0x8015576C` | 0x3C | `Entity` + `s8 tamerLevel` +0x38, `u8 raisedCount` +0x39 |
| `PARTNER_ENTITY` | `0x801557A8` | 0x80 | `Entity` + `Stats` +0x38 + `learnedMoves[2]` +0x58 + `name[20]` +0x68 + `lives` +0x7C ([partner.md](partner.md)) |
| `NPC_ENTITIES` | `0x80155828` | 8 x 0x68 | `Entity` + `Stats` +0x38, `flee` +0x58, `bits` (reward) +0x60, `scriptId` +0x65, `autotalk` +0x66 |
| `Entity` | | 0x38 | `s32 type` +0 (id in `DIGIMON_DATA`), `PositionData *posData` +4, `animPtr` +8, `anim.locX/Y/Z` +0x10/+0x14/+0x18 (position x2^15, the authority for movement), `animFrame` +0x1C, `frameCount` +0x1E, `animId` +0x2E, `loopCount` +0x2F, `animFlag` +0x30, `isOnMap` +0x34, `isOnScreen` +0x35 |
| `PositionData` | | 0x88 per bone | `GsDOBJ2` +0, `GsCOORDINATE2` +0x10, `VECTOR scale` +0x60, `SVECTOR rotation` +0x70 (`vy` = heading, +0x72), `VECTOR location` +0x78; `posData` points to bone 0 |
| `TAMER_POSITION_DATA` | `0x801A07E8` | 22 bones | player: position at `0x801A0860/64/68`, heading at `0x801A085A` |
| `PARTNER_POSITION_DATA` | `0x801866CC` | 34 bones | partner: position at `0x80186744/48/4C`, heading at `0x8018673E` |
| NPC `posData` | dynamic | | allocated with `malloc3` when the entity is created; pointer at `NPC_ENTITIES + i*0x68 + 4` |
| `MAP_DIGIMON_TABLE` | `0x8013CB50` | 8 x 0xC4 | placements read from the `.MAP`: `s16 typeId` +0, `path.waypoints[8]` +4, `aiSections[8]` +0x84, `activeSection` +0x94, `posX/Y/Z` +0xA8/AA/AC, `rotX/Y/Z` +0xAE/B0/B2, `trackingRange` +0xB4, `followMode` +0xBC, `animation` +0xBE, `stopAnim` +0xC1 |
| `STORED_TAMER_POS` | `0x80138720` | `VECTOR` | the player's position in the previous frame; the difference drives the camera |
| `MAP_TILE_DATA` | `0x8014F084` | 0x1BBC | background: 35 `MapTileData` (+0), 188 sprites (+0x2BC), `cameraX/Y` +0x1BB4/+0x1BB6 (background pixel at the top-left), `width/height` +0x1BB8/+0x1BB9 (in 128 px tiles), `partnerAreaResponse` +0x1BBA |
| `GS_VIEWPOINT` | `0x80185BA8` | `GsRVIEW2` | 3D camera (position and look-at) from the `.MAP` |
| `DRAWING_OFFSET_X/Y` | `0x80134EC0` / `0x80134EC4` | s32 | drawing offset (160,120 on load); `CAMERA_FOLLOW_PLAYER` (`0x80134DC8`) enables following |
| `TAMER_STATE` / `TAMER_SUB_STATE` | `0x80134C91` / `0x80134C92` | s8 | player state machine (below) |
| `PARTNER_STATE` | `0x80134C5B` | s8 | 1 follows, 6 toilet, 7 poop, 9 eats poop, 11 still... |
| `IS_IN_MENU` | `0x80134EF0` | | 0 in the world |
| `WORLD_POOP` | `0x80138504` | 100 x 4 | `u8 map, x, y` (tile), `s8 size`; saved |
| `CHEST_ARRAY` | `0x80150F00` | 8 x 0x38 | chests: `location` +0, `trigger` +0x30, `item` +0x32 (0xFF empty), `isTaken` +0x33, `tileX/Y` +0x34/+0x35 |
| `DROPPED_ITEMS` | `0x8013D4E0` | 11 x 0x10 | items on the ground: `SVECTOR` +0, `s32 type` +8 (0xFF empty), `tileX/Y` +0xC/+0xE |
| `MAP_3D_OBJ` | `0x80153240` | 6 x 0x1C | doors/boulder: `translation` +0, `rotation` +0x10, `direction` +0x18, `modelId` +0x1A |
| `SAVED_STATE` | `0x801555D0` | 0x19C | restored on load: `playerPos` +0, `partnerPos` +0x10, `currentScreen` +0x155, `previousScreen` +0x156, `currentExit` +0x157, `previousExit` +0x158 |
| `WORLD_OBJECTS` | `0x80137418` | 129 x 0xC | live objects (`objectId`, `instanceId`, `tick`, `render`); -1 = free |
| `LOADED_DIGIMON_MODELS` | `0x801BE7EC` | s32[8] | NPC models loaded on the screen (-1 free) |

**Player states** (`tamerTickOverworld`, `tamer.c:418-479`): 0 walking, 1 → 6 (menu), 5 screen change, 6 still, 7
picking up an item, 8 training, 9/13 praise/scolding, 11 fishing, 12 curling, 14 chest, 15 opening, 16 ending, 17 loses
a life to illness, 18 Machinedramon's appearance, 19 loses a life in battle, 20 prize.

## Screens

### `MapEntry` (`MAP_ENTRIES`, `map.h`)

| Field | Use |
|---|---|
| `filename[10]` | name without extension; the path is `\MAP\MAP<n>\<filename>.MAP`/`.TFS` with `n = id/15 + 1` (`buildMapPath`), though files are found by name only ([../mods/maps.md](../mods/maps.md)) |
| `num8bppImages`, `num4bppImages` | how many 8 and 4 bpp TIMs the `.MAP` holds (map sprites); both 0 = no sprite section |
| `flags` | bit 7 (0x80): the `.MAP` carries placed Digimon; bit 6 (0x40): no day/night cycle; bits 0-4: the screen's sound bank (`getMapSoundId`); bit 5 is not read |
| `doorsId` | 0 = no doors; otherwise entry `doorsId - 1` of `DOOR_MAPDATA` |
| `toiletId` | 0 = no toilet; otherwise `TOILET_DATA[toiletId - 1]` |
| `loadingName` | index into `MAP_NAME_PTR` (70 names): the caption shown on entering (`addMapNameObject`) |

`../data/map_files.csv` has the raw `MAP_ENTRIES` rows with the zone names.

### Screen list

Columns: `snd` = `flags & 0x1F`; `D/N` = has a day/night cycle; `doors` = `doorsId`; `toilet` = `toiletId`; `exits` =
`exit→screen.exit` read from the entity section of each `.MAP` (`script` = the exit has a spawn point but target -1:
scripts use it to place the player, for example arriving on Birdramon); `placed Digimon` = the entries of
`loadMapDigimon` in slot order 0-7 (slot n = `ENTITY_TABLE[n+2]`). A placement does not mean the Digimon appears: the
screen's script decides with `SET_DIGIMON`. Of 468 exits with a target, 173 have no reciprocal exit back (one-way exits
and script points).

| id | file | zone (`loadingName`) | flags | snd | D/N | doors | toilet | exits (exit→map.exit) | placed Digimon (slot: id) |
|---|---|---|---|---|---|---|---|---|---|
| 0 | MAYO01 | Native Forest (0) | 0x80 | 0 | yes | 0 | 1 | 0→111.3, 1→8.0, 2→2.0, 3→1.0 | 0:ModokiBetamon, 1:ModokiBetamon, 2:RedVegiemon, 3:RedVegiemon, 4:ModokiBetamon, 5:Dokunemon, 6:Dokunemon, 7:Dokunemon |
| 1 | MAYO02 | Kunemon's Bed (68) | 0x80 | 0 | yes | 0 | 0 | 0→0.3, 1→3.0, 2→4.0, 3→9.1 | 0:RedVegiemon, 1:Kunemon, 2:RedVegiemon, 3:Dokunemon, 4:Dokunemon |
| 2 | MAYO03 | Native Forest (0) | 0x80 | 0 | yes | 0 | 0 | 0→0.2, 1→6.0, 2→3.2, 3→3.1 | 0:Goburimon, 1:Goburimon, 2:Palmon, 3:Goburimon, 4:Goburimon |
| 3 | MAYO04A | Native Forest (0) | 0x80 | 0 | yes | 16 | 0 | 0→1.1, 1→2.3, 2→2.2 | 0:Etemon, 1:Aruraumon, 2:Aruraumon, 3:Goburimon, 4:Goburimon |
| 4 | MAYO04B | Native Forest (0) | 0x80 | 0 | yes | 0 | 0 | 0→1.2, 1→5.0 |  |
| 5 | MAYO05 | Coela Point (1) | 0x80 | 0 | yes | 0 | 0 | 0→4.1 | 0:Coelamon, 1:ModokiBetamon, 2:ModokiBetamon, 3:ModokiBetamon, 4:Agumon, 5:Agumon, 6:Coelamon, 7:Coelamon |
| 6 | MAYO06 | Dragon Eye Lake (2) | 0x8d | 13 | yes | 0 | 0 | 0→2.1 | 0:Seadramon |
| 7 | MAYO11 | Drill Tunnel Entrance (3) | 0x80 | 0 | yes | 0 | 0 | 0→111.2, 1→24.0 | 0:Market Manager |
| 8 | MAYO10 | Dragon Eye Lake (2) | 0x0d | 13 | yes | 0 | 0 | 0→0.1 |  |
| 9 | MAYO08A | Digimon Bridge (4) | 0x80 | 0 | yes | 0 | 0 | 0→script, 1→1.3, 2→11.0 | 0:Aruraumon, 1:Ninjamon, 2:Tsukaimon, 3:Etemon |
| 10 | MAYO08B | Digimon Bridge (4) | 0x80 | 0 | yes | 0 | 0 | 0→script, 1→1.3, 2→script | 0:ModokiBetamon, 1:ModokiBetamon, 2:Aruraumon, 3:Tsukaimon, 4:Tsukaimon, 5:Tsukaimon |
| 11 | TROP00 | Tropical Jungle (5) | 0x81 | 1 | yes | 0 | 0 | 0→9.2, 1→12.1, 4→1.-1 | 0:Aruraumon, 1:Aruraumon, 2:Tsukaimon, 3:Tsukaimon |
| 12 | TROP01 | Tropical Jungle (5) | 0x81 | 1 | yes | 0 | 0 | 0→13.1, 1→11.1, 2→16.1, 3→15.0, 4→script | 0:Piximon, 1:Muchomon, 2:Muchomon, 3:J-Mojyamon, 4:J-Mojyamon |
| 13 | TROP02 | Tropical Jungle (5) | 0x81 | 1 | yes | 0 | 10 | 0→34.1, 1→12.0, 2→14.2, 3→14.1 | 0:Yanmamon, 1:Yanmamon, 2:Yanmamon, 3:Tsukaimon, 4:J-Mojyamon, 5:J-Mojyamon |
| 14 | TROP03 | Tropical Jungle (5) | 0x81 | 1 | yes | 0 | 0 | 0→36.0, 1→13.3, 2→13.2, 3→15.1 | 0:RedVegiemon, 1:Vegiemon, 2:RedVegiemon, 3:Tsukaimon, 4:J-Mojyamon |
| 15 | TROP04 | Mangrove Region (6) | 0x81 | 1 | yes | 0 | 0 | 0→12.3, 1→14.3 | 0:Betamon, 1:ModokiBetamon, 2:J-Mojyamon, 3:Tsukaimon |
| 16 | TROP05 | Mangrove Region (6) | 0x81 | 1 | yes | 0 | 0 | 0→17.0, 1→12.2 | 0:Yanmamon, 1:Yanmamon, 2:Muchomon, 3:J-Mojyamon, 4:J-Mojyamon, 5:J-Mojyamon |
| 17 | TROP06 | Amida Forest (69) | 0x85 | 5 | yes | 0 | 0 | 0→16.0, 1→79.0 | 0:Centarumon, 1:Centarumon, 2:Centarumon |
| 18 | MIHA00 | Path Thru Mt. Panorama (7) | 0x82 | 2 | yes | 17 | 0 | 0→111.1, 1→233.0 | 0:Goburimon, 1:Goburimon, 2:Aruraumon, 3:Aruraumon, 4:Goburimon, 5:Goburimon, 6:Gotsumon, 7:Gotsumon |
| 19 | MIHA01 | Mt. Panorama Plains (9) | 0x82 | 2 | yes | 0 | 0 | 0→20.0, 1→234.1, 2→233.2, 4→1.-1 | 0:Mamemon, 1:MudFrigimon, 2:MudFrigimon, 3:MudFrigimon |
| 20 | MIHA02 | Path Thru Mt. Panorama (7) | 0x82 | 2 | yes | 0 | 0 | 0→19.0, 1→22.0 | 0:Gotsumon, 1:Goburimon, 2:Gotsumon, 3:Goburimon |
| 21 | MIHA03 | Mt. Panorama Spore Area (11) | 0x82 | 2 | yes | 0 | 0 | 0→18.1, 1→19.1, 2→19.2 | 0:Centarumon, 1:Unimon |
| 22 | MIHA04A | Foot of Mt. Panorama (10) | 0x82 | 2 | yes | 0 | 2 | 0→20.1, 1→69.0 | 0:Flarerizamon, 1:Flarerizamon, 2:Aruraumon, 3:Aruraumon, 4:Tsukaimon, 5:Tsukaimon, 6:Goburimon, 7:Goburimon |
| 23 | MIHA04B | Foot of Mt. Panorama (10) | 0x82 | 2 | yes | 0 | 2 | 0→20.1, 1→69.0, 2→32.1 | 0:Flarerizamon, 1:Flarerizamon, 2:Aruraumon, 3:Aruraumon, 4:Tsukaimon, 5:Tsukaimon, 6:Goburimon, 7:Goburimon |
| 24 | TUNN01 | Drill Tunnel (12) | 0xc2 | 2 | no | 0 | 0 | 0→7.1, 1→25.0 | 0:Goburimon |
| 25 | TUNN02 | Drill Tunnel 2nd floor (13) | 0xc2 | 2 | no | 0 | 0 | 0→24.1, 1→26.0, 2→28.0, 3→27.0 | 0:Goburimon, 1:Goburimon, 2:Goburimon, 3:Ogremon, 4:Agumon, 5:Agumon |
| 26 | TUNN03 | Drill Tunnel 3rd floor (14) | 0xc2 | 2 | no | 0 | 0 | 0→25.1, 1→114.0 | 0:Drimogemon |
| 27 | TUNN04 | Residential Area (15) | 0xc2 | 2 | no | 0 | 0 | 0→25.3 | 0:Drimogemon |
| 28 | TUNN05 | Underground Pond (16) | 0xc2 | 2 | no | 0 | 0 | 0→25.2, 1→29.0 | 0:Drimogemon, 1:Drimogemon |
| 29 | TUNN06 | Drill Tunnel 2nd floor (13) | 0xc2 | 2 | no | 0 | 0 | 0→28.1, 1→30.0 | 0:Drimogemon |
| 30 | TUNN07 | Lava Cave (17) | 0xc2 | 2 | no | 0 | 0 | 0→29.1, 1→31.0 |  |
| 31 | TUNN08 | Lava Cave (17) | 0xc2 | 2 | no | 0 | 0 | 0→30.1, 9→0.-1 | 0:Meramon |
| 32 | TUNN09 | Drill Tunnel (12) | 0x82 | 2 | yes | 0 | 0 | 0→123.1, 1→script | 0:Drimogemon, 1:Drimogemon |
| 33 | TUNN10 | Lava Cave (17) | 0xc2 | 2 | no | 0 | 0 | 0→123.2, 1→125.0 | 0:DemiMeramon, 1:DemiMeramon |
| 34 | DGHA01 | Overdell (18) | 0x84 | 4 | yes | 0 | 0 | 0→35.1, 1→13.0, 2→36.2 | 0:Darkrizamon, 1:Darkrizamon, 2:Darkrizamon, 3:Darkrizamon, 4:Darkrizamon, 5:Darkrizamon, 6:Tsukaimon, 7:Tsukaimon |
| 35 | DGHA02 | Overdell Cemetery (19) | 0xc4 | 4 | no | 24 | 0 | 0→52.0, 1→34.0 | 0:Bakemon, 1:Tsukaimon, 2:Tsukaimon, 3:Tsukaimon, 4:Soulmon, 5:Soulmon, 6:Soulmon |
| 36 | GCAN01 | Great Canyon Entrance (20) | 0x86 | 6 | yes | 0 | 0 | 0→14.0, 1→44.0, 2→34.2 | 0:Goburimon, 1:Goburimon, 2:Gotsumon, 3:Gotsumon |
| 37 | GCAN02 | Great Canyon Top Area (21) | 0x86 | 6 | yes | 19 | 0 | 0→43.2, 1→script, 2→39.0, 3→script | 0:Goburimon, 1:Goburimon, 2:Goburimon, 3:Weedmon, 4:Weedmon, 5:Weedmon |
| 38 | GCAN03 | Great Canyon Top Area (21) | 0x86 | 6 | yes | 18 | 0 | 0→43.1, 1→88.2, 2→41.2, 9→script | 0:Weedmon, 1:SandYanmamon, 2:SandYanmamon, 3:Gotsumon, 4:Gotsumon |
| 39 | GCAN04 | Great Canyon Bridge (22) | 0x86 | 6 | yes | 0 | 0 | 0→37.2, 1→88.1 | 0:Shellmon, 1:Goburimon |
| 40 | GCAN05 | Fortress Entrance (23) | 0x86 | 6 | yes | 22 | 0 | 0→41.0, 1→45.0 | 0:Agumon |
| 41 | GCAN06 | Great Canyon Bot. Area (24) | 0x86 | 6 | yes | 20 | 0 | 0→40.0, 1→42.0, 2→38.2 | 0:Muchomon, 1:Muchomon, 2:Weedmon, 3:Weedmon, 4:Weedmon, 5:Goburimon |
| 42 | GCAN07 | Great Canyon Bot. Area (24) | 0x86 | 6 | yes | 0 | 0 | 0→41.1, 1→script | 0:SandYanmamon, 1:SandYanmamon, 2:Weedmon, 3:Gotsumon, 4:Gotsumon, 5:Gururumon |
| 43 | GCAN08_1 | Great Canyon Top Area (21) | 0x86 | 6 | yes | 0 | 0 | 0→44.1, 1→38.0, 2→37.0 | 0:Goburimon, 1:Goburimon, 2:Goburimon, 3:Ogremon, 4:Agumon, 5:Agumon |
| 44 | GCAN09 | Great Canyon Top Area (21) | 0x86 | 6 | yes | 0 | 3 | 0→36.1, 1→43.0, 2→49.0 | 0:Gotsumon, 1:Weedmon, 2:Gururumon, 3:Gururumon |
| 45 | OGRE00 | Ogre Fortress (25) | 0xc6 | 6 | no | 0 | 0 | 0→40.1, 1→46.0, 4→1.-1 | 0:Gabumon, 1:Gabumon, 2:Gabumon |
| 46 | OGRE01 | Ogre Fortress (25) | 0xc6 | 6 | no | 0 | 0 | 0→45.1, 1→47.0, 2→script, 4→1.-1 | 0:Gabumon, 1:Gabumon, 2:Agumon |
| 47 | OGRE02 | Ogre Fortress (25) | 0xc6 | 6 | no | 0 | 0 | 0→46.1, 1→48.0, 4→1.-1 | 0:Agumon, 1:Agumon, 2:Agumon, 3:Machinedramon, 4:Analogman, 5:Muchomon |
| 48 | OGRE03 | Ogre Fortress (25) | 0xc6 | 6 | no | 0 | 0 | 0→47.1, 1→script, 4→1.-1 | 0:Agumon, 1:Agumon, 2:Ogremon, 3:Agumon, 4:Agumon, 5:Ogremon, 6:Nanimon |
| 49 | GCAN11 | Monochrome Shop (26) | 0xc6 | 6 | no | 0 | 0 | 0→44.2 | 0:Monochromon, 1:Goburimon, 2:Gotsumon, 3:Weedmon, 4:Muchomon |
| 50 | YAKA01 | Grey Lord's Mansion (27) | 0x44 | 4 | no | 0 | 0 | (no `.MAP` file for this id) | |
| 51 | YAKA02 | Grey Lord's Mansion (27) | 0xc4 | 4 | no | 0 | 0 | 0→58.1 | 0:Rockmon, 1:Rockmon |
| 52 | YAKA11A | Grey Lord's Mansion (27) | 0xc4 | 4 | no | 1 | 0 | 0→35.0, 1→60.0, 2→59.0, 3→57.2, 4→55.1, 5→55.2, 6→53.3 | 0:Devimon |
| 53 | YAKA11B | Grey Lord's Mansion (27) | 0x44 | 4 | no | 2 | 0 | 0→232.0, 1→64.0, 2→63.0, 3→52.6 |  |
| 54 | YAKA12 | Grey Lord's Mansion (27) | 0x44 | 4 | no | 3 | 0 | 0→56.0, 1→55.0 |  |
| 55 | YAKA13 | Grey Lord's Mansion (27) | 0xc4 | 4 | no | 4 | 0 | 0→54.1, 1→52.4, 2→52.5, 3→script | 0:Myotismon |
| 56 | YAKA14 | Grey Lord's Mansion (27) | 0xc4 | 4 | no | 5 | 0 | 0→54.0, 1→57.1 | 0:Soulmon, 1:Soulmon, 2:Soulmon |
| 57 | YAKA15 | Grey Lord's Mansion (27) | 0x44 | 4 | no | 6 | 4 | 1→56.1, 2→52.3, 3→58.0, 4→script |  |
| 58 | YAKA16 | Grey Lord's Mansion (27) | 0xc4 | 4 | no | 7 | 0 | 0→57.3, 1→51.0 | 0:Tsukaimon |
| 59 | YAKA17 | Grey Lord's Mansion (27) | 0xc4 | 4 | no | 8 | 0 | 0→52.2 | 0:Tsukaimon |
| 60 | YAKA18 | Grey Lord's Mansion (27) | 0x44 | 4 | no | 9 | 0 | 0→52.1, 1→68.0 |  |
| 61 | YAKA21 | Grey Lord's Mansion (27) | 0x44 | 4 | no | 0 | 0 | (no `.MAP` file for this id) | |
| 62 | YAKA22 | Grey Lord's Mansion (27) | 0x44 | 4 | no | 10 | 0 | (entity section unreadable: garbage values) |  |
| 63 | YAKA23 | Grey Lord's Mansion (27) | 0x44 | 4 | no | 11 | 0 | 0→53.2, 1→62.0, 2→script |  |
| 64 | YAKA24 | Grey Lord's Mansion (27) | 0x44 | 4 | no | 12 | 0 | 0→53.1 |  |
| 65 | YAKA25 | Grey Lord's Mansion (27) | 0x44 | 4 | no | 13 | 0 | (no `.MAP` file for this id) | |
| 66 | CHKA01 | Mansion Basement (28) | 0xc4 | 4 | no | 0 | 0 | 0→62.1, 1→script | 0:Myotismon, 1:Machinedramon, 2:Analogman, 3:Soulmon |
| 67 | SAIB01 | Underground Lab (29) | 0xc4 | 4 | no | 0 | 0 | 0→68.1, 1→221.0, 4→1.-1 | 0:Myotismon, 1:Bakemon |
| 68 | SAIB02 | Underground Lab (29) | 0xc4 | 4 | no | 0 | 0 | 0→60.1, 1→67.0, 4→1.-1 | 0:Tekkamon, 1:Darkrizamon, 2:Darkrizamon, 3:Darkrizamon, 4:Darkrizamon, 5:Darkrizamon |
| 69 | GIAS00 | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 0 | 0→22.1, 1→74.0, 2→70.0 | 0:ShimaUnimon, 1:ShimaUnimon, 2:Tsukaimon, 3:NiseDrimogemon |
| 70 | GIAS01 | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 0 | 0→69.2, 1→71.0, 2→131.0, 9→script | 0:Psychemon, 1:Psychemon, 2:ShimaUnimon, 3:NiseDrimogemon, 4:NiseDrimogemon, 5:Sharmamon |
| 71 | GIAS02 | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 0 | 0→70.1, 1→72.0, 2→script | 0:Elecmon, 1:Akatorimon, 2:Akatorimon, 3:Sharmamon, 4:Psychemon, 5:Psychemon, 6:Sharmamon |
| 72 | GIAS03 | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 0 | 0→71.1, 1→73.0, 2→77.2 | 0:Patamon, 1:ShimaUnimon, 2:Sharmamon, 3:Sharmamon, 4:Sharmamon |
| 73 | GIAS04 | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 0 | 0→72.1, 1→77.1 | 0:Biyomon, 1:ShimaUnimon, 2:ShimaUnimon, 3:Akatorimon, 4:Sharmamon, 5:Sharmamon, 6:Tsukaimon |
| 74 | GIAS05 | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 0 | 0→69.1, 1→76.0 | 0:Psychemon, 1:Psychemon, 2:Akatorimon, 3:Tsukaimon, 4:Tsukaimon, 5:Sharmamon |
| 75 | GIAS06A | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 0 | 0→70.2 | 0:Devimon, 1:Devimon, 2:Psychemon, 3:Psychemon, 4:Sharmamon, 5:Sharmamon |
| 76 | GIAS07 | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 0 | 0→74.1, 1→78.0, 2→77.0 | 0:Patamon, 1:Goburimon, 2:Leomon, 3:Sharmamon, 4:Sharmamon |
| 77 | GIAS08 | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 7 | 0→76.2, 1→73.1, 2→72.2, 3→138.0, 4→164.0 | 0:ShimaUnimon, 1:Sharmamon, 2:Sharmamon, 3:NiseDrimogemon, 4:Sharmamon, 5:Sharmamon |
| 78 | GIAS09 | Gear Savanna (30) | 0x8e | 14 | yes | 0 | 0 | 0→76.1 | 0:Leomon |
| 79 | KODA00 | Ancient Dino Region (31) | 0x85 | 5 | yes | 0 | 5 | 0→17.1, 1→80.0 | 0:Tyrannomon, 1:Vermilimon, 2:Vermilimon, 3:Yanmamon, 4:Yanmamon |
| 80 | KODA01 | Ancient Glacial Region (32) | 0x85 | 5 | yes | 0 | 0 | 0→79.1, 1→81.0 | 0:Vermilimon, 1:Yanmamon, 2:Vermilimon, 3:Yanmamon, 4:Vermilimon, 5:Vermilimon |
| 81 | KODA02 | Ancient Glacial Region (32) | 0x85 | 5 | yes | 0 | 0 | 0→80.1, 1→82.0, 9→script | 0:Monochromon, 1:Saberdramon, 2:Brachiomon, 3:Brachiomon |
| 82 | KODA03 | Ancient Glacial Region (32) | 0x85 | 5 | yes | 0 | 0 | 0→81.1, 1→83.0 | 0:Tyrannomon, 1:Tyrannomon, 2:Master Tyrannomon, 3:Master Tyrannomon |
| 83 | KODA04 | Ancient Speedy Region (33) | 0x85 | 5 | yes | 0 | 0 | 0→82.1, 1→84.0 | 0:Gotsumon, 1:Gotsumon, 2:Saberdramon, 3:Darkrizamon, 4:Darkrizamon, 5:Gotsumon |
| 84 | KODA05 | Ancient Speedy Region (33) | 0x05 | 5 | yes | 0 | 0 | 0→83.1, 1→85.0, 2→87.0 |  |
| 85 | KODA06 | Ancient Speedy Region (33) | 0x85 | 5 | yes | 0 | 0 | 0→84.1 | 0:Saberdramon |
| 86 | KODA07 | Ancient Speedy Region (33) | 0x85 | 5 | yes | 0 | 0 | 0→87.1 | 0:Meteormon, 1:Nanimon |
| 87 | KODA08 | Ancient Speedy Region (33) | 0x85 | 5 | yes | 0 | 0 | 0→84.2, 1→86.0 | 0:Saberdramon, 1:Saberdramon, 2:Darkrizamon, 3:Darkrizamon |
| 88 | FRZL01 | Freezeland (34) | 0x8b | 11 | yes | 0 | 0 | 0→89.1, 1→39.1, 2→38.1 | 0:SnowAgumon, 1:SnowGoburimon, 2:IceDevimon, 3:IceDevimon |
| 89 | FRZL02 | Freezeland (34) | 0x8b | 11 | yes | 0 | 0 | 0→90.2, 1→88.0 | 0:Hyogamon, 1:Hyogamon, 2:IceDevimon, 3:IceDevimon |
| 90 | FRZL03 | Freezeland (34) | 0x8b | 11 | yes | 0 | 6 | 0→93.2, 1→91.1, 2→89.0 | 0:SnowAgumon, 1:SnowAgumon, 2:SnowGoburimon, 3:SnowGoburimon |
| 91 | FRZL04 | Freezeland (34) | 0x8b | 11 | yes | 0 | 0 | 0→92.1, 1→90.1 | 0:SnowGoburimon, 1:SnowGoburimon, 2:Hyogamon, 3:IceDevimon, 4:IceDevimon, 5:IceDevimon |
| 92 | FRZL05 | Freezeland (34) | 0x0b | 11 | yes | 0 | 0 | 0→97.0, 1→91.0 |  |
| 93 | FRZL06 | Freezeland (34) | 0x8b | 11 | yes | 0 | 0 | 0→96.0, 1→94.0, 2→90.0 | 0:Hyogamon, 1:Hyogamon, 2:Hyogamon, 3:IceDevimon, 4:IceDevimon, 5:Hyogamon |
| 94 | FRZL07 | Freezeland (34) | 0x8b | 11 | yes | 0 | 0 | 0→93.1, 1→95.0, 2→script | 0:SnowGoburimon, 1:SnowGoburimon, 2:IceDevimon, 3:IceDevimon |
| 95 | FRZL08 | Freezeland (34) | 0x8b | 11 | yes | 0 | 0 | 0→94.1, 1→121.2 | 0:Garurumon, 1:SnowAgumon, 2:SnowAgumon, 3:Hyogamon, 4:Hyogamon, 5:Garurumon |
| 96 | FRZL12 | Freezeland (34) | 0x8b | 11 | yes | 0 | 0 | 0→93.0, 1→132.0 | 0:SnowAgumon, 1:SnowAgumon, 2:SnowGoburimon, 3:SnowGoburimon |
| 97 | ICSA01 | Ice Sanctuary (35) | 0xcb | 11 | no | 0 | 0 | 0→92.0, 9→0.0 | 0:Angemon |
| 98 | ICSA02 | Ice Sanctuary (35) | 0xcb | 11 | no | 0 | 0 | 0→script, 1→script, 2→script, 3→script | 0:Icemon, 1:Icemon, 2:BlueMeramon |
| 99 | ICSA03 | Ice Sanctuary (35) | 0xce | 14 | no | 0 | 0 | 0→script, 1→script |  |
| 100 | ICSA04 | Ice Sanctuary (35) | 0xcb | 11 | no | 0 | 0 | 0→script, 1→script | 0:Hyogamon, 1:Hyogamon, 2:Gururumon |
| 101 | ICSA05 | Ice Sanctuary (35) | 0xcb | 11 | no | 0 | 0 | 0→script | 0:BlueMeramon, 1:BlueMeramon, 2:Icemon, 3:Icemon |
| 102 | ICSA06 | Ice Sanctuary (35) | 0xcb | 11 | no | 0 | 0 | 0→script | 0:Icemon, 1:Hyogamon, 2:Hyogamon |
| 103 | ICSA07 | Ice Sanctuary (35) | 0xcb | 11 | no | 0 | 0 | 0→script | 0:Gururumon, 1:Gururumon |
| 104 | ICSA08 | Ice Sanctuary (35) | 0xcb | 11 | no | 0 | 0 |  | 0:Machinedramon, 1:Analogman, 2:SnowAgumon |
| 105 | BETL01 | Beetle Land (58) | 0x80 | 0 | yes | 0 | 0 | 0→script, 1→106.0 | 0:Tentomon, 1:Tentomon, 2:Tentomon, 3:Dokunemon, 4:Dokunemon, 5:Dokunemon, 6:Tentomon, 7:Tentomon |
| 106 | BETL02 | Beetle Land (58) | 0x80 | 0 | yes | 0 | 0 | 0→105.1, 1→108.0, 2→107.0, 3→script | 0:Tentomon |
| 107 | BETL03 | Beetle Land (58) | 0xce | 14 | no | 0 | 0 | 0→106.2 | 0:Kabuterimon, 1:Kabuterimon, 2:Kabuterimon |
| 108 | BETL04 | Beetle Land (58) | 0xce | 14 | no | 0 | 0 | 0→106.1 | 0:Kuwagamon, 1:Kuwagamon, 2:Kuwagamon |
| 109 | MAYO00 | Native Forest (0) | 0x80 | 0 | yes | 0 | 0 | 0→112.0, 1→111.0, 2→180.0 | 0:Dokunemon, 1:Dokunemon, 2:Agumon, 3:ModokiBetamon, 4:ModokiBetamon |
| 110 | MAYO01_2 | Native Forest (0) | 0x80 | 0 | yes | 0 | 0 | 0→109.1, 1→script, 2→7.0, 3→0.0 | 0:Sukamon, 1:Sukamon |
| 111 | MAYO02_2 | Native Forest (0) | 0x80 | 0 | yes | 0 | 0 | 0→109.1, 1→18.0, 2→7.0, 3→0.0 | 0:Sukamon, 1:Sukamon |
| 112 | TRAI00 | Green Gym (36) | 0x8e | 14 | yes | 0 | 0 | 0→109.0, 1→script | 0:Koromon, 1:Kabuterimon, 2:Kuwagamon |
| 113 | LEOM01 | Leomon Ancestor's Cave (37) | 0xc2 | 2 | no | 0 | 0 | 0→114.1 | 0:Nanimon |
| 114 | LEOM02 | Leomon Ancestor's Cave (37) | 0xc2 | 2 | no | 0 | 0 | 0→126.1, 1→113.0 | 0:Drimogemon |
| 115 | MIST01 | Misty Trees (38) | 0x89 | 9 | yes | 0 | 0 | 0→139.2, 1→116.0, 2→120.0 | 0:Fugamon, 1:Fugamon, 2:MoriShellmon, 3:Darkrizamon, 4:Darkrizamon, 5:Tsukaimon |
| 116 | MIST02 | Misty Trees (38) | 0x89 | 9 | yes | 0 | 0 | 0→115.1, 1→117.0, 2→118.0 | 0:MoriShellmon, 1:MoriShellmon, 2:MoriShellmon, 3:Fugamon, 4:Fugamon, 5:Darkrizamon, 6:Darkrizamon |
| 117 | MIST03 | Misty Trees (38) | 0x89 | 9 | yes | 0 | 0 | 0→116.1, 1→121.0 | 0:Kokatorimon, 1:Goburimon, 2:Goburimon, 3:Goburimon, 4:MoriShellmon, 5:MoriShellmon, 6:Goburimon, 7:Goburimon |
| 118 | MIST04 | Misty Trees (38) | 0x89 | 9 | yes | 0 | 0 | 0→116.2, 1→119.0 | 0:Goburimon, 1:Fugamon, 2:MoriShellmon, 3:Saberdramon, 4:Saberdramon |
| 119 | MIST05 | Misty Trees (38) | 0x8e | 14 | yes | 0 | 0 | 0→118.1, 1→121.1, 2→144.0 | 0:Cherrymon |
| 120 | MIST06 | Misty Trees (38) | 0x89 | 9 | yes | 0 | 0 | 0→115.2 | 0:Gabumon, 1:Goburimon, 2:Goburimon, 3:Tsukaimon, 4:Darkrizamon |
| 121 | MIST07 | Misty Trees (38) | 0x89 | 9 | yes | 0 | 0 | 0→117.1, 1→119.1, 2→95.1 | 0:Fugamon, 1:Fugamon, 2:Fugamon, 3:Goburimon, 4:Goburimon, 5:Fugamon, 6:Tsukaimon, 7:Tsukaimon |
| 122 | TUNN07_2 | Lava Cave (17) | 0x42 | 2 | no | 0 | 0 | 0→29.1, 1→124.0, 2→123.0 |  |
| 123 | TUNN07_3 | Lava Cave (17) | 0xc2 | 2 | no | 0 | 0 | 0→122.2, 1→32.0, 2→33.0 | 0:DemiMeramon |
| 124 | TUNN08_2 | Lava Cave (17) | 0x42 | 2 | no | 0 | 0 | 0→122.1, 9→0.-1 |  |
| 125 | TUNN08_3 | Lava Cave (17) | 0xc2 | 2 | no | 0 | 0 | 0→33.1, 9→0.-1 | 0:DemiMeramon |
| 126 | TUNN03_2 | Drill Tunnel (12) | 0x42 | 2 | no | 0 | 0 | 0→25.1, 1→114.0 |  |
| 127 | GCAN04_2 | Great Canyon (39) | 0x86 | 6 | yes | 0 | 0 | 0→37.2, 1→88.1 | 0:Shellmon, 1:Goburimon |
| 128 | GCAN08_2 | Great Canyon (39) | 0x86 | 6 | yes | 0 | 0 | 0→44.1, 1→38.0, 2→37.0 | 0:Goburimon, 1:Goburimon, 2:Goburimon, 3:Ogremon, 4:Agumon, 5:Agumon |
| 129 | GCAN10 | Great Canyon (39) | 0x86 | 6 | yes | 21 | 0 | 0→script | 0:Birdramon |
| 130 | OGRE04 | Ogre Fortress (25) | 0x46 | 6 | no | 0 | 0 | 0→46.2, 4→1.-1 |  |
| 131 | GIAS06B | Gear Savanna (30) | 0x83 | 3 | yes | 0 | 0 | 0→70.2 | 0:Market Manager, 1:Market Manager |
| 132 | FRZL13 | Freezeland (40) | 0x8b | 11 | yes | 0 | 0 | 0→96.1, 1→135.0, 2→133.0, 3→134.1, 4→134.0 | 0:Hyogamon, 1:Hyogamon, 2:IceDevimon, 3:IceDevimon |
| 133 | FRZL14 | Freezeland (40) | 0x8b | 11 | yes | 0 | 0 | 0→132.2 | 0:Mojyamon, 1:Mojyamon |
| 134 | FRZL15 | Freezeland (40) | 0x8b | 11 | yes | 0 | 0 | 0→132.4, 1→132.3, 2→136.0 | 0:Penguinmon, 1:Mojyamon |
| 135 | FRZL16 | Freezeland (40) | 0x8b | 11 | yes | 0 | 0 | 0→132.1 | 0:SnowGoburimon, 1:Whamon, 2:IceDevimon |
| 136 | FRZL17 | Freezeland (40) | 0xcf | 15 | no | 0 | 0 | 0→134.2, 1→script | 0:Penguinmon, 1:MetalGreymon |
| 137 | FRZL18 | Freezeland (40) | 0xcb | 11 | no | 0 | 0 | 0→94.2, 1→script | 0:Frigimon |
| 138 | STIC01 | Geko Swamp (41) | 0x8a | 10 | yes | 0 | 0 | 0→77.3, 1→139.0 | 0:Yanmamon, 1:Yanmamon, 2:Yanmamon, 3:Gekomon, 4:Gekomon, 5:Gekomon |
| 139 | STIC02 | Geko Swamp (41) | 0x8a | 10 | yes | 0 | 8 | 0→138.1, 1→140.0, 2→115.0 | 0:Yanmamon, 1:Yanmamon, 2:Gekomon, 3:Gekomon, 4:Otamamon, 5:Gekomon, 6:Gekomon, 7:Gekomon |
| 140 | GKYO01 | Volume Villa (42) | 0x8a | 10 | yes | 0 | 0 | 0→139.1, 1→141.0 |  |
| 141 | GKYO02 | Volume Villa (42) | 0xca | 10 | no | 0 | 0 | 0→140.1 | 0:ShogunGekomon, 1:Gekomon, 2:Gekomon, 3:Gekomon |
| 142 | OGRE10 | Secret Beach Cave (51) | 0xcb | 11 | no | 0 | 0 | 0→143.0, 1→script, 2→script | 0:Whamon, 1:Ogremon |
| 143 | OGRE11 | Secret Beach Cave (51) | 0xcb | 11 | no | 0 | 0 | 0→142.0 | 0:Ogremon, 1:Gabumon, 2:Gabumon, 3:WaruSeadramon |
| 144 | OMOC01 | Toy Town (50) | 0x89 | 9 | yes | 0 | 0 | 0→119.2, 1→145.0, 2→146.0, 3→147.0 | 0:ClearAgumon, 1:ToyAgumon, 2:Tankmon |
| 145 | OMOC02 | Costume House (62) | 0xc9 | 9 | no | 0 | 0 | 0→144.1 | 0:Monzaemon |
| 146 | OMOC03 | Robot House (63) | 0xc9 | 9 | no | 0 | 0 | 0→144.2 | 0:Tinmon, 1:Hagurumon, 2:Tinmon, 3:Tinmon |
| 147 | OMOC04 | Toy Mansion (61) | 0xc9 | 9 | no | 15 | 0 | 0→144.3, 1→148.0 |  |
| 148 | OMOC05 | Toy Mansion (61) | 0xc9 | 9 | no | 14 | 0 | 0→script, 1→script, 2→script, 3→script | 0:ToyAgumon, 1:ToyAgumon, 2:ToyAgumon |
| 149 | OMOC06 | Toy Mansion (61) | 0xc9 | 9 | no | 14 | 0 | 0→script, 1→script, 2→script, 3→script | 0:Tankmon, 1:Tankmon |
| 150 | OMOC07 | Toy Mansion (61) | 0xc9 | 9 | no | 14 | 0 | 0→script, 1→script, 2→script, 3→script | 0:ClearAgumon, 1:ClearAgumon, 2:ClearAgumon |
| 151 | OMOC08 | Toy Mansion (61) | 0xc9 | 9 | no | 0 | 0 | 0→script | 0:WaruMonzaemon, 1:Nanimon, 2:Hagurumon |
| 152 | FACT01 | Factorial Town (52) | 0x88 | 8 | yes | 0 | 0 | 0→153.0, 1→script | 0:Guardromon, 1:Guardromon, 2:PlatinumSukamon, 3:PlatinumSukamon, 4:Whamon |
| 153 | FACT02 | Factorial Town (52) | 0x88 | 8 | yes | 0 | 0 | 0→152.0, 1→script | 0:Guardromon, 1:Guardromon, 2:Geremon, 3:Geremon, 4:MetalGreymon |
| 154 | FACT03 | Factorial Town (52) | 0x88 | 8 | yes | 0 | 0 | 0→script, 1→script, 2→script, 3→script, 4→156.0 | 0:Guardromon, 1:PlatinumSukamon, 2:PlatinumSukamon, 3:Geremon, 4:Guardromon, 5:Guardromon |
| 155 | FACT04 | Factorial Town (52) | 0x88 | 8 | yes | 0 | 0 | 0→script, 1→script | 0:Geremon, 1:Geremon, 2:Geremon, 3:PlatinumSukamon, 4:PlatinumSukamon, 5:PlatinumSukamon, 6:Guardromon, 7:Guardromon |
| 156 | FACT05 | Factorial Town (52) | 0x08 | 8 | yes | 0 | 0 | 0→154.4, 1→71.2 |  |
| 157 | FACT06 | Factorial Town (52) | 0xc8 | 8 | no | 0 | 0 | 0→script | 0:Andromon |
| 158 | FACT07 | Factorial Town (52) | 0xc8 | 8 | no | 23 | 0 | 0→161.0, 1→162.0, 2→script | 0:Geremon, 1:Geremon, 2:Guardromon, 3:Guardromon, 4:Guardromon, 5:Guardromon |
| 159 | FACT08A | Factorial Town (52) | 0xc8 | 8 | no | 0 | 0 | 0→158.1 | 0:Giromon |
| 160 | FACT08B | Factorial Town (52) | 0xc8 | 8 | no | 0 | 0 | 0→158.1 | 0:Giromon |
| 161 | FACT09 | Factorial Town (52) | 0xc8 | 8 | no | 0 | 0 | 0→158.0, 1→155.0 | 0:Guardromon, 1:PlatinumSukamon, 2:Guardromon, 3:Geremon, 4:Geremon, 5:Geremon |
| 162 | FACT10 | Factorial Town (52) | 0xc8 | 8 | no | 0 | 0 | 0→158.2 | 0:Guardromon, 1:Guardromon, 2:Guardromon |
| 163 | FACT11A | Sewer (57) | 0xc8 | 8 | no | 0 | 0 | 0→script, 1→220.0 |  |
| 164 | GOMI01 | Trash Mountain (56) | 0x87 | 7 | yes | 0 | 0 | 0→77.4, 1→165.0 | 0:Psychemon, 1:Geremon, 2:Geremon, 3:Geremon, 4:Psychemon, 5:Psychemon |
| 165 | GOMI02 | Trash Mountain (56) | 0xce | 14 | no | 0 | 0 | 0→164.1 | 0:King of Sukamon, 1:Sukamon, 2:Sukamon, 3:Sukamon |
| 166 | MGEN01 | Mt. Infinity (59) | 0xd1 | 17 | no | 0 | 0 | 0→script, 1→script | 0:Vermilimon, 1:Vermilimon, 2:Rockmon, 3:Vermilimon, 4:Rockmon |
| 167 | MGEN02 | Mt. Infinity (59) | 0xd1 | 17 | no | 0 | 0 | 0→script, 1→script | 0:Piddomon, 1:Piddomon, 2:Gururumon, 3:Piddomon, 4:Gururumon |
| 168 | TWNA02 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Tanemon, 7:Whamon |
| 169 | TWNA03 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Palmon, 7:Whamon |
| 170 | TWNA04 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Vegiemon, 7:Whamon |
| 171 | TWNA05 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Tanemon, 7:Whamon |
| 172 | TWNA06 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Palmon, 7:Whamon |
| 173 | TWNA07 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Vegiemon, 7:Whamon |
| 174 | TWNA08 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Tanemon, 7:Whamon |
| 175 | TWNA09 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Palmon, 7:Whamon |
| 176 | TWNA10 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Vegiemon, 7:Whamon |
| 177 | TWNA11 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Tanemon, 7:Whamon |
| 178 | TWNA12 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Palmon, 7:Whamon |
| 179 | TWNA13 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script, 9→script | 0:Yuramon, 1:Sukamon, 2:Andromon, 3:Kokatorimon, 4:Greymon, 5:Airdramon, 6:Vegiemon, 7:Whamon |
| 180 | TWNB01 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 181 | TWNB02 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 182 | TWNB03 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 183 | TWNB04 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 184 | TWNB05 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 185 | TWNB06 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 186 | TWNB07 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 187 | TWNB08 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 188 | TWNB09 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 189 | TWNB10 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 190 | TWNB11 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 191 | TWNB12 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 192 | TWNB13 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 193 | TWNB14 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 194 | TWNB15 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 195 | TWNB16 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 196 | TWNB17 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 197 | TWNB18 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 198 | TWNB19 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 199 | TWNB20 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 200 | TWNB21 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 201 | TWNB22 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 202 | TWNB23 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 203 | TWNB24 | File City (43) | 0x8c | 12 | yes | 0 | 0 | 0→109.2, 1→112.1, 2→9.0, 3→script, 4→script, 5→script, 6→script | 0:Bakemon, 1:Shellmon, 2:Betamon, 3:Kunemon, 4:Tsunomon, 5:Elecmon, 6:Megadramon, 7:Ogremon |
| 204 | TWNA01 | File City (43) | 0x8c | 12 | yes | 0 | 9 | 0→script, 1→112.1, 2→218.0, 3→script, 9→script | 0:Jijimon, 1:Tokomon, 2:Jijimon, 3:Jijimon, 4:Yuramon, 5:Tokomon, 6:Tanemon |
| 205 | ROOM10 | Jijimon's house (48) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→script, 2→206.0 | 0:Jijimon, 1:Angemon, 2:Tokomon |
| 206 | ROOM11 | Jijimon's house (48) | 0xcc | 12 | no | 0 | 0 | 0→205.2, 1→script | 0:Botamon, 1:Monzaemon, 2:Airdramon, 3:Jijimon |
| 207 | ROOM12 | Birdra Transport (53) | 0x8c | 12 | yes | 0 | 0 | 0→script | 0:Birdramon, 1:Leomon |
| 208 | ROOM13 | Arena Lobby (54) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→script, 2→script, 3→script | 0:Greymon |
| 209 | ROOM14 | Treasure Hunt (55) | 0xcc | 12 | no | 0 | 0 | 0→script | 0:Drimogemon, 1:Gabumon |
| 210 | MGEN03 | Mt. Infinity (59) | 0xd1 | 17 | no | 0 | 0 | 0→script, 1→script | 0:Rockmon, 1:Piddomon, 2:Rockmon, 3:Piddomon, 4:Piddomon |
| 211 | ROOM02 | Item Keeper (44) | 0xcc | 12 | no | 0 | 0 | 0→script | 0:Agumon, 1:Poyomon, 2:Nanimon |
| 212 | MGEN04 | Mt. Infinity (59) | 0xd1 | 17 | no | 0 | 0 | 0→script, 1→script | 0:Vermilimon, 1:Gururumon, 2:Vermilimon, 3:Vermilimon, 4:Gururumon |
| 213 | ROOM04 | Centar Clinic (45) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→script | 0:Centarumon, 1:Coelamon |
| 214 | ROOM05A | Restaurant (46) | 0xcc | 12 | no | 0 | 0 | 0→script | 0:Meramon, 1:Tyrannomon, 2:Garurumon, 3:Frigimon, 4:Vademon, 5:Digitamamon |
| 215 | ROOM05B | Restaurant (46) | 0xcc | 12 | no | 0 | 0 | 0→script | 0:Meramon, 1:Tyrannomon, 2:Garurumon, 3:Frigimon, 4:Vademon, 5:Digitamamon, 6:Giromon |
| 216 | ROOM06 | Item Shop (47) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→script | 0:Patamon, 1:Biyomon, 2:Unimon, 3:Monochromon, 4:Piximon, 5:Punimon |
| 217 | ROOM07 | Secret Item Shop (49) | 0xcc | 12 | no | 0 | 0 | 0→script | 0:Numemon, 1:Mojyamon, 2:Mamemon, 3:Devimon, 4:Ninjamon |
| 218 | ROOM08 | Jijimon's house (48) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→script, 2→script, 3→script | 0:Jijimon, 1:Tokomon, 2:Botamon, 3:Airdramon |
| 219 | MGEN05 | Mt. Infinity (59) | 0xd1 | 17 | no | 0 | 0 | 0→script, 1→script | 0:Vermilimon, 1:Rockmon, 2:Rockmon |
| 220 | FACT11B | Sewer (57) | 0xc8 | 8 | no | 0 | 0 | 0→163.1 | 0:Numemon, 1:Numemon, 2:Nanimon |
| 221 | SAIB03 | Underground Lab (29) | 0xc4 | 4 | no | 0 | 0 | 0→67.1 | 0:SkullGreymon |
| 222 | MGEN98 | Mt. Infinity (59) | 0xd1 | 17 | no | 0 | 0 | 0→script, 1→script | 0:MetalGreymon |
| 223 | ROOM19 | Arena Lobby (54) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→script, 2→script, 3→script | 0:Greymon, 1:Airdramon, 2:MetalGreymon |
| 224 | YAKA26 | Grey Lord's Mansion (27) | 0xc4 | 4 | no | 6 | 0 | 0→54.1, 1→52.4, 2→52.5 | 0:Myotismon |
| 225 | MGEN99 | Mt. Infinity (59) | 0xd1 | 17 | no | 0 | 0 | 0→222.1 | 0:Machinedramon, 1:Analogman, 2:Airdramon, 3:Digitamamon |
| 226 | MGEN11 | Back Dimension (67) | 0xd1 | 17 | no | 0 | 0 | 0→script, 1→script | 0:Piddomon, 1:Piddomon, 2:IceDevimon, 3:IceDevimon |
| 227 | MGEN12 | Back Dimension (67) | 0xd1 | 17 | no | 0 | 0 | 0→script, 1→script | 0:Tekkamon, 1:Tekkamon, 2:BlueMeramon, 3:BlueMeramon |
| 228 | MGEN13 | Back Dimension (67) | 0xd1 | 17 | no | 0 | 0 | 0→script, 1→script | 0:Tankmon, 1:Tankmon, 2:Rockmon, 3:Rockmon |
| 229 | MGEN14 | Mt. Infinity (59) | 0x51 | 17 | no | 0 | 0 | 0→script, 1→script |  |
| 230 | MGEN15 | Mt. Infinity (59) | 0x51 | 17 | no | 0 | 0 | 0→script, 1→script |  |
| 231 | MGEN16 | Mt. Infinity (59) | 0x51 | 17 | no | 0 | 0 | 0→script, 1→script, 2→script |  |
| 232 | YAKA25 | Grey Lord's Mansion (27) | 0xc4 | 4 | no | 0 | 0 | 0→53.0 |  |
| 233 | MIHA05 | Mt. Panorama Spore Area (11) | 0x82 | 2 | yes | 0 | 0 | 0→18.1, 1→234.0, 2→19.2 | 0:Unimon |
| 234 | MIHA06 | Mt. Panorama Spore Area (11) | 0x82 | 2 | yes | 0 | 0 | 0→233.1, 1→19.1 | 0:Vademon |
| 235 | ROOM20 | Digimon Curling (60) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→script, 2→script | 0:Penguinmon, 1:MetalGreymon |
| 236 | TEND01 | File City (43) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script | 0:Jijimon, 1:Greymon, 2:Airdramon |
| 237 | TEND02 | File City (43) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→112.1, 2→218.0, 3→211.0, 4→script, 5→script, 6→script | 0:Jijimon, 1:Greymon, 2:Airdramon |
| 238 | TOPN01 | File City (43) | 0xcc | 12 | no | 0 | 0 | 0→script, 1→112.1, 2→218.0, 3→script, 9→script | 0:Jijimon, 1:Tokomon, 2:Jijimon, 3:Jijimon, 4:Yuramon, 5:Tokomon, 6:Tanemon, 7:Poyomon |

Screens 50, 61 and 65 have no `.MAP` of their own on the disc (a YAKA25 exists at id 232); the three share script 5
with five other screens and may be dead entries. YAKA22's entity section does not decode as exits.

Groups: `MAYO` Native Forest/Coela Point/Dragon Eye Lake, `TROP` Tropical Jungle, `MIHA` Mt. Panorama, `TUNN` Drill
Tunnel/Lava Cave, `DGHA` Overdell, `GCAN` Great Canyon, `OGRE` Ogre Fortress, `YAKA` Grey Lord's Mansion, `SAIB`
Underground Lab, `GIAS` Gear Savanna, `KODA` Ancient Dino Region, `FRZL` Freezeland, `ICSA` Ice Sanctuary, `BETL` Beetle
Land, `MIST` Misty Trees, `LEOM` Leomon's cave, `OMOC` Toy Town, `FACT` Factorial Town, `GOMI` Trash Mountain, `MGEN`
Mt. Infinity/Back Dimension, `TWNA`/`TWNB`/`TEND`/`TOPN` File City, `ROOM` interiors, `GKYO` Volume Villa, `TRAI` gym,
`STIC`/`CHKA`.

## How a screen is entered

The file-level chain (MAPHEAD section, `FB`, `loadMap` into `GENERAL_BUFFER`, the `.TFS` read in
`returnFromScriptFile`, tile streaming) is in [../mods/maps.md](../mods/maps.md#how-a-screen-is-loaded-summary-of-the-chain).
The control flow around it:

1. A change is requested: the player steps on an exit tile (`checkMapInteraction`: `TARGET_MAP =
   MAP_WARPS.targetMap[exit]`, `CURRENT_EXIT = targetExit[exit]`, tamer state 5) or a script runs `WARP_TO` (`4B screen
   exit section` → `scriptTickChangeMap`). Both fade to black over 20 frames, draw the zone caption halfway and call
   `changeMap(mapId, exitId)`.
2. `changeMap` (`map.c:5458-5525`): `unloadMap` (empties tiles, removes objects 0xFA9/0xFB3...0xFBF and chests),
   `removeMapEntities` (frees the 8 NPCs and unloads their models), `clearDroppedItems`; `PREVIOUS_SCREEN =
   CURRENT_SCREEN`, with ten special cases so that going back makes sense after Birdramon, Seadramon's boat, the beach
   cave and similar one-way trips (`map.c:5466-5521`); `CURRENT_EXIT = exitId`; `runMapHeadScript(mapId)`.
3. `loadMap` reads the `.MAP` parts in order: setup (camera, 3 lights, ambient, projection distance, two lists of 4
   regions compared with the partner's `RAISE_DATA.favoredRegion` → `partnerAreaResponse` 1/2, which drives the
   partner's like or dislike of the area; size and tile list), 8 bpp TIMs, 4 bpp TIMs, map sprites (only if there are
   TIMs; on screens 0x58-0x60 and 0x84-0x87 instances 0x14-0x22 are scattered at random: snowflakes), entities
   (`loadMapEntities`: 120 bytes of `MapWarps`, places the player at `MAP_WARPS[CURRENT_EXIT]` and the partner 200 units
   in front, facing the player; then `loadMapDigimon`), doors if `doorsId`, crystals on 101-103, training poop on 0xA5,
   and the collision grid. Then it loads the sound bank (`flags & 0x1F`), sets `CURRENT_SCREEN`, resets the waypoints
   and checks for fishing (6, 8), curling (136), a shop (`SHOP_MAPS`: 131, 133, 134, 141, 207, 211, 215, 218) or an
   arena (208, 223), loading the matching overlay.
4. After the screen script's initialization, `setupMap` loads the 3 background CLUTs (`MAP_CLUTS`), applies the time of
   day, distributes the 128x128 tiles, centres the 2D camera on the player and uploads the visible 4x3 window.
5. `tamerTickChangeMap` fades in, puts player and partner in states 0/1 and calls `checkMapInteraction` again (in case
   they spawned on a trigger).

The death map is the same, deferred: `setDeathMap` stores it and `changeToDeathMap` calls `changeMap`. On loading a
save, `initializeLoadedMap` restores positions; if the player appears on top of an NPC of certain types it moves them to
`currentExit`, otherwise it switches the NPC off (`isOnMap = 0`). `SAVED_STATE.npcMaps[8]` is written on saving but
never read back. After the ending `gameClearSave` sets `CURRENT_SCREEN = getFileCityTopMap()`.

## World loop and objects

Every frame `gameLoop` runs the active script (if any), then `tickObjects()` and `renderObjects()` over `WORLD_OBJECTS`.
Player, partner and NPCs are objects (`initializeDigimonObject(type, slot, tick)`, `model.c:2786`); other fixed ids:
background 0xFA0 (`renderMap`), zone caption 0xFA1, clock 0xFA2, poop 0xFA8, doors 0xFA9, camera movements 0xFB1, chests
0xFB5, boulder 0xFB6, crystals 0xFB7, Meramon's tremor 0xFB8, light transition 0xFBE, items on the ground 0x195.

## Player movement and collision

- **Pad** (`tamerTickWalkingState`, `tamer.c:481-560`): directions are the `PadRead` bits (up 0x1000, right 0x2000,
  down 0x4000, left 0x8000); confirm 0x40 (✕), cancel 0x10 (△), 0x8 R1. Moving uses animation 3 (run), or 2 (walk) while
  R1 or △ is held; standing still, 0. △ opens the menu (state 1 → 6).
- **Heading** is rounded to 8 directions (multiples of 0x200 in a 0x1000 turn) relative to the camera: `getMapRotation`
  is the `.MAP`'s camera angle, so "up" always moves away from the camera. Heading 0 faces +Z; 0x400 +X, 0x800 -Z,
  0xC00 -X.
- **Speed** is not a constant: `entityMoveForward` (`map.c:3804-3843`) advances `momentum->delta[8]` units (x2^15) per
  frame, the root displacement carried by each model's walk/run animation. It stores the position in `anim.locX/locZ`
  and recomputes `posData->location` from them, with Y = 0.
- **Collision** (`entityCheckCollision`, `map.c:3527-3591`): tries the step and undoes it if (a) it would leave the
  battle area (battle only), (b) it hits the map (`checkMapCollisionX/Z`: tiles under the leading edge of the
  `DIGIMON_DATA[type].radius` with bit 7 set are walls) or (c) it hits another live entity
  (`entityCheckEntityCollision`: radius-versus-radius rectangles; when ✕ is pressed while standing, the player's grows
  50 units forward to reach a talk). Returns 10 (map), 11 (area), the entity index, or -1 when free. `collisionGrace`
  tries the 4 headings of `COLLISION_GRACE_ROTATION` and turns up to 0x50 per frame towards the free side: sliding along
  walls.
- **Tile ↔ world** (`getModelTile`): `tx = x/100 + 50`, `tz = 50 - z/100` (with a correction for rounding towards zero);
  tile centre `x = (tx - 50)*100 + 50`, `z = (50 - tz)*100 - 50`.
- **Grid values** (`getTileTrigger`): 0 free; 0x80 wall; any other value is a trigger that `checkMapInteraction`
  handles when stepped on: 110-119 exit (`value - 110` indexes `MAP_WARPS`), 120 toilet (if the partner needs to go,
  `condition & 8`, MH 0x4E2 runs), 51-79 a script section run on stepping, 80-109 a script section run on ✕ (signs,
  machines). Scripts can block tiles (`setImpassableRect/Square`, opcode `7C`); chests block 4x4 tiles. The shadow under
  entities disappears over walls. A 1-tile gap between walls is impassable for the player's collision box.

## Camera

The 3D camera is fixed per screen (`GS_VIEWPOINT`); what moves is the background. `tickCameraFollowPlayer` projects
the player's previous and current positions and shifts `MAP_TILE_DATA.cameraX/Y` and `DRAWING_OFFSET_X/Y` by the same
amount, clamped at the background edges (`cameraIsAtEdge`), reloading tiles into VRAM when boundaries are crossed
(`handleTileUpdate`). Scripts move the camera with `createCameraMovement(target, frames)` (object 0xFB1) and hand it
back with `setCameraFollowPlayer`. The background is a grid of at most 35 tiles of 128x128 px, of which 4x3 are in
VRAM. Rendering new backgrounds for this camera is covered in [../mods/maps.md](../mods/maps.md).

## Interaction

`checkMapInteraction` (`tamer.c:627-686`) runs in state 0 and after every screen change: if the player touches an NPC
(2-9) that has `autotalk`, or presses ✕, it calls section `NPC_ENTITIES[i].scriptId` of the screen's script with
`TALKED_TO_ENTITY` = index; then it checks the tile trigger and finally the chests (`checkChestCollision`: tile ±1 →
state 14). Items on the ground are picked up automatically within ±1 tile (`checkItemPickup`, state 7);
`DROPPED_ITEMS` is filled by `SPAWN_ITEM` (`74`) or battle loot. Script entity ids: 0xFD player, 0xFC partner, and the
`.MAP` `scriptId` for NPCs (`getEntityFromScriptId`).

## Entities: life cycle

1. `loadMap` → `clearMapDigimon` empties `MAP_DIGIMON_TABLE` and `ENTITY_TABLE[2..9]`; `loadMapDigimon` fills the
   table with the `.MAP`'s up to 8 placements **without creating them**.
2. The screen script decides which exist: `LOAD_DIGIMON` (`46 type`) loads the model (up to 8 in
   `LOADED_DIGIMON_MODELS`) and `SET_DIGIMON` (`47 type slot autotalk`) creates the entity in `ENTITY_TABLE[slot+2]`
   with the position, rotation and animation from the table; it fails silently if the type does not match
   `MAP_DIGIMON_TABLE[slot].typeId` (`scriptSetDigimon`, `overworld.c:1061-1086`). `UNLOAD_ENTITY` removes it. An NPC's
   battle stats (HP, techniques, the `bits` it pays, `battle_ui.c:291`) come from the `.MAP`, not from `DIGIMON_DATA`.
3. Every frame `NPCEntityTickOverworld` (`overworld.c:1192-1323`): unless a script animation is set
   (`NPC_ACTIVE_ANIM`) or it is stopped (`stopAnim`, via `setMovementEnabled`), it runs its path (`aiSections`: 0 wait
   `waypoints[i].vx` frames, 1 walk to the point, 2 run to the point; -1 restarts) and its `followMode`:

   | `followMode` | Behaviour |
   |---|---|
   | 1 | path only (town NPC) |
   | 2, 11 | turns towards the player inside the `trackingRange` square (`NPCEntityIsInTrackingRect`) |
   | 3-5, 12-14 | **chases** the player, walking, inside the square (wild Digimon; 12 is the value used) |
   | 6/15, 7/16 | chases (animation 2 / 4) inside the "radius" (`NPCEntityIsInTrackingRadius`, which compares `dx + dz` without squaring against `(0.6*range)^2`) |
   | 8, 9, 17, 18 | chases with animation 2 inside the square |

   The C code does not distinguish 3/4/5 or 12/13/14; only scripts might. Then it checks collision: if it hits the
   player and has `autotalk`, it launches its section without a button press; if it hits something while walking,
   `collisionGrace`. `isOnScreen` is recomputed with a 320x240 margin.
4. `removeMapEntities` on leaving frees `posData`/`momentum` (`removeEntity`) and unloads the models.

## Partner following

The partner follows a circular queue of 30 tiles (`PARTNER_WAYPOINT_*`, `partnerTickCollision`, `map.c:3394-3500`):
when there is no straight 5-tile-wide path between them (`isFiveTileWidePathBlocked`) it targets the player's last tile
and follows the trail; if both it and its next tile are off screen it teleports there, and `tickPartnerWaypoints` moves
it to the off-screen tile closest to the player. The player keeps a similar queue (`TAMER_WAYPOINT_*`,
`tickTamerWaypoints`) that is saved with the game.

## Wild Digimon and battles

There is no encounter table: each screen's species are its `.MAP` placements, with fixed stats per placement. The only
randomness is the scripts' (`STORE_RANDOM`), and they read the time with `STORE_DATE`, so which slot appears when, and
with what probability, lives in `DG.SCN` screen by screen. The script starts a battle with `START_BATTLE` (`66`)
against `TALKED_TO_ENTITY`: `startBattle` (`tamer.c:795-846`) sets `GAME_STATE = 1`, runs `BTL_battleMain` and on
return applies happiness/discipline (-30/-20 on a loss, -10/-6 on fleeing, +2 on a win), re-reads the `.TFS` and
advances the clock 20 minutes (`advanceBattleTime`). The battle itself is in [combat.md](combat.md); the mod's instant
field battles (patches 0233-0234) keep that order of loading. A wild Digimon placed too close to an arrival point can
spawn into an empty battle: keep placements well away from every exit's spawn point.

## Time of day

Three CLUTs per background (`MAP_CLUTS`: 0 day, 1 evening, 2 night). `updateTimeOfDay` picks by `HOUR`: 16-19 evening
(lights x1.0/0.7/0.7), 20-5 night (x0.5), otherwise day; `renderMap` starts the transition at 16, 20 and 6, and
`tickDaytimeTransition` interpolates the 256 CLUT entries over 25 frames, unless the partner is dying or evolving or the
player is in state 17/19. `flags & 0x40` disables all of it (interiors, caves). It is re-evaluated after a battle. The
music switches variant at 6 and 21 (`handleMusicOverride`). The full list of consumers is in
[core.md](core.md#day-and-night). The mod keeps a resident copy of the palettes (patch 0159).

## File City

The upper city is 13 screens with the same layout and different scenery: TWNA01 (204, the initial one) and TWNA02-13
(168-179). `getFileCityTopMap` (`map.c:5716-5763`) chooses among the twelve from five triggers:

`index = 168 + (T220 and T214 ? 6 : 0) + (T221 ? 3 : 0) + (T225 ? 2 : T246 ? 1 : 0)`

T246 is set by MAYO03's script (2, Palmon), T225 by TROP03's (14, Vegiemon), T221 by GCAN10's and OGRE04's (129/130,
Birdramon), T220 by the Ice Sanctuary's (97-103, Angemon), T214 by OMOC03's (146, Monzaemon) `[inferred from a byte
scan]`. Its only caller is `gameClearSave`. The rest of the city's buildings are not in C: each TWNB01-24 screen
(180-203) is a fixed set the scripts choose with `WARP_TO` `[inferred]`. The twelve TWNA02-13 share script 162, and the
TWNB screens share their list of placed Digimon. `MAP_LIGHT_UPDATE_DATA` (`script_common.c:252`, `utils2.c:543-565`)
switches sprites 0x31-0x32 of TWNB04 (183) between 7:00 and 19:00 (the city lights `[inferred]`). These rules, the
revival screen and NPC presence as data are in [../mods/city-rules.md](../mods/city-rules.md).

## Recruitment and prosperity

Prosperity is pstat 1 (`0x801BE032`). The scripts raise it with `ADD_TO_PSTAT` (`1F _ 01 value`, capped at 255) at the
end of each recruitment event and mark the recruit with `SET_TRIGGER 200+type`; the city script and
`getFileCityTopMap` read those triggers to change the city's scenery and NPCs (recruits appear as placements of the
TWNA/TWNB screens). `recalculateProsperity` rewrites pstat 1 from the triggers before every save, at game start and on City entry (IDs 3..58 in original story, only the owned City roster in extended story) ([scripts.md](scripts.md#pstats)).
What each Digimon requires (a battle, an item, a time of day) is in each screen's bytecode, not in C.

Points per screen, from a byte scan of `DG.SCN` for `1F ?? 01 vv` `[inferred; several figures on one screen are
alternative branches of the same script]`:

| Screen (script) | +prosperity | Screen (script) | +prosperity |
|---|---|---|---|
| 1 MAYO02 Kunemon's Bed | 1 | 97/98/100/101/103 Ice Sanctuary | 2 |
| 2 MAYO03 | 1 | 107, 108 Beetle Land | 2 |
| 3 MAYO04A | 3 | 109 MAYO00 | 1, 1 |
| 5 MAYO05 Coela Point | 2 | 113, 114 Leomon's cave | 1 |
| 6 MAYO06 Dragon Eye Lake | 2 | 115, 116, 120, 121 Misty Trees | 1 |
| 9 MAYO08A Digimon Bridge | 0, 2 | 117 MIST03 | 2 |
| 12 TROP01 | 3, 3 | 122-125 Lava Cave | 1 |
| 13 TROP02 | 3 | 127 GCAN04_2 | 2, 2 |
| 14 TROP03 | 2 | 129 GCAN10 (Birdramon) | 2 |
| 15, 16 Mangrove | 1 | 130 OGRE04 | 2 |
| 17 TROP06 Amida Forest | 2, 2, 2 | 133 FRZL14 | 2 x4 |
| 19 MIHA01 | 3, 3 | 134 FRZL15 | 2 |
| 20 MIHA02 | 3 | 137 FRZL18 | 2 |
| 21 MIHA03 | 2, 3 | 142 OGRE10 Secret Beach Cave | 2 |
| 22 MIHA04A | 2 | 146 OMOC03 Robot House | 3 |
| 24, 25 Drill Tunnel | 2 | 151 OMOC08 Toy Mansion | 1 |
| 31-33 Lava Cave / Drill Tunnel | 2 | 153, 154, 157, 159 Factorial Town | 3 (157 and 159: 3, 3) |
| 34, 35 Overdell | 2 | 165 GOMI02 Trash Mountain | 1 |
| 36-38 Great Canyon | 2 | 168-179 upper File City | 2 |
| 40 GCAN05 | 0 | 220/229-231 (script 180) | 1, 1 |
| 48 OGRE03 | 1 | 225 MGEN99 | 3, 7, 3 |
| 49 GCAN11 Monochrome Shop | 2 | 233, 234 MIHA05/06 | 2, 3 |
| 67, 68 Underground Lab | 3 | 235 ROOM20 Curling | 3 |
| 69 GIAS00 | 3 | scripts 198 and 206 (no screen) | 3, 1 |
| 71-73 Gear Savanna | 1 | 78 GIAS09 | 2 |
| 82 KODA03, 86 KODA07 | 2, 1 | 95 FRZL08 | 2 |

Script 5 (shared by screens 4, 30, 50, 61, 65, 84, 126, 140) also matches the pattern with 3, probably a false positive.
The screen → script mapping comes from MAPHEAD: section *screen* starts with `FB 00 script screen`; 254 sections use 197
scripts. The shops and buildings that open with each recruit are `ROOM*`/`TWNB*` screens the city script lets the
player enter by trigger; the C code only knows `SHOP_MAPS` and `ARENA_MAPS`, and `checkShopMap` skips loading the shop
overlay once when trigger 41 is set (`script_common.c:2985`).

## Horizon connections

Horizon connections preserve the original story's road and area unlocks. The
Drain's sewer connection needs Whamon or the reopened town; the Rubbish Mouth and
Iron Hills use the existing northern-road flags; the Overdell Pass preserves the
first jungle crossing. Their checks are step handlers on the new screens, with
unrestricted retreats and an escape for older saves stranded inside the Seam.
The [world audit](../mods/world-audit.md) documents the exact conditions, original
alternatives, deliberate arc changes and source/output verification.

## Birdramon

`BIRDRA_TRANSPORT_TARGETS[6]` (`0x8013024C`, `{u8 mapId, u8 exit, u16 trigger, u32 bits}`); the menu
(`calculateBirdramonMenuStrings`) shows the zone name and the price, and offers a destination only if its trigger is
set:

| Destination | Exit | Trigger (set by the script of) | Price |
|---|---|---|---|
| 38 GCAN03 Great Canyon Top Area | 9 | 221 (GCAN10/OGRE04, Birdramon) | 1000 |
| 70 GIAS01 Gear Savanna | 9 | 190 (GIAS06B) | 1000 |
| 79 KODA00 Ancient Dino Region | 9 | 188 (KODA04/KODA06) | 1500 |
| 93 FRZL06 Freezeland | 9 | 351 (FRZL06) | 2000 |
| 119 MIST05 Misty Trees | 9 | 147 (MIST05) | 2500 |
| 105 BETL01 Beetle Land | 0 | 210 (MAYO06, Seadramon) | 2500 |

The trip is a script `WARP_TO` from ROOM12 (207); `changeMap` then corrects `PREVIOUS_SCREEN`/`PREVIOUS_EXIT` so the
player seems to come from the neighbouring screen. The second byte is the arrival exit `[inferred]`: it matches a
`script` point in GCAN03, GIAS01 and BETL01, but in KODA00, FRZL06 and MIST05 that exit sits at (0,0,0).

## Chests, doors and other objects

- **Chests**: `SPAWN_CHEST` (`75 item x y z rotation trigger`) → `spawnChest` (`map_object.c:782-847`): takes a free
  `CHEST_ARRAY` slot, spawns open (`isTaken`) if the trigger is already set, blocks 4x4 tiles and shifts its interaction
  tile 4 tiles by the rotation. Opening (`tamerTickTakeChest`) animates the tray, gives the item and sets the trigger;
  with a full inventory it closes again. Chests are emptied on every screen change.
- **Doors** (`DOOR_MAPDATA`): 24 entries of up to 6 models `\DOOR\DOOR<nn>.TMD` (255 empty) with position and
  rotation. Used by 1-13 Grey Lord's Mansion, 14-15 Toy Mansion (147-150), 16 MAYO04A, 17 MIHA00, 18-22 Great Canyon
  (37, 38, 40, 41, 129), 23 FACT07, 24 DGHA02. `loadDoors` loads at most 4 distinct models and creates object 0xFA9.
  Opening is up to the script: `tickRotateDoor` rotates 33 units per frame for 32 frames (models 0, 9-13, 16-19), lowers
  200/frame (5, 31, 32) or slides 30/frame (0x14-0x1E). The door's collision is set by the script with `7C`.
- **Toilets** (`TOILET_DATA`): 10 entries `(x1, z1, x2, z2)`; screens with a `toiletId`: 1 MAYO01, 2 MIHA04A/B, 3
  GCAN09, 4 YAKA15, 5 KODA00, 6 FRZL03, 7 GIAS08, 8 STIC02, 9 all of upper File City (168-179, 204), 10 TROP02.
- **Teleport crystals** (Ice Sanctuary 101-103): fixed positions in `loadWarpCrystals`, scenery only; the jump is
  scripted.
- **Boulder** (`76`/`77`/`78`): `\ETCNA\IWA.TMD` at (-300, -500, 2000), pushed by the script.
- Toy Town boxes (`BIGBOX`/`SMABOX`), gear (`GAND`), Angemon's pedestal (`ABOX`), dirt pile and cart (`T_YAMA`,
  `DOSYA`, `HAKO`) and the training poop (`TRY`, only in GOMI02) follow the same scheme in `map_object.c`.

## Poop and toilets

The partner builds up the need to go (`tickPoopingMechanic`) and when `poopingTimer` reaches 0 enters state 7
(`tickWildPoop`): it stops, poops on its tile (`createPoopPile`, at most 100 piles in `WORLD_POOP`, each with its screen)
and loses happiness and discipline; the player loses a tamer level with 1 % probability. Taken to a toilet (tile 120 on a
screen with `toiletId`) it enters state 6 (`tickPartnerToilet`): it walks to `TOILET_DATA[toiletId-1]` point 1 then
point 2, plays animation 10 and gains +2/+2. Poop is drawn scaled by `size` on every screen where it lies
(`renderPoop`), and Sukamon/Numemon (types 39 and 11) eat it when they get close. The care side is in
[partner.md](partner.md#poop-and-the-virus-bar-tickpoopingmechanic-createpooppile).

## Writing state by hand

- Writing `CURRENT_SCREEN` loads nothing, but changes what is looked up in `MAP_ENTRIES[CURRENT_SCREEN]` (day/night,
  toilet, which poop is drawn); `CURRENT_SCREEN_ID` is only read by scripts. A screen change is requested by writing
  `TARGET_MAP` and `CURRENT_EXIT` and putting the tamer in state 5; `tamerTickChangeMap` does the rest (the normal path
  also stops the clock first).
- Moving an entity within a screen needs both `posData->location` and the `Entity`'s `anim.locX/Z` (position x2^15),
  as `setEntityPosition` does (`model.c:2957-2970`), or `entityMoveForward` undoes it on the first step; for the player
  also `STORED_TAMER_POS`, or the camera jumps. The 2D camera does not re-centre by itself after a long move.
- The city scenery is only re-evaluated when the city is entered again.
- `SKIP_MAP_FILE_READ = 1` before changing to the same screen repeats `loadMap` without reading the disc (useful after
  editing the collision in RAM).

Unverified: `MapEntry.flags` bit 5 and `MapWarps.spawnY` are never read (spawnY is always 0 in the files seen); the
meaning of `followMode` 3/4/5 versus 12/13/14 and of the placement fields `unk1`, `unk2`, `chargeMode` and `flee` (only
battle or scripts use them); the prosperity table and the triggers per screen come from a byte scan of the bytecode, not
from running it.

## City recruitment

The extended story has 89 residents worth 169 prosperity points, defined by
`content/tables/city-residents.json`. A first wild victory recruits an eligible
species with a jingle and a narrator announcement. Repeated victories, fleeing
and losing recruit nobody. ModokiBetamon, Dokunemon, Vermilimon, IceDevimon,
DarkLizardmon and Gururumon stay wild enemies; the Kennel keeper and hunters
keep their story roles. The original story retains its 50 recruits and 100 points.
