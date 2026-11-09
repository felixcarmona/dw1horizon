# Memory-card progress after v0.0.6 → v0.0.7

The reported reset is **not reproduced with a complete v0.0.6 two-block save**.
There is a reproduced older writer defect that can produce the reported loss
before an upgrade: saving over a one-block file on a full card reports success
without writing the extension. The current inline writer already fixes that
defect. The reporter's card was not supplied, so this does not establish which
condition affected that player. Hawkmon remaining absent after the loss is
still unconfirmed.

## Source and release checks

The published USA discs were used, with European World 2003 as the model source:

| Disc | Published image SHA-1 |
|---|---|
| v0.0.6 | `bc729710bdc57f23fc8f4f0754951aba5ae93cc2` |
| v0.0.7 | `5a83f998b9efe45603b6573043d9c275cac10588` |

v0.0.6 was reconstructed from its release package and checked against that
package's image hash. The prepared v0.0.6 MENU overlay matches the published
one byte for byte; the executable's first difference is in patched data at
file offset `0x7db70`, after the code. Its rebuilt ELF supplies the emulator
symbols. No replacement save implementation was used to create the cards.

Both releases write tagged **layout 4** with two blocks. Layout 5 and the
one-block inline format arrived later; they cannot explain a v0.0.6 → v0.0.7
layout mismatch. Applying each tag's patch series shows:

- `loadSaveCopy`, `isExtensionValid`, `applyRecords`, `prepareSaveFile`,
  `saveFileStart`, `writeSaveFile`, `pickSaveCopy` and `needsNewExecutable` are
  identical between the two releases.
- `loadSavegame` adds Chinese nickname detection, without changing the saved
  script state, history or recruited records.
- Species IDs, the 1,024-bit history and recruit arrays, tags `0x0007` and
  `0x0008`, the City resident list and the story `save.lock` retain their meanings.
  The mod's 65 named flags and six named variables keep their slots.
- Native history lives in the original payload's trigger bits. Imported history
  and high recruit flags live in the extension. Hawkmon is species 184;
  scripts address its recruited bit as `0x80b8`.
- Hawkmon's two placement sources are unchanged: unrecruited at Great Canyon
  Entrance (36), recruited at Birdra Transport (207), with Extended Story on.

## Emulator evidence

PCSX-Redux cold boots and memory-card Continues use original 2 MB RAM. The
source cards are copied before use. No emulator state crosses versions.

The October corpus card loads and resaves on the published v0.0.7 disc with its
history, recruit bits and named story state intact. A new corpus card,
[`20261105-v0.0.6.json`](../../tools/dev/saves/corpus/20261105-v0.0.6.json),
was written by the published v0.0.6 game, stripped of title/icon art and
cold-loaded and resaved on that same release before acceptance. It retains an
imported Omnimon on screen 300, distinctive inventory/stats/options, VS data,
named story state and marked history/recruits including Hawkmon. Its manifest
discloses the controlled RAM setup.

The [native-city variant](../../tools/dev/saves/corpus/20261105-v0.0.6-native-city.json)
was also written and cold-loaded by v0.0.6. It has a native Agumon in Jijimon's
house (both screen fields 218), all 20 high City resident bits marked, and an
ordinary payload checksum. The Agumon was prepared through the game's evolution
state machine, followed by the native save flow in Cheats.

Both complete v0.0.6 cards load on v0.0.7 and current main with all 128 bytes of
each extended bitset and the native history/recruit flags intact. Hawkmon is
absent from screen 36 and present on screen 207. Native saves and another cold
Continue preserve that progress; v0.0.7 writes layout 4 and main writes layout 5.
A raw `.mcr` copy of the imported fixture, with its directory chain changed from
blocks 1 → 2 to 1 → 15, also loads correctly on v0.0.7.

On a separate v0.0.7 cold boot, calls to the actual `hasDigimonRaised` return 1
for marked species 180, 184, 373, 461 and 476; `isDigimonRecruited` returns 1
for all 20 high City residents. The existing `chart_card_roundtrip.chart` helper
captures all five Chart tabs. The inspected Rookie and Mega pages show their
retained portraits (3/45 and 3/54), rather than empty history. These screenshots
and the video stay in ignored build output.

A controlled native-city copy with both NEW DIGIMON and EXTENDED STORY saved OFF
retains every marked history/recruit bit on v0.0.7, but Hawkmon appears at neither
site. The added chart entries are hidden with NEW DIGIMON off. These options
can change what a player sees without deleting progress; they do not establish
that the reporter changed either option.

The test also visits Jijimon's house. A pending root-memory event can legitimately
recruit SkullGreymon there. The harness compares the written card with the state
immediately before saving and permits additional recruits from those story
events after another Continue; it still rejects lost progress. The initial load
comparison remains exact.

## Reproduced old failure

Start with an original one-block save and fill a private card with dummy files
until all 15 blocks are occupied. On v0.0.6, mark extended history/recruits in
RAM, including Hawkmon, and save through the native card menu in Cheats:

1. The game reports success, retains an 8,192-byte allocation and writes layout 4.
2. Neither extension is present. The stored payload checksum is ordinary, so
   the old loader accepts the file.
3. A cold Continue on v0.0.6 itself clears the marked extended history/recruits;
   native history survives. The same card loads with those bits absent on
   v0.0.7 and main.
4. Hawkmon reappears on screen 36 and is absent from 207. This reproduces the
   loss, but contradicts the report's additional missing-Hawkmon observation.

The actual C from **both** old tags also reproduces the writer decision in a
host shim: `writeSaveFile` cannot grow the file, changes an inverted checksum
back to the ordinary checksum, and calls the one-block writer successfully.
Creating a new slot with only one free block has a similar fallback in the
old source; that separate creation path was not played in this investigation.

Current main saves the same marked state on a full card in one block using
layout 5. A fresh Continue retains it, including Hawkmon's city placement.
This is the existing fix in `require-complete-card-saves.patch` and
`Store-complete-Horizon-saves-in-one-memory-card-block.patch`, rather than a new
migration added here.

Learned moves are in the original payload: the original card and the incomplete
v0.0.6 output both retain `04000000000000000000000000000000`. That field
surviving while the extension-only bitsets disappear is consistent with this
failure. Equipment also lives in the original payload, but a changed species
moveset can change the interpretation of its saved slot numbers. Main's later
technique-layout migration intentionally remaps equipment; neither observation
alone proves that the recruit/history extension was loaded.

Retaining only the first block of a valid old two-block save was tested
separately. The native-city variant loads on v0.0.7 but loses the missing
extension's bits; the imported-partner/screen-300 variant is refused with Data
Error (2). Native partners on native screens can have ordinary checksums even
with extended history/recruits; imported partners or new screens normally
require a valid extension. This is **not evidence that a particular emulator
truncated the reporter's card**. A fragmented raw card is a directory chain,
not two necessarily adjacent blocks; a `.mcd`/`.mcr` suffix does not identify the
emulator that wrote it.

## Repeating the checks

With a disc and its matching executable/ELF/map:

```sh
python3 tools/dev/saves/releases.py check
python3 tools/dev/playtest/save_upgrade.py DISC.cue --exe EXE \
  --card tools/dev/saves/corpus/20261105-v0.0.6.mcd \
  --roundtrip --out build/save-upgrade
python3 tools/dev/playtest/legacy_save_capacity.py OLD.cue --exe OLD_EXE \
  --legacy-card build/states/original.mcd --write --expect-loss \
  --out build/old-full-card
python3 tools/dev/playtest/legacy_save_capacity.py MAIN.cue --exe MAIN_EXE \
  --legacy-card build/states/original.mcd --write \
  --out build/main-full-card
```

The original card must be an actual one-block save; it is not committed here.
The full-card harness writes controlled markers before invoking the game's
writer and records JSON plus Hawkmon screenshots. The ordinary upgrade harness
checks the entire saved bitsets, native flags, both placements and optional
resave/Continue. Neither edits the source card.

The English-only main build passed the existing heap gates (screen 207 margin
12,800 B for this language subset); it is a test build, not a replacement for
the full release's 640 B margin. Offline validation: 149 selftest checks pass,
none skipped; 91 focused tests pass, with the final save/corpus subset rerun
after adding both cards. The full patch series applies, all three corpus cards
pass file checks, and the docs have no dead references. OpenCV was installed
in a private test environment after the first selftest's sole failure was a
missing `cv2` import; the final run has no failures.

## Recovery and limits

No new migration is justified by these results. A complete extension loads;
the reproduced incomplete save contains no record of which imported species
were raised or recruited. Guessing those bits would invent player progress.
Recovery needs an older intact card backup, or inspection of a supplied card
for another intact payload/extension pair. Current main prevents future loss
on full cards, but cannot reconstruct bytes that an old writer never saved.

The report has no attached card, screenshot or video. The player's exact
before/after cards, emulator/version, card format/export method, free-block
count and saved options remain unknown. These tests do not emulate every
older emulator's CPU/BIOS/card timing, and are not physical-console tests.
No game C, main-executable data or heap allocation changes in this investigation.
