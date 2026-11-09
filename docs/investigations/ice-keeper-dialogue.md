# Ice Sanctuary keeper dialogue

The v0.0.7 Portuguese report, message `1569151285201207356`, describes the
second Angemon closing the game. It has no attachment or save. The confirmed
fault occurs after opening the Wall of Hearts: talking to the Angemon who
remains on screen 311 reaches an invalid speaker-name lookup.

## Cause

`arcs/vault/wall-of-hearts.py` places Angemon on screen 310. Choosing to open
the wall sets `root3`, unrecruits Angemon and warps to 311. The thaw narration
finishes normally. `arcs/vault/melted-wall.py` then lets the keeper speak his
own line and jump to script 211, section 8, the city Record Keeper's hints.

Those shared hints explicitly name script speaker 6. The Sanctuary originally
placed its sole actor in physical slot 0 with the default script id 5. Speaker
6 was absent. `getSpeakerName` calls `scriptIdToEntityId` and dereferences its
result without an absent-speaker guard. This is an invalid actor reference,
not a second model load inside dialogue or an absent-NPC unload. Angemon's
species/model id is the native 20 and does not cross a byte-width boundary.

Original-2-MB PCSX-Redux, interpreter/debugger, Portuguese v0.0.7:

- Walk along the aisle of 310, talk, choose the first answer and finish the thaw.
- Walk along the aisle of 311 and talk. The keeper's first line uses speaker 5.
- The shared hints request speaker 6 with only NPC slot 0 present.
- The emulator reports `Unaligned address 0xffffffff in LW from 0x800fe97c`
  and `First chance exception: LoadAddressError from 0x800fe97c`; execution
  pauses at the exception vector `0x80000080`.

Initial fixture setup uses a native Agumon card, recruited Angemon and a normal
warp to 310. Walking, choices, both screen transitions and conversations use
pad input. Teleporting directly beside an NPC without panning the camera can
leave it off screen and disable interaction; the reproduction walks from the
arrival point instead.

## Fix

Keep the keeper in physical slot 0 and explicitly give it script id/talk
section 6. The Python story frontend now exposes the backend's existing
`place(..., section: ...)` support as `npc(..., section=...)` on new screens,
with range and duplicate-id checks. Its own greeting, the map's script id and
the shared library now agree. No engine patch is needed.

The built VALT02.MAP has the same 43,428 bytes and one Angemon record; compared
with v0.0.7, exactly one byte changes, script id 5 to 6. No model, allocation,
saved flag, text key or resident executable source changes.

## Checks

`tools/test_dws_safety.py` checks explicit talk ids, duplicate ids and invalid
ranges. `test/test_ice_keeper.py` compiles the actual caller and hint library
and checks that every shared NPC speaker exists in the caller. Removing the
explicit section makes this regression fail.

`tools/dev/playtest/ice_keeper.py` boots a card on a specified 2 MB disc, walks
to both Angemons, advances the thaw and exercises both introductory and repeat
hints. `--expect-crash` checks the old exception; `--check-decline` also checks
the alternate wall choice. Build artifacts, screenshots and JSON stay under
`build/`.

The English/Portuguese test disc passes the actual-archive heap gate: all 320
setups fit, `main_BSS_END=0x801cc280`, heap 195,696 bytes, screen 207 margin
10,976 bytes. These are the two-language test layout's figures, not the full
release layout's 640-byte margin. This change adds zero resident engine bytes
and leaves its heap size unchanged.

The fixed disc was exercised in Portuguese and English on 2 MB PCSX-Redux:
opening the wall, the full thaw, the keeper's introduction, repeat hints and
walking afterward all pass. English also exercises declining the wall choice
before accepting it. The same probe's `--expect-crash` run reproduces the fault
on Portuguese v0.0.7. `{player}` expansion also uses `getSpeakerName(253)`;
the probe distinguishes that special name from NPC speaker ids.

The full self-test initially used a copied build fixture: its species lint
referenced that fixture's old model paths and its balance check used older
portrait coordinates. Both pass against the fresh build (48/48 species checks;
all 126 balance tables identical). The NPC-original audit is likewise run
against the fresh image. Compiler tests pass (196, two internal skips), along
with 13 safety tests, 43 island tests, type-stub checks and patch-series
application. No original-console hardware or DuckStation check was performed;
the full release language layout was not rebuilt.
