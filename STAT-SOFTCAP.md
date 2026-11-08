# Stat growth soft cap: audit and review proposal

> Historical growth proposal, superseded by opt-in HARD and a combat-only Defense
> continuation above 999. Permanent stat growth remains unchanged. See
> [HARD implementation and evidence](HARD-DIFFICULTY.md). The historical buff
> sensitivity incorrectly allowed six Full Potential casts for repeat
> Machinedramon: the current Brains rules allow five. Do not use that six-cast
> row as a legal encounter state.

## HP/MP review: the first-life Pukumon report

**No general HP/MP growth reduction is justified by this report.** The game uses
HP/MP in units ten times the other attributes: 8005 HP is 800.5 normalized,
9520 MP is 952 normalized, versus the reported Offense/Defense/Speed 650–820.
HP is within that band; normalized MP is 16–46% higher. A screenshot without
its save/training history cannot identify the exact route or gains.

Pukumon's evolution targets are 8000 HP, 7000 MP, 800 Offense, 800 Defense,
700 Speed and 700 Brains. Below a target, evolution averages old and target;
at or above it, evolution adds 10% of the target. Its possible parents include
MarineDevimon (4600/4850 HP/MP targets) and Divermon (5000/5000), as well as
Dragomon. These target magnitudes already use the ten-to-one scale.

A **constructed arithmetic witness**, not a reconstruction of the player's
save, reproduces the reported HP/MP exactly without chips, food, inheritance,
post-evolution fights or gym bonuses:

| Checkpoint / action | HP | MP | Offense | Defense | Speed | Brains |
|---|---:|---:|---:|---:|---:|---:|
| Before Pukumon evolution (assumed state) | 4740 | 4890 | 500 | 500 | 500 | 500 |
| After actual Pukumon blend | 6370 | 5945 | 650 | 650 | 600 | 600 |
| After 12 HP, 32 MP, 5 Speed and 5 Brains ordinary sessions | **8005** | **9520** | **674** | **714** | **675** | **655** |

The 54 sessions use Pukumon's actual offense-speed affinity and Mega multiplier.
Each HP session gives +130 HP / +2 Offense; MP gives +110 MP / +2 Defense;
Speed gives +15 Speed / +15 HP; Brains uses MP affinity and gives +11 Brains /
+11 MP. Every session still costs time, fatigue and care. This proves arithmetic
plausibility; a complete first-life route and care schedule were not replayed.
The added Mega lifetime is 120 h, so 54 training hours are not intrinsically
an impossible lifetime budget before allocating sleep, rest and care.

Other sources can reach these numbers earlier: gym recruitment/manual/counter
bonuses and Digipine; +50/99 HP/MP per win against a 5000/9999-HP/MP single
foe, respectively; evolution averaging; ordinary food +100 all HP/MP with +10
other stats or +200 targeted HP/MP; restaurants; and the stage's earlier training.
At the same enemy budget, battle floors are also about 5/9.9 normalized HP/MP
points, matching typical 5/9 other-stat floors. Rebirth contributes **zero on a
first life**. Chips are not required, and their absence does not exclude those
other sources. Screenshot numbers alone cannot establish which were used.

Proposal: retain NORMAL growth. If repeatable first-life playtests later show
MP disproportionate after normalization, record its sources separately before
changing targets or battle floors. Avoid applying a literal 999 HP/MP knee or
reducing all six attributes because raw HP/MP numbers look larger. The previous
soft-cap proposal below is retained only as historical evidence.


Status: **proposal only; gameplay is unchanged**. Baseline: `origin/main`
`0cbdeb2ccef749de68abe2f6be9376fa2e97ed9d` (2026-11-07).

## Decision supported by the numbers

Apply diminishing **permanent gains**, keeping the 9999 stat ceiling, and bound
the Offense contribution to finishers. The initial review candidate is ×1 through
999, ×½ from 1000–1999 and ×¼ thereafter. Apply equivalent knees at **9990 and
19990 HP/MP**, whose units are ten times the other stats. Applying a 999-HP knee
would weaken ordinary evolution targets and change progression below the
original game's limits.

This candidate curbs growth but does **not** make every boss dangerous. Heavy
and extreme scenarios still exceed most enemies' Offense by at least 500, giving
1 damage from ordinary direct attacks. It chiefly reduces finisher bursts;
ordinary-only boss TTK moves modestly. It should not be presented as a complete
difficulty fix, and no boss buffs are proposed here.

## Evidence boundary

The tables measure committed numeric data and evaluate the current integer
formulas. They are **controlled scenarios, not observed player-save ranges**.
No ordinary, intensive or extreme complete raise was played for this audit, and
no new wall-clock boss timing was recorded. Existing runtime evidence in
[the damage investigation](docs/investigations/technique-damage.md) confirms that
boss buffs matter: repeat Machinedramon reached 3046 Offense / 1607 Defense
in a recorded loss. That historical run does not validate the proposed growth.

The starting anchor, 1500 HP/MP and 150 other stats at Champion, comes from
`tools/evo_tree.py:practical`. Actual evolution blends then use target species
12 (MetalGreymonVirus) and 373 (WarGreymon). These are arithmetic checkpoints;
the audit does not prove the evolution picker selects this route, the training
fits automatic evolution deadlines, the partner survives every fight, or a
complete care/lifetime schedule is feasible. In particular, the heavy schedule
requires lifetime extension and accumulated money. **Requested empirical raise
ranges and AI combat times remain unmeasured.** Review the proposal as a source
model, with that validation still outstanding.

## Where growth comes from today

The full ordered patch series was applied to an isolated source copy inside
this worktree. The raw `decomp/` alone has the original limits and is insufficient.
Numeric inputs come from the owned JSON and story, rather than an extracted disc.

| Source | Current rule / measured input | Coverage required by a later patch |
|---|---|---|
| File City gym | Base 100 HP/MP or 10 other stat points, secondary gains 2; level/type multiplier, then recruitment ×1.2, upgrade ×1.2 and manual ×1.2 when eligible | Both TRN and TRN2; primary and secondary gains |
| Other gyms | Primary rows 120/150 HP/MP or 12/15 points; TRN2 has manual bonus, no recruitment bonus | Same final gain rule after existing multipliers |
| x5 | Five normal sessions, subject to early stops and individual clock/care costs | Each completed session, never tax the aggregate again |
| Slot prizes | Gain factors miss 0.5, triple 2, matching 4, jackpot 10 | Scale the resulting gain, do not soften the random prize factor |
| Training foods | Digipine ×1.5 for 6 h, flags 63; Supercarrot / Hawk Radish ×1.2 for 6 h for their flagged stats | Apply food multiplier before soft growth |
| Battles | Per stat, max of legacy gain and strongest enemy stat × factor / 1000; factors 10/12/16 for 1/2/3 enemies | Award the final permanent delta once; do not change initial combat stats |
| Evolution | If old ≥ target, add target/10; otherwise new = (old+target)/2 | Compute current positive delta first, then soften that delta; never scale the whole replacement stat |
| Ordinary chips | +50 single stat or +500 HP/MP, 9999 bits each in the secret shop | Item consumption and cost stay independent of awarded amount |
| DV chips | +100 to each of two stats or +1000 HP and MP; −6 lifetime hours | Same soft gain, retain lifetime penalty |
| Food | Deluxe Mushroom +10 all four, +100 HP/MP; stat fruit +20 or +200 HP/MP; Black Trout +1 all four, +10 HP/MP | Include small +1 awards; no permanent zero-gain lock |
| Restaurants | Script `partner.add` / max_hp / max_mp awards; best Digitamamon result +7 each, +70 HP/MP (42 normalized points total) | Script stat writes must use the same helper as items |
| Other scripts | Tunnel hauling totals +50 Offense, +50 Defense, +500 HP across five trips | All positive permanent script additions, including future authored rewards |
| Rebirth | Fresh base plus previous stats × tamer level %, up to 10% | Apply soft gain to inherited addition above newborn base, reset fractional remainders on rebirth |
| Sukamon / special evolution | Percentage scaling and backed-up-stat restoration | Distinguish new positive growth from restoring an already-owned snapshot; do not tax restoration twice |

The upgrade counter is **not simply ten adult training sessions**: current TRN
setup increments the gym counters when level <3. The scenarios below leave
that bonus off. A developed gym with it can award another ×1.2 before rounding.
A full Mega File City primary stat session is 13 unupgraded, 18 with recruitment
and manual, or 22 with the counter too; Digipine changes those last two to 27
and 33. A normal x5 block gives five such gains only if all five complete.
No jackpot or Digipine uptime is assumed in the main scenarios.

Mojyamon grants no direct stat write. Its relevant outputs are **one Deluxe
Mushroom/day**, one Digipine/day and one Chain Melon/day. That is +10 each other
stat and +100 HP/MP daily from the mushroom before soft growth, optional gym
boost uptime from Digipine, and +24 h lifetime from the melon. Inputs, daily
caps, recruitment and travel still constrain use. The old unlimited chip or
cash loop is absent. Buying chips for 9999 bits is a repeatable resource sink;
there is no finite lifetime-independent maximum below 9999 while extensions
and purchased boosts remain available. See [the economy audit](docs/mods/balance.md#61-the-economy-rule).

Sources: `content/tables/{training,training-gains,battle-rules,evolution-rules,
care-rules,tamer-level,shops}.json`; `content/items/*.json` effects;
`content/species/*.json`; `story/base/zones/libraries/s217` and `s218`;
patched `main/{battle_ui,item,evolution,partner_impl,script_value}.c`,
`trn/trn_reward.c`, `trn2/trn2_reward.c`, and `trn/trn_block.h`.

## Controlled raise inputs and resulting stats

Three stages are modeled: Champion, Ultimate, Mega. At each stage: distribute
gym sessions cyclically HP/MP/O/D/S/B; award single-enemy battles; consume the
six ordinary chip types; take best-roll Digitamamon meals; then evolve at the
first two stage boundaries. Every gain is clipped at the current hard limit.
The proposed run re-evaluates battle/evolution gains from its own lower stats.
It is **not** a transformation of the final current stat.

| Scenario | Gym sessions by stage | Battles by stage | Each chip type by stage | Meals by stage | Extra resources |
|---|---|---|---|---|---|
| Normal budget | 84 / 60 / 60 | 24 / 40 / 60 | 1 / 1 / 1 | 4 / 4 / 4 | No gym bonuses |
| Heavy budget | 144 / 120 / 180 | 80 / 120 / 200 | 8 / 8 / 8 | 20 / 20 / 20 | Recruitment + manual; no counter |
| Max grind stress | Same as heavy | Same as heavy | Same, then 200 more of each chip | Same as heavy | Stockpiled resources; not a fresh-save raise |

Battle floor anchors: 3000/3000/400/300/250/250 for the first stage, then
5000/5000/700/500/400/400, in HP/MP/O/D/S/B order. These are explicit mixed-area
training assumptions, not named encounter placements. Probabilistic extra +1
battle gains, status penalties, deaths, fatigue and rest are excluded. All gym
sessions are unexhausted normal sessions, no slots. The best restaurant roll is
an upper contribution, not an expected meal outcome. The max scenario uses
**the same 200 extra chips** even after today's stats cap, to compare equal
inputs without silently stopping its proposed counterpart early.

Resource checks: normal chips cost 179982 bits, heavy 1439856, max 13438656;
meals add 18000 / 90000 / 90000 bits at 1500 each. Clock costs before travel,
rest or meals are 245h20m normal (204 gym h + 124 fights ×20m) and 577h20m heavy
(444 h + 400 fights ×20m). Heavy cannot fit those activities plus sleep into
a baseline lifetime without extensions. If modeled with 8 h sleep per day,
577h20m active time alone implies at least 866 h of life, before travel/care.
These constraints are why the following are budget sensitivities, not measured
normal-player outcomes.

| Budget | Rules | HP | MP | Offense | Defense | Speed | Brains |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Normal | today | 15034 | 14934 | 1796 | 1524 | 1402 | 1402 |
| Normal | proposal | 12512 | 12462 | 1397 | 1261 | 1200 | 1200 |
| Heavy | today | 30000 | 30000 | 5970 | 5250 | 4840 | 4840 |
| Heavy | proposal | 25384 | 25359 | 2741 | 2561 | 2459 | 2459 |
| Max grind | today | 30000 | 30000 | 9999 | 9999 | 9999 | 9999 |
| Max grind | proposal | 30000 | 30000 | 5241 | 5061 | 4959 | 4959 |

Sensitivity ranges vary gym, fight, meal and stage-chip counts together by
±25%; max's extra 200 chips remain fixed. They are **not confidence intervals**.

| Budget | Rules | HP | MP | Offense | Defense | Speed | Brains |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Normal | today | 12015–18414 | 12640–18314 | 1452–2159 | 1192–1842 | 1168–1677 | 1163–1671 |
| Normal | proposal | 11002–14202 | 11315–14152 | 1225–1579 | 1095–1420 | 1083–1338 | 1081–1335 |
| Heavy | today | 30000–30000 | 30000–30000 | 4558–7403 | 4000–6485 | 3690–5975 | 3687–5972 |
| Heavy | proposal | 22356–28452 | 22331–28427 | 2388–3100 | 2249–2870 | 2171–2743 | 2171–2742 |
| Max grind | today | 30000–30000 | 30000–30000 | 9999–9999 | 9999–9999 | 9999–9999 | 9999–9999 |
| Max grind | proposal | 30000–30000 | 30000–30000 | 4888–5600 | 4749–5370 | 4671–5243 | 4671–5242 |

## Proposed gain arithmetic and rounding

Use a raw-effort coordinate. For stat `s`, define:

```
C(s) = min(s,999) + 2*clamp(s-999,0,1000) + 4*max(s-1999,0)
new = inverse_C(C(old) + raw_positive_gain + saved_remainder)
new_remainder = budget - C(new)
```

HP/MP use 9990/19990 knees and a middle width of 10000. Split across knees
inside an award. For example, from 990, a +50 chip reaches 1019 with one raw
unit carried; from 1990 it reaches 2007 with zero carried. Four +1 awards above
1999 earn one stat point, equal to a single +4 award. Never round every small
award up to one (an exploit), down to zero permanently, or apply the lower tier
to an entire award that crosses a knee. Cap at 9999/30000 only after integration.

Remainders need 0–3 raw units per stat: 12 bits for six stats if packed. Their
save location and lifecycle must be checked before implementation. Restore an
old save's existing stats unchanged; initialize new remainders to zero. Negative
changes, current HP/MP recovery, temporary battle buffs and difficulty modifiers
are outside permanent growth. A shared item helper alone is insufficient:
evolution, script values, battle rewards and both gym overlays bypass it.

| Raw award within one tier | ≤999 | 1000–1999 | ≥2000 |
|---|---:|---:|---:|
| +1 small reward | 1 | 0.5 | 0.25 |
| +7 restaurant roll | 7 | 3.5 | 1.75 |
| +10 Deluxe Mushroom | 10 | 5 | 2.5 |
| +20 stat fruit | 20 | 10 | 5 |
| +50 ordinary chip | 50 | 25 | 12.5 |
| +80 evolution delta | 80 | 40 | 20 |
| +100 DV award | 100 | 50 | 25 |

Fractions are carried, not displayed as permanent fractional stats. HP/MP
awards use the same rates in their scaled tiers. Rebirth at tamer level 10 from
9999 Offense adds 999 to a Fresh base of 10: today 1009, proposed 1004 with
zero raw units carried. Repeated inheritance cannot bypass the gain rule.

For tuning, a single raw budget of 9999 from zero reaches 3749 with ×½/×¼;
×¼/×⅛ at the same knees reaches 2624. Even the stronger variant still exceeds
most boss Offense by 500. Keep ×½/×¼ as the review candidate until real raises
establish how much ordinary progression it affects; do not silently adopt the
stronger variant as a difficulty fix.

## Ordinary techniques and matching finisher tail

Ordinary damage retains the current curve: the multiplier at Offense−Defense
+500 is 2, at +1000 is 2.5, at +5000 is 2.9, asymptotically 3. The negative
side reaches zero stat power at −500, then final damage floors to 1. Type sum,
integer truncation, 90–110% roll, block and difficulty still apply.

Current finishers use `(Offense + species finisher power) × type_sum / 30`,
ignore Defense, and are linear in Offense up to the final 30000 damage clamp.
Partner charge ≥41 multiplies by charge/40, up to ×2 at 80. Enemies use a
100–200% multiplier, then variance. It is the Offense response that is unbounded
by a soft curve, not the final hit's numeric limit.

Propose the same **rational shape** as the ordinary tail, anchored at 999:

```
effective_offense(O) = O                              if O <= 999
                     999 + floor(999*(O-999)/O)       otherwise
```

Use effective Offense in place of Offense inside the finisher formula, for
partner and enemy finishers in BTL/STD/VS. It approaches 1998, preserves all
values through 999, and leaves species power, element, charge and final clamps
in their original order. This curve and the gain soft cap have different jobs:
one limits a hit's sensitivity to high Offense, the other slows acquisition of
permanent stats. Enemy finishers above 999 become weaker too; this is included
in the buff sensitivity and must be reviewed.

| Offense | Current effective O | Proposed effective O | Neutral full finisher, power 255: current → proposed |
|---|---:|---:|---:|
| 500 | 500 | 500 | 1510 → 1510 |
| 999 | 999 | 999 | 2508 → 2508 |
| 1999 | 1999 | 1498 | 4508 → 3506 |
| 5000 | 5000 | 1798 | 10510 → 4106 |
| 9999 | 9999 | 1898 | 20508 → 4306 |

## Boss budgets today versus proposal

The benchmark is MetalEtemon with each scenario's O/D/HP/MP, Thunder Justice
(power 586, Air), NORMAL, 100% roll, no block or buffs, enough MP. The raised
WarGreymon path supplies a stat budget; this benchmark is a separate controlled
combat fixture, not a claim that WarGreymon learns Thunder Justice.

TTK means **landed hits × an assumed 3 seconds per hit**. It is not measured
wall-clock combat. No finisher is included in those TTK values; a fully charged
finisher is listed separately, without assuming a ready gauge. Brains discounts,
accuracy, animation, target switching, healing, guard, status and AI can change
actual times. Tables of incoming damage give one landed direct attack, not an
observed total taken during a fight. The CSV also includes an explicitly
standardized power-586/type-sum-40 incoming probe and enemy finisher ranges.

| Encounter | HP / O / D | Normal TTK s | Heavy TTK s | Max grind TTK s |
| --- | --- | --- | --- | --- |
| MGEN99:0 Machinedramon | 9400 / 999 / 650 | 27 → 30 | 24 → 24 | 24 → 24 |
| CHKA01:1 Machinedramon | 9999 / 999 / 800 | 30 → 33 | 27 → 27 | 24 → 27 |
| MGEN99:3 Digitamamon | 9999 / 999 / 720 | 15 → 15 | 12 → 12 | 12 → 12 |
| Cup base 350, Mega median (neutral) | 9999 / 999 / 999 | 24 → 30 | 18 → 21 | 18 → 18 |
| factory/remodelling:datamon | 3000 / 640 / 340 | 6 → 6 | 6 → 6 | 6 → 6 |
| residents/knightmon:knightmon | 4500 / 720 / 380 | 12 → 15 | 12 → 12 | 12 → 12 |
| shore/sea-ambush:waruseadramon | 4500 / 560 / 280 | 9 → 9 | 6 → 9 | 6 → 6 |
| hunters/ambush-mist:hunter | 3200 / 540 / 300 | 6 → 6 | 6 → 6 | 6 → 6 |
| shore/beach-cave:ogremon | 4400 / 520 / 270 | 9 → 9 | 9 → 9 | 9 → 9 |
| airdramon/ambush:slot5 | 4400 / 610 / 320 | 9 → 9 | 6 → 9 | 6 → 6 |

| Strongest authored direct move, landed hit | Normal taken | Heavy taken | Max grind taken |
| --- | --- | --- | --- |
| MGEN99:0 Machinedramon | 1 → 455 | 1 → 1 | 1 → 1 |
| CHKA01:1 Machinedramon | 1 → 455 | 1 → 1 | 1 → 1 |
| MGEN99:3 Digitamamon | 1 → 372 | 1 → 1 | 1 → 1 |
| Cup base 350, Mega median (neutral) | probe only: 1 → 372 | probe only: 1 → 1 | probe only: 1 → 1 |
| factory/remodelling:datamon | 1 → 1 | 1 → 1 | 1 → 1 |
| residents/knightmon:knightmon | 1 → 1 | 1 → 1 | 1 → 1 |
| shore/sea-ambush:waruseadramon | 1 → 1 | 1 → 1 | 1 → 1 |

| Full neutral Battle finisher | Today | Proposal |
| --- | --- | --- |
| Normal | 4102 | 3076 |
| Heavy | 12450 | 3776 |
| Max grind | 20508 | 4124 |

All three repeat Machinedramon sites (mansion CHKA01, Ice Sanctuary ICSA08,
Ogre Fortress OGRE02) share 9999 HP / 999 O / 800 D. Mt. Infinity uses 9400 /
999 / 650. Analogman has 300 HP / 50 O / 50 D and is a scene actor; there is
no separate Analogman combat TTK. The hypothetical fixture one-shots him in
both rulesets, but that is not a second boss battle. Digitamamon's post-ending
challenge uses 9999 / 999 / 720. Back Dimension corridors are 3400–6100 HP,
320–830 O, 280–420 D; do not label them separate high-stat Mega bosses.
The summit story branch reuses the same Machinedramon encounter. No additional
unique high-stat post-game Mega encounter was found in this source census;
friendly Mega actors are not counted as bosses.

The full [boss CSV](docs/data/stat-softcap/bosses.csv) covers 42 encounter/fixture
rows × three partner scenarios, including every explicit named `fight(...)`
participant in the added arcs, optional resident challenges, multi-enemy escorts,
and all six nonzero tournament base-stat bands. Imported base aliases were
resolved to TWNA02:5, OGRE11:0/3 and MGEN99:0. Repeated alternative branch
placements remain visible rather than inflating a count of distinct bosses.
Each multi-enemy row is an individual target budget; simultaneous enemies,
AoE and summed incoming damage are not simulated. Empty-argument `fight()`
wild encounters are not claimed as boss coverage.

Tournament initial stats use independent −30..+30% rolls, level factors ×1 /
×2 / ×2.5 / ×3.5, and ceilings 999 stats / 9999 HP. Finals add no round-based
stat multiplier. Base-300 Mega O/D rolls 735–999, base-350 857–999. The table
uses median neutral Mega fixtures, not actual fixed final opponents or technique
identities. Lower-level or elemental finals vary; named final pools and live
matches still need replay. A guessed incoming technique would not be evidence,
so their damage column uses the standardized probe instead.

### Full Potential sensitivity

Do not infer boss invulnerability from the unbuffed tables. At repeat
Machinedramon's allowed six Full Potential casts, Offense reaches 3807 and
Defense 1848. Final Machinedramon's 300 Brains permit four casts; the repeat
profile's 800 permits six. The following uses the power-586/type-sum-40 probe
for incoming damage against each partner; all values are landed hits, 100% roll.

| Partner | Casts | Boss O | Boss D | Ordinary taken | Enemy finisher maximum |
| --- | --- | --- | --- | --- | --- |
| Normal | 0 | 999 | 800 | 1 → 372 | 4615 → 4615 |
| Normal | 4 | 2437 | 1398 | 1916 → 2010 | 9889 → 6776 |
| Normal | 6 | 3807 | 1848 | 2172 → 2189 | 14911 → 7315 |
| Heavy | 0 | 999 | 800 | 1 → 1 | 4615 → 4615 |
| Heavy | 4 | 2437 | 1398 | 1 → 588 | 9889 → 6776 |
| Heavy | 6 | 3807 | 1848 | 1 → 2029 | 14911 → 7315 |
| Max grind | 0 | 999 | 800 | 1 → 1 | 4615 → 4615 |
| Max grind | 4 | 2437 | 1398 | 1 → 1 | 9889 → 6776 |
| Max grind | 6 | 3807 | 1848 | 1 → 1 | 14911 → 7315 |

Finishers use Machinedramon power 260, its Mech sum 50 against MetalEtemon,
maximum enemy ×2 and 110% roll. The proposal weakens high-buff enemy finishers
while lower partner Defense can increase ordinary damage. Real AI determines
whether those casts happen before defeat; neither the six-cast row nor the
unbuffed row is a prediction of an entire fight.

## Evolution reachability

No raisable species has an Offense, Defense, Speed or Brains requirement above
999 in the committed on or off requirement rows. The maxima are all **600**.
Normalized HP/MP requirements also stay below 999: max HP row 700 means
**7000 actual HP** (Machinedramon), max MP 600 means **6000 actual MP**
(including SkullGreymon). These remain below the proposed HP/MP knee 9990.
There are 93 positive partner HP rows and 86 MP rows above 999 in *actual HP/MP
units*; they are not above the corresponding scaled knee. No such requirement
needs to be lowered, and no >999 four-stat requirement needs an exception.

This proves the proposed rule leaves all numeric requirement thresholds in
its ×1 region. It does not re-prove sibling picker competition, timely natural
evolution, moves/battle bonuses, weight or care. Those checks must run again
if growth is implemented, particularly for same-level Ultimate routes. Full
practical witnesses and a live first-generation raise remain required.

## Reproduction, checks and implementation plan after review

```
python3 tools/stat_softcap_audit.py --out build/stat-softcap
```

With matplotlib and numpy installed, `python3 tools/stat_softcap_charts.py`
also renders the one-page summary, full boss table and two-page PDF.

The script emits event ledgers, ±25% scenarios, 126 boss comparison rows,
resolved source paths, buff sensitivities and the >999 requirement scan.
Committed numeric outputs: [scenario ledger](docs/data/stat-softcap/scenarios.json)
and [boss CSV](docs/data/stat-softcap/bosses.csv). No disc input is needed.
Current ordinary damage was checked with
`python3 tools/dev/playtest/damage_curve_host.py build/softcap-source`:
**1,699,915 C/Python comparisons**, 85 powers, differences −9999..9999,
monotonicity, original interval preservation and UBSan clean. All three battle
overlays call that helper. The proposed growth model also asserts that 100
separate +1 gains equal one +100 award across both knees for all six stats.
The finisher proposal is evaluated in Python only; no patched finisher C exists.

1. Review the arithmetic candidate and the unresolved damage-floor limitation.
   Collect actual normal/heavy raises and boss traces before treating these
   scenario bands as observed progression. Keep scenario input logs alongside
   live evidence so different food, inheritance and economy budgets are visible.
2. Once implementation is authorized, add one shared permanent-gain contract,
   carry fractional raw units, and route both gyms, battle rewards, evolution,
   items, script additions and rebirth through it. Inspect all other base-stat
   writes for restoration, loss or temporary effects. Ensure the x5 UI displays
   actual integrated gains without awarding or taxing them twice.
3. Add the rational finisher Offense helper consistently in BTL/STD/VS. Preserve
   ≤999 behavior, integer ordering, type factors, charge, EASY and hard hit caps.
4. Export unnumbered C patches into `mods/patches/series` and `index.md`; run
   `python3 tools/patch_series.py check --apply`. Measure `main_BSS_END` before
   and after, then full multilingual 2 MB build and heapcheck. A packed 12-bit
   remainder is a design budget, not an approved or measured save allocation.
5. Validate threshold-crossing gains for every source, +1 accumulation,
   negative/restore/rebirth lifecycle, old saves, x5 stops, on/off requirements,
   and a complete raise. Replay both Machinedramon fights, Analogman's ending,
   Digitamamon, Back Dimension, named tournament finals and branching Horizon
   fights with ordinary/heavy/extreme partners; record TTK, damage taken,
   buffs, finishers, MP, difficulty and technique identities.

**The original audit stopped at this document.** It changed no C, balance JSON or story behavior.
No executable was built and no heap measurement is claimed for that audit;
there is no C change to measure. No emulator was started. Live raise distributions,
actual boss wall-clock times and hardware validation remain untested.
