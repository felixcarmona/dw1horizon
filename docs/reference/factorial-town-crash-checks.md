# Factorial Town crash checks

## File City Andromon

The v0.0.6 File City service calls `andromon.talk()` when the partner is not
Mamemon. That dispatches the same recruited-Andromon hook again, without a
textbox or a yield. The result is a script loop, not a failed model load.

PR #231, commit `175050c4`, replaces that call with the original city greeting
and returns. It is already on main. The Gear reading on screen 157 is a separate
hook; its archive flag does not select the faulty File City branch.

The final v0.0.6 release image has SHA-1
`bc729710bdc57f23fc8f4f0754951aba5ae93cc2`. English DuckStation at 2 MB and 100%
CPU reproduces the File City loop with Agumon and Beelzemon (403). The Beelzemon
case follows an actual completed Gear reading, with the Gear retained.

On main `17f7cf4d`, both Agumon and Beelzemon finish the archive reading, retain
the Gear, recruit Andromon through his native conversation, receive the File
City greeting and return to free field control. The existing five File City
service tests also pass, including the unchanged Mamemon remodeling outcomes.

## Guardromon after reload

Screen 162 is the remodeling room. It has a service Guardromon and two ordinary
wild guards. The service is already excluded from ordinary wild encounters in
v0.0.6. Screen 158 also has a nighttime group of three Guardromon.

Main additionally keeps the ordinary guards away while Datamon awaits
recruitment in room 162. Recruit Datamon and re-enter to test the roaming guards.
The generated setup tests extended recruit trigger `33062` (`0x8000 + 294`).
Confusing this state with a missing NPC or failed load produces an invalid test.

On the release disc, a memory-card Continue into room 162 with Beelzemon loads
both roaming guards, runs their techniques, awards the win and returns to field
control. A subsequent predefined battle naming all three loaded Guardromon also
wins without assisted damage. These checks did **not** reproduce the reported
crash. They do not establish its root cause.
The release-disc stress check also completes with all four first Beelzemon
technique slots equipped (`0x2e` through `0x31`).

Main also completes that three-enemy stress encounter with Agumon and Beelzemon,
without assisted damage. The Beelzemon fixture equips all four first technique
slots. Its actual archive model is 99,480 bytes (99,464 on the release disc).

Main contains the post-v0.0.6 EFE initialization guard from `7810e037`. It fixes a
known quick-battle crash, but a passing v0.0.6 Guardromon fixture cannot establish
that this was the crash in the report. The original memory card, partner and
equipped techniques, and whether the reload used an emulator state, remain
necessary to identify that failure precisely.

## Reconstructing a fixture

Keep emulator states with their exact disc version. For the cross-version
comparison, boot each disc and Continue from a memory card instead.

```sh
python3 tools/dev/playtest/factorial_card.py INPUT.mcd build/guards.mcd \
  --partner 403 --scene guards
python3 tools/dev/playtest/factorial_card.py INPUT.mcd build/gear.mcd \
  --partner 3 --scene gear
python3 tools/dev/playtest/factorial_card.py INPUT.mcd build/city.mcd \
  --partner 3 --scene city
```

The input is a valid original one-block USA save supplied locally. The helper
sets the native factory progression, Gear/archive flags, a trained partner and
English options, then recomputes both checksums. Its scenes distinguish
Andromon before recruitment and the archive reading from his recruited city
visit. One-block saves cannot store Datamon's extended recruit bit; advance that
recruitment before the main remodeling-room battle check. A city visit still
uses Andromon's normal daylight schedule and random visit roll.

For a three-enemy stress encounter on room 162, use the existing predefined
battle registers immediately before its ordinary battle instruction: `p250=1`,
`p251=5`, `p252=6`, `p253=7`. These are the script IDs of the three loaded guards,
not their species IDs. Require all three entities to be present, observe
`ENEMY_COUNT=3`, then clear `p250` after returning to the field. This deliberately
includes the service NPC; it is a stress check rather than the natural encounter.
Clear trigger 1 too if it was set to prevent escape for the fixture.

## Memory evidence

For the nine-language build of `17f7cf4d`, `main_BSS_END=0x801ce124` and the
legacy heap check reports 187,856 bytes. Checking the actual disc's MAPHEAD and
DIGI.DAT covers 255 resident setup sections, all fitting; the tightest margin is
3,136 bytes on screen 207. Relevant conservative setup margins are:

| Screen | Scene | Margin |
|---|---|---:|
| 157 | Andromon's room | 156,456 B |
| 158 | Factory wild encounters | 61,400 B |
| 162 | Remodeling room | 34,480 B |
| 168 | File City | 67,352 B |

The fixture helper changes no C code or resident allocation. These margins
exclude a simple model-heap exhaustion explanation for the tested scene states;
they are not proof that every attack or emulator-state combination is safe.

The complete nine-language developer build produced image SHA-1
`7db6fdc55ebd9235e9ed250295925d81da45ac60`; a second build reproduced it.
Selftest passed 124 checks with four generated-input checks deferred during the
rebuild. All four deferred checks then passed: compiled city rosters, flat
sprites, all 126 balance tables and all 692 evolution-chart routes.

## KingSukamon loading regression (v0.0.8)

The `598f6a6f` baseline also completes both the ordinary two-guard encounter and
three-guard stress encounter with KingSukamon (120), Beelzemon (403), and
MegaGargomon (335), with quick battle both enabled and disabled. These twelve tests boot a native memory
card on a 2 MB emulator, enter through controller movement, let the partner fight
automatically, and require normal return to field control. Enemy HP changes and
attack animations rule out an idle enemy-AI explanation in these fixtures.

A controlled interpreter regression starts from the same KingSukamon room state
and baseline disc. With both existing EFE traversal guards active, the quick
three-guard battle finishes and returns to field control at battle frame 1214.
After verifying the battle overlay's instructions, replacing only the loading
branches in `BTL_tickEFEEngine` and `BTL_renderEFEEngine` with NOPs stalls the
same encounter at frame 54, with `MOD_BATTLE_LOADING=2`. The frame remains
unchanged for more than 150 seconds; the CPU reaches the exception vector.
This isolates traversal during asynchronous effect initialization as a sufficient
cause of a loading freeze. Keep both guards from `7810e037` and `ce7dc4a9`.
This RAM-only negative test does not identify the player's exact failure: the
original save state and its matching executable were not available.

Guardromon's first five techniques remain the original disc's Prominence Beam,
Megaton Punch, Power Crane, All Range Beam and Full Potential. The battle's
normal `usedMoves` collection records enemy techniques without excluding the
service NPC or predefined encounters. Native learning still checks the partner's
specialties, allowed techniques, existing knowledge and learning roll. No NPC
flags, technique lists, battle outcomes or learning rules are changed.

MegaGargomon learns Full Potential during the quick-off three-guard test with the
normal learning chance: its previously cleared learned bit becomes set after the
battle. A separate quick-off two-guard fixture leaves only All Range Beam unknown,
equips known techniques, and sets that technique's primary-specialty learning
chance to 100 in RAM. It also learns through the native post-battle code and
returns to field control after the normal medal dialog. The guaranteed roll is
only a test fixture; the shipped learning chances remain unchanged.
