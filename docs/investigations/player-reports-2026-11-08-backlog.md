# Player-report backlog: v0.0.7 controls and next-release fixes

This audit distinguishes existing 0.0.8 fixes from new regressions. The main baseline is
`a8505228`; the release control is the `v0.0.7` tag. Vanilla means the USA disc, SHA-1
`5611645da66183e30d11fb6c11a2784ff47e1fdb`. Runtime fixtures use PCSX-Redux with the
interpreter and debugger. They seed save data, quest state, starting stats or encounter
joins; the observations below distinguish real game execution from host checks and
forced cleanup.

## Replies for the players

1. **Portuguese Drowned Shore caption:** fixed in 0.0.8 (`5319a195`). The ferry
   destination uses the translated screen caption, “Costa Submersa”, and the
   same fix covers every supported language and both fonts.
2. **Agumon on the Amida Forest rocks:** fixed in 0.0.8 (`ad5c0183`). The original
   map left parts of the visible rocks walkable. The reviewed collision edits
   block those rock edges while keeping the trial paths open.
3. **Aqua Magic above 1000 Offense:** not reproduced in field or tournament
   battles. The release already raises 1000 to 1070 and 1500 to 1605, with a
   9999 ceiling. A separate versus-mode 999 clamp is fixed in 0.0.8
   (`ad5c0183`); it does not explain a field-battle report.
4. **BlueMeramon repeats its line:** fixed in 0.0.8 (`ad5c0183`). The second
   BlueMeramon on Back Dimension screen 227 now starts its fight in both story
   modes. Vanilla and v0.0.7's original-story version omitted that fight;
   v0.0.7's extended-story override already started it.
5. **Mt. Infinity triple-battle crash:** not reproduced in PCSX-Redux.
   The entrance encounter is checked with three actual participants, both battle-start
   settings, native/imported partners and 2 MB/8 MB RAM. ePSXe and physical hardware remain untested.
6. **Bonus Try:** works in the checked release and main cases. It remains a
   separate training-menu choice after normal or x5 training. A miss awards
   half the normal gains; the other slot payouts and reel assistance are
   original game rules. Both builds pass all 16 exercise/location variants after normal and x5
   training, with a separate Bonus Try after each.

## Caption path and collision controls

The Whamon offer in `story/mods/what-the-island-forgot/arcs/shore/city-dock.py` warps to
screen 309, entry 0. Its
`story/mods/what-the-island-forgot/screens/309-drowned-shore.json` caption is now
encoded from the selected language's `screen.caption.drowned_shore` key into SCRN.DAT.
Both the current and original font copies contain the localized bytes in all nine
languages. Header cache invalidation in `modScreenFileChanged` prevents a previous
language's caption surviving a switch. The native caption renderer reads this same
record; the ferry has no separate English caption string.

`tools/dev/playtest/shore_captions.py` runs the actual city section 55, selects the
shore offer, and captures its caption. The section must be a regular interaction
(`event=0`): the engine intentionally suppresses a warp's caption for event sections.
Its `--before --languages pt-br` control reproduces “Drowned Shore” on v0.0.7. All nine
actual ferry arrivals pass on main: eight languages at 2 MB, plus Chinese at 8 MB. This
supplements the audit of all 18 SCRN banks.

The rock screenshots identify screen 17, TROP06, including the southern rocks.
`tools/maps/tilegrid.py` projects the original collision cells onto the disc's
background art. The south-east foot cells `(61,81)` and `(61,82)` have value 54
(walkable trial triggers) in vanilla and v0.0.7; main sets them to 128 (wall). These are
among the 26 reviewed cells in `content/maps/TROP06.json` added by `ad5c0183`, rather
than a new map change. Runtime controls load and read those same collision values from
vanilla, v0.0.7 and main, and record pad walking near the edge. The existing collision
regression also checks unchanged arrivals/camera/entities and reachability of all three
trial goals and the exit.

## Aqua Magic and BlueMeramon

Aqua Magic is technique 21. Its data row adds 7% Offense, 8% Defense and 7% Speed. Both
release and current `BTL_applyBuffMove` / `STD_applyBuffMove` use 32-bit multiplication
and `addWithLimit(..., STAT_CAP)`. The helper sums in 32 bits, then clamps at 9999;
supported values cannot overflow either operation. Calling the actual loaded release
overlays with the partner instance gives:

| Starting stat | Offense | Defense | Speed |
|---:|---:|---:|---:|
| 999 | 1068 | 1078 | 1068 |
| 1000 | 1070 | 1080 | 1070 |
| 1500 | 1605 | 1620 | 1605 |
| 9000 | 9630 | 9720 | 9630 |
| 9999 | 9999 | 9999 | 9999 |

These are function-level runtime probes, not claims of playing every cast's animation.
Vanilla's loaded field/tournament functions give 900 → 963/972/963. The host regression
compiles the actual field, tournament and versus functions and checks all five
configured buffs, repeated casts and cap boundaries. Main passes 4320 checks. The
release fails only the versus cases (1008 checks), as expected from its remaining 999
clamp. `--rules-root` selects the release's own formula encoder and data so a later
table layout cannot distort this control.

The BlueMeramon report is script 186, section 8, NPC slot 3 (species 104). Vanilla and
the release's original-story handler say the line and recruit, then return; neither
calls `startBattle`. The release's extended-story takeover does call it. `ad5c0183`
changes the base handler to `recruitable(...)` and removes the redundant takeover.
Lowering tests verify a battle in both story modes and the extended story's win guard
before recruitment. Runtime section probes observe `startBattle` directly; no battle
result is injected by that probe.

## Mt. Infinity and Bonus Try checks

The entrance is screen 166, MGEN01, with Vermilimon in slots 0/1/3 and Golemon (the
native Rockmon) in slots 2/4. The return portal from screen 167 enters it through
arrival 1; File City section 56 enters through arrival 0. `--city-entrance` selects the
latter route. Its authored maps, and the related MGEN04/MGEN05 encounters, were
inspected for spawn locations, equipped animation slots and arrival heights.
Vermilimon's equipped slots are 48/49/52/53; Golemon's are 47/49/50/51. The rebuilt
models and their equipped clips are checked against the vanilla control; optional unused
slots are not treated as missing battle animations. The final DIGI.DAT entries are
identical between release and main: 82,506 bytes for Vermilimon and 60,266 for Golemon.
All equipped clips are resident (no cold flags), decode to finite poses and have valid
bounded durations.

`tools/dev/playtest/infinity_portal.py` now records actual participants, heap
integrity/free blocks, tile window, execution state, battle-time stream opens and cold
reads. `--all-join` seeds only the join chance and requires three real participants;
visibility/collision and the three-enemy limit still execute native encounter code.
`--cleanup` zeros the participating enemies' HP only after at least 90 loaded battle
ticks; it proves loading, battle progress and return, not a complete unassisted combat
win. Natural-join controls and a complete triple-enemy win without HP cleanup are
retained separately. Complete, unassisted triple-battle wins pass on both the release
and main at 2 MB with Armageddemon and 9999 Offense. The release retains at least 41,448
bytes of free heap; main retains at least 40,360 bytes in that run. The field stream
must never reopen during combat, the tile window must stay fixed, and no cold clip read
may occur in combat.

The completed battle controls are:

| Build | RAM | Partner | Battle loading | Control |
|---|---|---|---|---|
| v0.0.7 | 2 MB | Agumon | normal and quick | Natural joins; two participants |
| v0.0.7 | 2 MB | Agumon | normal and quick | Three Vermilimon; cleanup after loaded progress |
| v0.0.7 | 2 MB | Armageddemon | quick | Three Vermilimon; complete win without HP cleanup |
| v0.0.7 | 8 MB | Armageddemon | quick | Three Vermilimon; cleanup after loaded progress |
| main | 2 MB | Agumon and Armageddemon | normal and quick | Four three-Vermilimon runs; cleanup after loaded progress |
| main | 8 MB | Armageddemon | normal and quick | Two three-Vermilimon runs; cleanup after loaded progress |
| main | 2 MB | Armageddemon | quick | Three Vermilimon; complete win without HP cleanup |

The six main cleanup runs retain at least 38,728 bytes of free heap. All sampled heaps
are intact, all battle-time stream-open/cold-read counts are zero, and each loaded
battle keeps a fixed tile window. The File City entrance also returns successfully on
release and main with two Golemon; it does not produce a third participant in these
fixtures and is kept separate from the triples. Authored arrival heights are zero. This
does not reproduce the reported ePSXe failure.

Bonus Try uses pstat 246 = 1. The x5 row writes 2, which `modBlockArm` consumes as a
normal session block; it neither starts nor removes the separate slot game.
`tools/dev/playtest/training_bonus.py` exercises the native menus, exercise setup, reel
stops, awards, tally and caller's completion. It checks Bonus Try after both normal and
x5 training at every gym. Starting stats/care are reset between runs to isolate payout
and state handling. A fixture must wait for the script's training-completion handshake
as well as free tamer control; repeatedly pressing Confirm during that return can select
another exercise at the same training spot and is not a Bonus Try defect.

On v0.0.7 and main, all 64 distinct matrix rows per build pass: 16 exercise/location
variants, normal and x5 sessions, each followed by a Bonus Try. This covers Green Gym,
Gear Savanna, Misty Trees, Beetle Land, Ice Sanctuary and Trash Mountain. Controlled
final stopped reels of 777 also exercise the native jackpot payout/tally: Green Gym HP
+1000, Beetle Land HP +1200 and Trash Mountain MP +1500. Those are forced payout tests,
not chance-based jackpot wins. The observed 5/20/40 payouts and assistance rules match
the vanilla implementation. The related entry in `docs/ideas.md` asks for a higher
chance of matching symbols; it is a balance proposal. This audit retains the native
odds. The separate MP x5 return-walk delay is already fixed in 0.0.8 by `208d0d83`; it
does not change Bonus Try selection or payouts.

Reproduction commands (use the matching executable beside its ELF/map):

```sh
python3 tools/dev/playtest/shore_captions.py DISC --exe EXE --out build/ferry
python3 tools/dev/playtest/shore_captions.py DISC --exe EXE --out build/ferry8 --ram8
python3 tools/dev/playtest/buff_caps_host.py build/decomp-dev
python3 tools/dev/playtest/infinity_portal.py DISC --exe EXE --out build/infinity \
  --all-join --cleanup --video-seconds 0 --species 3 407 --quick 0 1
python3 tools/dev/playtest/infinity_portal.py DISC --exe EXE --out build/infinity8 \
  --all-join --cleanup --video-seconds 0 --ram8 --species 407 --quick 0 1
python3 tools/dev/playtest/training_bonus.py DISC --exe EXE --out build/bonus
```

## Validation

- Full main build at `a8505228`: image SHA-1
  `eb3e34c0251a42274b8570cc29f8dba1af7733b3`.
- 30 targeted caption, collision and recruitment unit tests pass; main's
  compiled buff regression passes 4320 checks.
- Actual main ferry arrivals pass in all nine languages, supplemented by all
  18 final SCRN language/font banks. Release Portuguese reproduces English.
- Main's exact BlueMeramon section starts a fight in both story modes. Spanish
  release/main field and tournament buff values match the table above.
- All 64 distinct gym cases per build pass, plus the release's three controlled
  jackpot payouts and a fresh normal/x5/Bonus Try held-input control.
- All six main triple-battle loading/progress/return cases pass. Complete wins
  without HP cleanup pass at 2 MB on release and main. The battle table above
  records the additional natural-join and entrance controls.
- Both main heap gates pass: 186,768 bytes of heap; all 320 actual-archive
  screen setups fit; the tightest setup (screen 207) retains 2,048 bytes.
- MENU/title storage passes all nine language layouts: MENU is 55,172 bytes,
  leaving 124 bytes inside 27 sectors, with identical title bytes across
  language reloads.

Interrupted processes and Redux API-timeout attempts were retained separately and their
missing cases repeated from fresh states. Only complete observations count in the
matrices. Normal exercise cancellation uses a held pad input, released after the first
award, as in the existing MP timing probe; this avoids repeated temporary Vsync
listeners during the approach walk. All audit emulators were stopped.

This change adds developer probes and the investigation record. No additional gameplay
patch was justified by the audit; resident-memory and MENU code are unchanged.
