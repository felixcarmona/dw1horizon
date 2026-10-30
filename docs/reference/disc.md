# The disc

The layout of the Digimon World (USA) disc: identification, the directories and files and what each one is for, the
physical order, the executable's own file table (which is how the game really finds files) and what that means for
a rebuilt disc. File formats are in [file-formats.md](file-formats.md); the code overlays in
[executable.md](executable.md).

## Identification

| | |
|---|---|
| Game | Digimon World (USA), Bandai, 2000 |
| Serial | SLUS-01032; executable `SLUS_010.32` |
| `SYSTEM.CNF` | `BOOT = cdrom:\SLUS_010.32;1`, `TCB = 4`, `EVENT = 16`, `STACK = 801FFFF0` |
| Image | one track, `MODE2/2352`, 162 318 sectors (381 771 936 bytes); the redump `.bin` + `.cue` is the reference ([../building.md](../building.md) gives its SHA-1) |
| ISO 9660 | system `PLAYSTATION`, volume `DIGIMON`, publisher `BANDAI AMERICA INC.` |
| Other versions | Japan SLPS-01797 (the original release) and its budget reprint SLPS-91233; Europe SLES-02914 and the language variants SLES-03434 to 03437 |

Sectors 0–15 hold the Sony license data (kept as `license_data.dat` by the extractor and written back on rebuild).
Data files use Mode 2 Form 1 sectors (2048 usable bytes). Only the four `.STR` movies mix in Form 2 sectors (video and
XA audio), so they are copied as raw sectors ("mixed" type in mkpsxiso). The volume metadata, the file order, dates
and sector types of a rebuilt disc come from the committed layout `tools/disc-layout.xml` (metadata only).

## Contents (818 files, 336 MB)

```
/SYSTEM.CNF
/SLUS_010.32            main executable (675 840 B)
/*_REL.BIN              16 code overlays (BTL, DGET, DOO2, DOOA, EAB, ENDI, EVL, FISH, KAR, MOV, MURD, SHOP,
                        STD, TRN, TRN2, VS)
/MMM.DAT                27 648 000 B of zeros; the last file on the disc
/CARD/CARD.ALL          1.9 MB: the 66 card images
/CHDAT/ALLTIM.TIM       3.3 MB: the 180 Digimon textures, one per 0x4800 bytes
/CHDAT/MMD0..MMD5/      178 .MMD: model and animations of each Digimon (BOYS.MMD is the tamer)
/DOOR/DOOR00..32.TMD    33 door models
/ETCDAT/                22 files: TIMs and TMDs for the HUD, menus and minigames (ITEM.TIM, FISHING.TIM,
                        SLOT.TIM, KARRING.TMD, TAMA.TMD, ETCTIM.BIN with 9 TIMs, ...)
/ETCHI/                 EFEDAT.EFE (2.5 MB of battle effects), BOSS_EFE.TMD, LIFE.TIM, MAHI.TMD, OP.TIM
/ETCNA/                 18 files: TITLE2.TIM, TITLE256.TIM and prop TMDs (boxes, rocks, the warp, the medal)
/MAP/MAP1..MAP17/       242 pairs NAME.MAP (data) + NAME.TFS (background), 134 MB
/MOVIE/                 OP1.STR, OP2.STR, ED2.STR, EDR.STR (146 MB)
/SCN/DG.SCN             804 864 B: the 222 screen scripts (events, dialogue)
/SCN/MAPHEAD.SCN        24 686 B: the screens' header scripts
/SOUND/VHB/             7 sound banks: SS, SL (system), FAALL (music), VBALL, VLALL (voices), ESALL, SB (effects)
/STDDAT/                44 arena files: stages (*_TOGI.TIM/TMD/ATR), HUD, GRADE/*.TIM (one per cup)
```

By extension: 242 TFS, 242 MAP, 178 MMD, 66 TMD, 52 TIM, 18 BIN, 7 VHB, 4 STR, 2 SCN, 2 ATR, 1 EFE, 1 ALL,
1 DAT, 1 CNF.

The full inventory with LBA, size and sector count of each file in the original layout is
[data/disc-files.csv](data/disc-files.csv) (columns `path, lba, size, sectors, xa_attr`; `xa_attr` 0x2555 marks the
four mixed-sector movies). `tools/isolist.py` lists the same from an image (with an extra `kind` column).

### Overlays as files

The overlays are plain files in the root, read whole into fixed RAM addresses: their header, sizes, load addresses
and roles are in [executable.md](executable.md#overlays-_relbin). Three of them (`BTL`, `STD`, `VS`) carry a TIM and a
TMD before their code. `SHOP_REL.BIN` is on the USA disc and is still loaded on the shop maps, although the USA
executable already contains its code.

### Map files

The screens' files are spread over `MAP/MAP1..MAP17` by prefix; the executable builds the path
`\MAP\MAP<id/15+1>\<NAME>.MAP` but only the name counts (below). Prefixes: MAYO (Native Forest, File City
surroundings), TROP (Tropical Jungle), MIHA, TUNN (Drill Tunnel), DGHA, GCAN (Great Canyon), OGRE (Ogre Fortress),
YAKA, GIAS (Gear Savanna), SAIB, CHKA, KODA, FRZL (Freezeland), ICSA (Ice Sanctuary), BETL (Beetle Land), LEOM, MIST
(Misty Trees), TRAI, GKYO, OMOC (Toy Town), STIC, FACT (Factorial Town), GOMI (Trash Mountain), MGEN (Mt. Infinity
and the Back Dimension), TWNA/TWNB (File City), ROOM, TEND, TOPN. Which screen id uses which file and its area name:
`../data/map_files.csv` (`MAP_ENTRIES`); the format and the screen-loading chain: [../mods/maps.md](../mods/maps.md),
[world.md](world.md).

## The file table

**The game does not use the ISO file system to load data.** The executable carries its own table,
`FILE_OFFSET_TABLE` (RAM `0x8011FE1C`, 819 entries of `{i32 sector, i32 size, char *name}`; source
`decomp/src/main/file_table_us.c`), and reads by absolute sector with `CdRead`. `lookupFileTable` keeps only what
follows the last `\` of a path and compares it with the names in the table, so directories are irrelevant and every
name must be unique across the disc. The name strings sit in the executable from `0x8011D490`. Leftover paths to
directories that do not exist on the disc (`CHDAT\TMD0\`, `CHDAT\MTN0\`) are remnants of an earlier format in which
models and animations were separate files.

Two exceptions are looked up through the file system with `CdSearchFile`: the movies (by the STR player) and the
overlays and `BOSS_EFE.TMD` (path requests of the read queue, [engine.md](engine.md#file-loading)). `DG.SCN` is also
found by name.

Consequence for a rebuilt disc: the sector and size that count are the executable's, not the ISO's. A replaced file
either keeps its sector run (padded to its original size, so no later file moves) or the whole disc is laid out again
and the table rewritten inside the executable. `tools/build-disc.py` does the first by default and the second with
`--relayout` (which also allows new files, given a table entry for their name: patch 0147 and `tools/newfiles.py`).

## Physical order

The original image lays files out by LBA in this order: `SYSTEM.CNF` (LBA 23), `CARD.ALL` (25), `ALLTIM.TIM`
(950), the MMDs, `DOOR`, `ETC*`, `MAP`, `MOVIE`, `SCN`, `SOUND`, `STDDAT`, the 16 overlays, `SLUS_010.32` (148 338)
and finally `MMM.DAT` (148 668–162 168). Between directories there are gaps of 1–2 sectors (the directory records).

### Seek order

A screen change performs about fifteen small reads one after the other (`.MAP`, `SHOP_REL`, `FAALL.VHB`,
`ALLTIM` and each NPC's `MMD`, `.TFS`, ...). In the original order the 127 MB of movies sit between `MAP` and
`SOUND`/the overlays, so each load seeks about 110 000 sectors back and forth. `tools/build-disc.py --seek-order`
(with `--relayout`; the default of `tools/build-full.sh`, `SEEK_ORDER=0` keeps the original order) puts first
everything a load reads (`CHDAT`, `DOOR`, `ETC*`, `SCN`, `SOUND`, `STDDAT`, the overlays, the executable), then
`MAP`, then `MOVIE`, with `MMM.DAT` last. At real CD timing this takes a typical indoor ↔ town transition from about
6.5–7.4 s to 5.7–6.8 s. With instant seeks the floor is about 3.6–4.2 s: the rest is per-command cost and the
alternating `ALLTIM`/`MMD` reads, which no file order removes. Emulator save states made on one layout read wrong
sectors on the other.

## `MMM.DAT`

27.6 MB of zeros at the end of the disc (13 500 sectors). Nothing references it except its file-table entry; it is
most likely padding that pushes the data towards the inner, faster part of the disc. It is free space for mods: new
files can be placed in its sectors without moving any other LBA ([../mods/maps.md](../mods/maps.md),
[../mods/species.md](../mods/species.md)).
