# Quick battle start and melee techniques

QUICK BATTLES starts combat while sounds and technique effects load. Fighters may
choose a move and approach their target during this time, but must wait before
starting its animation, charging MP or executing its effect.

`BTL_startQueuedMove` already enforced this wait for ranged attacks and buffs.
`BTL_tickMeleeAttack` has its own execution path and bypassed that guard. A melee
attack could start with all four effect slots still set to `-1`: its MP charge
was applied, but there was no loaded effect to hit the enemy. This was ordinary
battle AI acting after the shortened intro, rather than an overworld command
surviving battle initialization. It affected enemy melee attacks too.

The melee path now waits at contact, before changing attack or finisher state.
Its out-of-range finisher path also waits. Approach movement and the queued move
are preserved, so execution can resume when the effects are ready. The loader is
unchanged: music, sound bank and voices finish staging through `GENERAL_BUFFER`
before the EFE engine and technique effects use that memory.

The change lives in `BTL_REL` and adds no persistent state. In full eight-language
builds, `main_BSS_END` remains `0x801ceb00` and the heap remains 185328 bytes:
0 bytes of main heap lost. Run the regression against a prepared patched tree:

```sh
python3 tools/dev/playtest/quick_battle_start_host.py build/decomp-dev
```

This compiles the actual melee function with host observers. It exercises both
loading phases, approach movement, the preserved queue, MP charging, cooldowns
and the finisher charge/hold/execute sequence. The unchanged source fails its
first loading assertion.

For an emulator reproduction, use original 2 MB RAM and compare QUICK BATTLES on
and off from the same pre-encounter state. Equip a melee technique such as Sonic
Jab on Agumon, place the partner within contact distance, and use a trained
partner whose charge can complete before the battle assets finish loading.
Log `MOD_BATTLE_LOADING`, `BATTLE_FRAME_COUNT`, the fighter's queued animation and
effect slots, partner MP and target HP at `BTL_setupMoveExecution`. Before the
fix, execution can occur in loading phase 1 or 2 with slot `-1`; after the fix it
must first occur with loading 0 and a valid slot. Also check a ranged technique,
a scripted NPC battle, and more than one partner. A technique that misses after
loading is complete still legitimately costs MP.
