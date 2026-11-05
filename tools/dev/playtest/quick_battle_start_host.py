#!/usr/bin/env python3
"""Exercise the real melee attack function while quick-battle assets load.

Usage: python3 tools/dev/playtest/quick_battle_start_host.py build/decomp-dev
The source function is extracted verbatim; the host stubs observe side effects.
"""
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    source = (Path(sys.argv[1]) / 'src/btl/battle_main.c').read_text()
    start = source.index('int32_t BTL_tickMeleeAttack(DigimonEntity *digimon, DigimonEntity *target, FighterData *fighter, int16_t arg3)\n{')
    end = source.index('\nvoid BTL_tickRangedAttack(', start)
    function = source[start:end]
    harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
#define FIGHTER_FLAG_ATTACKING 32
#define BM(name) 10
#define DIGI_PARA(type) para[type]
typedef struct { int x, y, z; } VECTOR;
typedef struct { struct { int16_t vy; } rotation; VECTOR location; } PositionData;
typedef struct { int animFlag; } Anim;
typedef struct { int type; PositionData *posData; Anim anim; } Entity;
typedef struct { int mp; } Stats;
typedef struct { Entity entity; Stats stats; } DigimonEntity;
typedef struct { int flags, queuedAnim; } FighterData;
struct { int radius; } para[2] = {{120}, {120}};
Entity *ENTITY_TABLE[2], *FINISHING_ENTITY;
int8_t MOD_BATTLE_LOADING;
int NO_AI_FLAG, BTL_FINISHER_TIMER, BTL_FINISHER_AURA_ID;
int distance, animations, executions, auras, walking, cooldown, tech, chargeups;
void handleBattleIdle(DigimonEntity *d, Stats *s, int f) { (void)d; (void)s; (void)f; }
uint32_t BTL_getDistanceSquared(Entity *a, Entity *b) { (void)a; (void)b; return distance; }
void entityLookAtLocation(Entity *e, VECTOR *v) { (void)e; (void)v; }
int entityGetTechFromAnim(Entity *e, int a) { (void)e; (void)a; return tech; }
void BTL_initializeFinisherChargeup(int t) { (void)t; chargeups++; }
void startAnimation(Entity *e, int a) { (void)e; (void)a; animations++; }
int BTL_addFinisherAura(Entity *e, int t) { (void)e; (void)t; auras++; return 1; }
int BTL_isMoveOnCooldown(Entity *e, FighterData *f) { (void)e; (void)f; return cooldown; }
void BTL_setupMoveExecution(DigimonEntity *d, DigimonEntity *t, FighterData *f) {
    (void)t; (void)f; executions++; d->stats.mp -= 18;
}
void BTL_setWalking(Entity *e, Stats *s, int f) { (void)e; (void)s; (void)f; walking++; }
int entityCheckCollision(void *a, Entity *e, int x, int y) { (void)a; (void)e; (void)x; (void)y; return -1; }
'''
    checks = r'''
int main(void) {
    PositionData pos[2] = {0};
    DigimonEntity d = {{0, &pos[0], {0}}, {3000}};
    DigimonEntity t = {{1, &pos[1], {0}}, {700}};
    FighterData f = {64, 51};
    ENTITY_TABLE[1] = &d.entity;
    /* Both staging phases: no animation, MP charge, effect, finisher lock or aura.
       The queued move survives so the same call can start it once loading ends. */
    for (int loading = 1; loading <= 2; loading++) {
        MOD_BATTLE_LOADING = loading;
        distance = 100;
        BTL_tickMeleeAttack(&d, &t, &f, 0);
        assert(d.stats.mp == 3000 && !animations && !executions);
        assert(f.flags == 64 && f.queuedAnim == 51 && !NO_AI_FLAG);
        distance = 1000000;
        BTL_tickMeleeAttack(&d, &t, &f, 0);
        assert(walking == loading); /* approach still runs during loading */
        NO_AI_FLAG = 1; FINISHING_ENTITY = &d.entity;
        BTL_tickMeleeAttack(&d, &t, &f, 0);
        assert(!animations && !executions);
        NO_AI_FLAG = 0;
        distance = 100; tech = 0x3a;
        BTL_tickMeleeAttack(&d, &t, &f, 0);
        assert(!NO_AI_FLAG && !auras && !chargeups && !animations);
        tech = 43;
    }
    MOD_BATTLE_LOADING = 0; distance = 100;
    cooldown = 1;
    BTL_tickMeleeAttack(&d, &t, &f, 0);
    assert(!animations && !executions && d.stats.mp == 3000);
    cooldown = 0;
    BTL_tickMeleeAttack(&d, &t, &f, 0);
    assert(animations == 1 && executions == 1 && d.stats.mp == 2982);
    assert(f.flags & FIGHTER_FLAG_ATTACKING);
    /* The original finisher charge/hold/execute sequence still works when ready. */
    f.flags = 64; tech = 0x3a;
    BTL_tickMeleeAttack(&d, &t, &f, 0);
    assert(NO_AI_FLAG && chargeups == 1 && auras == 1 && executions == 1);
    BTL_tickMeleeAttack(&d, &t, &f, 0);
    assert(BTL_FINISHER_TIMER == 9 && executions == 1);
    distance = 1000000; BTL_FINISHER_TIMER = 0;
    BTL_tickMeleeAttack(&d, &t, &f, 0);
    assert(executions == 2);
    puts("ok: both loading phases, approach, queued move, MP, cooldown and finisher");
}
'''
    with tempfile.TemporaryDirectory(prefix='quick-battle-host-') as directory:
        cfile = Path(directory) / 'test.c'
        binary = Path(directory) / 'test'
        cfile.write_text(harness + function + checks)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Werror', '-Wno-unused-variable',
                        str(cfile), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
