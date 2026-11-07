# KingSukamon's launch point and techniques

KingSukamon (120) keeps its Sukamon rig at 171/100 scale, radius 279 and
height 496. Fast Poop Toss's hand origin now uses bone 12 at
`[-127, -160, -60]`, replacing the scaled `[35, -20, 0]` donor offset.
At the release pose this lowers the projectile to native Sukamon height
while retaining KingSukamon's horizontal release point. The mesh and all
55 existing animation slots are byte-identical. Two shared animation-table
references add 8 bytes to the model, from 77,138 to 77,146 bytes.

The local offset comes from transforming a 232-unit downward displacement
back through the hand's release-pose rotation, holding world X/Z fixed.
Runtime traces measure the release at animation frame 22: native Sukamon
and corrected KingSukamon both launch 297 units above the caster's position;
baseline KingSukamon launches at 529.

The donor row is specific to species 120. Sukamon (39) and the preserved
KingSukamon scene model (463) are unchanged. Poop Rnd Toss, Rnd Spd Toss and
Party Time use the same donor hand point and receive the same local offset;
other effect origins keep their previous scaling. No technique's power,
accuracy, collision box, projectile script or animation program changes.

KingSukamon gains Ice and Nature alongside Filth. Ice is the game's category
for water techniques. Water Blit is a thrown water shot; Poison Powder
extends its noxious spray into a nature cloud. Both borrow Whamon's existing
`[2, 60, 0, 10]` effect row, mapped to the entity point `[0, 0, -297, -300]`.
The existing donor table holds 13/16 entries and 12/24 origin mappings.

| Technique | Slot | Shared clip | Power | MP per cast | Accuracy | Status chance |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Fast Poop Toss | 48 | Existing toss | 122 | 96 | 40 | 11% |
| Water Blit | 55 | Toss (48) | 211 | 102 | 74 | 0% |
| Poison Powder | 56 | Spray (47) | 117 | 171 | 77 | 62% |

MP per cast is three times the stored `mpCost`. At equal Offense/Defense,
neutral specialties and a 100% damage roll, direct damage equals the power
column. Poison ticks are additional. Technique identities, learning chances,
finisher slot 54 and the first nine moves remain in place. NEW DIGIMON off
keeps the previous nine-move loadout.

The specialties also change incoming element-factor sums:

| Incoming element | Before | After |
| --- | ---: | ---: |
| Fire | 40 | 42 |
| Battle | 40 | 40 |
| Air | 40 | 42 |
| Nature | 40 | 50 |
| Ice / water | 40 | 32 |
| Mech | 40 | 42 |
| Filth | 30 | 30 |

These sums enter the damage formula with divisor 30. Compared with its previous
specialties, incoming Ice/water's factor falls 20% and Nature's rises 25%.
KingSukamon's base stats and finisher power stay the same. Numbers come from the owned technique JSON,
`type-factors.json` and `tools.battle_audit.damage`.

## Repeating the battle audit

Use the executable matching the disc, a free emulator port and a private
emulator home. For each target 96 (Tsukaimon), 3 (Agumon) and 5 (Greymon), run:

```sh
export DW_SYMS="$PWD/build/kingsukamon/exe/SLUS_010.32"
export EMU_PORT=39462 EMU_HOME="$PWD/build/king-proof-home"
python3 -m tools.dev.playtest.battle_hits build/kingsukamon.cue \
  build/king-proof-96 --ids 120 --slots 48 --partner 96 \
  --seconds 120 --clear-path --video --trace
```

Repeat with `--ids 39` for native Sukamon. The fixture loads the selected
battle model before initialization, bypassing the field-only NPC twin
substitution. A defending target has no outgoing techniques; both sides use
fixed fixture stats and 30,000 HP. The game supplies model loading, motion,
projectiles, collision, accuracy and damage. Both the emulator expansion flag
and its raw RAM dump must confirm original 2 MB mode.

`--trace` observes the actual bone transforms, geometric contacts
(`BTL_calculateHitChance`) and direct hits (`BTL_calculateDamage`). It writes
`origins`, `contacts` and `hits` into `result.json`; it never changes a game
value. Each origin row contains battle frame, animation, animation frame,
bone, local xyz and xyz relative to the caster. Origins update during the
wind-up, so use the last transform before the projectile leaves. Direct-hit
counts exclude poison ticks, which can otherwise inflate HP-loss counts.

## Measured results

Each row is a 120-second recording with NEW DIGIMON on, NORMAL, 30 FPS and
quick battles off. Enemy Offense/Speed are 500; target stats are 400. Wall-time
throughput varies, so rates use completed releases, not damage per second.

| Target | Native hits / casts | King before | King after | Geometric contacts: native / before / after |
| --- | ---: | ---: | ---: | --- |
| Tsukaimon | 7/20 (35.0%) | 7/20 (35.0%) | 7/24 (29.2%) | 20/20 / 20/20 / 24/24 |
| Agumon | 11/24 (45.8%) | 7/27 (25.9%) | 4/15 (26.7%) | 24/24 / 27/27 / 15/15 |
| Greymon | 2/13 (15.4%) | 6/14 (42.9%) | 6/17 (35.3%) | 13/13 / 14/14 / 17/17 |

All 57 native, 61 baseline King and 56 corrected King releases make geometric
contact. Release height is 297 / 529 / 297 units respectively on every tested
target. The controlled baseline does not reproduce a vertical collision
failure; the correction measurably restores native launch height and retains
connectivity. These small samples do not establish an accuracy improvement.
The native accuracy value of 40 and its normal speed/guard rules remain active.
Moving-opponent hit rates and physical PlayStation hardware are untested.

A completed release has its final hand transform at animation frame 22.
Contact and damage calls are attributed within the following 50 logic frames;
a trailing release with no contact is excluded if that observation window has
not elapsed. This counts an already-observed release even when recording starts
partway through its wind-up. Random hits are distinct from geometric contact.

Separate 60-second 2 MB battles against Agumon exercise the shared origins and
added clips:

| Technique | Slot | Direct hits | Geometric contacts | HP loss |
| --- | ---: | ---: | ---: | ---: |
| Poop Rnd Toss | 50 | 1 | 7 | 84 |
| Rnd Spd Toss | 51 | 4 | 9 | 568 |
| Water Blit | 55 | 4 | 7 | 1336 |
| Poison Powder | 56 | 3 | 3 | 293 |

These totals prove effect/clip connectivity, not DPS equivalence. HP loss can
include poison ticks. Party Time must be exercised as the partner's charged
finisher: equipping slot 54 as an ordinary NPC attack does not schedule it.

Party Time also passes through the partner finisher path in original 2 MB mode:
slot 54 and effect 321 play and cause 1176 damage to Agumon. The fixture fills
the gauge, waits for `BTL_FINISHER_READY`, requests the finisher with Square
and supplies full charge, as the existing species-proof harness does. Damage
and projectile collision remain the game's own.

The full nine-language build keeps `main_BSS_END = 0x801ce104`, a 187888-byte
heap and 31536 bytes free on the tightest swept screen (OGRE03), all unchanged
from the baseline. No runtime C or patch-series changes are needed. All 183
import-provider and 38 record-original provider model/texture pins still match.

The complete `[48, 55, 56, 54]` loadout also runs in original 2 MB mode:
1757 logic frames, all four clips observed, 4577 actual HP loss. Both new
effects and the corrected toss coexist with Party Time in one battle.
The native generator reference for `SCUD-partner.MMD` changes from
`38048e8649f7d6725706722e5646857f1fc576ea` to
`38e56d19fc10faa835b6a515450e70c47dcf2251`; the change is the two shared
clip references. All other native model references remain unchanged.

Validation: full build, patch-series apply check and selftest pass
(129 checks, no failures or top-level skips). The two legacy prerequisite
skips inside the DWS unit group are unrelated to these content changes.
