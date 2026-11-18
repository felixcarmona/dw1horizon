#!/usr/bin/env python3
"""Exercise the patched C cold loader on the host, including cache invalidation.

python3 tools/dev/playtest/cold_cache_host.py build/decomp-int
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    tree = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/decomp-int')
    source = (tree / 'src/main/mod_species.c').read_text()
    body = source[source.index('uint32_t MOD_COLD_PENDING;'):source.index('/* MOD (species rules as data)')]
    preamble = r'''
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <stdio.h>
typedef struct { int animId, animFrame, frameCount, loopCount, animFlag; } Anim;
typedef struct { int type; Anim anim; } Entity;
static struct { struct { Entity entity; } digimonEntity; } PARTNER_ENTITY;
static uint8_t COLD_ANIM_BUFFER[8192], cache[65536], PARTNER_MODEL_BUFFER[1];
typedef struct { int pixelPage, clutPage, pixelOffsetX, pixelOffsetY, modelId, useCount; uint8_t *mmdPtr; } ModelComponent;
static ModelComponent PARTNER_MODEL;
#define COLD_ANIM_MAX 8192
#define COLD_CACHE cache
#define COLD_CACHE_SECTORS 32
static int MOD_COLD_CACHE_TYPE = -1, GAME_STATE, queued, blocked, starts;
static uint8_t *busy;
uint8_t *loadColdAnimation(void *, uint32_t, int32_t);
static void tickFileReadQueue(int n) { (void)n; *busy = 0; }
static int getDigimonModelRef(int t, char **file, int *sector, int *size) {
 (void)t; *file = "DIGI.DAT"; *sector = 100; *size = 90000; return 1;
}
int32_t addFileReadRequestSection(char *p, uint8_t *b, int32_t o, int32_t n, uint8_t *flag, int32_t a, int32_t c) {
 (void)p;(void)o;(void)n;(void)a;(void)c; assert(b == COLD_ANIM_BUFFER);
 busy = flag; *busy = 1; queued++; return 1;
}
static void readFileSectors(char *p, uint8_t *b, int o, int n) {
 (void)p;(void)o;(void)n; assert(b == COLD_ANIM_BUFFER); blocked++;
}
void startAnimation(Entity *e, uint8_t slot) {
 assert(loadColdAnimation(e, 0x81000004, slot) == COLD_ANIM_BUFFER + 16); starts++;
}
'''
    checks = r'''
int main(void) {
 Entity *e = &PARTNER_ENTITY.digimonEntity.entity;
 uint32_t a = 0x81000004, b = 0x81000200;
 e->type = 241;
 assert(loadColdAnimation(e, a, 0x16) == NULL && queued == 1);
 assert(MOD_COLD_PENDING == a && !(e->anim.animFlag & 1) && e->anim.frameCount == 0x7fff);
 tickFileReadQueue(0); tickColdAnimation(e); assert(starts == 1);
 for (int i=0;i<35;i++) assert(loadColdAnimation(e,a,0x16) == COLD_ANIM_BUFFER+16);
 assert(queued == 1 && blocked == 0);
 // Same entry under a different slot must not reuse the old slot's key.
 assert(loadColdAnimation(e,a,0x17) == NULL && queued == 2);
 tickFileReadQueue(0);
 assert(loadColdAnimation(e,b,0x19) == NULL && queued == 3);
 tickFileReadQueue(0);
 assert(loadColdAnimation(e,a,0x16) == NULL && queued == 4);
 // Cancelled playback still leaves a valid buffer when its read finishes.
 MOD_COLD_PENDING = 0; tickFileReadQueue(0);
 assert(loadColdAnimation(e,a,0x16) == COLD_ANIM_BUFFER+16 && queued == 4);
 // Same-species model reload invalidates; a different species cannot inherit it.
 invalidateColdAnimation();
 assert(loadColdAnimation(e,a,0x16) == NULL && queued == 5);
 invalidateColdAnimation(); assert(COLD_READ_BUSY && !MOD_COLD_PENDING && !COLD_READY);
 e->type = 373;
 assert(loadColdAnimation(e,a,0x16) == NULL && queued == 6);
 invalidateColdAnimation();
 // Blocking writes replace the queued cache as well.
 GAME_STATE = 1;
 assert(loadColdAnimation(e,b,7) == COLD_ANIM_BUFFER && blocked == 1);
 assert(loadColdAnimation(e,b,7) == COLD_ANIM_BUFFER && blocked == 1);
 assert(loadColdAnimation(e,a,0x16) == COLD_ANIM_BUFFER+16 && blocked == 2);
 MOD_COLD_CACHE_TYPE = e->type;
 // HP beyond the previous 32 KB limit now starts in expanded RAM.
 assert(loadColdAnimation(e,0x81002200,0x1b) == cache+34816 && blocked == 2);
 invalidateColdAnimation(); assert(MOD_COLD_CACHE_TYPE == 0);
 PARTNER_MODEL.useCount = 7;
 COLD_READY = a; MOD_COLD_PENDING = a; MOD_COLD_CACHE_TYPE = e->type;
 ModelComponent *model = initializePartnerModel();
 assert(model == &PARTNER_MODEL && model->useCount == 7);
 assert(model->pixelPage == 0x15 && model->clutPage == 0x7a01 && model->pixelOffsetX == 0);
 assert(model->pixelOffsetY == 0x80 && model->modelId == 0 && model->mmdPtr == PARTNER_MODEL_BUFFER);
 assert(!COLD_READY && !MOD_COLD_PENDING && MOD_COLD_CACHE_TYPE == 0);
 puts("PASS: restarts, slots, overwrite, cancellation, model reload, blocking and expanded cache");
}
'''
    assert int(re.search(r'#define COLD_CACHE_SECTORS\s+(\d+)', source)[1]) == 32
    model = (tree / 'src/main/model.c').read_text()
    assert model.count('invalidateColdAnimation();') == 2 and model.count('m = initializePartnerModel();') == 2, 'cover sync load, async load and apply'
    helper = model[model.index('static __attribute__((noinline)) ModelComponent *initializePartnerModel'):model.index('ModelComponent *loadMMD(int32_t digiType, int32_t modelType)\n{')]
    with tempfile.TemporaryDirectory() as tmp:
        c, exe = Path(tmp) / 'cold.c', Path(tmp) / 'cold'
        c.write_text(preamble + body + helper + checks)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
