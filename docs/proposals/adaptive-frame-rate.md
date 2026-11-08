# Adaptive presentation rate study

Status: experimental prototype, disabled by default. **Do not ship adaptive selection yet.**
Keep the production CPU-based AUTO selector; an explicit AUTO/60/20 override is a
better next product experiment than silently enabling this policy. The current
release has no frame-rate option: restoring one is a separate UI/localization and
save-compatibility change, not part of this prototype.

The problem is real: the supplied Gamma observation is approximately 54 real fps
when forced to 60, despite a standard-speed CPU-probe result. It is a motivation,
not a measurement reproduced here. A polling-loop count cannot establish that a
particular renderer/emulator can present three evenly spaced pictures per tick.
Conversely, 54 is not evenly paced 60: a strict deadline policy should reject it.

## Constraints and alternatives

Read together with [the scheduler and 72-case study](../reference/frame-rate.md).
That study found roughly 20 fps with worse pacing when requesting 60 at standard
CPU speed: Gear Savanna alternated 20/40 and a tournament had a 15 fps 1% low
versus 20. Its production decision explicitly says: “No load-based downgrade is
added: expensive scenes must not make the mode oscillate”. This study does not
supersede that decision or its measurements.

| Policy | Benefit | Cost or failure mode |
|---|---|---|
| Current CPU AUTO | Cheap, stable across expensive scenes; overclock changes can be followed during existing idle waits | Core timing shortcuts can fool the probe; host/GPU presentation is not measured |
| Presented-deadline feedback | Exercises the real tick, rendering, interpolation, GPU wait and extra-pass skip paths; no emulator identification | Must first expose poor pacing; guest vblank deadlines cannot detect an emulator or compositor repeating/dropping pictures outside the guest |
| Periodically retry 60 | Can recover after a temporary expensive effect ends | An overloaded scene repeatedly becomes uneven; cooldown alone slows oscillation rather than preventing it |
| Retry only on a scene/menu boundary | Bounds stationary-scene switches, places recovery near an existing cut | Nearby maps can still alternate rates; opening a cheap menu does not prove the field will sustain 60 |
| Per-scene failure memory | Avoids repeatedly calibrating a known expensive map or battle family | Map identity does not encode actors, camera, effects, partner models or overclock changes; expiry/invalidation is essential |
| Boot/title calibration | Makes one decision, avoiding play-time changes | The normal title is unrepresentative. Loading a representative field and tournament workload costs boot time and CD traffic, and still cannot cover all models/effects |
| Explicit AUTO/60/20 | Lets the player compensate for an unusual emulator; predictable behavior | Requires choosing a mode; forced 60 can retain the pacing problems already documented |

A 320-scene bitset alone needs 40 bytes, or 80 bytes for two bits per scene. An
8-byte record per scene needs 2,560 bytes, before code, battle classification and
expiry state. Avoid a heap-allocated history or representative model set on a
2 MB console. A single “field failure / tournament failure” cache is smaller,
but overgeneralizes substantially. None of those caches is implemented here.

A title calibration could spend 3–5 seconds testing after asset load, but would
need a real gameplay render workload and separate battle tests. Testing a dummy
triangle loop, title text, or a blank field would give unjustified confidence.
Calibration also needs timeout and original-hardware tests; the loading time
must not be mistaken for rendering failure.

## Prototype

Build the patched decomp with `make TOOLCHAIN=gcc FPS=60 ADAPTIVE_FPS=1`, or pass
`ADAPTIVE_FPS=1` to `tools/build-full.sh` / `tools/mods.sh build int`. The flag is
validated as 0/1 and included in generated `fps.h`, so changing it rebuilds its
dependents. Full-build native-cache arguments include it. Default is 0; `FPS=20`
still compiles out adaptive/multipass code. No menu, save field or allocation is
added.

The prototype chooses 60 at boot independently of the CPU count. At the beginning
of each presentation tick it detects changes to map generation, game state or
field/battle presentation flags. It observes actual flips at the existing swap
site, not just requested mode or render count. A tick is imperfect if fewer than
three passes are shown or any flip misses its assigned refresh. Existing
per-pass skip/budget checks and 20 Hz logic deadlines remain in force.

* Ignore the first 30 eligible ticks after a boundary (about 1.5 seconds).
* Evaluate successive 120-refresh windows. More than 5% imperfect ticks makes a
  window bad; a good window clears the consecutive-window vote. The tolerance
  permits occasional misses; it is not a guarantee of every deadline.
* Two consecutive bad windows latch the mode to 20 at the end of a tick.
  This normally exposes about 5.5 seconds of trial pacing, including warmup.
* Time alone never returns it to 60. A later boundary permits a retry only when
  at least 1,800 refreshes (30 seconds) have elapsed since the downgrade.
* Fast battle pairs, forced diagnostic timing, pause, the battle load pump and
  curling's match cadence reset evidence. A tick lasting at least 120 refreshes
  also resets evidence. Ordinary streaming stalls remain part of gameplay cost.

There is deliberately no automatic “good performance at 20 implies 60 fits”
rule: one pass cannot establish that three passes will fit. This is asymmetric
hysteresis: sustained evidence to drop, a cut plus cooldown to try again. It
prevents stationary load oscillation, not all visible changes across a route.
Returning to a previously failed scene after cooldown can expose another bad
trial. Frequent boundaries can also keep restarting warmup, delaying rejection.

Field and battle transitions clear accumulated evidence rather than transferring
an easy-field success into a complex fight. Tournament/bracket state changes
also count as boundaries. The x2 battle renderer intentionally shows fewer
pictures and must not vote against x1 60. Story battle loading is excluded by
`MOD_LOAD_PUMP`; an effect loaded during active combat is ordinary workload.
A pause does not authorize an upgrade. Menus are not used as a capability test;
a future menu retry needs an explicit entry/exit notification and a fresh field
trial, not only `GAME_STATE` observation.

Diagnostic RAM controls exist only in the experimental build:
`MOD_ADAPT_POLICY`: 0 adaptive, 1 current CPU AUTO, 2 forced 60, 3 forced 20.
`MOD_ADAPT_SWITCHES` counts adaptive upgrades/downgrades. Switching diagnostic
policy starts a fresh controller trial; it is not a saved player option.
The CPU notice still reports CPU capability, so it can advise overclock while
this experiment is trying 60. That inconsistency is another shipping blocker.

## Measurement

At standard CPU speed, each stationary scene downgraded once and then held
exactly three refreshes per swap. Forced 60 failed to sustain evenly spaced 60
in all three fixtures. The initial adaptive trial still exposes uneven pacing:
the tournament's full-minute 1% low is 19.46, even though its steady 1% low is 20.

| Scene / policy | Whole minute fps / 1% low | Steady fps / 1% low | Switches / guest minute |
|---|---:|---:|---:|
| File City / AUTO | 20.00 / 20.00 | 20.00 / 20.00 | 0 |
| File City / Forced 60 | 46.60 / 30.00 | 46.98 / 30.00 | 0 |
| File City / Adaptive | 21.85 / 20.00 | 20.00 / 20.00 | 1 |
| Gear Savanna / AUTO | 20.00 / 20.00 | 20.00 / 20.00 | 0 |
| Gear Savanna / Forced 60 | 39.99 / 29.39 | 39.98 / 29.27 | 0 |
| Gear Savanna / Adaptive | 21.81 / 20.00 | 20.00 / 20.00 | 1 |
| Tournament / AUTO | 20.00 / 20.00 | 20.00 / 20.00 | 0 |
| Tournament / Forced 60 | 20.00 / 18.00 | 20.00 / 17.65 | 0 |
| Tournament / Adaptive | 19.99 / 19.46 | 20.00 / 20.00 | 1 |

A separate live one-minute route starts a fresh adaptive trial in Gear Savanna,
requests a warp to File City at refresh 2,402 (40.03 s), and retains controller
history across the real unload/load. Observed mode changes are refresh 327 → 20,
2,741 → 60 and 3,070 → 20: **3 switches per guest minute**. The cooldown prevents
stationary oscillation, but an actual scene change still exposes another uneven
60 trial and downgrade. This does not meet an unconditional “no visible
oscillation” promise. Loading time is included in this route's clock; it is not
used as an FPS comparison.

The corresponding host-time observations are below. The host was shared and
running below real time; these figures do not establish PSX capability or
physical display presentation. In particular, “20 fps” in the first table is
normalized guest time, not a claim that this host delivered 20 pictures per
wall-clock second.

| Scene / policy | Host flips/s / 1% low |
|---|---:|
| File City / AUTO | 16.64 / 11.57 |
| File City / Forced 60 | 38.01 / 16.32 |
| File City / Adaptive | 17.54 / 10.53 |
| Gear Savanna / AUTO | 16.81 / 11.75 |
| Gear Savanna / Forced 60 | 33.94 / 15.97 |
| Gear Savanna / Adaptive | 18.91 / 11.86 |
| Tournament / AUTO | 18.01 / 13.22 |
| Tournament / Forced 60 | 17.60 / 12.30 |
| Tournament / Adaptive | 17.40 / 12.41 |

The measurements are pinned to base `a8505228` plus the prototype (study
commit `3868bbb6`, before rebasing). Main subsequently added the independent
jukebox/feline fix; the branch is rebased for a conflict-free draft. The FPS
matrix was not rerun after that upstream update. Rebased build/heap validation
is reported separately below, rather than relabeling the recorded captures.

The comparison uses the same experimental executable and its AUTO/forced/feedback
policies. AUTO invokes the existing probe/idle selector; its extra diagnostic
policy-dispatch overhead is included. It is not a byte-identical production-disc
comparison. Assets come from the full game, with the executable and overlays
rebuilt from this branch and runtime gameplay tables encoded through
`tools/balance.py build`. The intro movie is skipped for test startup.

Each scene is a matching-executable checkpoint, original 2 MB RAM, NTSC, OpenBIOS,
PCSX-Redux development build 389, source
`b0a245bc23c303b081fa578364e1ead9bd2727e5`, software renderer, x86-64 dynarec.
The table uses nominal 60 refreshes/s, like the existing frame-rate reference;
NTSC's approximately 59.94 Hz changes the absolute rates slightly.

`tools/dev/fps/adaptivecheck.py` samples `MOD_FPS_RENDERS` on every GPU vblank,
rejecting intervals in which more than one swap was missed by the sampler. That
counter increments only at an actual `GsSwapDispBuff` site. Observing its change
on the following vblank shifts all timestamps by one refresh without changing
swap spacing. This avoids breakpoint-induced guest timing changes. The tool also
records monotonic host timestamps, because guest pacing alone is not real-time
throughput. These are guest display flips, not proof of monitor/compositor scans.

Six setup refreshes are excluded so restoring a checkpoint/setting a diagnostic
policy does not count as a performance-driven switch. Each capture lasts 3,600
refreshes (one guest minute); the steady sample excludes its first 600 refreshes.
FPS is intervals divided by elapsed time. “1% low” is the reciprocal of the mean
of the slowest ceiling(1% of intervals), not the 99th percentile alone.
Switches/minute uses the full guest minute. Raw interval/mode/host-time samples
are retained with the local report. Stationary field checkpoints do not exercise
walking tile uploads or every possible NPC combination. File City is screen 168,
south entrance, and Gear Savanna is screen 69 near the Factorial Town gate, with
a native Agumon partner. The tournament is an Agumon/Drimogemon match. Both
fighters are seeded at a tick boundary with 30,000 HP/MP, offense 100, defense
999, speed/brains 500 to keep the same match alive for every full capture;
effect scripts, models and normal AI/render loops still run. These fixtures
are not a replay of the old study's walk or tournament. In particular, the
File City forced-60 result must not be substituted for its heavier scenes.

Redux overclock is unavailable in this installed build: its source declares
`OverClock` and `PsxClock` only, has no users of those fields, omits them from
serialized settings, and uses a constant 33,868,800 Hz clock. SPU/emulation speed
changes the speed of the whole machine, not CPU work per vblank. No synthetic
CPU-probe write is claimed as an overclock test. The earlier 250% results in the
reference remain historical evidence, not new results from this prototype.
No real 60-capable profile was available here: the keep-60 path has synthetic
deadline coverage only. Original hardware and Gamma were not tested.

Example (after starting a private matching Redux instance and saving scenes):

```sh
python3 tools/dev/fps/adaptivecheck.py \
  --disc build/adaptive.cue --exe build/adaptive/SLUS_010.32 \
  --port 42516 --out build/adaptive-results \
  file-city=build/states/file-city.state \
  gear-savanna=build/states/gear-savanna.state \
  tournament=build/states/tournament.state
```

## Memory and validation

The measured-revision builds use the same full-language text padding, generated
roster/font inputs and added-file list. Only `ADAPTIVE_FPS` differs.

| Quantity | Flag 0 | Flag 1 | Change |
|---|---:|---:|---:|
| Main text | 509,616 B | 510,368 B | +752 B |
| Static controller/control storage | 0 B | 56 B | +56 B |
| `main_BSS_END` | `0x801ce1a0` | `0x801ce4c8` | +808 B |
| Aligned usable heap | 187,728 B | 186,928 B | −800 B |
| MENU load size | 55,172 B | 55,172 B | 0 B |
| Actual-archive minimum setup margin | 3,008 B | 2,208 B | −800 B |

MENU remains below its 55,296-byte limit, with 124 bytes spare. All 320 setup
scripts fit the actual full model archive; screen 207 (Birdramon, Leomon,
Hawkmon) remains tightest. The older sweep-based heap check also passes; its
30,576-byte Ogre Fortress minimum is not a substitute for the actual-archive
2,208-byte margin. No dynamic heap or persistent per-scene storage is used.

After rebasing onto the jukebox/feline update, both native flag builds pass.
The updated baseline has `main_BSS_END = 0x801ce1e0` and 187,664 bytes of heap;
the updated prototype has `main_BSS_END = 0x801ce508` and 186,864 bytes of heap.
The isolated adaptive cost remains 752 bytes of text plus 56 bytes of static
storage, or 800 aligned heap bytes. MENU is still 55,172 bytes. The rebased
actual-archive check covers all 320 setups with a 2,144-byte minimum margin on
screen 207. These updated layout checks do not constitute a rerun of FPS captures.

The extracted-C sanitizer test exercises real controller functions with even
frames, skipped passes, late flips, isolated/sustained bad windows, a synthetic 54/60 stream, exclusions,
boundary cooldown, counter wrap and diagnostic controls. Existing AUTO threshold,
idle-budget, boot and legacy compatibility tests remain applicable with the flag
off. A matched compile with flag 0 produces byte-identical main and 17 overlay
binaries to the unpatched parent, including production's uninitialized mode
storage. Both flag values build successfully. The measured 427-patch series
and the rebased 428-patch series both apply to the pinned decompilation using a
private source clone, without requiring the owner's checkout.

## Recommendation and remaining risk

Keep this opt-in. A guest-side controller cannot satisfy “real hardware and every
emulator” by itself: an emulator may decouple guest vblank, CPU counters, GPU
submission and actual display refresh. Host overload can reduce real fps while
all guest deadlines appear met. Conversely, a transient heavy effect can cause a
permanent downgrade until another cut. Per-scene caching would reduce repeated
trials but add invalidation errors and memory cost.

Before any default change, require real-console 2 MB timing and memory tests,
Gamma/device captures with actual display timestamps, a genuine emulator CPU
100%/250% matrix, moving field routes, repeated field/battle/menu transitions,
late effect streaming, same-build save-state restoration and x2/pause/curling
checks. In particular, an even guest-side 60 result is not evidence that Gamma
presents evenly on the phone. Prefer explicit AUTO/60/20 control until that
external-presentation gap and the visible retry behavior are resolved.
