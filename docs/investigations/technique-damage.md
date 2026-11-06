# Why a 586-power technique can deal 798 damage

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
