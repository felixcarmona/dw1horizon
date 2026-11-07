# Battle hit investigation

The crowned golden partner is KingSukamon (120). Its partner model uses
Sukamon's native animation rig at 171/100 scale. Fast Poop Toss is technique
50, equipped through animation slot 48 on these two species. Its launch origin
borrowed Sukamon's effect row at 171/100 scale (`content/tables/effect-donors.json`)
in this investigation's baseline, raising the visual release point. The
subsequent [KingSukamon correction](../mods/kingsukamon.md)
lowers the shared hand-toss origin to native release height without resizing
the model. The EFE motion script is unchanged; the enlarged origin alone does
not establish an arc defect.

The original USA game lands this technique on Tsukaimon (96). The historical
Horizon baseline also lands it with KingSukamon. The native trial has
three damaging casts and four zero-damage casts at release gaps of 651–674
units; KingSukamon lands casts at about 673–680 units too. Native misses are
therefore present at comparable distances. The native
EFE chunk and the built chunk are identical. Its projectile collision box has
half-extents of 100, 700 and 100 units; the elevated visual alone does not
establish a vertical collision failure. Technique 50 retains its native
accuracy value of 40. Random misses and a moving target must be distinguished
from a reproducible model-size defect before changing aiming or hit boxes.

Knightmon (321) equips Megaton Punch, Counter and Buster Dive in its first
three map slots. Its Buster Dive already receives the native dash repair
introduced before v0.0.6; see [the reach audit](../mods/buster-dive.md).
The baseline Knightmon's Buster Dive damages a defending KingSukamon, but
isolating Megaton Punch reproduces repeated misses. Native Andromon's isolated
punch damages the same partner. Runtime line-hit traces show Knightmon's
endpoint about 282 units behind its body during animation frames 12–15, the
native effect's active window. The clip's forward strike occurs later.

The imports registry repairs Megaton Punch on five species:

| Species | Clip repair |
|---|---|
| Knightmon (321) | Share its existing Pulse Laser arm clip |
| Bastemon (432) | Share its existing Muscle Charge arm clip |
| Fujinmon (317) | Retime its Power Crane strike |
| Pharaohmon (319) | Retime its existing punch strike |
| Raijinmon (333) | Retime its Power Crane strike |

The reach follow-up also repairs Buster Dive on Zudomon (219), Diaboromon
(237) and Beelzemon (403). Their old clips had no dash; a separate full body
program exceeded the resident buffer. A close first cast can hit, but after
knockback repeated casts at the AI's longer launch gap miss. The range defect
is distinct from an absent effect or a move that can never cause damage. Compact body-pose recipes now retain the
exact native root track and fit the existing buffers; see the
[reach audit](../mods/buster-dive.md).

These are clip selections and timing recipes in
`content/models/imports/models.json`. The moves, technique parameters, effect
files, collision sizes, mesh, textures and runtime C remain unchanged.
`tools/models/technique_timing.py` maps output pose samples to reviewed source
samples after field overlays and the Buster Dive pass. Recipes pin the source
program and preserve its duration, first and last pose; sound and texture
events follow the timing map. Only the selected attack slot is replaced.
Storage checks reject resident or streamed animation overflow. There is no
runtime animation fallback.

The timing map uses zero-based sample pairs `[output, source]`. For example,
Pharaohmon's native collision frames 12–15 receive source samples 33–36 rather
than the earlier wind-up. This aligns visible acting with the existing hit
window instead of extending the window or forcing a successful accuracy roll.

## Repeating the runtime checks

Use the executable matching the built disc and a separate emulator home:

```sh
export DW_SYMS="$PWD/build/battle-hits/exe/SLUS_010.32"
export EMU_PORT=39282 EMU_HOME="$PWD/build/emu-39282"
python3 -m tools.dev.playtest.battle_hits build/battle-hits.cue \
  build/battle-hit-proof --ids 321 40 --partner 120 --seconds 40 --video
python3 -m tools.dev.playtest.toss_hits build/battle-hits.cue \
  build/toss-hit-proof --partner 120 --distance 800 --seconds 30 --trials 2
```

The enemy fixture replaces Native Forest's first ModokiBetamon before model
loading and entity initialization. It preserves the native model-loading
bookkeeping for unloading, omits other opponents, and places the fighters
beside the loaded camera. Models, animations, effect files, AI, accuracy and
damage use the built game. Test health, stats and equipped slots are fixtures;
HP loss is measured rather than injected. With `--clear-path`, the tamer moves out of the attack corridor so spectator
collision does not block a dash. The enemy check requests Defend
and equips no partner attacks. The toss check disables enemy attacks but
allows movement. Both reject the emulator's 8 MB expansion and require a
2,097,152-byte RAM dump.

`battle_hits --all --until-hit --seconds 90` checks each imported species' first three map attacks.
A passing group proves that the loadout can cause damage; it does not prove
that each individual move connects. `--technique 46` selects each species' Megaton Punch slot. `--slots 46,48` starts separate battles
for those individual animation slots, loading their effects before combat.
`--until-hit` ends a damage audit after an observed hit and cannot be combined
with fixed-duration video. Counter requires an attacking opponent and cannot be proved by a defending
fixture. Native Agumon with `--partner 3 --partner-attack 51` exercises it through
Sonic Jab; both Knightmon and native Andromon reflect real damage in that test. Buffs likewise should not be judged by outgoing damage. A short run
with no HP loss is a candidate for a longer controlled reproduction, not
proof of a broken technique.

Each result records species, slots, partner stats, logic frames, technique,
loaded effect ID, animation, movement and target HP. Snapshots and optional
video permit review. Fixture timeouts are distinct from in-game misses.

The targeted timing tests are `python3 -m unittest tools.test_technique_timing`.
They verify contact samples, unchanged slots and mesh, retained events, storage
bounds, and rejection of unreviewed sources or invalid timing maps.

## Audit and battle evidence

The static audit covers 175 imported species and 2192 technique slots. Every
slot is present. The runtime loadout audit observes damage from all 175 imports;
that proves each tested loadout has a damaging attack, not that every move
works. Of 102 imported Megaton Punch users inspected offline, 26 geometric
candidates were tested individually and five defects reproduced. The current
Buster Dive roster has 68 imports; the three storage exceptions were tested
individually. Eight looping Kimeramon clips were flagged statically, but its
loadout deals damage, so a loop alone did not justify a change.

Fresh baseline (`c8ed3594`) and repair revision `8f18e467` trials measure
these HP losses. They predate the later damage-curve and HUD changes:

| Species | Technique | Baseline | Repaired |
|---|---|---:|---:|
| Knightmon (321) | Megaton Punch | 0 | 3739 |
| Fujinmon (317) | Megaton Punch | 0 | 1858 |
| Pharaohmon (319) | Megaton Punch | 0 | 3258 |
| Raijinmon (333) | Megaton Punch | 0 | 2798 |
| Bastemon (432) | Megaton Punch | 0 | 3795 |
| Zudomon (219) | Buster Dive | 558 | 3582 |
| Diaboromon (237) | Buster Dive | 558 | 3000 |
| Beelzemon (403) | Buster Dive | 0 | 4134 |

Punch trials use KingSukamon and 45-second recordings; dash trials use native
Agumon and 60-second recordings. Normal AI, accuracy and damage remain active.
Logic-frame counts vary with emulator throughput, so these totals establish
connectivity rather than compare damage per second. All five repaired punches
also connect against small native Agumon in separate trials.

Zudomon and Diaboromon's baseline damage comes from the closer first cast.
Zudomon then misses nine later active windows at about 797 units; Diaboromon
misses twelve completed later casts at about 756 units. Their repaired clips
continue to damage after knockback, including launches at 752–801 units.
Beelzemon's baseline has ten non-damaging casts at gaps 665–778 units. Native
Patamon's unchanged Buster Dive causes 4224 damage in the same 2 MB fixture.
Native accuracy can still produce misses after repair; no hit is forced.

The actual packed models preserve every non-selected slot's live program bytes,
mesh and texture. Only eight imported model pins change; all texture pins stay
the same. That revision's full nine-language build retains `main_BSS_END = 0x801ce5e0`, a
186640-byte heap and 30288 bytes free on the tightest swept screen. All battle
proof uses the emulator's original 2 MB configuration, without its expansion.
