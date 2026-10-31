#!/usr/bin/env python3
"""Run the patched field battle loop on the host with deterministic tick events.

Usage: python3 tools/dev/playtest/timed_battle_host.py build/decomp-int
The function under test is extracted verbatim from the supplied patched source.
"""
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    source = (Path(sys.argv[1]) / 'src/btl/battle_main.c').read_text()
    start = source.index('int32_t BTL_battleMain(void)\n{')
    end = source.index('\nint16_t BTL_getAttackTech', start)
    function = source[start:end]
    harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
#define PSTAT_BATTLE_TIME_LIMIT 242
#define PSTAT_BATTLE_TIMED_OUT 241
#define FIGHTER_FLAG_ATTACKING 32
#define FIGHTER_FLAG_KNOCKED_BACK 16
#define FIGHTER_FLAG_BLOCKING 128
typedef struct { int flags, hpDamageBuffer; } FighterData;
struct { FighterData fighter[4]; struct { int currentCommand[2]; } player; } combat;
#define COMBAT_DATA_PTR (&combat)
struct { struct { struct { struct { int currentHP; } current; } stats; } digimonEntity; } PARTNER_ENTITY;
int COMBAT_AREA_X, COMBAT_AREA_Y, DRAWING_OFFSET_X, DRAWING_OFFSET_Y;
int BATTLE_FRAME_COUNT, NO_AI_FLAG, ENEMY_COUNT;
void *FINISHING_ENTITY;
int pstat[256], scenario, deinit_frame;
void *ENTITY_TABLE[2];
void BTL_getRemainingEnemies(void *entity, int16_t *enemies, int16_t *count) {
    (void)entity; (void)enemies;
    *count = scenario == 10 && BATTLE_FRAME_COUNT >= 20 ? 0 : 1;
}
int readPStat(int n) { return pstat[n]; }
void writePStat(int n, int v) { pstat[n] = v; }
void BTL_initializeCombat(void) {}
void BTL_handleBattleIntro(void) {}
int BTL_isBattleFinished(void) {
    if (scenario == 6 && BATTLE_FRAME_COUNT == 22) {
        PARTNER_ENTITY.digimonEntity.stats.current.currentHP = 0;
        return 1;
    }
    return BATTLE_FRAME_COUNT >= 30 || (scenario == 7 && BATTLE_FRAME_COUNT >= 20);
}
void BTL_tickPartnerAI(void) {}
void BTL_tickEnemyAI(void) {}
void BTL_tickFighterStates(void) {
    int f = BATTLE_FRAME_COUNT;
    if (scenario == 1 || scenario == 6) {
        NO_AI_FLAG = f < 24;
        FINISHING_ENTITY = NO_AI_FLAG ? &combat : NULL;
    }
    if (scenario == 2) combat.fighter[ENEMY_COUNT].flags = f < 24 ? FIGHTER_FLAG_ATTACKING : 0;
    if (scenario == 3) combat.fighter[0].flags = f < 24 ? FIGHTER_FLAG_KNOCKED_BACK : 0;
    if (scenario == 4) combat.fighter[1].flags = f < 24 ? FIGHTER_FLAG_BLOCKING : 0;
    if (scenario == 5) combat.fighter[1].hpDamageBuffer = f < 24 ? 10 : 0;
    if (scenario == 8) FINISHING_ENTITY = f < 24 ? &combat : NULL;
}
void BTL_tickPartnerWaypointTrail(void) {}
void BTL_battleTickFrame(void) { assert(BATTLE_FRAME_COUNT < 100); }
void BTL_tickQuickStartText(void) {}
void handlePause(void) {}
void BTL_endQuickStartText(void) {}
void modBattleLoadFinish(void) {}
void removePauseBox(void) {}
void BTL_deinitializeCombat(void) { deinit_frame = BATTLE_FRAME_COUNT; }
'''
    checks = r'''
int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    for (scenario = 0; scenario <= 10; ++scenario) {
        combat = (typeof(combat)){0};
        BATTLE_FRAME_COUNT = 0; NO_AI_FLAG = 0; FINISHING_ENTITY = NULL;
        ENEMY_COUNT = 3;
        PARTNER_ENTITY.digimonEntity.stats.current.currentHP = 100;
        pstat[242] = scenario == 9 ? 0 : 1;
        pstat[241] = 1; /* a previous timeout must never leak into this battle */
        int r = BTL_battleMain();
        printf("scenario %d: teardown tick %d, result %d, timed out %d, finisher lock %d\n",
               scenario, deinit_frame, r, pstat[241], NO_AI_FLAG);
        assert(pstat[242] == 0);
        if (scenario == 6) { assert(r == -1 && !pstat[241]); }
        else if (scenario == 7 || scenario == 9 || scenario == 10) { assert(r == 1 && !pstat[241]); }
        else {
            assert(r == 1 && pstat[241] == 1);
            assert(deinit_frame == (scenario == 0 ? 20 : 25));
            assert(!NO_AI_FLAG && !FINISHING_ENTITY);
            for (int i=0; i<=ENEMY_COUNT; ++i)
                assert(!combat.fighter[i].flags && !combat.fighter[i].hpDamageBuffer);
        }
    }
}
'''
    build=Path(__file__).resolve().parents[3] / 'build'
    build.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='timed-battle-',dir=build) as temp:
        c = Path(temp) / 'test.c'; exe = Path(temp) / 'test'
        c.write_text(harness + function + checks)
        subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
