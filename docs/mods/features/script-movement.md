# Scripted translation endpoints

A scripted absolute move divides each remaining coordinate distance by its
requested duration. Integer division can produce a zero step before the actor
has reached the destination. Previously a positive remainder then failed the
arrival comparison forever. The same defect affected single-axis moves.

A zero-step axis now snaps to its destination when polled. Nonzero steps keep
their existing crossing checks. There is no timeout, additional state, animation
replacement or change to battle loading.

## Devimon's departure

Mt. Infinity screen 247 (`MGEN06`) loads script 194. Its step-2 handler, section
53, contains the original Devimon encounter. The final page of
`s194.sec53.u6` is the laugh after the battle. It precedes a flight to
(-4562, 41), three one-second pauses with tamer/partner turns, the entity wait,
Devimon's removal and a camera return. Trigger 321 is set after the camera wait.
The extended-story shortcut replaces the encounter before this point and does
not run this departure.

A controlled post-battle fixture places Devimon at (-4543, 0, 22), facing 512.
Both position and the animation accumulator are updated, as when setting an
entity position. The original flight animation and script remain active.
On the unpatched executable, the scene remains at `WAIT_FOR_ENTITY`, slot 7,
with movement type 8 and both steps zero. The flight pose can keep moving while
the script remains blocked. This is a position-dependent regression fixture;
it does not require a particular partner species.

## Memory

Matched eight-language builds move `main_BSS_END` from `0x801ceb00` to
`0x801ceb70`: 112 additional bytes in main, with no new buffers or state.
The heap decreases from 185,328 to 185,216 bytes. All 320 screen setups fit
the actual model archive; the smallest remaining margin is 496 bytes on
screen 207 (608 bytes before the patch).

## Checks

Build the full eight-language disc and use its matching executable symbols.
All runtime checks require exactly 2 MB of RAM.

```sh
python3 tools/dev/playtest/script_move_host.py build/decomp-dev \
  --out build/move-host
python3 tools/dev/playtest/devimon_departure.py build/devimon-dialogue-hang.cue \
  --exe build/devimon-dialogue-hang/exe/SLUS_010.32 \
  --out build/devimon-proof
```

Use `--language es --partners 62` to check the Spanish dialogue with WereGarurumon.
Use `--expect-stalls` for the host check and `--expect-stall` for the emulator
check against an unpatched build. `--natural` omits the position fixture.
The host sweep compiles the actual translation functions and checks 6,241
planar positions plus 79 positions on each single axis. It isolates endpoint
arithmetic and does not replace the live animation/script check.

The emulator check seeds the foe at one HP and lets an attack finish the
battle. A native return breakpoint latches the short final page before a held
confirm can advance past it between host polls. It then checks the final dialogue, departure, camera return, restored
control and trigger 321. Its checkpoints belong to the executable that made
them; never load them into another build. Results and captures are local build
artifacts. Original unmodified combat and physical hardware need separate
playtesting.
