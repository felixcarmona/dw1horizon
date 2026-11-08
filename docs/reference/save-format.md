# Save format

How a saved game is stored on the memory card: the original game's fixed file (header, two payload copies, checksum), and
the tagged extensions Horizon keeps inline in new saves and in a linked second block in legacy saves. The OPTIONS bytes a
save carries are described in [../mods/options.md](../mods/options.md); id widths in [ids.md](ids.md); where the
extension lives in RAM while a card operation runs in [memory.md](memory.md).

## The original file (v1)

One memory card block, 0x2000 bytes (`SaveFile` in `decomp/src/main/main_menu.c`): a 0x200-byte card header followed by
two identical 0xF00-byte payloads (`SavegamePayload saves[2]`), the second a backup of the first.

| File offset | Size | Field |
|---|---|---|
| 0x000 | 2 | `"SC"`, the card header magic |
| 0x002 | 1 | icon display flag (number of icon frames) |
| 0x003 | 1 | block count |
| 0x004 | 64 | title, Shift-JIS (what the BIOS card manager shows) |
| 0x044 | 12 | reserved |
| 0x050 | 16 | PocketStation bytes, unused by the game (patch 0193 puts the options copy here, below) |
| 0x060 | 32 | icon CLUT (16 colours) |
| 0x080 | 3 x 0x80 | icon frames (16x16, 4 bpp) |
| 0x200 | 0xF00 | payload copy 0 |
| 0x1100 | 0xF00 | payload copy 1 |

### Payload

Offsets inside one payload. `loadSavegame` and `writeSavegame` (`main_menu.c`) copy these fields to and from the
game state ([ram-map.md](ram-map.md) has the RAM side).

| Offset | Type | Field |
|---|---|---|
| 0x000 | i32 | main state |
| 0x004 | VECTOR | tamer position |
| 0x014 | VECTOR | partner position |
| 0x024 | `{u8 screen, u8 x, u8 y, i8 size}[100]` | poop piles in the world (0x190 bytes; screen 0xFF = none) |
| 0x1B4 | i32 | money |
| 0x1B8 | i32 | partner species |
| 0x1BC | u8[16] | partner's learned-technique bits |
| 0x1CC | u16, u16 | current frame, last handled frame |
| 0x1D0 | i16 x 4 | year, day, hour, minute |
| 0x1D8 | u16 x 3 | play time: frames, hours, minutes |
| 0x1E0 | `PartnerPara` (0x84) | the partner's care state (hunger, sleep, toilet, happiness, discipline, timers, training counters...) |
| 0x264 | i16 x 6 | merit, battles started, battles fled, tournaments won, tournament wins, tournaments lost |
| 0x270 | `Stats` (0x20) | partner base stats, equipped techniques and current HP/MP |
| 0x290 | u8[0x17C] | script state (triggers and registers, copied whole to and from `SCRIPT_STATE_PTR`) |
| 0x40C | `Inventory` (0x5B) | item ids [30], amounts [30], name-order [30], bag size |
| 0x467 | char[20] | tamer name |
| 0x47B | char[20] | partner name |
| 0x48F | i8 | partner lives |
| 0x490 | i8 | tamer level |
| 0x491 | u8 | raised count |
| 0x492 | i8[8] | NPC screens |
| 0x49A | u8 x 4 | current screen, previous screen, current exit, previous exit |
| 0x49E | i8[30], i8[30] | tamer waypoints X, Y |
| 0x4DA | i8 x 7 | previous tile X/Y, waypoint current/count, start tile X/Y, waypoint active |
| 0x4E1 | u8[0x1B] | unused (0x4E4..0x4FB is where the version word goes, below) |
| 0x4FC | i32 | checksum |
| 0x500 | `RegisteredDigimon[40]` (0x40 each) | Digimon registered for VS mode: stats, name, species (u8), techniques; bytes 0x20-0x23 of a record (unused by the original game) hold the species past 255 (see below) |

### Checksum

`createSavegameChecksum` is the plain unsigned byte sum of payload bytes 0x000..0x4E3 plus 0x500..0xEFF. Bytes
0x4E4..0x4FB (24 bytes, zero in every original save) and the checksum itself are not covered. A copy is valid when the
stored value equals the sum. Loading tries copy 0, then copy 1.

## Current single-block file (v5)

New Horizon saves occupy **one 8 KiB card block**, retaining the original header,
all 40 VS registrations and both complete payload copies. Existing one-block and
two-block saves can be loaded. Saving an existing two-block file leaves its
allocation and second block in place; moving it to a fresh slot creates a
one-block file. No save is deleted to resize it.

Each `RegisteredDigimon` has 28 unused bytes at record offsets `0x24..0x3F`.
Across 40 registrations these provide **1,120 bytes per payload copy**. The current
record list uses at most **850 bytes including framing**, leaving **270 bytes**
of margin even with every bit populated. No compression is necessary. Each
copy's extension is scattered in order through these bytes; no registration
field or payload offset changes. A compile-time bound includes every written
record and rejects future growth beyond the available space.

The payload version word is 5. Inside the scattered bytes is the same `DW4E`
record envelope described below, with version 4 and size 1,120. The link at
extension offset 8 is the payload's ordinary byte sum **excluding the 40 unused
ranges**, rather than its stored checksum, avoiding a checksum cycle. Its own
checksum covers the first 1,116 extension bytes. The payload's stored checksum
still uses the original algorithm over the complete payload, including the
scattered bytes, inverted for content the original executable cannot represent.

Saving writes copy 1 (`0x1100..0x1FFF`) first, then the header and copy 0
(`0x0000..0x10FF`), waiting for each write. Each copy contains its own extension:
an interrupted overwrite retains an intact old or new copy. The first save to a
new slot has no pre-existing backup until one copy has completed. Reads fetch block 1 first and only request a second block for legacy payloads.
All reads, including VS mode, unpack inline extensions before choosing a copy. The world
scratch staging area remains unchanged; no heap buffer or decompressor is added.

The original executable can read native-only payloads because the checksum and
all original field offsets remain unchanged. It cannot interpret Horizon records;
if it changes a payload, the extension link becomes stale and Horizon migrates
the original fields as before. Older Horizon executables do not understand
version 5 and report Data Error. Save editors must preserve the unused VS bytes
to retain Horizon data and recompute both checksums/link when changing fields.
`tools/dev/memory_card.py` decodes both inline and legacy extensions.

`python3 tools/dev/saves/measure.py` reports raw and compressed sizes for
controlled early/mid/late/full-Chart profiles derived from the release corpus.
The raw maximum is independent of progress and compression ratio.

## Legacy extended file (v2/v4)

A file written by earlier Horizon builds is two blocks (0x4000): the v1 file unchanged in the first 0x2000 bytes, then one
0x1000-byte extension per payload copy, copy 0's at file offset 0x2000 and copy 1's at 0x3000. Every offset of the v1
part is pinned by compile-time `SAVE_LAYOUT_CHECK`s, so the original executable and the VS mode see an ordinary v1 file.

- **Version word.** Payload bytes 0x4E4..0x4E7 hold `"DW2\0"` and 0x4E8 the layout version of the extension, inside the
  range the checksum skips. Zero (an original save) is version 0. 2 is the older fixed-struct extension (still read),
  4 is the legacy tagged list; 5 is the inline tagged list written today. A version the build does not know gives "Data Error" (card menu error 2) rather
  than a misread.
- **Legacy blocks.** Earlier builds created a two-block file (seven saves fit on a card). Two free blocks are required when
  creating a slot. A one-block legacy file grows to two blocks when a spare block is available (libmcrd cannot grow
  a file in place). Without room, saving reports the card-full error and leaves the existing file untouched. Earlier
  builds silently wrote only the original block when space ran out, losing extension-only progress.
- **Refusing the original executable.** When a save holds content the original game cannot represent (a partner species
  of 180 or more, an item id of 128 or more, a screen of 255 or more, or any extended raised/recruited bits), the v1
  checksum is stored bit-inverted. The original then shows "Data Error" instead of loading a partner it cannot draw; this build validates such a copy through
  its extension. A save with only original content keeps a correct v1 checksum and stays loadable by the original game.
- **Stale extensions.** If the original executable saves over an extended file it rewrites only the v1 part. Each
  extension stores the v1 checksum of the payload it was written with, so it no longer matches and the build reads the
  v1 data and migrates it again; the next save writes a valid extension.

### v4 extension

```
 0      "DW4E"          magic
 4      u16 version     4
 6      u16 size        bytes of the extension, checksum included
 8      i32 v1Checksum  checksum of the v1 payload saved with it
12      records         u16 tag, u16 length, then length bytes; little endian, no padding
        end record      tag 0, length 0
        zeros
size-4  i32 checksum    byte sum of everything before it
```

An extension counts only when magic, its own checksum and its copy of the v1 checksum all match.

### Records

`include/dw/save_tags.h` (added by patch 0129) is the registry.

| Tag | Content | Patch |
|---|---|---|
| 0x0001 | i16 current screen, i16 previous screen; authoritative, the v1 bytes hold the low byte | 0129 |
| 0x0002 | i16[n] inventory item ids, -1 = empty | 0129 (16-bit items: 0018) |
| 0x0003 | i32 partner species | 0129 |
| 0x0004 | u16[n] script registers w0.. (w0..w15 are saved, the rest are scratch) | 0129 |
| 0x0005 | i16[n] species of the VS-mode registered Digimon (kept for reading tools; the whole species since `Register-a-species-past-255-for-battle-mode-as-itsel.patch`) | 0129 |
| 0x0006 | i16[n] screens of the poop piles, -1 = none; authoritative since screens beyond 255 (a pile on screen 255+ is 0xFF in the v1 bytes) | 0129, 0146 |
| 0x0007 | bit array: species raised | 0129 |
| 0x0008 | bit array: species recruited | 0129 |
| 0x0009 | u8[n] OPTIONS bytes, layout in [../mods/options.md](../mods/options.md); a shorter record leaves the later options at their defaults | 0167 and later |
| 0x000A | i16 species, i16 vanilla species: NEW DIGIMON off turned the loaded partner from the first into the second; loading with the option on turns it back | 0182 |
| 0x000B | `{i16 screen, u8 tileX, u8 tileY}[64]`: ground item spots picked up today (screen -1 = empty), forgotten at midnight | 0230 |
| 0x8001, 0x8002 | reserved in the registry for required story-state records; not written by this patch series | |

### Reading rules

- A **known** record is copied as far as both sides have room, `min(length, what the build holds)`. What it does not
  cover keeps the value the v1 part or the defaults gave it (a shorter bit array leaves the rest 0; fewer inventory
  slots leave the others as v1 had them). Surplus elements are dropped.
- An **unknown** record is skipped by its length.
- A **missing** record changes nothing.
- An unknown record with **bit 15** of its tag set (a *required* record) makes the file unreadable: "Data Error" rather
  than loading without what it holds.

### Compatibility rules

1. A tag number is never reused and never changes meaning. If a record's element type changes (an id growing from 16
   to 32 bits), it gets a new tag; a writer may write both while older builds exist.
2. A record may only grow at its end.
3. New state that must survive goes into a new record, not into the v1 part. It is optional unless losing it would be
   wrong.
4. A build writes layout 5 and reads layouts 1, 2 and 4. A save moves forward when the game saves
   it.

### Loading a v1 save

A version-0 payload is migrated in place: the u8 ids are widened (0xFF item = empty, 0xFF screen = none), and from then on
the extension's records are authoritative. Original ids keep their numbers in this build, so nothing is renumbered.

## Writing and reading the file

- **Where the extension lives.** `SAVE_FILE` (resident) holds only the v1 file, as in the original, because the VS
  registrations live there between card operations. The two extensions are staged at `SAVE_EXT_ADDR` 0x8004E000
  (`SAVE_EXT_MAX` 0x4000, `memmap.h`) in the world scratch, which is free whenever the card menu runs (patches 0092,
  0093); see [memory.md](memory.md) for what that area must stay clear of.
- **Legacy copy order (patch 0096).** An extended file is written and read in four parts, each waited for: copy 1's payload
  (0x1100..0x1FFF), copy 1's extension (0x3000), then the header with copy 0's payload (0x0000..0x10FF), then copy 0's
  extension (0x2000). A write that stops anywhere leaves one whole valid copy; copy 1 goes first so a file that has
  just grown from one block keeps its old copy 0 until the last part. A one-block file is one part.
- **Choosing a copy.** `pickSaveCopy` (Continue, VS mode) takes the first copy whose extension links, then one that is
  valid without it (a stale extension).
- **Errors.** A part that does not start, or a libmcrd code beyond the message table, is reported as error 1 ("Not
  Inserted") so the message index stays in range.
- **The game-clear save** waits for the ending's sound bank to finish loading before it writes, because that bank is
  staged in the area just below the extension.

## What loading leaves out

- **Absent content (patches 0114, 0115).** A species, item or technique the build does not have keeps its id but has an
  empty row. After `loadSaveCopy`, `dropAbsentSaveContent` turns a partner of an absent species into the first
  reincarnation baby that exists (stats and name kept; equipped techniques and learned bits cleared, since they were
  the old species'), removes absent items from the bag, unequips absent techniques and clears their learned bits.
  `dropAbsentRegistered` does the same for the VS registrations and the item keeper's stock; a registration whose
  `wideId` names a species the build lacks fights as the original kept in its byte.
- **Registrations past species 255.** The save machine writes a species of 256 or more as the original it is based on
  in the record's byte (`getOriginalType`, the species file's `effects_like`) and as itself in `wideId` (record bytes
  0x20-0x21) with `wideCheck` (0x22, a copy of the byte) and `wideTag` (0x23, 0xD7). The original game and older builds
  read the byte; a build with `registeredSpecies()` reads `wideId` when the tag and the copy match, so a slot an older
  build registers over again is read by its new byte. A record written before this field (v0.0.5 and earlier) has
  only the stand-in and keeps it until the partner is registered again. The battle mode reads records as they were
  registered, whatever NEW DIGIMON says: with it off the partner is already its vanilla counterpart when it registers.
- **NEW DIGIMON off (patch 0182).** A partner of a new species becomes its species file's vanilla counterpart (stats,
  care and age kept; techniques re-slotted, else its first learned one; its own finisher), and record 0x000A remembers
  the swap. Raised and recruited flags stay. See [../mods/species.md](../mods/species.md) and
  [../mods/options.md](../mods/options.md).

## Card formats and recovery

Horizon writes one game file, `BASLUS-01032DMR<n>`. Legacy two-block saves link both blocks through the card directory; new saves hold both extensions inline in one block. There is no
second companion file. A raw 128 KiB `.mcr` and `.mcd` use the same card layout; changing the filename suffix neither
adds nor removes extension data. Every partial write waits for `MemCardSync` before the next begins. Per-game card
selection and when an emulator flushes its card image to disk are emulator settings, outside the game file format.
The [official ePSXe configuration guide](https://www.epsxe.com/android/memcard.html) documents separate file selections
for the two card ports and distinguishes memory-card saves from emulator states.

If history or recruits disappear after Continue:

1. Back up the complete card image before saving again. Check that the emulator selected the same card and slot;
   per-game card settings can select a different image from the global card paths. Let the game finish saving,
   then close the emulator normally so pending card writes reach disk.
2. Inspect the file's directory size and both blocks, not only its icon/header. Keep both blocks when copying a legacy save
   through a card manager. New v5 saves carry all extensions inside their first block.
3. Restore a complete earlier card backup if the extension is missing or overwritten. A legacy save with its extension missing cannot
   reconstruct which imported species were raised or recruited. If still running with the correct progress in RAM,
   free a card block and save through the game before resetting; do not overwrite the only backup. An earlier emulator
   state may also contain the missing progress: load it with the same build that created it and make a complete
   in-game save on a card with enough space, then boot the updated build from that card. Do not load the old state
   directly into a different build.
4. The new writer refuses to discard the extension and protects extended history/recruits with the inverted payload
   checksum even when the current partner is native. If both extensions of such a save are damaged, Continue reports
   Data Error instead of loading empty extended flags. Old saves remain readable, including earlier one-block saves;
   the next successful save preserves the progress they still contain.

A missing extension alone does not explain loss of native raised triggers. Without the failing card, an entirely
empty Chart cannot be attributed to ePSXe or to card format solely from a screenshot.

## The options copy in the card header

Patch 0193 writes a copy of the `SAVE_TAG_OPTIONS` bytes into the card header's PocketStation bytes (file 0x50..0x5F; a
PocketStation looks for its own magic there, which this does not match), so the title can show and apply a save's
options from the same 0x80-byte header read the slot list makes:

| Offset | Field |
|---|---|
| 0x50 | `"O"` |
| 0x51 | bits 0–4: count of option bytes that follow (at most 12); bit 7: CHEATS; bits 6 and 5: reserved, ignored on load and cleared on write |
| 0x52 | u16 save number: one past the highest number seen on the cards (`MOD_SAVE_NUMBER`), so the newest save has the highest |
| 0x54 | u8[count] the options bytes |

Saved-options bytes 1 and 3 (header offsets 0x55 and 0x57) are reserved.
Their values are ignored when loading; new saves write 1 to both. The field
digital clock, care HUD and status panels are permanent. Byte 13's former
inverted enemy-style/brief flags are ignored and written as zero. All other byte
positions stay unchanged.

Patch 0276 extended record 0x0009 to 14 bytes. Byte 12 retains the Cheats
flags. Byte 13 and header bits 6/5 formerly selected enemy-bar style and brief
display; they are now reserved. The patcher preserves old saved bytes, and the
runtime ignores these choices. No save version or required tag changes.

The extension's record stays what a Continue applies; the header copy is for display and for the boot options. At boot
(patch 0205, `modBootOptions`) the card slots are read before the title so the title screen is already in the newest
save's language and font.

## Original bug fixed

Patch 0050: the save title's name fields are cleared before a name is copied into them. The original copied over the
previous contents, so a short tamer name could show the tail of a longer one left from the default.

## Diagnosing missing Chart history

Native raised flags use the original payload's triggers (`RAISED_TRIGGER`), while
species without a native trigger use extension tag `0x0007`. Losing or rejecting
the extension can therefore remove imported history without removing native
history. Check both copies' payload checksums, extension checksums and linked
payload checksums before attributing an empty chart to an emulator. Also check
the selected card and save slot: a valid older save is still valid data.

`tools/dev/playtest/chart_card_roundtrip.py` marks native and imported history
and extended recruit flags, saves through the game's card menu, moves the extension
block to a nonadjacent free block in a disposable raw 128 KiB `.mcr` image, and Continues from a fresh
boot. It checks history and recruit bits and records all five Chart tabs before
and after, waiting for each page's icon reads to finish before capturing it.
This exercises the raw card and its directory chain; it does not emulate ePSXe's
CPU, BIOS or card timing.

```sh
python3 tools/dev/playtest/chart_card_roundtrip.py build/NAME.cue \
  --exe build/NAME/exe/SLUS_010.32 --out build/chart-card-proof
```

The capacity and interruption proofs execute the prepared C implementation and
boot disposable raw-card snapshots. The emulator test starts from an original
one-block save, fills the card completely, saves marked history/recruits and
reloads `.mcd` and `.mcr` copies. It also loads an old two-block save, migrates it
and checks its retained allocation.

```sh
python3 tools/dev/saves/capacity.py build/decomp-dev
python3 tools/dev/saves/inline.py build/decomp-dev
python3 tools/dev/playtest/inline_card_roundtrip.py build/NAME.cue \
  --exe build/NAME/exe/SLUS_010.32 --legacy-card build/states/original.mcd \
  --out build/save-inline-proof
python3 tools/dev/playtest/inline_power_cut.py build/NAME.cue \
  --exe build/NAME/exe/SLUS_010.32 --card build/save-inline-proof/written.mcd \
  --out build/save-live-cut
```

The live-cut test pauses the real game at its second `MemCardWriteFile`, after
copy 1 has synchronized. It kills that disposable emulator, checks that the disk
image did not change during shutdown, and cold-loads the resulting raw `.mcr`.
The old and new copies are checked independently before the reload.

## Related

- [ids.md](ids.md): which ids grew and what the v1 bytes keep.
- [../mods/options.md](../mods/options.md): the OPTIONS record and when a Continue applies it.
- [../developing.md](../developing.md): emulator tests, including card images for save tests; `tools/dev/memory_card.py` reads and
  edits card images, `tools/dev/saves/` cuts a save's writes at every point.

## Every release's save

`tools/dev/saves/corpus/` is an append-only corpus: a 128 KB card and JSON manifest for each release, starting with
20261027 (`d2796814`, the package in `build/web-release`). Earlier release cards have not been reconstructed; the older
format migration tests above remain separate. Never regenerate an older fixture with a newer executable.

Each manifest records the release, disc SHA-1, card SHA-1, tag numbers and names, decoded file state, and state read from
RAM after a fresh boot and Continue. Story flags and variables are recorded by **mod and name**, together with their lock
slot and value. A slot renumbering therefore fails even when two slots happen to hold the same value. New names and tags
may be appended. The fixtures exercise WTIF on a new screen, an imported partner with distinctive stats, city recruits,
items in the inventory and bank, bits, non-default options and a VS registration. These are controlled regression fixtures:
state is prepared with emulator RAM writes and the roster shortcut, then written by the release's own save code.

Cards are committed after `mcd.py strip` clears the save title, icon palette and all three icon frames, removes other
files and clears their blocks. The options in the unused PocketStation header bytes stay intact. Those cosmetic bytes
are outside the payload checksums; a fresh Continue from the stripped card is required before acceptance. Unstripped
cards, screenshots and resaved output stay under ignored `build/`. No game art is added to the repository.

```sh
python3 tools/dev/saves/releases.py check
python3 tools/dev/saves/releases.py emu build/wtif.cue --exe build/wtif/exe/SLUS_010.32
```

The file check needs only Python's standard library, the cards and the source tree. The tag registry comes from the
tracked patch series, rather than an arbitrary developer's decomp build (`--tags HEADER` selects a specific header).
`--story DIR` selects a scratch story tree for testing locks. Empty corpora fail. The emulator check needs PCSX-Redux as
in [the emulator guide](../developing.md), the disc's executable and its `.elf.map`. It uses a private home in `build/`,
a separate port (default 38231), ordinary 2 MB RAM, and stops its emulator even on failure. It boots from cards, never
save states. It compares screen, partner, stats, inventory, bank, bits, options, roster and named story state, then saves
again through Jijimon and parses the result with `mcd.py`. Poop, picked ground spots and scratch script registers may
change during that trip; all other old records and the named story state must survive. Original cards are never edited.

After checking the existing corpus, add the new release's card with `releases.py add` (see Making a release in
[patcher.md](../patcher.md)). That command also verifies the candidate's stripped-card Continue and round trip before
copying it into the corpus, and refuses to overwrite an existing release.

## Daily ground pickups

Patch 0265 assigns stable IDs from `content/ground-items.json` and remembers them
in a 128-byte daily bitset. Save tag `0x000C` preserves this bitset; older saves
remain readable. The bitset covers all 499 authored pickup locations, including
266 in the extended story, without evicting earlier pickups on a busy day. A row's optional `at` is the tile the spawn really
lies on that screen when it is not the script's own (a script shared with an original screen); its ID and key stay the
script's tile, so moving a spot never changes a save.

## Technique layout A

Required tag `0x8003` (`SAVE_TAG_TECHNIQUE_LAYOUT`) contains one byte, `1`. It versions the equipped animation-slot interpretation introduced by [technique coherence A](../proposals/technique-coherence.md). Missing means the pre-A layout, including original, legacy and inline saves. New saves, including default saves, write layout 1; later Continues skip migration. A malformed or unknown layout is refused. The required bit makes earlier readers refuse an unsafe downgrade.

On load, after species/options extension records are applied and before absent-content cleanup or NEW DIGIMON conversion, the eleven old slot arrays resolve equipped ordinary slots into old technique IDs. Surviving compatible known IDs retain their slots. Removed selections choose an already-known compatible ordinary replacement, first preferring the same element and then the closest power; lowest species slot breaks ties. Fallbacks avoid already equipped selections. With no candidate the selection becomes empty. The finisher index and all learned words remain unchanged. Both the active partner and saved-state equipment mirrors receive the result. Evolution/rebirth continue to use their normal current-data paths.

The migrator, old arrays and save builder live in MENU. To retain its 27-sector allocation and the field heap, title-only Options rendering and setters share the existing EVL title tail with the language picker. Both overlays are already loaded before title Options; field saves load MENU alone. No mutable revision state is added. Resident size and all screen margins are measured by the full build. Five extension bytes are added; inline packing and its capacity checks remain authoritative. `tools/test_technique_coherence.py` compiles the production C helper and exercises every former ordinary slot with full, partial and empty learned libraries.

Registered VS fighters also save animation slots. Continue migrates their equipment before a new save receives the layout marker; the direct VS card loader applies the same migration to legacy entries. Because registrations contain no learned library, removed or incompatible selections become empty and surviving selections retain their identity. Older direct VS loaders did not honor required extension tags; do not use A registrations with an older engine.

BlackKingNumemon has one unavoidable legacy exception. Released v0.0.7 used Battle IDs in indices 8 and 10–13 and no index 15; the unversioned audit baseline had Ice IDs there. Neither format identifies that data revision, and a complete learned library cannot distinguish them. Unmarked saves therefore clear those six ambiguous equipped indices (8, 10, 11, 12, 13, 15), including registrations, instead of guessing. Common Filth selections and finisher index 14 survive; every learned bit remains. The JSON arrays still match A exactly. Once a save has layout 1, its current Ice selections survive later Continues. Host tests cover both historical arrays with a full 128-bit library.
