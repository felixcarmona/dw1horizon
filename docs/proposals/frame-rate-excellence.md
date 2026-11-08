# Frame rate: the cadence ladder (60 / steady 30 / 20)

Status: implemented for 0.0.8 on `fps-excellent`; review measurements below.

## Summary

The game's logic runs at 20 Hz; the renderer can show one, two or three frames per tick. Until now the choice was
all or nothing: three passes a tick (60) or one (20), picked at the title by a CPU probe. That loses in both
directions: a probe cannot see what an emulator really presents (the Gamma player got 20 fps from a core that
shows 54), and three passes in a scene that cannot carry them give 20 fps with uneven spacing (a tournament at
100 % CPU: every first pass late, 1 % low 18).

AUTO replaces the probe's decision with a **ladder of three cadences, chosen from what the last ticks
actually cost and showed**, in every loop that draws the world:

| Level | Frames a tick | Pattern (refreshes between frames) | When |
|---|---|---|---|
| 60 | up to 3 | 1,1,1 (a pass that does not fit is skipped, as today) | at least `KEEP60` frames per 32 ticks are shown (default 60 = 37.5 fps) |
| steady 30 | 1 then 2 | 2,2,2 | 60 does not pay, and tick + first pass and the extra pass each fit in two refreshes |
| 20 | 1 | 3,3,3 | neither does (the original's timing) |

Steady 30 is the curling match's cadence (patch 0292) made available to every scene: an even tick shows one frame at
its second refresh and ends there; the odd tick is computed in that spare refresh, so its two frames (at its first
and third refresh) both have two refreshes of CPU time. Every frame is two refreshes apart, interpolated for the
refresh it is shown at; the logic stays at two ticks per six refreshes (20 Hz).

What this gives at the standard 100% CPU budget in Redux, 2 MB (average / 1% low):

| Scene | Legacy AUTO | Forced 60 | Ladder |
|---|---:|---:|---:|
| file-city | 20/20 | 48.60/30.00 | 48.00/30.00 |
| gear-savanna | 20/20 | 40.00/30.00 | 40.00/30.00 |
| freezeland | 20/20 | 20.00/20.00 | 30.00/30.00 |
| wild | 20/20 | 22.03/20.00 | 29.28/19.20 |
| tournament | 20/20 | 20.00/18.75 | 29.92/24.00 |

A faster core can choose 60 directly from its real rendering costs, even when its CPU polling count is ordinary.
The evidence includes a Redux core-budget simulation; Gamma and physical-console timing remain unmeasured.
The existing per-pass deadline checks remain in place.

**0.0.8 design:** ship the ladder as AUTO (the default), keep the merged OPTIONS row as the override (AUTO / 60 / 20; 60 = lock level 60, 20 = lock level 20), drop the
title-screen workload trial (the first second of play is the trial, in the real scene, and it is rechecked
continuously). Keep the CPU notice as advice only.

## Why a ladder, and why these rules

**What "best" means here.** With 20 Hz logic the picture can only be improved by interpolated frames between
ticks, so the quality of motion is (a) how many frames are shown and (b) how evenly they are spaced. A pass that
misses its refresh is not only a lost frame: it shifts the next one, and the 1,2,1,2 or 2,4 patterns that result
are what players call stutter even when the average is 40 fps. Interpolation targets each pass’s intended refresh; an overrun can miss that target. A steady 2,2,2
removes the cadence variation of 1,2,1,2, while best-effort 60 can retain substantially more motion samples. Hence three rungs, not two.

**Why measured cost, not a probe.** The CPU probe (0.0.7) counts loop iterations against the hblank counter; it
measures how fast the core runs a polling loop, not how fast it renders and presents. It missed Gamma (fast
rendering, ordinary probe) and it cannot see scene cost at all. A title-screen workload trial measures a synthetic
scene once. The ladder measures the real scene, every tick, with the same hblank counter the present helper already
uses for its pass budget checks, and it double-checks the line counts against what was actually shown (frames per
tick, late frames). If the lines promise 60 and the frames do not come, it steps down anyway.

**How retries are bounded.** Stepping down is cheap and fast (16 ticks, 0.8 s, after a scene gets heavy). Stepping up
needs a full 32-tick window whose costs predict the higher cadence, plus a wait (`cool`) that doubles after every
try that fails (32, 64, ..., 1024 ticks), so a scene that lies about its costs is tried less and less often. A map
change clears the evidence and the wait but keeps the level, so a lighter map can try the next rung after a full window and a heavier
one can first step down after 0.8 s. Bursty effects can cause further changes (measured below). The world and the battle loops remember their levels separately: a battle starts
from the last battle's level, not from a trial, and the world comes back to its own.

**Why not 40, or "30 when 60 does not fit" everywhere.** Three refreshes per tick on a 60 Hz display allow only
three even patterns: 1,1,1; 2,2,2; 3,3,3. Two frames per tick are always 1,2 or 2,1. So when 60 drops frames the
honest alternatives are an uneven 40-45 or a steady 30; the ladder's default keeps 60 while it still shows at least
1.875 frames a tick (37.5 fps), to retain the extra motion samples, and the locked steady-30 comparison below quantifies the alternative. The diagnostic `MOD_CAD_KEEP60`
threshold can prefer the lower rung; 60 is the shipping default.

**Real hardware.** Standard-clock Redux is the 2 MB timing control. Steady 30 requires tick + first pass and
extra pass each to fit within two refreshes with margin. The presenter checks each pass's budget even after a
level has been selected. These emulator measurements do not establish a minimum rate for every console scene.

## Implementation

Patch `Choose-the-frames-a-tick-shows-from-what-the-last-ticks-cost.patch` (main.c, main_menu.c, mod_fps.h,
mod_present.h). The adaptive functions compile only when `FPS != 20`; the FPS=20 build retains its single-pass path:

- `modCadArm` runs at the start of `modPresent` for every tick of three refreshes that is not a test tick and that
  curling has not armed itself (`MOD_RENDER_CADENCE` 1/2/4 stay curling's). It switches contexts (world / battle
  loops), notices map changes, and arms the level: 60 leaves the normal three passes; steady 30 arms
  `MOD_RENDER_CADENCE = 8 | half` (the present helper's existing pair logic, the `8` keeps both curling overlay helpers
  out); 20 arms `16` (one frame at 3/3, interpolation off, the end counted as mode 0).
- Entering steady 30 on an odd tick uses one unmeasured 60 tick to align the pair. It is excluded from
  cadence evidence so it cannot spuriously mark the new 30 rung as failing. Both curling-only overlay calls
  are guarded against the ladder’s 8/16 cadence flags.
- At the end of `modPresent`, `modCadRecord` stores the tick (the decision scans its window every eight recorded ticks): `tick + first pass` lines (`MOD_PERF_P0END`), the
  costliest extra pass with its setup, frames planned, shown and late; packed in one word, 32-word ring. Fast battle
  ticks, pumped loads, pause frames and ticks over 789 lines (a blocking read) are not recorded.
- The decision (`MOD_FPS_POLICY` 0): down from 60 when shown frames fall under `KEEP60`/32 a tick (to steady 30 if
  every recorded tick fits it, else to 20); down from 30 when late or skipped frames exceed `KEEP30` (4) per 32
  ticks; up after a full window and the wait: 30 → 60 when the costs predict at least `KEEP60 + 4` frames per 32
  ticks (`modCadPredict60`: the first pass is shown at the vblank after it ends, each extra pass starts at the
  previous swap and must end inside the tick, 12 lines of margin), 20 → 30 when every tick fits two refreshes.
- `MOD_FPS_POLICY` 1/2/3 lock 60 / steady 30 / 20; 4 is the legacy idle CPU-probe selector. The OPTIONS row maps AUTO/60/20 to 0/1/3, retaining save bytes A0/A1/A2.
- RAM for tools: `MOD_CAD_LEVEL`, `MOD_CAD_SWITCHES`, `MOD_CAD_LAST`, `MOD_CAD_KEEP60`, `MOD_CAD_KEEP30`.
- `tools/test_fps_ladder.py` compiles the three functions natively and replays measured cost profiles through them
  (levels reached, drop speed, no flapping, failed-try waits, context memory, locks); `tools/selftest.sh` runs it.

Cost: see "Heap and overlays".

## Evidence

Measured with `tools/dev/fps` style captures (a Lua vblank listener records every presented frame and the ladder's
level; guest time, so the loaded host does not bias the numbers), PCSX-Redux, OpenBIOS, dynamic recompiler at the
standard clock unless stated. Each capture is 1800 refreshes (30 s); "steady" excludes the first 300. 1 % low is
the reciprocal mean of the slowest 1 % of frame intervals. Scenes: File City south entrance (screen 168, standing
and walking), Gear Savanna (69), Freezeland (88, snow), a wild fight in Native Forest (0), a tournament fight
(Arena, seeded HP so it lasts).

FPS cells are **average / 1% low**, nominal 60 Hz, after five seconds of settling. Switches/min include
the initial settling change and are extrapolated from each 30-second capture. Intervals use the same settled
window. “Legacy AUTO” is the separately built pre-ladder CPU-probe control, reproducing the old 20 cadence;
its polling decision remains 20 even in the faster-core simulation. This is a policy comparison, not a claim
that these development images are the released v0.0.7 binary.

Standard core (100%):

| Scene | RAM | Legacy AUTO | Forced 60 | Ladder | Ladder intervals (refreshes: count) | Switches/min |
|---|---:|---:|---:|---:|---|---:|
| file-city | 2 MB | 20/20 | 48.60/30.00 | 48.00/30.00 | 1:900 2:300 | 0 |
| file-city | 8 MB | 20/20 | 48.42/30.00 | 48.10/30.00 | 1:904 2:297 | 0 |
| gear-savanna | 2 MB | 20/20 | 40.00/30.00 | 40.00/30.00 | 1:500 2:500 | 0 |
| gear-savanna | 8 MB | 20/20 | 40.00/30.00 | 40.00/30.00 | 1:500 2:500 | 0 |
| freezeland | 2 MB | 20/20 | 20.00/20.00 | 30.00/30.00 | 2:749 | 2 |
| freezeland | 8 MB | 20/20 | 20.00/20.00 | 30.00/30.00 | 2:750 | 2 |
| wild | 2 MB | 20/20 | 22.03/20.00 | 29.28/19.20 | 1:1 2:694 3:35 4:1 | 6 |
| wild | 8 MB | 20/20 | 22.48/20.00 | 29.30/20.00 | 2:697 3:35 | 6 |
| tournament | 2 MB | 20/20 | 20.00/18.75 | 29.92/24.00 | 2:743 3:4 | 2 |
| tournament | 8 MB | 20/20 | 20.00/18.75 | 29.84/20.00 | 2:737 3:8 | 2 |
| file-city-walk | 2 MB | 20/20 | 45.56/30.00 | 45.36/30.00 | 1:768 2:366 | 0 |
| file-city-walk | 8 MB | 20/20 | 44.82/30.00 | 44.78/30.00 | 1:738 2:380 | 0 |
| gear-savanna-walk | 2 MB | — | 40.00/20.00 | 32.22/30.00 | 1:111 2:694 | 4 |

Faster-core simulation (eligible RAM JIT cycle charges halved; video/GTE/BIOS timing retained):

| Scene | RAM | Legacy AUTO | Forced 60 | Ladder | Ladder intervals (refreshes: count) | Switches/min |
|---|---:|---:|---:|---:|---|---:|
| file-city | 2 MB | 20/20 | 60.00/60.00 | 60.00/60.00 | 1:1500 | 0 |
| file-city | 8 MB | 20/20 | 60.00/60.00 | 60.00/60.00 | 1:1500 | 0 |
| gear-savanna | 2 MB | 20/20 | 59.72/40.91 | 59.72/40.91 | 1:1486 2:7 | 0 |
| gear-savanna | 8 MB | 20/20 | 59.72/40.91 | 59.72/40.91 | 1:1486 2:7 | 0 |
| freezeland | 2 MB | 20/20 | 59.16/30.00 | 59.16/30.00 | 1:1458 2:21 | 0 |
| freezeland | 8 MB | 20/20 | 59.16/30.00 | 59.16/30.00 | 1:1458 2:21 | 0 |
| wild | 2 MB | 20/20 | 57.80/30.00 | 57.80/30.00 | 1:1390 2:55 | 0 |
| wild | 8 MB | 20/20 | 58.08/30.00 | 58.08/30.00 | 1:1404 2:48 | 0 |
| tournament | 2 MB | 20/20 | 58.04/30.00 | 58.04/30.00 | 1:1402 2:49 | 0 |
| tournament | 8 MB | 20/20 | 58.08/30.00 | 58.08/30.00 | 1:1404 2:48 | 0 |

Every final capture records approximately 20 logic ticks/s. Fast profiles keep the 60 rung while their CPU
polling counts remain below 8500: the probe does not gate AUTO. Neither Gamma nor physical hardware was tested.
The complete matrix, forced steady-30 comparison and two-minute Freezeland/wild
captures are in [the CSV](frame-rate-excellence.csv). Raw vblank rows and matching save states are retained
with the local measurement artifacts.

**Choice for File City and Gear Savanna:** keep the default KEEP60=60 (37.5 fps). At rest, the useful extra
frames retain a 30 fps 1% low; locking 30 removes those frames without raising that tail. During the moving
Gear Savanna workload, the ladder uses steady 30 from refresh 73 to 1585, then retries 60. The capture has
no forced-60 three-refresh intervals, and its 1% low rises from 20 to 30.
File City walking retains the higher cadence. Thus the choice follows scene cost rather than a blanket map rule.
The forced steady-30 comparison makes the pacing/throughput choice explicit. Moving Gear Savanna is a 2 MB
comparison; walking samples that crossed map exits were discarded.

Two-minute AUTO captures at the standard core budget:

| Scene | RAM | Average / 1% low | Intervals (refreshes: count) | Switches/min | Switches in last minute |
|---|---:|---:|---|---:|---:|
| freezeland | 2 MB | 30.00/30.00 | 2:3449 | 0.5 | 0 |
| freezeland | 8 MB | 29.99/29.17 | 2:3447 3:2 | 0.5 | 0 |
| wild | 2 MB | 29.50/19.43 | 1:2 2:3274 3:112 4:3 | 3.5 | 4 |
| wild | 8 MB | 29.69/20.00 | 1:1 2:3341 3:72 | 2.5 | 0 |

All four finish on the 30 rung. Wild-battle effects can still cause late frames and temporary drops to 20;
the paired scheduler does not guarantee 30 when the work exceeds its two-refresh budget.

## Heap and overlays

Merged-main baseline and integrated nine-language layout:

| Budget | Before ladder | Final |
|---|---:|---:|
| main_BSS_END | 0x801CE3F0 | 0x801CEAEC (+1,788 B) |
| Aligned usable heap | 187,136 B | 185,360 B (−1,776 B) |
| Minimum actual-archive setup margin | 2,416 B | 640 B (screen 207) |
| MENU | 53,484 B | 53,484 B / 55,296 B limit |
| Title UI | 0x8006A79C–0x8006C490 | 0x8006A79C–0x8006C4A4 (+20 B) |

All ten linked layouts (base plus nine languages) agree. MENU's 27-sector read ends at 0x800602E0,
before title UI; EVL's sector read ends at 0x8006C800. All overlay linker assertions pass, and all 320
setups fit against actual DIGI.DAT bytes. The ladder allocates nothing and requires no expanded RAM.
The existing Chinese-only 8 MB requirement remains.

Validation: cached nine-language developer build; native rebuild of all languages after the final C fix,
reusing manifest-verified unchanged assets; 143 selftest checks passed, none skipped; 116,928 localization
entries audited with zero errors; ladder/override/title host tests rerun after the final compatibility fix.
The disc NPC audit now honors the already-authored reviewed footprint while still rejecting other changes.


## Risks and limits

- Redux has no working CPU overclock setting here. The faster-core simulation halves eligible JIT RAM block
  charges while retaining video timing, GTE/multiply latency and BIOS charges. It is an approximate budget model,
  not a hardware overclock. No Gamma or console measurement is claimed.
- The ladder sees guest presentation only: an emulator or compositor that drops or repeats pictures after the swap
  is invisible to it, as to every other approach.
- The steady pair samples input one refresh early on alternate ticks (as curling has since 0292); the logic per
  tick is unchanged. The final File City, wild battle and tournament comparisons match all 120 recorded state hashes
  between single-pass 20 and steady 30, including battle overlays.
- Changing level costs one irregular interval; the ladder bounds how often that happens (see the switch counts).
- CPU percentage is still approximate advice; it never gates AUTO. The title hint now says “AUTO: 60 / 30 / 20
  FPS” in nine languages, and its FPS field uses the active rung, including 30. The widest uncondensed hint is 173 of 254 px
  across New, Original and Classic fonts.
