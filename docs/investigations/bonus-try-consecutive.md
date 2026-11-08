# Consecutive Bonus Try investigation

The November 8 report says the first Bonus Try worked but the second moved
another symbol despite a correctly timed press. Messages 1569063703989723289,
1569063746599649453 and 1569063800530010143 mention a save state but include
neither the state nor a recording. The exact checkpoint and input sequence are
unknown.

## Source evidence

Both training overlays have the same reel logic. `startSlotSession` resets the
session result and phase; `createSlotMachineBox` resets result, payout, state,
autostart, reel positions, scroll, speed and settling. It rolls assistance anew.
Starting the spin clears all three stop counters. The first two reels write
their target symbols before the third can read them. Old targets are not used
to decide a later round. These functions are in `src/trn/trn_slots.c` and
`src/trn2/trn2_slots.c` of the patched engine.

`chooseReelStop` deliberately adds one or two symbols on the third reel when
assistance is 0 and the proposed stop would complete a triple. Assistance 1
also forces a slip when the first two symbols are sevens and the next stop
would complete 777. Assistance 2 can help land sevens. A new machine draws
assistance from `content/tables/slot-machine.json`: five entries of 0, four of
1 and one of 2. A different outcome on a second round therefore does not by
itself demonstrate stale state. Restoring a checkpoint preserves whichever
assistance was already selected, along with input and RNG state.

The gym scripts write pstat 246 explicitly for every menu selection: 0 for
normal training, 2 for x5 and 1 for Bonus Try. The block helper consumes 2 as
normal training; Bonus Try enters its own slot session. There is no source
evidence that a first completed Bonus Try disables the next one.

## Checks and scope

`python3 tools/dev/playtest/training_bonus_host.py build/decomp-int` compiles
the actual round initializer, tick, stop-choice, result accessors and session
completion functions from each overlay with UBSan. UI and sound are stubbed.
For every assistance mode and input spacing of 1–39 ticks it completes two
consecutive rounds, retaining overlay storage between them: 234 rounds per
overlay, 468 total. Each round is also replayed from copied pre-spin and
spinning checkpoints, restoring slot/session, input and deterministic RNG
state, and must produce the identical final state. A clean third-reel setup
reproduces the deliberate one/two-symbol forced miss. Each overlay also passes
42 stopped-triple payout cases, including 777 for all six stats, and a held
Confirm check requiring a new press before the next reel can stop.

These state copies are host checks, not emulator save-file loads. The emulator
test `tools/dev/playtest/training_bonus.py` now plays two Bonus Tries on the
same visit after normal/x5 training, then reloads the field checkpoint after
the first Bonus Try and plays the second again. Its existing 16 gym/exercise
variants remain. That extended emulator matrix has **not been run** for this
investigation: this worktree has no extracted discs, built image or emulator.
Earlier single-bonus emulator results are recorded in
[the report audit](player-reports-2026-11-08-backlog.md).

No gameplay defect is established by these checks. Intentional reel assistance
explains an extra symbol in a clean round, but cannot be confirmed as the cause
of the player's particular run without the checkpoint or a recording. Preserve
the existing odds; removing the forced misses is a separate balance change.
The changes here close a regression-test coverage gap and do not claim to fix
the reported gameplay. No engine patch, executable or allocation changes are
made, so the main executable and original-2-MB heap budget are unchanged.
