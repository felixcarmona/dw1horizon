# Root Clearing: Spanish caption and battle return

Report 1569111669790081034, v0.0.7. The attachment shows the English loading
caption "Root Clearing". The separate description says that, after a victory,
the tamer appeared stuck while pad input moved the camera; another fight
restored normal behavior. There is no capture or save of that second symptom.

## Caption cause and existing fix

In v0.0.7, `tools/screens.py` encoded the screen JSON's `caption` directly with
Latin-1. Its `build_files` entry point did not receive a language or consult a
text bank. Screen 314 therefore shipped `Root Clearing` in SCRN.DAT regardless
of the selected language. This was a shared custom-screen routing omission,
not a missing Spanish translation of a native area-name slot.

Main already fixes this in `5319a195` (Translate area captions in every
language). `tools/derive/steps/screens.py` passes each bank's language into
`build_files`; `tools/localize/captions.py` resolves the text key and encodes
it into the existing 36-byte field. `invalidate-localized-screen-captions.patch`
invalidates both the sector and header caches when the language/font changes.
The title renderer uses `getScreenCaption`; Root Clearing needs no special
runtime string or resident table.

The current inventory has 70 native title slots sharing 68 names, plus 69
extended screen records sharing 26 captions. Five of those captions reuse
native area keys; 21 have custom caption keys. All nine languages pass the
missing/empty/English-placeholder audit (reviewed native proper names and
cognates are allowed). No additional untranslated title was found.
Chinese coverage here is offline; its existing 8 MB runtime requirement remains.

| Language | Root Clearing caption |
| --- | --- |
| English | Root Clearing |
| Spanish | Claro de las Raíces |
| Brazilian Portuguese | Clareira das Raízes |
| French | Clairière des racines |
| German | Wurzellichtung |
| Italian | Radura delle Radici |
| Japanese | 根の広場 |
| Catalan | Clariana de les Arrels |
| Simplified Chinese | 树根空地 |

`test_authored_captions_reach_screen_files` now exercises the real
`build_files` entry point for every authored screen and all nine languages.
It checks the encoded on-disc caption bytes, including screen 314, and verifies
that the rest of SCRN.DAT is identical between languages. Its small synthetic
MAPHEAD sections isolate caption routing; they are not a story playthrough.
Replacing localization with the old direct-English path causes eight failures,
one per translated language. The existing native-slot audit and compiled
screen-cache language-switch regression cover the other two title paths.

## Battle-return investigation

Root Clearing's two talk handlers call `fight`, then optionally give Meat.
They load no models inside the interaction and contain no custom camera or
movement commands. Its models are loaded during screen setup. Thus the known
second-LOAD_DIGIMON-in-a-talk hang does not describe these handlers.

The common START_BATTLE opcode returns from `startBattle`, then queues movement
slot 10 as a type-7 camera pan to the tamer (script entity 0xFD), unless trigger 1
selects the boss path. It yields until that movement completes. The normal
script cleanup re-enables movement and camera follow. This return-pan/script
handoff is a plausible place to investigate the described lasting failure;
that is a hypothesis, not a reproduced cause.

`c6ef50d9` changes the field-music and background-header disc reads on the way
back. It is already an ancestor of v0.0.7. That brief whole-picture stall is
not evidence of the reported persistent actor/camera mismatch. An unconditional
camera reset would mask the state that needs diagnosing and could interrupt
legitimate scripted pans, so this investigation adds no speculative engine fix.

`tools/dev/playtest/battle_return.py` provides a repeatable runtime probe:

```sh
DISPLAY=:187 python3 tools/dev/playtest/battle_return.py build/control.cue \
  --exe build/control/exe/SLUS_010.32 --out build/return-root \
  --screen 314 --language 1 --quick 1
DISPLAY=:187 python3 tools/dev/playtest/battle_return.py build/control.cue \
  --exe build/control/exe/SLUS_010.32 --out build/return-root-second \
  --screen 314 --language 1 --quick 1 --slot 1 --stay \
  --state build/return-root/returned.state
```

Use a checkpoint only with its exact disc. `--screen 0` selects the repeatable
Native Forest encounter; `--quick 0` checks the ordinary battle-start path.
The probe discloses its card/care/stat/learned-technique and approach writes.
Equipped moves are animation IDs, so it asks the real species mapping for
Spit Fire's slot before combat. Enemy HP and camera state are not written.
Acceptance requires an actual victory counter increment, free script/tamer
state, closed reward boxes, restored camera ownership, changing physical and
animation positions under Left/Right input, and native projected visibility
after each walk. Collision may block one direction; at least one must move.
`--walk-only --state FILE` rechecks a return checkpoint without another fight
or any fixture writes to the loaded game.
The JSON, screenshots and same-disc states stay under the requested output
folder. An actor that only appears stationary cannot pass on state flags alone.

## Runtime results

PCSX-Redux interpreter/debugger checks used original 2 MB RAM and native Agumon.
Five unforced victories passed the return, pad movement and visibility checks:

| Image / language | Screen | Quick battles | Result |
| --- | --- | --- | --- |
| v0.0.7 / Spanish | Root Clearing (314) | On | Passed |
| v0.0.7 / Spanish | Native Forest (0) | Off | Passed |
| Current engine / English | Native Forest (0) | On | Passed |
| Current engine / English | Native Forest (0), second NPC without reloading | On | Passed; victory count 1 → 2 |
| Current engine / English | Root Clearing (314) | On | Passed |

Two additional Root Clearing runs with quick battles off remained in combat
for a long time. To isolate the return path, the participating enemy's HP was
set to zero at battle ticks 5066 (v0.0.7) and 3673 (current engine). The normal
victory/reward/pan sequence then returned control in both. These are forced
victory controls, not natural-combat acceptance. Their exact writes are in the
local `forced-victory.json` sidecars.

An initial current-engine check stopped after a stationary Left step. Its
checkpoint still showed the last reward box closing, and the camera did not
move independently. Rechecking that exact return state after the box closed
gave an unchanged position against the left boundary and a 350-unit Right
step, with the tamer visible. This is not the reported lasting camera/actor
mismatch. The probe now waits for reward boxes and accepts a blocked direction
only when another direction actually moves the tamer.

The release-control image SHA-1 is `5a83f998b9efe45603b6573043d9c275cac10588`.
The current-engine English test image is `7fb2f79e5e10cd905596793e4711f7a33de5934b`:
its C sources match the applied series; an unrelated imported-model variant in
that image is not used by these native-species cases. These are isolated copies
of existing images, not a newly built nine-language release.

The persistent failure was not reproduced. The return-pan/movement handoff
remains a hypothesis; a frozen rendered transform despite changing physical
coordinates would instead point to animation/render restoration. The probe
records both positions to distinguish those cases. The player's exact partner,
save, battle ending and emulator settings are unavailable. Imported/tall
partners, the player's emulator, DuckStation and physical hardware were not
tested here. A capture or save of the stuck state is still needed to establish
the cause; no additional game fix is claimed for it.

Exact local artifacts and checks are recorded in the worktree's uncommitted
task report. This change contains developer tests and this record;
it changes no C, executable bytes, screen records, translations or heap size.
