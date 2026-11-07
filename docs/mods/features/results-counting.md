# Battle results counting

The USA game can skip both stat absorption and bits with a fresh press of
confirm (Cross) or cancel (Triangle). Holding a button before the results box
becomes active does not create a fresh press. Reward text and box-closing
animations are separate from the counters. After the counting press, another
fresh confirm/cancel press can dismiss the separate reward-text wait.

## Source evidence

The pinned USA decompilation implements the result sequence in
`src/main/battle_ui.c`:

- `handleBattleEndBox` (`0x800ed710`) opens the boxes, waits for stat gains and
  their timer, opens the balance box, waits for bits, then waits for reward text.
- `createPostBattleStatsBox` sets `POST_BATTLE_STATS_TIMER` to 100.
- `tickPostBattleStatsBox` (`0x800ee088`) tests the pad, sets
  `SHOULD_SKIP_BIT_COUNTING`, transfers every remaining gain with stat caps, and
  clears both the gains and timer. Its original condition requires exactly one
  confirm/cancel button, with neither button present in the previous sample.
- `tickBitBox` (`0x800edac8`) uses the same latch to add all remaining bits at
  once. The stat press therefore skips bits too.
- `renderPostBattleStatsBox` (`0x800ee1fc`) normally absorbs one point in one
  stat per render after the initial wait. `BTL_battleTickFrame` waits for three
  refreshes per ordinary tick.
- `BTL_initializeBattleEndText` starts a separate 60-tick wait. Even an empty
  text buffer retains that wait after bits finish; `BTL_tickBattleEndText`
  decrements it and clears it on a new confirm/cancel press. Closing each box
  animates over five ticks. A single counting press does not supply the later
  text press automatically.

Main preserves this skip. The existing
`Accept-tally-skip-presses-while-other-pad-buttons-are-held.patch` additionally
accepts each new face-button edge with other buttons or controller 2 held.
That patch is absent from tag `v0.0.6`; the narrower original input condition
there can explain a rejected combined press, but is inherited from vanilla.

Horizon does increase natural counting time: `content/tables/battle-rules.json`
sets `statGainEnemyFactors` to `[10, 12, 16, 100]`, enabling an enemy-stat reward
floor. It is 1% against one enemy and 1.6% against three. The former one-point
counter made these larger rewards take additional ticks. The stat-cap and HUD
patches change limits and number widths, but do not remove the skip. Both old
counters decrement pending gains even when the displayed stat has reached its
cap; saturation itself was never a shortcut. The reward floor is an intentional
[balance rule](../../decisions.md), and its rewards remain intact.

The economy table also raises battle bits to 150% of the map payout. Counting
those bits one at a time adds another wait (150 becomes 225 in Native Forest).

Battle speed changes tick scheduling and can accelerate the tally. Quick battle
start changes loading before combat. The post-battle stall patch changes field
music/background reads on return to the world. Neither removes the tally's pad
handling. `Type-a-battle-s-reward-text-without-waiting-for-a-bu.patch` concerns
reward text after counting, not stat absorption.

## Change

`Bound-battle-gain-animation-by-the-original-results-wait.patch` absorbs all six
stat rows and the bits during the final part of the existing 100-tick stat wait.
Each step divides the remaining reward over the remaining ticks, rounding up,
and clamps the resulting stat or wallet value. Both counters finish by the stat
deadline, whichever box callback runs first. Reward size therefore adds no time
to the original minimum stat phase. The balance box still opens afterwards,
showing the final wallet.

A fresh confirm/cancel press transfers every remaining stat gain and bit and
clears the stat wait. The later reward-text wait keeps its original input path.
Counting runs in logic callbacks; rendering only displays the values, so extra
presentation passes cannot transfer rewards twice. No allocation or persistent
state is added. Stat gains, bit payouts, and their caps are preserved.

## Validation

The host regression compiles the actual battle and gym callbacks against the
prepared tree's cap definitions and uses the production 16-bit stat arrays:

```sh
python3 tools/dev/playtest/tally_input_host.py build/decomp-dev
python3 tools/patch_series.py check --apply
```

It covers 786,432 pad combinations and 32 combined reward/cap cases, including
all six rows, zero rewards, stat gains of 30,000, 65,535 pending bits, a press
during counting, both control layouts, and both box-callback orders. Natural
counting finishes within 100 ticks; skipped and natural totals match at their
caps. Reward-text ticking starts only after the balance box opens.

Runtime measurements use PCSX-ReARMed libretro commit
`7b0e8f8fadfbce3d170d195b9d9eecaabfa08c8e`, interpreter, HLE BIOS, default
CPU timing, no frameskip, and disconnected controller 2. The harness asserts
exactly `0x200000` bytes of system RAM. The original USA disc runs without code
patches. The earlier OpenBIOS boot attempts and forced CPU-clock diagnostics
are excluded from the measurements.

The early fixture is Agumon against one ModokiBetamon in Native Forest (map 0),
using the save's 800 HP, 600 MP, and 80/60/70/70 stats. The late fixture is
Agumon against two Vermilimon in Mt. Infinity (map 166), using 5,000 HP/MP and
500 in the other stats. Tests warp to those maps and set enemy current HP to
zero after combat initializes, then follow the game's normal victory/results
path. Actors are positioned/hidden to keep the late group consistent between
versions; their stats and bits remain the map's own data. Variable reward text
is suppressed after rewards are calculated in the paired stopwatch tests; its
empty 60-tick wait is retained. This isolates results
from fight length without replacing the reward calculation or input handlers.

Frame zero is the first refresh with the newly created result timer. Stat time
ends when the timer and all six pending gains are zero; bits time ends when the
remaining bits reach zero; screen time ends when all three result boxes are
inactive. Seconds below use nominal 60 Hz refresh units. A counting press starts
at refresh 24 (0.40 s); the two-press case adds another at refresh 60 (1.00 s).

| Vanilla fixture | Gains (HP, MP, offense, defense, speed, brains) | Bits | Natural stat phase | Natural full screen | Full screen, one press | Full screen, two presses |
|---|---|---:|---:|---:|---:|---:|
| Native Forest | 0, 2, 2, 1, 1, 3 | 150 | 336 refreshes / 5.60 s | 999 / 16.65 s | 243 / 4.05 s | 78 / 1.30 s |
| Mt. Infinity | 1, 1, 2, 1, 1, 0 | 3800 | 327 / 5.45 s | 11940 / 199.00 s | 243 / 4.05 s | 78 / 1.30 s |

In both fixtures, the first press completes stats by refresh 27 (0.45 s) and
bits by refresh 48 (0.80 s). The second press clears the remaining reward-text
wait. The late natural screen is dominated by the original one-bit-per-tick
counter, rather than stat absorption. A separate vanilla three-Vermilimon case
paid 5,700 bits and took 294.07 seconds without counting input; its stat phase
was only 5.50 seconds.

The matching main/fixed battle groups contain the same partner and enemy stat
values. Their gains and bit payouts are identical before and after this patch;
the early payout is 225 and the late payout is 5,700 because of the economy rule.
Both runs use QUICK BATTLES on and ordinary battle speed.

| Fixture | Vanilla stats | Main stats | Fixed stats and bits | Vanilla full screen | Main full screen | Fixed full screen |
|---|---:|---:|---:|---:|---:|---:|
| Native Forest | 336 refreshes / 5.60 s | 360 / 6.00 s | 312 / 5.20 s | 999 / 16.65 s | 1248 / 20.80 s | 525 / 8.75 s |
| Mt. Infinity, two Vermilimon | 327 / 5.45 s | 681 / 11.35 s | 312 / 5.20 s | 11940 / 199.00 s | 17994 / 299.90 s | 525 / 8.75 s |

Main's early gains are `3,7,2,1,1,3`; its late gains are
`50,57,8,4,2,3`. The fixed build awards those same gains and every bit. Runtime
assertions compare the final stats and wallet against their initial values plus
the calculated rewards, with the game's caps applied.

In the fixed build, the first press finishes both counters by refresh 27
(0.45 s). Two presses close either fixture at refresh 78 (1.30 s), using confirm
or cancel under either US or Japanese controls. R2 speed mode accelerates the
stat phase rather than blocking input: on this core the late baseline took
681 refreshes ordinarily and 229 in fast mode, while the fix took 312 and 105.
Those fast-mode figures are emulator observations, not physical-console speed
measurements.

A separate 2 MB runtime stress case starts with stats one point below their
caps, pending gains of 30,000 HP/MP and 9,999 in the other rows, 65,535 pending
bits, and a wallet of 999,990. Without input, all counters complete by refresh
312; stats finish at `30000,30000,9999,9999,9999,9999` and the wallet at 999,999.

The full nine-language build passes. Before and after, `main_BSS_END` is
`0x801cdf84` and the aligned heap is 188,272 bytes: zero resident growth.
`heapcheck` passes, and all 320 archive-backed screen setups fit. The tightest
setup is screen 207 with 3,552 bytes of margin. Runtime captures cover English
in 2 MB emulation; physical PlayStation hardware and other runtime languages or
regional bases were not tested.
