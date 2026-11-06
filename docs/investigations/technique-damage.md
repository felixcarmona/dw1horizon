# Why a 586-power technique can deal 798 damage

The diagnosis below records the former ±500 plateau. The current
[bounded extension](#bounded-high-stat-extension-2026-11-06) preserves the
original interval and extends positive advantages; 798 is the before case
of the worked example.

Ordinary techniques do use Offense. However, only the difference between the
attacker's Offense and the target's Defense matters, and that difference stops
at 500 in either direction. Once Offense is at least 500 above Defense, more
Offense cannot increase that ordinary hit. This cap comes from the original
Digimon World formula; Horizon kept it.

The supplied status image identifies MetalEtemon, with 4420 Offense. The written
report says 4430 and describes another species. Neither discrepancy changes the
explanation once the difference is capped. There is no species named Fairymon
in the current roster, so the exact target, its Defense, the difficulty setting
and the random roll cannot be recovered from these attachments. The example
below reproduces 798 exactly with explicitly stated inputs; it is not a claim
to have reconstructed the player's missing battle state.

## Ordinary techniques

Take the technique's power `P`, the battle Offense `O` and target Defense `D`.
First limit `O − D` to the range −500 through +500, then calculate:

```
stat power = P + truncate((limited difference × P) / 500)
element damage = truncate((stat power × element sum) / 30)
hit damage = truncate((element damage × random percentage) / 100)
```

The random percentage is a whole number from 90 through 110. C integer division
truncates toward zero at each division, including a negative stat difference.
A normal hit cannot go below 1. Horizon caps a hit at 30,000; the original capped
it at 9,999. Counter uses this same formula with only 30% of the target's Defense.
A blocked ordinary attack has an additional 10–30% multiplier.

The element sum comes from the technique's element against **each of the
target's three specialties**. The table uses 20 for double effectiveness,
10 for neutral and 2 for one-fifth effectiveness; add the three numbers and
divide by 30. An empty specialty contributes 10. This is an average across
three slots, not three factors multiplied together. The attacker's own
specialties and Vaccine/Data/Virus attribute add no separate damage bonus.
Electricity is called **Air** in this engine. Thunder Justice is technique 8,
Air element, power 586.

A worked example matching the reported 798, assuming NORMAL difficulty and an
unblocked hit:

| Input | Value |
|---|---:|
| Offense | 4430 |
| Defense (illustrative) | 600 |
| Power | 586 |
| Target specialties (illustrative) | Nature, Battle, empty |
| Air factors | 2 + 10 + 10 = 22 |
| Random roll | 93% |

1. `4430 − 600 = 3830`, limited to **500**.
2. `586 + (500 × 586 / 500) = 1172`.
3. `1172 × 22 / 30 = 859` after truncation.
4. `859 × 93 / 100 = 798` after truncation.

Lillymon has those three specialties in the current roster. This demonstrates
a possible element matchup; it does not establish that “Fairymon” was Lillymon.
Any Defense up to 3930 produces the same capped result with Offense 4430. With
these factors the entire random range is **773–944**. A fully neutral target
would instead take **1054–1289**. Raising Offense from 4430 to 9999 would not
raise either range if Defense stayed 600. Against Defense 4300, however, the
same 4430 Offense gives a difference of only 130, so additional Offense would
still help until the difference reached 500.

Evolution level (Rookie, Champion, Ultimate, Mega) is **not a multiplier in
this damage calculation**. Level affects stat profiles, available techniques
and species-specific finisher power indirectly. It also appears elsewhere in
battle logic, including automatic hits against levels below 3 and counter
chance. Those rules do not multiply the damage of a landed normal hit. Status
penalties and stat buffs can change the battle stats entering the formula.

## Finishers

Finishers use another formula and ignore Defense:

```
base = truncate(((Offense + finisher power) × element sum) / 30)
charged = truncate(base × charge / 40)  [only when partner charge >= 41]
damage = truncate(charged × random percentage / 100)
```

Charge tops out at 80, so a full charge doubles the base. At charge 40 or less
there is no charge multiplier. The final 90–110% variance still applies. Enemy
finishers use a random 100–200% multiplier instead of the partner's charge.
Finisher power and element are resolved for the casting species in Horizon;
a borrowed native finisher ID does not force every species to share its power.
Finishers spend the finisher gauge and do not deduct their displayed MP cost.

For the pictured MetalEtemon, NEW DIGIMON on gives power **255**, Battle element.
Against the illustrative Nature/Battle/empty target, Battle is neutral in all
three slots, so its sum is 30. Using the report's Offense 4430, full charge and
a 110% roll gives `(4430 + 255) × 2 × 110 / 100 = 10,307`.
Using the image's 4420 instead gives **10,285**. With NEW DIGIMON off,
MetalEtemon's power is 222; 4430 Offense still gives **10,234** at that charge
and roll. These are possible hits, not guaranteed finisher damage. Different
finisher elements can change the result substantially.

The retained EASY option doubles damage dealt by the partner and halves damage
taken (rounding upward) after the calculation. NORMAL leaves it unchanged.
A precise replay must record that setting too.

## What Horizon changed, and whether to change it

The original unpatched `BTL_calculateDamage` and `STD_calculateDamage` already
have the ±500 stat-difference limit, the element sum divided by 30, the 90–110%
roll and the separate Defense-free finisher calculation. Horizon moved the
constants into owned JSON data while retaining those values. The larger stat
ceiling (999 → 9999) and damage ceiling (9999 → 30000) expose the mismatch:
ordinary attacks saturate early, while finishers keep growing with Offense.
Horizon also has difficulty modifiers and species-specific finisher scalars.
Thus the plateau is original behavior, while the size of the high-stat gap is
amplified by Horizon's expanded limits and balance data.

A balance review is advisable before altering this. Simply removing the clamp
would make large stat gaps increase damage far beyond the original range and
would affect enemies as well as the partner. Simply replacing 500 with 5000 in
both places would make ordinary attacks *weaker* at ordinary stat differences.
Any new curve should be compared at equal stats, modest advantages and extreme
stats, for both sides, alongside MP costs, attack speed, statuses and finishers.
The reported 798 is consistent with the current rules and is not evidence that
Offense is ignored. **No battle code or balance data has been changed.**

Sources in this checkout: `content/tables/battle-formulas.json`,
`content/tables/type-factors.json`, `content/techniques/8-thunder-justice.json`,
`content/species/65-metaletemon.json`, `content/species/209-lillymon.json`,
`docs/reference/combat.md` (Damage and With the caps patches), and
`docs/mods/balance.md` (species mode moves and finisher scalars).
The requested `docs/reference/battle*.md` files do not exist here; combat.md is
the battle reference. Compare original `decomp/src/btl/battle_main.c` and
`decomp/src/std/std_main.c` with the applied versions in `build/decomp-dev/`,
plus `include/dw/caps.h`, `include/dw/mod_options.h` and `modSpeciesMove`.

## Bounded high-stat extension (2026-11-06)

The analysis above describes the previous plateau. Ordinary techniques now keep
all its arithmetic through a difference of +500, but extend the positive side
with a rational tail. The negative side and finishers retain their existing
rules. The earlier statement that no battle data changed is historical.

### Sources, populations and progression

`tools/battle_audit.py` reads the committed species, map placements, technique,
type-factor and tournament JSON. Reproduce the complete tables and resolved
placement rows with:

```sh
python3 tools/battle_audit.py --out build/battle-audit
```

There is no representative player-save population in the repository. Calling
an invented set of player stats an observed distribution would be misleading.
Instead the audit gives explicit progression scenarios, supported by the
species-mode target bands, evolution gains and the training model in
`tools/evo_tree.py`. Untrained species target bands are not automatically the
stats of a raised partner: training, inheritance, evolution's averaging and
battle gains change them. Rookie Offense evolution gains have min/median/max
45/50/100, Champion 0/150/250, Ultimate 400/595/900 and Mega 550/800/800.
The curated ordinary Ultimate band is 300–900 and Mega band 500–800. Early 100,
mid 350 and late 800 therefore span ordinary progression; 1500 is a trained
post-game scenario, 4000 a strong late scenario for the boss
comparison, 6000 an extreme post-game case, and 9999 the trained ceiling.
4000 is deliberately not described as a typical first-generation partner.

Of 989 original-map placements, three have level `none` and are excluded from
enemy statistics. The largest is the Market Manager (9100 Offense/Defense),
a noncombat actor. The other 986 rows include inactive story actors, friendly
recruits and repeated placements. They are a census of potential data, not
986 independent battles or a measure of how often a player meets each enemy.
Their Offense min/median/max is 10/210/999, Defense 30/120/800, and HP
200/800/9999. The JSON census is supplemented after generating the story maps:
`python3 tools/battle_audit.py --maps build/damage-curve-before-maps`.
The 127 added-map placements have HP min/median/max 400/1200/4500,
Offense 100/380/660 and Defense 70/200/360. At partner stat 100, 17/127
enemy rows exceed +500; at stat 350, none do. At partner stat 800,
82/127 partner attacks exceed +500; at 1500 or above all 127 do.
Retouched original maps are excluded from this supplement to avoid counting
them twice. These rows also include friendly actors and are not encounter
probabilities. The runtime tests and full-build heap sweep cover built content
separately.

| Partner O = D | Partner leads by >500 | Partner trails by >500 | Enemy leads by >500 | Enemy trails by >500 |
| --- | --- | --- | --- | --- |
| 100 early | 0/986 | 6/986 | 113/986 | 0/986 |
| 350 mid | 0/986 | 0/986 | 6/986 | 0/986 |
| 800 late | 849/986 | 0/986 | 0/986 | 543/986 |
| 1500 post-game | 986/986 | 0/986 | 0/986 | 986/986 |
| 4000 strong late | 986/986 | 0/986 | 0/986 | 986/986 |
| 6000 extreme | 986/986 | 0/986 | 0/986 | 986/986 |
| 9999 max-trained | 986/986 | 0/986 | 0/986 | 986/986 |

Matching each scenario to its region gives a narrower comparison:

| Region | Partner O = D | Placements | Partner >+500 | Enemy >+500 | Enemy O min/median/max | Enemy D min/median/max |
| --- | --- | --- | --- | --- | --- | --- |
| Native Forest | 100 | 51 | 0 | 2 | 30/150/700 | 30/70/580 |
| Gear Savanna | 350 | 53 | 0 | 0 | 10/340/420 | 100/180/200 |
| Factorial Town | 800 | 45 | 25 | 0 | 40/530/690 | 50/280/580 |
| Mt. Infinity / Back Dimension | 800 | 63 | 18 | 0 | 50/680/999 | 50/330/720 |
| Back Dimension corridors | 1500 | 12 | 12 | 0 | 320/700/830 | 280/355/420 |

The twelve Back Dimension corridor placements (MGEN11–13) have Offense
320/700/830, Defense 280/355/420 and HP 3400/4900/6100. They are not Mega
bosses. The repeat Machinedramon fights in Ice Sanctuary, Ogre Fortress and
the mansion basement use 9999 HP, 999 Offense and 800 Defense; the final
Mt. Infinity fight uses 9400 HP, 999 Offense and 650 Defense. These are the
actual post-game Mega boss profiles rather than assumed thousands of Defense.
Analogman has 300 HP and 50 Offense/Defense. The story fights Machinedramon;
Analogman is a scene actor, not a second high-HP combat boss
(`story/base/zones/mt-infinity/s184-225/script.py`). Digitamamon's post-ending
challenge has 9999 HP, 999 Offense and 720 Defense.

Tournament stats come from `STD_initializeOpponent`, not the species' wild
stats and not a final-round damage multiplier. The JSON cup bases span 100–350.
Each stat independently rolls −30..+30%, then scales ×1 Rookie, ×2 Champion,
×2.5 Ultimate or ×3.5 Mega. Generated initial Offense/Defense cap at 999
and HP at 9999; combat buffs can subsequently exceed 999, up to STAT_CAP 9999;
round number does not scale them. A base-300 Mega has stat range 735–999,
and base-350 857–999. Against a 100-Defense partner, 61/61 raw stat rolls in
these two cases exceed +500. Against a 350-Defense partner, the upper rolls
still do; against 800 Defense none do. A 1500-Offense partner exceeds +500
against every tournament Defense roll, including finals. The generated audit
lists every nonzero cup base and all 61 stat rolls.

### Curve and exact integer behavior

Let `K = statDifferenceClamp = 500`, `V = statDifferenceDivisor = 500`,
`H = tailHalfDifference = 500`, and `T = tailPowerDivisor = 1`. First compute
the original stat power, preserving signed division toward zero:

```
base = P + trunc(clamp(O − D, −K, K) × P / V)
excess = O − D − K
if excess > 0 and H > 0 and T > 0:
    base += trunc(trunc(P × excess / (excess + H)) / T)
```

Apply the original element sum, random roll, difficulty, minimum and cap in
their original order. No fixed-point approximation is inserted into the
−500..+500 interval. Below −500, stat power stays zero and the final damage
floor remains one before block handling. In particular, truncating negative
products is not Python floor division.

For real-valued positive differences the multiplier above the knee is
`2 + (diff − 500) / diff`, approaching 3 from below. The join is continuous
with the same initial slope as the old rising segment. A logarithm keeps
growing without a bound and needs an approximation; square root needs an
integer-root routine; a piecewise linear extension creates slope corners.
This rational curve uses one extra signed integer division, no loop, no
floating point, no allocation and no resident function body (the shared helper
is compiled into the three battle overlays). Missing/nonpositive tail rules
disable the extension, as the other owned battle rules do.

For nonnegative signed-16-bit battle stats and power, `P × excess` is at most
32767² = 1,073,676,289; the sum `excess + H` is at most 65534, and its product with positive
`T ≤32767` is at most 2,147,352,578. Both numerator and denominator fit
signed 32 bits. The C combines the two positive truncating divisions into
one division by `(excess + H) × T`, which gives exactly the same quotient.
The actual capped stats only reach 9999 and ordinary technique powers are
much smaller. Integer division is the R3000's native operation; no 64-bit
multiply/divide helper is needed. The two parameters append four bytes to
`MOD_BATTLE` without renumbering any existing slot.

| O−D | Original multiplier | New ideal multiplier | Old / new neutral damage, P=586 |
| --- | --- | --- | --- |
| −9999 / −500 | 0 | 0 | 1 / 1 |
| −250 | 0.5 | 0.5 | 293 / 293 |
| 0 | 1 | 1 | 586 / 586 |
| +250 | 1.5 | 1.5 | 879 / 879 |
| +500 | 2 | 2 | 1172 / 1172 |
| +750 | 2 | 2.3333 | 1172 / 1367 |
| +1000 | 2 | 2.5 | 1172 / 1465 |
| +1500 | 2 | 2.6667 | 1172 / 1562 |
| +2500 | 2 | 2.8 | 1172 / 1640 |
| +5000 | 2 | 2.9 | 1172 / 1699 |
| +9999 | 2 | 2.95 | 1172 / 1728 |

With the earlier illustrative inputs (Offense 4430, Defense 600, Air sum 22,
93% roll), the reported 798-damage example becomes 1145. The audit imports the
canonical element order from `tools/species.py`; a regression test pins that
worked example and Machinedramon’s Air sum of 22.

This applies symmetrically to the partner and enemies in field/story, STD
and VS. VS uses `VS_rollAttackOutcome` for damage and retains its separate
9999 damage ceiling and original pending-damage handling; this change does
not enlarge those limits. BTL and STD retain Horizon's 30000 ceiling.

### Equal stats, advantages and finisher ratios

These ordinary hits are neutral, power 586, 100% roll, and apply to either
attacker. The finisher is MetalEtemon power 255 with partner charge 80; enemy
finishers instead use their independent 100–200% factor.

| O | D | Ordinary old | Ordinary new | Full partner finisher | Fin/old | Fin/new |
| --- | --- | --- | --- | --- | --- | --- |
| 800 | 800 | 586 | 586 | 2110 | 3.60 | 3.60 |
| 800 | 550 | 879 | 879 | 2110 | 2.40 | 2.40 |
| 1500 | 1250 | 879 | 879 | 3510 | 3.99 | 3.99 |
| 4000 | 4000 | 586 | 586 | 8510 | 14.52 | 14.52 |
| 4000 | 800 | 1172 | 1666 | 8510 | 7.26 | 5.11 |
| 9999 | 100 | 1172 | 1728 | 20508 | 17.50 | 11.87 |
| 9999 | 9999 | 586 | 586 | 20508 | 35.00 | 35.00 |
| 100 | 9999 | 1 | 1 | 710 | 710.00 | 710.00 |

Equal-stat finisher ratios remain 14.52× at Offense/Defense 4000 and 35× at
9999. The positive tail reduces the disparity when Offense leads Defense.

### Boss hit counts, time and finishers

Use MetalEtemon with 4000 Offense, Thunder Justice (power 586, Air), NORMAL,
100% damage roll, no block or buffs. The Air sum is 22 against Machinedramon and Analogman, 50 against
Digitamamon, and 30 for the explicitly neutral tournament scenarios.
The fully charged Battle finisher uses power 255; its element sum can differ
from the ordinary technique. Finisher power, charge and Defense-free formula
are unchanged.

| Target | HP / Defense | Ordinary old → new | Landed hits old → new | TTK at 3 s/hit | Full finisher | Finisher/ordinary old → new |
| --- | --- | --- | --- | --- | --- | --- |
| Repeat Machinedramon | 9999 / 800 | 859 → 1221 | 12 → 9 | 36 → 27 s | 8510 | 9.91 → 6.97 |
| Mt. Infinity Machinedramon | 9400 / 650 | 859 → 1224 | 11 → 8 | 33 → 24 s | 8510 | 9.91 → 6.95 |
| Analogman actor (hypothetical hit) | 300 / 50 | 859 → 1234 | 1 → 1 | 3 → 3 s | 8510 | 9.91 → 6.90 |
| Digitamamon challenge | 9999 / 720 | 1953 → 2780 | 6 → 4 | 18 → 12 s | 8510 | 4.36 → 3.06 |
| Cup base 300, Mega median, neutral | 9999 / 999 | 1172 → 1660 | 9 → 7 | 27 → 21 s | 8510 | 7.26 → 5.13 |
| Cup base 350, Mega median, neutral | 9999 / 999 | 1172 → 1660 | 9 → 7 | 27 → 21 s | 8510 | 7.26 → 5.13 |

These are deterministic landed-hit budgets, not claims of measured AI combat
time. At 3 seconds between landed hits, multiply the count by three. Actual
travel, technique animation, accuracy, blocks, stuns, healing, MP and finisher
use change wall-clock TTK. Thunder Justice's displayed stored MP cost is 110,
ordinary cost 330 before brains discount; the comparison assumes enough MP.
Three other surviving post-game Machinedramon placements share the repeat
profile, so they are not given invented different stats. Cup finals choose
opponents from their pools: a neutral Mega is a conservative stat scenario,
not a claim that every cup is guaranteed to end against that species.

### Buffs and actual battle risk

The census and hit-budget table deliberately use unbuffed stats. Real boss
buffs are substantial, and the live baseline test confirmed them: repeat
Machinedramon reached 3046 Offense and 1607 Defense before the partner was
knocked out. Full Potential adds 25% Offense and 15% Defense/Speed per cast,
with integer truncation. Its use budget comes from Brains: the final boss's
300 Brains permit four buffs; the repeat boss's 800 permit five. The complete
stage table is generated by `tools/battle_audit.py` from those owned rules.

| Boss after all Full Potential casts | Casts | Offense / Defense | Enemy Thunder Justice old → new | Partner Thunder Justice old → new | Enemy finisher range, unchanged |
| --- | --- | --- | --- | --- | --- |
| Final Machinedramon | 4 | 2437 / 1135 | 1562 → 2105 | 859 → 1213 | 4045–9889 |
| Repeat Machinedramon | 5 | 3046 / 1607 | 1562 → 2169 | 859 → 1199 | 4959–12122 |

Here the partner has 4000 Offense and 800 Defense; ordinary rolls are 100%.
Enemy Air sum is 40 against MetalEtemon, partner Air sum is 22 against
Machinedramon. The enemy Mech finisher uses sum 50 and the complete 100–200%
enemy bonus plus 90–110% variance. A fully buffed repeat boss's finisher can
already one-shot a 12000-HP partner at its upper roll **before this change**.
The tail also raises the boss's ordinary attacks: it is not a partner-only
advantage. The no-buff TTK budget must not be mistaken for an AI simulation.

Tournament buffs also exceed the generator's 999 stat ceiling: the baseline
STD trace recorded enemy Offense 1035. At the five-use budget, a hypothetical
999-Offense opponent using Muscle Charge (+30%) five times reaches 3705.
This is a reachable bound only for an opponent with that technique and budget,
not a claim about every final. Conversely, retained buffs already let bosses
escape the negative floor against high-Defense partners; changing that floor
is not necessary to make all boss attacks meaningful.

### Risks and negative-side decision

- At every difference above +500 the stat-power increase is less than 50% of
  the previous 2× plateau; final hit ratios also include integer rounding. Even a max-trained attacker cannot reach 3× power.
  With the committed strongest ordinary power 722, double element effectiveness
  and a 110% roll, the new ordinary ceiling is below 4766, or 9532 on EASY.
  It cannot newly one-shot 9999-HP Machinedramon on NORMAL. EASY, statuses,
  multiple attack objects and already-low-HP foes still need consideration;
  the floor is not a promise that bosses always survive every possible move.
- Enemy 999 Offense versus partner 100 Defense, neutral power 586: 1172 →
  1432 at a 100% roll, or 586 → 716 incoming on EASY. For example, a 1300-HP partner survives the old 1172 hit but dies to
  the new 1432 hit. A weak partner can die sooner. This is symmetric, not a partner-only buff. Group hits can stack.
- Negative stat gaps remain at the original floor. All 986 placements have
  Offense ≤999: a 1500-Defense trained partner receives floor ordinary
  damage from this unbuffed population. Raising the negative floor would change those
  battles far more widely than fixing the positive plateau, and no audit
  evidence justifies that separate rebalance.
- At 9999 Offense versus 100 Defense, power 586 neutral EASY outgoing damage
  becomes 3456 instead of 2344. EASY still applies after element/variance and
  before the 30000 cap. The cap remains reachable by strong finishers;
  ordinary damage with the current JSON powers does not approach it.
- Counter first reduces target Defense to 30%. At O=D=4000, power 586 neutral,
  the result is 1172 → 1653. It uses the same tail and can benefit even against
  an otherwise equal-stat defender. Buffs/statuses alter the inputs as before.
- A block multiplies the already calculated ordinary hit by 10–30%. At the
  maximum gap, neutral power 586 produces 117–351 before and 172–518 after
  rounding. Block probability, MP cost, invulnerability and counter selection
  do not change. The one-damage floor is inside calculateDamage: a later
  block can truncate it to zero, as before.
- Finishers remain much stronger than ordinary hits at high Offense. At the
  strong-late boss scenarios their ratio falls from roughly 4–10 to 3–7,
  rather than eliminating the reason to charge and spend a finisher gauge.
  Gauge growth is independent of the damage amount: one point per battle tick,
  4% of the goal per completed attack, and fixed 6%/8% block bonuses for
  defender/attacker. A shorter fight can therefore end before a finisher is
  available; the tail does not grant extra gauge per point of damage.

### Verification

The nine-language full builds measure `main_BSS_END` at 0x801CE5E0 before
and 0x801CE5E4 after (+4 bytes). Both align the heap start to 0x801CE5F0,
leaving the same 186640-byte heap. All 320 archive-backed screen setups fit,
with minimum margin 1920 bytes. BTL/STD overlays each shrink 36 bytes and VS
grows 76 bytes. The full executable and scripted 2 MB before/after battle
evidence is recorded in the worktree report. Reusable checks compile the actual helper and all three complete
old/new damage functions under undefined-behavior sanitization:

```sh
python3 tools/dev/playtest/damage_curve_host.py build/decomp-curve
python3 tools/dev/playtest/damage_functions_host.py build/decomp-int build/decomp-curve
python3 tools/patch_series.py check --apply
```

The controlled emulator harness uses MetalEtemon with 4000 Offense, 800 Defense,
700 Speed/Brains and 12000 HP/MP, equipped only with Megaton Punch. The chart's
Thunder Justice comparison remains a separate formula model. The field foe is
Factorial Town's Guardromon (FACT02 slot 1), the predefined boss is repeat
Machinedramon (ICSA08 slot 0), and the STD test starts cup 4. Enemy stats, damage
rolls and outcomes are not overridden. Initial partner position and story
actor visibility are set so a direct test start reproduces the prerequisites
of an actual encounter; the boss uses QUICK BATTLES and hides Analogman as the
story does before combat. The field case uses the original intro.

```sh
xvfb-run -a .venv/bin/python tools/dev/playtest/damage_curve_battles.py \
  build/damage-curve-before.cue --exe build/damage-curve-before/exe/SLUS_010.32 \
  --old --out build/battles-before
xvfb-run -a .venv/bin/python tools/dev/playtest/damage_curve_battles.py \
  build/damage-curve.cue --exe build/damage-curve/exe/SLUS_010.32 \
  --out build/battles-after
```

Each ordinary hit records actual attacker/target species, battle Offense and
Defense, move power, element sum, random roll and returned damage. Every result
must equal the selected old/new reference. The harness verifies the emulator
exposes exactly 2 MB, battle frames advance, the fight finishes and at least
one partner hit exercises a positive gap above 500. An executable fingerprint
prevents resuming a checkpoint on a different executable. Instrumented emulator
wall times are not hardware performance measurements or the chart's model TTK.

The completed 2 MB runs checked 78 ordinary damage results across all six
cases. The following pairs have identical captured inputs in both builds:

| Live case | O / D | Power | Element sum | Roll | Old hit | New hit |
| --- | --- | --- | --- | --- | --- | --- |
| Field partner | 4000 / 340 | 320 | 30 | 110% | 704 | 1007 |
| Field enemy | 630 / 800 | 226 | 50 | 108% | 270 | 270 |
| Boss partner | 4000 / 1607 | 320 | 30 | 106% | 678 | 946 |
| Boss enemy | 3046 / 800 | 573 | 50 | 104% | 1986 | 2757 |
| STD partner | 4000 / 701 | 320 | 30 | 104% | 665 | 947 |
| STD enemy | 1035 / 800 | 52 | 40 | 101% | 102 | 102 |

This demonstrates the tail for both sides and both overlays, and unchanged
hits inside the original interval. The repeat boss knocked out the partner
in both runs; these are formula/execution checks, not a guarantee of victory
with an ordinary-only moveset. Instrumented wall times also differ with host
load and random AI events and are not used as before/after TTK measurements.
