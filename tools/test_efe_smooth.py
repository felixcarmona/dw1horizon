#!/usr/bin/env python3
"""Smooth battle effects (include/dw/mod_efe_smooth.h, docs/reference/frame-rate.md).

The header comes from its patch in mods/patches. Two checks:
- its draw table against the engines' own handlers: every listed sub-opcode is a draw, and the operand count is the
  number of values that handler takes off the script stack (in BTL, STD and VS alike);
- the header's code compiled for the host (x86-64, pointers kept below 2 GB so the PSX's int32_t pointer casts hold)
  and driven tick by tick: blending, the 20 fps and interpolation-off pass-through, cuts, restarts, live values, the
  short way round, the instance transform put back, the particle step.

Usage: test_efe_smooth.py [DECOMP]   (DECOMP: a decomp tree for the handler count check; default decomp/)
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = 'include/dw/mod_efe_smooth.h'
DECOMP = ROOT / 'decomp'

DRAWS = {3, 4, 20, 22, 24, 31, 60, 65, 66, 68, 70, 77, 79, 82, 85, 86, 87, 92}


def header_text():
    """The header as its patch creates it."""
    series = (ROOT / 'mods/patches/series').read_text().split()
    for name in series:
        text = (ROOT / 'mods/patches' / name).read_text(errors='replace')
        m = re.search(r'^diff --git a/%s b/%s\nnew file mode.*?\n@@[^\n]*\n(.*?)(?=^diff --git |\Z)' % (HEADER, HEADER),
                      text, re.S | re.M)
        if m:
            return '\n'.join(line[1:] for line in m.group(1).splitlines() if line.startswith('+')) + '\n'
    raise AssertionError('no patch in the series creates ' + HEADER)


STUBS = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
int32_t *EFE_DATA_STACK;
void *EFE_CURRENT_DATA_SEGMENT;
int32_t EFE_SCRIPT_HEAD = 0x80100000;
int32_t MOD_RENDER_PASS, MOD_RENDER_ALPHA = 4096, MOD_FPS_TICKS, MOD_INTERP_STATS[7];
int32_t MOD_FPS_MODE = 2, MOD_FPS_INTERP = 1, MOD_RENDER_CADENCE;
int8_t MOD_TICK_FAST;
'''


def host_source(header):
    body = re.sub(r'^#include <dw/[^>]*>\n', '', header, flags=re.M)
    return STUBS + body


DUMP = r'''
int main(void) {
	const uint8_t *d;
	for (d = MOD_SMOOTH_DRAWS; d[0] != 0; d += 2 + (((d[1] & 0x1f) + 1) >> 1)) {
		int n = d[1] & 0x1f, i;
		printf("%d %d %d", d[0], n, (d[1] & MSM_T) != 0);
		for (i = 0; i < n; i++) printf(" %d", (d[2 + (i >> 1)] >> ((i & 1) << 2)) & 15);
		printf("\n");
	}
	printf("limits %d %d %d\n", MSM_VALS, MSM_PTRS, (int)(d + 1 - MOD_SMOOTH_DRAWS) == (int)sizeof(MOD_SMOOTH_DRAWS));
	return 0;
}
'''

BEHAVIOUR = r'''
/* the instance: frame, position, rotation */
static int32_t inst[7];
static int32_t stack[64];
static int32_t pos[4], col[4], scl[4];
static int32_t seen[32];
static int calls;

/* stands for a draw: what it was given (pointers read through), then pops them */
static void sprite(void) { /* renderProjectedSprite: 13 operands */
	int32_t *sp = EFE_DATA_STACK - 13;
	int32_t *p = (int32_t *)sp[0], *c = (int32_t *)sp[1];
	seen[0] = p[0]; seen[1] = p[1]; seen[2] = p[2];
	seen[3] = c[0]; seen[4] = sp[2]; seen[5] = sp[10]; seen[6] = sp[4];
	EFE_DATA_STACK = sp;
	calls++;
}
static void model(void) { /* drawTMD: id, scale, the instance transform */
	int32_t *sp = EFE_DATA_STACK - 2;
	int32_t *s = (int32_t *)sp[1];
	seen[0] = inst[1]; seen[1] = inst[4]; seen[2] = s[0];
	EFE_DATA_STACK = sp;
	calls++;
}

static void push_sprite(int32_t u, int32_t scale, int32_t rot) {
	int32_t v[13] = {(int32_t)pos, (int32_t)col, scale, scale, u, 0, 16, 16, 8, 8, rot, 0, 0};
	memcpy(stack, v, sizeof(v));
	EFE_DATA_STACK = stack + 13;
}
static void push_model(int32_t id) {
	stack[0] = id; stack[1] = (int32_t)scl;
	EFE_DATA_STACK = stack + 2;
}

/* one render pass of the engine with one sprite draw */
static void pass_sprite(int r, int32_t alpha, int32_t u, int32_t scale, int32_t rot) {
	MOD_RENDER_PASS = r; MOD_RENDER_ALPHA = alpha;
	modSmoothBegin();
	modSmoothSub(0, 0);
	push_sprite(u, scale, rot);
	modSmoothCall(sprite, 24);
	assert(EFE_DATA_STACK == stack);
	modSmoothEnd();
}
static void pass_model(int r, int32_t alpha) {
	MOD_RENDER_PASS = r; MOD_RENDER_ALPHA = alpha;
	modSmoothBegin();
	modSmoothSub(1, 2);
	push_model(7);
	modSmoothCall(model, 3);
	modSmoothEnd();
}
static void tick(void) { MOD_FPS_TICKS++; inst[0]++; }
static void at(int32_t x) { pos[0] = x; }

static void run(void) {
	int32_t saved[13];
	EFE_CURRENT_DATA_SEGMENT = inst;

	/* 20 fps: each draw is called once with its own operands, the stack untouched */
	MOD_FPS_MODE = 0;
	at(0); tick(); pass_sprite(0, 4096, 0, 4096, 0);
	at(300); tick(); push_sprite(0, 4096, 0); memcpy(saved, stack, sizeof(saved));
	MOD_RENDER_PASS = 0; MOD_RENDER_ALPHA = 4096; modSmoothBegin(); modSmoothSub(0, 0); modSmoothCall(sprite, 24);
	assert(!memcmp(saved, stack, sizeof(saved)) && seen[0] == 300 && modSm.curN == 0);
	modSmoothEnd();

	/* 60 fps: thirds of the step from the last tick's pose to this one's */
	MOD_FPS_MODE = 2;
	at(0); col[0] = 0; tick(); pass_sprite(0, 1365, 0, 4096, 10);
	at(300); col[0] = 60; tick();
	pass_sprite(0, 1365, 0, 4096, 40); assert(seen[0] == 100 && seen[3] == 20 && seen[5] == 20);
	pass_sprite(1, 2730, 0, 4096, 40); assert(seen[0] == 200 && seen[3] == 40 && seen[5] == 30);
	pass_sprite(2, 4096, 0, 4096, 40); assert(seen[0] == 300 && seen[5] == 40);
	assert(modSm.cc == 0); /* an extra pass at 3/3 looks nothing up */
	assert(pos[0] == 300 && col[0] == 60); /* the operands it points at are not written */

	/* a sprite cell change (flipbook) draws its own pose */
	at(600); tick(); pass_sprite(0, 1365, 16, 4096, 40); assert(seen[0] == 600);
	/* a jump wider than a tick's motion (2048) is a cut */
	at(600 + 3000); tick(); pass_sprite(0, 2048, 16, 4096, 40); assert(seen[0] == 3600);
	/* angles: the short way round (350 -> 10 degrees passes 0) */
	at(3600); tick(); pass_sprite(0, 2048, 16, 4096, 350);
	tick(); pass_sprite(0, 2048, 16, 4096, 10); assert(seen[5] == 0);
	/* a restarted sub-effect (its frame did not move on by one) */
	at(3700); MOD_FPS_TICKS++; inst[0] = 0; pass_sprite(0, 1365, 16, 4096, 10); assert(seen[0] == 3700);
	/* a camera cut (the snapshot counted a snap) */
	at(3800); tick(); MOD_INTERP_STATS[3]++; pass_sprite(0, 1365, 16, 4096, 10); assert(seen[0] == 3800);
	/* a skipped tick (no render in between) */
	at(3900); tick(); tick(); pass_sprite(0, 1365, 16, 4096, 10); assert(seen[0] == 3900);

	/* a value that moves between the passes of one tick (bones, camera) is already interpolated: drawn as it is */
	at(4000); tick(); pass_sprite(0, 1365, 16, 4096, 10); assert(seen[0] == 3934);
	at(4010); pass_sprite(1, 2730, 16, 4096, 10); assert(seen[0] == 4010);
	at(4100); tick(); pass_sprite(0, 1365, 16, 4096, 10); assert(seen[0] == 4100);
	scl[0] = 4096;

	/* the ladder's 20 fps level (one frame at 3/3): nothing logged, the next tick draws its own pose */
	MOD_RENDER_CADENCE = 16;
	at(4200); tick(); pass_sprite(0, 4096, 16, 4096, 10); assert(seen[0] == 4200 && modSm.curN == 0);
	MOD_RENDER_CADENCE = 0;
	at(4300); tick(); pass_sprite(0, 1365, 16, 4096, 10); assert(seen[0] == 4300);

	/* a battle x2 tick (one pass at 3/3): nothing logged either */
	MOD_TICK_FAST = 1;
	at(4400); tick(); pass_sprite(0, 4096, 16, 4096, 10); assert(seen[0] == 4400 && modSm.curN == 0);
	MOD_TICK_FAST = 0;
	at(4500); tick(); pass_sprite(0, 1365, 16, 4096, 10); assert(seen[0] == 4500);

	/* interpolation off: as at 20 fps */
	MOD_FPS_INTERP = 0;
	at(4400); tick(); pass_sprite(0, 1365, 16, 4096, 10); assert(seen[0] == 4400);
	MOD_FPS_INTERP = 1;

	/* outside the engine's render: never touched */
	at(0); push_sprite(16, 4096, 10); modSmoothCall(sprite, 24); assert(seen[0] == 0);

	/* model draws: the instance transform for the pass, put back after */
	scl[0] = 4096; inst[1] = 0; inst[4] = 4000; tick(); pass_model(0, 2048);
	scl[0] = 8192; inst[1] = 1000; inst[4] = 100; tick(); pass_model(0, 2048);
	/* x half way; the rotation 4000 -> 100 the short way (196 forward), so 2; the scale 4096 -> 8192 */
	assert(seen[0] == 500 && seen[1] == 2 && seen[2] == 6144);
	assert(inst[1] == 1000 && inst[4] == 100 && scl[0] == 8192);
	/* a non-draw sub-opcode goes straight through */
	calls = 0; MOD_RENDER_PASS = 0; modSmoothBegin(); push_model(7); modSmoothCall(model, 5); assert(calls == 1); modSmoothEnd();

	/* particles: back along the last step, not on the tick they were born */
	modSmoothEmitTicked(); tick(); MOD_RENDER_PASS = 0; MOD_RENDER_ALPHA = 2048; modSmoothBegin();
	assert(modSmoothParticle(500, 30, 2, 1000) == 516);
	assert(modSmoothParticle(968, 30, 2, 1000) == 968);
	MOD_RENDER_ALPHA = 4096; assert(modSmoothParticle(500, 30, 2, 1000) == 500);
	modSmoothEnd();
	tick(); MOD_RENDER_ALPHA = 2048; modSmoothBegin(); /* the emitters did not tick */
	assert(modSmoothParticle(500, 30, 2, 1000) == 500);
	modSmoothEnd();
	puts("PASS");
}

static void *thread(void *unused) { (void)unused; run(); return NULL; }

int main(void) {
	pthread_t t;
	pthread_attr_t a;
	size_t size = 1 << 20;
	void *stackmem = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_32BIT, -1, 0);
	assert(stackmem != MAP_FAILED);
	pthread_attr_init(&a);
	pthread_attr_setstack(&a, stackmem, size);
	assert(pthread_create(&t, &a, thread, NULL) == 0);
	pthread_join(t, NULL);
	return 0;
}
'''


def compile_run(source, tmp, name):
    c, binary = Path(tmp) / (name + '.c'), Path(tmp) / name
    c.write_text(source)
    subprocess.run(['cc', '-std=gnu99', '-O1', '-no-pie', '-fno-pie', '-Wall', '-Werror', '-Wno-int-to-pointer-cast',
                    '-Wno-pointer-to-int-cast', '-Wno-unused-function', str(c), '-o', str(binary), '-lpthread'],
                   check=True)
    return subprocess.run([str(binary)], check=True, capture_output=True, text=True).stdout


def usa_only(source):
    """The source as the USA build sees it: the Japanese branches of `#if VERSION_...(JP...)` dropped."""
    out, skip = [], []
    for line in source.splitlines():
        s = line.strip()
        if s.startswith('#if'):
            skip.append('JP' in s and 'VERSION' in s)
            if skip[-1]:
                continue
        elif s.startswith('#else') and skip:
            skip[-1] = not skip[-1]
            continue
        elif s.startswith('#endif') and skip:
            skip.pop()
            continue
        if not any(skip):
            out.append(line)
    return '\n'.join(out) + '\n'


def handler_pops(source, prefix):
    """opcode -> net values the handler takes off the data stack"""
    source = usa_only(source)
    table = re.search(r'%s_EFE_SUB_OPCODES\[97\] = \{(.*?)\n\};' % prefix, source, re.S).group(1)
    names = {int(op, 0): name for op, name in re.findall(r'\{\s*(0x[0-9a-fA-F]+|\d+),\s*(\w+)\s*\}', table)}

    def body(name):
        m = re.search(r'^void %s\(void\)\n\{\n(.*?)^\}' % name, source, re.S | re.M)
        return m.group(1) if m else ''

    def net(name):
        b = body(name)
        n = b.count('EFE_POP1(') + b.count('*--EFE_DATA_STACK') - b.count('EFE_PUSH1(')
        for callee in re.findall(r'\b(%s_render\w+)\(\);' % prefix, b):
            n += net(callee)
        return n

    return {op: net(name) for op, name in names.items()}, names


class SmoothEffects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.header = header_text()
        cls.tmp = tempfile.TemporaryDirectory(prefix='dw-efe-smooth-')
        out = compile_run(host_source(cls.header) + DUMP, cls.tmp.name, 'dump')
        cls.rows = {}
        for line in out.splitlines():
            f = line.split()
            if f[0] == 'limits':
                cls.limits = [int(x) for x in f[1:]]
            else:
                cls.rows[int(f[0])] = (int(f[1]), int(f[2]), [int(x) for x in f[3:]])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_table_lists_the_draws(self):
        self.assertEqual(set(self.rows), DRAWS)
        vals, ptrs, whole = self.limits
        self.assertEqual(whole, 1, 'the table walk must end on its terminator')
        for op, (n, t, kinds) in self.rows.items():
            self.assertLessEqual(sum(3 if k & 8 else (1 if k not in (0, 1) else 0) for k in kinds) + 6 * t, vals, op)
            self.assertLessEqual(sum(1 for k in kinds if k & 8), ptrs, op)
            self.assertLessEqual(len(kinds) and max(kinds), 15)
            for k in kinds:
                self.assertNotIn(k, (8, 9), 'pointer operands are values, not identifiers or ignored (%d)' % op)

    def test_counts_match_the_handlers(self):
        for prefix, path in (('BTL', 'src/btl/battle_effect.c'), ('STD', 'src/std/std_effect.c'),
                             ('VS', 'src/vs/vs_effect.c')):
            src = DECOMP / path
            if not src.exists():
                self.skipTest('no decomp tree (%s)' % src)
            pops, names = handler_pops(src.read_text(errors='replace'), prefix)
            for op, (n, t, kinds) in self.rows.items():
                self.assertEqual(pops[op], n, '%s sub-opcode %d (%s)' % (prefix, op, names[op]))
                self.assertRegex(names[op], r'_(draw|render)', '%s sub-opcode %d is a draw' % (prefix, op))

    def test_behaviour(self):
        self.assertIn('PASS', compile_run(host_source(self.header) + BEHAVIOUR, self.tmp.name, 'behaviour'))


if __name__ == '__main__':
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        DECOMP = Path(sys.argv.pop(1)).resolve()
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
