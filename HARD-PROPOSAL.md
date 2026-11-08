# HARD difficulty: approach proposal

> Historical approach review. Approach A is implemented with the subsequently
> specified HARD damage floor and shared Defense continuation; see
> [current rules and evidence](HARD-DIFFICULTY.md). Tables below describe the
> original alternatives and do not include those later changes.

**Status at this review: proposal only; no HARD game changes were included.**
Experimental implementation work was parked. The existing
[stat audit](STAT-SOFTCAP.md) is retained as historical analysis; its universal
soft-growth and finisher-soft-cap candidates are not recommended here.
Gameplay inputs are pinned to `origin/main` commit
`0cbdeb2ccef749de68abe2f6be9376fa2e97ed9d`.

## Recommendation and intended challenge

Choose **A: fixed multipliers**, aimed at an ordinary late partner around
650–820 Offense/Defense, rather than a partner at 9999. Preserve permanent
stat growth, existing EASY/NORMAL behavior and rewards. A small HP increase
and much stronger enemy attacks provide danger without turning every boss
into a long HP grind.

At O=D=800, the original NORMAL ordinary-hit budgets for final/repeat
Machinedramon are 51/72 seconds. A projects **63/90 seconds**, about 24–25%
longer, with a neutral power-586 incoming hit rising from **819 to 1338**.
These are controlled integer-formula projections with an assumed 3 seconds
per landed ordinary hit, not observed AI timings. Healing, blocks, statuses,
accuracy and finishers can change played outcomes substantially.

A deliberately lets very trained partners outgrow fixed encounters. **At
9999 Defense, the ordinary incoming-damage floor remains 1 under A and B.**
C removes that advantage by following the partner, with the training/reward
tradeoffs shown below. Selecting that tradeoff is part of this review.

## Shared scope and safeguards for a future implementation

- Affect actual enemy participants in wild encounters, native boss/story
  fights, added Horizon fights and single-player tournament matches/finals.
  Apply the same rules with EXTENDED STORY or NEW DIGIMON on or off.
- Keep friendly/noncombat map actors, the partner, tamer, two-player VS and
  permanent growth unchanged. Analogman's ending is a Machinedramon fight;
  his 300-HP scene actor is not another boss to strengthen.
- Apply scaling once at battle setup. Keep the encounter's original stats
  for rewards and restore temporary field stats, including maximum HP, on
  exit/flee. Re-entering a fight must not compound multipliers.
- Tournament opponents first use their existing generated stats and original
  generation ceilings; then apply HARD, with final limits 30000 HP and 9999
  other attributes. MP remains unchanged in every variant.
- Keep bits, drops, prizes and permanent battle gains unchanged. In particular,
  the 1% battle floor must read **original enemy stats**, not HARD's inflated
  HP or attributes. HARD is an optional challenge, not a faster farming route.
- Retain the current ordinary-technique curve, element chart, statuses, random
  rolls, block mechanics, finisher charge/gauge and final damage cap. No global
  diminishing finisher curve is proposed. Enemy finisher power is scaled once;
  scaled Offense already contributes through the existing finisher formula.

## Three approaches

### A. Fixed encounter multipliers — recommended

| Component | Proposed HARD factor |
|---|---:|
| Enemy HP | ×1.10 |
| Enemy Offense | ×1.50 |
| Enemy Defense | ×1.05 |
| Enemy Speed | ×1.15 |
| Enemy Brains | ×1.50 |
| Enemy finisher power | ×1.50 |
| Partner direct technique/finisher damage | ×0.95 |
| Enemy empty-slot idle weight | ×0.25, minimum 1 |
| Enemy MP / rewards / all permanent gains | unchanged |

Store factors as owned JSON percentages, not C literals. Multiply then truncate
and clamp; apply the partner's 95% modifier before the final damage minimum/cap.
Poison keeps its existing percentage of the target's maximum HP, so increasing
enemy HP also increases poison damage against that enemy. Scripted percentage
damage keeps its current semantics.

The inexpensive AI change is fewer idle choices when a usable move exists.
Keep existing move-usability/MP/counter guards. Higher Brains also feeds the
existing target and buff-priority rules; do not claim a new tactical AI.
For reference, a 20-weight idle slot beside 80 total action weight falls from
20% to about 5.9% idle before other existing priority adjustments.

Pros: small implementation and memory cost, predictable fixed encounters,
training remains valuable, minimal tuning surface. Cons: uniform changes can
hurt early encounters disproportionately; strong grind can still trivialize
ordinary damage. The optional 5% partner modifier also reduces the effect of
a chosen technique slightly. If that modifier is undesirable, it can be removed
and HP retuned after review; the tables here specifically include it.

The earlier ×2 HP draft is not recommended: at 800 Offense it projected roughly
120/171 seconds for final/repeat Machinedramon, far above the intended baseline.

### B. Fixed multipliers by encounter tier

Use the **unmodified encounter**, independent of the partner and species-mode
level changes: Late if HP ≥8000 or Offense ≥800; otherwise Mid if HP ≥3000 or
Offense ≥400; otherwise Early. Apply the first matching rule in that order.
These thresholds and factors would also live in owned JSON.

| Tier | HP | Offense | Defense | Speed | Brains | Finisher power |
|---|---:|---:|---:|---:|---:|---:|
| Early | ×1.10 | ×1.20 | ×1.05 | ×1.10 | ×1.20 | ×1.20 |
| Mid | ×1.15 | ×1.40 | ×1.10 | ×1.15 | ×1.40 | ×1.40 |
| Late | ×1.25 | ×1.60 | ×1.15 | ×1.25 | ×1.60 | ×1.60 |

Partner direct damage stays at 100%; idle weighting and all reward/growth rules
are as in A. Native/repeat Machinedramon, Digitamamon's challenge and the median
Mega final are Late; the listed Horizon fights and Guardromon are Mid.

Pros: gentler early enemies and a more pronounced late challenge; no partner
penalty; training retains value. Cons: thresholds create abrupt jumps, unusual
stat-specialist enemies can receive an unexpected tier, and late fights get
longer. Authored boss exceptions would add maintenance and metadata costs.
Using species level directly is another possibility, but would make difficulty
change when NEW DIGIMON changes a species' tier; encounter tiers avoid that.

### C. Enemies follow the partner

Start from A's enemy factors. On battle entry, add these floors using the
partner's **permanent base stats before conditions or battle buffs**:

```
enemy HP      >= floor(partner maximum HP * 75 / 100)
enemy Offense >= partner Defense
enemy Defense >= max(0, partner Offense - 250)
enemy Speed   >= floor(partner Speed * 90 / 100)
enemy Brains  >= floor(partner Brains * 80 / 100)
```

Retain the 30000/9999 ceilings, ×1.50 enemy finisher power, 100% partner damage,
A's idle-weight change and unchanged rewards. Sample once, not every frame or
after a buff. The tables use exactly these floors, including in wild encounters.

Pros: ordinary enemy hits remain relevant even against maximum Defense; fixed
boss data needs less continual retuning. Cons: the world follows investment,
weak wild enemies gain boss-sized HP, raising a partner can lengthen fights,
and high-stat enemy finishers can reach the 30000 damage cap. Because finishers
ignore Defense, linking enemy Offense to partner Defense can make Defense
training increase finisher damage taken. Players can
influence the snapshot by temporarily lowering permanent stats; tying the rule
to temporary combat buffs would introduce further exploits and instability.
This is the least compatible approach with rewarding growth and is not the
recommendation.

## Impact table: source-measured inputs and calculated outcomes

These are **analytic projections**, not measurements from new HARD battles.
No proposed variant or complete raise was played for this proposal. TTK means
`ceil(enemy HP / ordinary landed hit) × 3 seconds`; damage taken means one
unblocked **neutral power-586 incoming probe**, at a 100% damage roll. It is
not a claim that every enemy uses that technique or element, and not total
damage over a played fight. Buffs, status, MP exhaustion, healing, movement,
accuracy and finisher readiness are excluded. An attacker dying before all the
assumed hits makes this a hit budget, not a predicted victory time.

Outgoing benchmark: MetalEtemon, Thunder Justice (power 586, Air), NEW DIGIMON
on. Actual target specialties determine outgoing element multipliers. The
partner fixtures are explicit scenarios, not population estimates:

| Partner | HP | MP | O = D = Speed = Brains |
| --- | --- | --- | --- |
| Normal late | 8005 | 9520 | 800 |
| Strong | 15000 | 15000 | 1500 |
| Maximum | 30000 | 30000 | 9999 |

The ordinary stat multiplier retains 2× power at +500 Offense−Defense,
2.5× at +1000 and 2.9× at +5000. The negative side reaches the 1-damage floor
at −500. Signed integer division truncates toward zero at each step.

Each following cell is **assumed TTK seconds / incoming probe damage per hit**.

| Encounter | Partner | NORMAL | A fixed | B tiered | C follows partner |
| --- | --- | --- | --- | --- | --- |
| Final Machinedramon | Normal late | 51 / 819 | 63 / 1338 | 75 / 1390 | 60 / 1338 |
| Final Machinedramon | Strong | 30 / 1 | 33 / 584 | 36 / 700 | 54 / 586 |
| Final Machinedramon | Maximum | 24 / 1 | 27 / 1 | 30 / 1 | 105 / 586 |
| Repeat Machinedramon | Normal late | 72 / 819 | 90 / 1338 | 117 / 1390 | 84 / 1338 |
| Repeat Machinedramon | Strong | 33 / 1 | 39 / 584 | 42 / 700 | 54 / 586 |
| Repeat Machinedramon | Maximum | 24 / 1 | 30 / 1 | 30 / 1 | 105 / 586 |
| Digitamamon challenge | Normal late | 27 / 819 | 33 / 1338 | 42 / 1390 | 33 / 1338 |
| Digitamamon challenge | Strong | 15 / 1 | 18 / 584 | 18 / 700 | 24 / 586 |
| Digitamamon challenge | Maximum | 12 / 1 | 15 / 1 | 15 / 1 | 48 / 586 |
| Wild Guardromon | Normal late | 6 / 387 | 6 / 755 | 6 / 682 | 21 / 755 |
| Wild Guardromon | Strong | 6 / 1 | 6 / 1 | 6 / 1 | 39 / 586 |
| Wild Guardromon | Maximum | 3 / 1 | 6 / 1 | 6 / 1 | 75 / 586 |
| Horizon Knightmon | Normal late | 18 / 493 | 21 / 914 | 21 / 829 | 30 / 914 |
| Horizon Knightmon | Strong | 15 / 1 | 15 / 94 | 15 / 10 | 54 / 586 |
| Horizon Knightmon | Maximum | 12 / 1 | 15 / 1 | 15 / 1 | 105 / 586 |
| Horizon Datamon | Normal late | 9 / 399 | 9 / 773 | 9 / 698 | 21 / 773 |
| Horizon Datamon | Strong | 6 / 1 | 9 / 1 | 9 / 1 | 39 / 586 |
| Horizon Datamon | Maximum | 6 / 1 | 6 / 1 | 6 / 1 | 75 / 586 |
| Horizon WaruSeadramon | Normal late | 9 / 305 | 12 / 632 | 12 / 568 | 18 / 632 |
| Horizon WaruSeadramon | Strong | 9 / 1 | 9 / 1 | 9 / 1 | 30 / 586 |
| Horizon WaruSeadramon | Maximum | 6 / 1 | 9 / 1 | 9 / 1 | 60 / 586 |
| Mega tournament final | Normal late | 87 / 819 | 120 / 1338 | 210 / 1390 | 114 / 1338 |
| Mega tournament final | Strong | 27 / 1 | 33 / 584 | 39 / 700 | 39 / 586 |
| Mega tournament final | Maximum | 18 / 1 | 21 / 1 | 24 / 1 | 78 / 586 |

Original encounter anchors, before any proposed factor:

| Encounter | HP | Offense | Defense |
| --- | --- | --- | --- |
| Final Machinedramon | 9400 | 999 | 650 |
| Repeat Machinedramon | 9999 | 999 | 800 |
| Digitamamon challenge | 9999 | 999 | 720 |
| Wild Guardromon | 1700 | 630 | 340 |
| Horizon Knightmon | 4500 | 720 | 380 |
| Horizon Datamon | 3000 | 640 | 340 |
| Horizon WaruSeadramon | 4500 | 560 | 280 |
| Mega tournament final | 9999 | 999 | 999 |

Repeat Machinedramon's mansion, Ice Sanctuary and Ogre Fortress placements
share the same 9999/999/800 profile. The tournament row is an explicitly neutral
**median base-350 Mega** fixture: initial independent O/D rolls are 857–999,
HP rolls can also vary, and finals have no separate round multiplier. Actual
named opponents, elemental matchups and generated rolls must be tested after
an approach is approved. New Horizon anchors are the authored challenge
placements, not assumed species evolution targets.

### Finishers and buffs can dominate the ordinary table

Machinedramon's finisher uses its current Offense plus species power, ignores
Defense and rolls an enemy 100–200% factor and 90–110% variance. This table
shows its **unbuffed finisher range against MetalEtemon**, including actual
Mech effectiveness; the previous table's incoming probe was neutral.

| Partner | NORMAL | A | B | C |
| --- | --- | --- | --- | --- |
| Normal late | 1888–4615 | 2831–6921 | 3020–7383 | 2831–6921 |
| Strong | 1888–4615 | 2831–6921 | 3020–7383 | 2835–6930 |
| Maximum | 1888–4615 | 2831–6921 | 3020–7383 | 15583–30000 |

A neutral full-charge partner finisher with power 255 deals:

| Partner | NORMAL | A | B | C |
| --- | --- | --- | --- | --- |
| Normal late | 2110 | 2004 | 2110 | 2110 |
| Strong | 3510 | 3334 | 3510 | 3510 |
| Maximum | 20508 | 19482 | 20508 | 20508 |

Consequently a maximum partner can still one-shot A/B's unbuffed Machinedramon
with a ready full finisher. C's 22500 HP floor survives that one benchmark hit,
but it can in turn hit the maximum partner for 30000. Gauge readiness, charge
execution and actual technique identity determine whether either happens.

Full Potential is a separate uncertainty: each cast adds 25% Offense and 15%
Defense/Speed with truncation. Current rules permit **four casts** for final
Machinedramon's 300 Brains and **five** for the repeat profile's 800 Brains;
the historical audit's six-cast statement was incorrect. Existing NORMAL runtime evidence reached
3046 Offense / 1607 Defense, consistent with five repeat-profile casts.
A/B/C can raise starting values and buff priority further. C's Brains floor
can also raise the final boss's available buff casts from four to five. More Brains increases
existing buff priority; it does not by itself add a new tactic or unlimited
casts. Unbuffed projections therefore cannot establish whole-fight safety.

## Memory, menus and save compatibility

Current compiled nine-language reference: `main_BSS_END = 0x801ce104`, heap
**187888 B**. The actual-archive story sweep checked 320 setups with no failures;
its smallest recorded margin was **3168 B on screen 207**. These are baseline
measurements, not HARD certification. The full disc pipeline was stopped at
the language-patch stage; no completed HARD build or emulator test is claimed.

| Approach | Resident rule-data estimate | Additional work / uncertainty |
|---|---:|---|
| A | 8 signed-16-bit fields = 16 B | Shared save/UI change; overlay scaling and damage helpers; existing raw snapshot storage can be reused |
| B | About 48 B including three factor rows and tier thresholds | Overlay tier classifier; authored exceptions, if chosen, need a separately budgeted mapping |
| C | About 26 B for A's fields plus five floor parameters | Overlay partner-stat sampling and floors; avoid a persistent per-enemy cache |

Component sizing from the parked experiment found a 12-byte resident save-reader
increase and the 16-byte A rule extension: **28 B before alignment, strings and
other layout effects**. Reserve roughly 128 B resident for initial planning,
with overlay helpers likely hundreds of bytes, then measure the complete build.
Do not subtract whole-executable sizes across an English-only and a padded
multilingual build: their layouts differ.

The baseline `MENU_REL.BIN` is **54248 B**: 27 sectors at 2048 B gives 1048 B
until the next sector boundary. That is arithmetic headroom, not proof of
allocated disc space. The planned third value uses existing generic option
layout and unused language-row storage; no row or menu array needs to grow.
Budget roughly 80–160 B of menu code/text before locale padding. Verify both
actual overlay bounds and the neighboring ending overlay when packaging.

UI plan: EASY / NORMAL / HARD in the existing DIFFICULTY row and title options,
all nine translations, all supported font modes. Eight languages retain 2 MB
support; Chinese retains its existing 8 MB/dedicated-font requirement. Check
long labels, selected-value coloring and the original-font layout visually.

Save plan: retain option byte 10, NORMAL=0 and EASY=1, with HARD=2. Missing or
invalid legacy difficulty defaults to NORMAL; explicit saved EASY remains EASY.
Keep the existing title-header and tagged-record copies and their lengths,
including explicit title-option precedence on Continue. Older game versions
interpret the new value as NORMAL. No new record, save-version bump or growth
migration is needed. Round-trip and legacy-save tests are required after review.

## HP/MP finding and proposal: retain current growth

The first-life report is **8005 HP / 9520 MP**, with Offense/Defense/Speed
650–820 and no chips. HP/MP use ten times the other stat units: normalized
values are **800.5 HP / 952 MP**. HP lies within that band; MP is 16–46% higher.
Both remain below the original game's 9999 HP/MP ceiling. This is not evidence
of a tenfold balance error, and no general HP/MP reduction is proposed.

| Source | Current numeric contribution |
|---|---|
| Pukumon evolution targets | 8000 HP / 7000 MP / 800 O / 800 D / 700 S / 700 B |
| Evolution formula | Below target, average old and target; at/above it, add target/10. Targets are not flat +8000/+7000 awards |
| Gym base | 100 HP/MP versus 10 other points before affinity, level and bonuses; x5 repeats five sessions with their costs |
| Pukumon normal Mega gym | HP +130 with +2 O; MP +110 with +2 D; Speed +15 plus +15 HP; Brains +11 plus +11 MP |
| Single-enemy battle floor | +50 HP/MP against 5000 in that stat, or +99 against 9999; normalized 5/9.9, comparable to typical +5/+9 other-stat floors |
| Ordinary chips (excluded by report) | +500 HP/MP versus +50 other stats |
| Foods | Deluxe Mushroom +100 HP/MP and +10 other stats; targeted fruit +200 HP/MP or +20 another stat; Black Trout +10 HP/MP and +1 others |
| Restaurant | Best Digitamamon result +70 HP/MP and +7 other stats |
| Training foods | Digipine ×1.5 or targeted ×1.2 boosts; recruitment/manual/counter bonuses can also apply |
| Rebirth | Zero inherited gain on a first life |

An exact **constructed arithmetic example**, not the player's reconstructed
history, uses no chips, food, gym bonuses or post-evolution battles:

| Step | HP | MP | O | D | S | B |
|---|---:|---:|---:|---:|---:|---:|
| Assumed pre-Pukumon state | 4740 | 4890 | 500 | 500 | 500 | 500 |
| After actual evolution blend | 6370 | 5945 | 650 | 650 | 600 | 600 |
| After 12 HP, 32 MP, 5 Speed and 5 Brains ordinary sessions | **8005** | **9520** | **674** | **714** | **675** | **655** |

The 54 sessions use Pukumon's actual offense-speed affinity and Mega multiplier,
including Brains' use of MP affinity. Its Mega evolution adds 120 lifetime hours;
54 training hours are not inherently impossible before allocating care and
sleep. A complete first-life route, evolution picker and care schedule have
not been replayed. Its current parents include Dragomon, MarineDevimon and
Divermon; earlier training/evolution and food or battles could contribute too.
A screenshot and the absence of chips cannot identify the exact source mix.

Proposal: keep global HP/MP gains and all other growth unchanged. If further
first-life playtests show a normalized MP excess, log evolution, training,
battle and food contributions separately before proposing a targeted adjustment.
Do not introduce a literal 999-HP knee or treat large raw HP/MP numbers as proof
that all stats should grow more slowly.

## Evidence and next decision

Numeric sources: [battle formulas](content/tables/battle-formulas.json),
[type factors](content/tables/type-factors.json),
[Thunder Justice](content/techniques/8-thunder-justice.json),
[training](content/tables/training.json),
[training gains](content/tables/training-gains.json),
[evolution rules](content/tables/evolution-rules.json),
[Pukumon](content/species/401-pukumon.json), owned map placements and the
Horizon challenge scripts. Integer calculations use the existing audit's
`damage`/signed-truncation functions. The table parameters and formulas above
fully specify A/B/C; no game code is needed to evaluate them.

Review the fixed-world versus partner-following tradeoff and A's factors before
implementation. If approved, validate unchanged EASY/NORMAL, raw-stat rewards,
repeated battle/flee restoration, finisher power, legacy/new saves, all supported
languages/fonts, a full multilingual 2 MB build, `main_BSS_END`, heap/MENU_REL
budgets and selftest. Then play actual boss, wild, Horizon and tournament
fights with these profiles and record TTK, total damage taken, buff use,
finishers, healing and MP. Physical hardware and all proposed HARD runtime
behavior remain untested.

**Current deliverable: this proposal only. No game code or push.**
