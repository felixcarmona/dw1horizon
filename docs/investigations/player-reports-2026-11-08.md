# Player reports from v0.0.7

## Camera after Continue

Confirmed in v0.0.7 and main, and absent from the matching original-disc control.
Load a Green Gym memory-card fixture at world (0, 0, 0) and hold Left immediately.
Both actors leave the view. Waiting 60 logic ticks before walking produces the
same correct framing as vanilla. The native projected-bounds check confirms
that the tamer is off-screen in the bad case and visible in both controls.

`initializeLoadedMap` already computes the saved camera position and uploads its
window before returning field control. It also queued another fixed-target pan
at that same saved position. Horizon's asynchronous camera-band reads can keep
that pan active until tick 53, while the tamer is free to move. When following
resumes, its per-step delta does not recover the movement lost during the pan.
The wrong offset persists: in the same fixture vanilla/waited Horizon ends at
`DRAWING_OFFSET_X=312`, but immediate v0.0.7 ends at 165 with the same tamer
position (-2250, 0, 544).

`CAMERA_FOLLOW_PLAYER=1` and `CAMERA_HAS_TARGET=0` at the end do not prove correct
framing: both are also true in the broken capture. The regression therefore
checks the real engine's `entityIsOffScreen` bounding-box projection and the
screenshots, as well as ownership. Right from some other positions only waits
two ticks and does not reproduce the problem, explaining why position matters.

The fix removes only the redundant queued Continue pan. The synchronously
positioned/uploaded saved view is ready for the first walking tick. No new state
or input gate is needed; scripted camera pans retain their existing path.
Native Agumon reproduces the regression, so it does not depend on a tall partner,
title settings, status bars or cold imported animations. A taller partner also
exhibits it. English and Portuguese, quick-battle settings, delayed input and
other load screens are covered by the diagnostic/acceptance runs in the task
report. These tests use real memory-card Continue and pad input at 2 MB.
On the final nine-language image, immediate Left in Green Gym passes with native
Agumon, Portuguese Frigimon and WereGarurumon; File City (screen 168, quick
battles off) also passes. Follow is active from the first field tick in every
case. The final immediate-Left tamer remains visible at drawing offset X = 320;
the v0.0.7 fixture was off-screen at X = 165.

DuckStation could not be used for acceptance in this environment: the installed
build with OpenBIOS stalled before its title loop (including a landing-screen
VSync wait), and the vanilla USA disc also did not reach its title. Stock 2 MB
runs with/without instruction-cache timing, a minimal settings file, interpreter/
recompiler, and a full v0.0.7 movie-enabled run at 250% were tried. These setup
failures are not camera reproductions. The reported camera defect was reproduced
and compared against vanilla in PCSX-Redux.

## MP x5 result-table delay

This is a Horizon regression in both v0.0.7 and main. State 3 awards the first MP
session and starts the return walk; state 4 waits for that walk; only state 5
advances the remaining sessions. The live-care x5 implementation moved those
awards out of a synchronous loop into separate one-second intervals, but left
MP's intervals behind the walk. HP starts its intervals immediately. Vanilla
has no x5 block; its MP x1 table opens before the return walk, as Horizon x1 does.

Native Frigimon reproduces it without a cold-animation request. In the 2 MB
English main build, the first-to-fifth award span was 152 logic ticks (7.6 s)
for Green Gym MP and 84 ticks (4.2 s) for HP. Trash Mountain MP used 124 ticks
(6.2 s). v0.0.7 gave the same intervals. An x5 block stopped by hunger after
its first session opened the table immediately, explaining the reported
"sometimes". These are emulated logic times, not host stopwatch timings.

The full patched disc reproduces the intended 84-tick (4.2 s) MP block in
both gyms; HP remains at 84 ticks, MP x1 and the first-session hunger stop remain
immediate. Each real award advances exactly one hour, and the hunger/poop/
tiredness costs and final return to field control pass the regression.

The patch lets state 4 fall through to the same block-wait code as state 5.
The remaining four awards then progress during the return walk. A completed or
skipped tally cannot return field control until the walk finishes. Both MP
overlays share the correction; their one-session gains, care costs, ordinary
inter-session waits, early stops and aggregate tally are retained. The change
is entirely inside TRN/TRN2, with no resident executable or MENU additions.

The x5 choice in v0.0.7 is the gym menu's normal-training x5 row (pstat 246 = 2).
R2's old training toggle was removed earlier; the tests select that same menu
flag and use the real native gym state machine for everything after setup.

## Shellmon's rescue

The player later confirmed that Shellmon was already shown as recruited in the
City tab (2026-11-08, 14:27 UTC). Their screenshot selects a coloured Shellmon
with +2 prosperity. Breaking the Motor on the extended-story chase route had
already recruited it. A recruited Shellmon is correctly absent from the canyon.

For a save that has not broken the Motor, raising the fortress lift again
reverses the rescue state, just as on the original USA disc. This is recoverable.

After hearing Shellmon on Great Canyon Bridge, ride the lift on the adjacent
Great Canyon Top Area **down to Ogre Fortress**. Leave that lift down: walk out
through the fortress, then take the **other lift**, at Great Canyon Bottom Area,
up to the top area near Freezeland. Return through the top area toward the
fortress lift. The approach now leads to screen 127, where Shellmon is waiting.
Talk to Shellmon there to recruit it (top-area route 38 → 43 → 37 → 127). Riding the fortress lift up instead resets
the rescue state; lower it again and repeat the outside route.

The executable map numbers and flags make the two routes unambiguous:

| Event | Script/section | Flags after it |
|---|---|---|
| Fortress defeated | 48 | 175 set |
| Hear the plea on the bridge | 39/51 | 182 set |
| Fortress lift down, arrival inside | 48/54 | 180 clear, 181 set |
| Fortress lift up, arrival outside | 37/53 | 180 set, 181 clear |
| Lower canyon lift down | 41/53 | 180 set, 181 clear |
| Lower canyon lift up | 38/55 | preserves 180 and 181 |

Bridge screen 39 places Shellmon with flags 175 + 180. The recruitable rescue
screen 127 places it with 181 + 182. Both require that Shellmon is not already
recruited (flag 235). Screen 37's exit selects 127 when flag 180 is clear.
The fortress's Goblimon fight is not an additional recruitment condition.

With the extended story enabled, breaking the Motor recruits Shellmon directly
for two prosperity points. Look in lower File City, the newspaper-stand area (layouts 180–203), after
that choice. Talk to Shellmon once to start the newspaper (flag 78). Leaving the Motor intact preserves the original lift route; the extra
Shaft/Engine Room lift is separate from the original fortress lift. Its chase
menus can fall through to the original ride-up menu.

Commit `39cd309f` changes the order of Shellmon's join announcement and departure;
it does not change presence conditions, lift flags or access to the rescue.
These route and presence rules are the same in v0.0.7 and main.

Validation: `dws.py city-verify` compared both presence declarations with the
original disc's MAPHEAD instructions exhaustively (16 states, all equal).
An original-disc 2 MB emulator run seeded the cleared/plea/unrecruited flags,
executed the real lift arrival handlers 37/53 and 48/54, and loaded screen 127:
Shellmon was absent
on 127 after riding up and present after leaving the fortress lift down.

The follow-up is in Discord channel `1563219062606004297`, messages
`1568995290805964912`, `1568995429767446610` and screenshot message
`1568995499627774152`. No message was sent as part of this investigation.

## Storage reserve

The full main build exposed a separate budget issue: MENU was 55,236 bytes,
within its 27 sectors but leaving only 60 bytes, below the storage checker's
100-byte reserve. The MP change touches only TRN/TRN2 and did not cause this.
Sharing argument setup between card read/write and expressing their two/three
iteration bound directly reduces MENU by 64 bytes to 55,172 (124 spare).
The budget-only change keeps `main_BSS_END` at `0x801ce57c`; the final camera
removal reduces it to `0x801ce56c`, leaving 186,768 bytes of heap (16 more).
The story heap gate passes, including screen 207 with a 2,048-byte margin.
The card format, IO order and read/write arguments do not change. No evidence connects the old reserve shortage to the
camera report.

The actual save C helpers pass corruption, registration preservation, all 65
card-frame interruptions and legacy two-block overwrite cases after the change.
Full final-build storage and runtime results are recorded in the task report.

## Repeating the focused checks

```sh
python3 tools/patch_series.py check --apply
python3 tools/dev/playtest/training_mp_host.py build/decomp-dev
python3 tools/dev/playtest/training_care_hud_host.py build/decomp-dev
python3 tools/test_training_calendar.py build/decomp-dev
python3 tools/dev/saves/inline.py build/decomp-dev
python3 tools/dev/playtest/training_mp.py build/dev-everything.cue \
  --exe build/dev-everything/exe/SLUS_010.32 --out build/mp-proof
python3 tools/test_load_camera.py build/dev-everything.cue \
  --exe build/dev-everything/exe/SLUS_010.32 --out build/load-proof \
  --button LEFT --position 0 0 0
python3 tools/title_storage_check.py build/dev-everything/exe/SLUS_010.32.elf \
  build/dev-everything/exe-*/SLUS_010.32.elf
```

Use `training_mp.py --before` for the v0.0.7/main controls. `test_load_camera.py --expect-offscreen` checks the old regression control.
Camera fixtures also support `--original`, a delayed direction, another native screen, and a shorter
hold near an exit. Every runtime acceptance above retains original 2 MB RAM.
The nine-language build includes Chinese's separate 8 MB module; it is not
selected in these 2 MB tests.
