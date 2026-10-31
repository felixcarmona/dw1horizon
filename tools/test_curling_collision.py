#!/usr/bin/env python3
"""Check curling's collision cutoff against the original disc's SDK sqrt.

SquareRoot0 quantizes its argument before a table lookup. Check every interval
of that lookup, including both endpoints, over its nonnegative input domain.
This catches the tempting but incorrect replacement by distance squared < 150².
"""
from pathlib import Path
import re
import os
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CurlingCollision(unittest.TestCase):
    def test_compacted_scan(self):
        tree = Path(os.environ.get('DW_CURLING_TREE', ROOT/'build/decomp-dev'))
        path = tree/'src/kar/kar.c'
        if not path.exists() or not shutil.which('cc'):
            self.skipTest('needs prepared patched tree and host C compiler')
        def function(source):
            start = source.index('\nvoid KAR_updateCollisions(void)\n{')+1
            end = source.index('{', start)+1
            depth = 1
            while depth:
                depth += (source[end] == '{')-(source[end] == '}')
                end += 1
            return source[start:end]
        after = function(path.read_text())
        revisions = subprocess.check_output(
            ['git', '-C', str(tree), 'log', '--format=%H', '--', 'src/kar/kar.c'], text=True).split()
        before = None
        for rev in revisions:
            source = subprocess.check_output(
                ['git', '-C', str(tree), 'show', rev+':src/kar/kar.c'], text=True)
            candidate = function(source)
            if 'a / 5' in candidate:
                before = candidate
                break
        self.assertIsNotNone(before, 'reference indexed scan must exist in history')
        self.assertIn('active[15]', after, 'test the compacted implementation')
        code = SCAN_TEST.replace('@BEFORE@', before.replace('KAR_updateCollisions', 'before_scan'))
        code = code.replace('@AFTER@', after.replace('KAR_updateCollisions', 'after_scan'))
        with tempfile.TemporaryDirectory() as folder:
            c = Path(folder)/'scan.c'
            binary = Path(folder)/'scan'
            c.write_text(code)
            subprocess.run(['cc', '-std=c99', '-O2', '-fwrapv', str(c), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('40960 fixtures matched', result.stdout)

    def test_original_lookup_cutoff(self):
        exe = ROOT / 'extracted/SLUS_010.32'
        if not exe.exists():
            self.skipTest('needs extracted USA executable')
        symbols = (ROOT / 'decomp/config/us/symbols.txt').read_text()
        address = int(re.search(r'^SQRT = (0x[\da-fA-F]+);', symbols, re.M)[1], 16)
        data = exe.read_bytes()
        load = struct.unpack_from('<I', data, 0x18)[0]
        table = struct.unpack_from('<192h', data, address-load+0x800)
        intervals = []
        for leading in range(0, 32, 2):
            exponent = (31-leading)//2
            for index in range(64, 256):
                shift = 24-leading
                if shift >= 0:
                    low = index << shift
                    high = ((index+1) << shift)-1
                else:
                    quantum = 1 << -shift
                    low = (index+quantum-1)//quantum
                    high = (index+1+quantum-1)//quantum-1
                low = max(low, 1 << (30-leading))
                high = min(high, (1 << (32-leading))-1, 0x7fffffff)
                if low > high:
                    continue
                result = (table[index-64] << exponent) >> 12
                intervals.append((low, high))
                for value in (low, high):
                    self.assertEqual(result < 150, value < 22528,
                                     (value, result, leading, index))
        intervals.sort()
        end = 0
        for low, high in intervals:
            self.assertEqual(low, end+1)
            end = high
        self.assertEqual(end, 0x7fffffff)


SCAN_TEST = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define JP 0
#define US 1
#define VERSION_IS(v) ((v) == US)
#define VERSION_EQUAL_OR_NEWER(v) 1
typedef struct { int32_t vx, vy, vz, pad; } VECTOR;
typedef struct { int32_t state; VECTOR pos, target; } KarStone;
typedef struct { struct { KarStone stones[5]; } row; } KarRow;
static KarRow KAR_D_8005B5A0[3];
static int32_t MAIN_D_80135244;
static uint64_t trace;
static unsigned calls;
static void mix(int32_t value) { trace = (trace ^ (uint32_t)value) * UINT64_C(1099511628211); }
static int index_of(KarStone *stone) {
    for (int p=0; p<3; p++) for (int i=0; i<5; i++)
        if (stone == &KAR_D_8005B5A0[p].row.stones[i]) return p*5+i;
    abort();
}
static void KAR_bounceOffWall(void) { mix(777); }
static int32_t KAR_distance(int32_t x, int32_t z) {
    /* The unchanged distance function is a deterministic oracle here.
       The separate lookup test covers the SDK's approximate cutoff. */
    uint32_t n=(uint32_t)(x*x)+(uint32_t)(z*z), root=0, bit=1u<<30;
    while (bit>n) bit>>=2;
    while (bit) { if (n>=root+bit) {n-=root+bit;root=(root>>1)+bit;}
                 else root>>=1; bit>>=2; }
    return root;
}
static void KAR_resolveStoneCollision(KarStone *a, VECTOR av, KarStone *b, VECTOR bv) {
    int ai=index_of(a), bi=index_of(b);
    if (++calls>100000) abort();
    mix(ai);mix(bi);mix(av.vx);mix(av.vy);mix(av.vz);
    mix(bv.vx);mix(bv.vy);mix(bv.vz);
    /* Exercise callbacks changing the next substep's endpoints and states.
       All real resolver state writes preserve positivity too. */
    a->target=av; b->target=bv;
    a->pos.vx=10000+ai*400; b->pos.vx=10000+bi*400;
    a->pos.vz=ai*100; b->pos.vz=bi*100;
    if (a->state==2) a->state=3;
    if (b->state==2) b->state=3;
}
@BEFORE@
@AFTER@
static uint32_t seed=0x12345678;
static uint32_t next(void) {seed=seed*1664525u+1013904223u;return seed;}
int main(void) {
    KarRow initial[3], expected[3];
    for (unsigned fixture=0; fixture<40960; fixture++) {
        memset(initial,0,sizeof initial);
        unsigned mask=fixture<32768?fixture:next()&32767;
        for (int p=0;p<3;p++) for (int i=0;i<5;i++) {
            int id=p*5+i; KarStone *s=&initial[p].row.stones[i];
            s->state=(mask&(1u<<id))?1+next()%3:-(int32_t)(next()%3);
            s->pos.vx=fixture<32768?i*79:(int32_t)(next()%2048)-1024;
            s->pos.vz=fixture<32768?p*83:(int32_t)(next()%2048)-1024;
            s->target=s->pos;
            s->target.vx+=(int32_t)(next()%129)-64;
            s->target.vz+=(int32_t)(next()%129)-64;
            s->target.vy=(int32_t)(next()%256)-128;
        }
        MAIN_D_80135244=(fixture%97==0)?6:11;
        memcpy(KAR_D_8005B5A0,initial,sizeof initial);trace=17;calls=0;before_scan();
        uint64_t original=trace; unsigned original_calls=calls;
        memcpy(expected,KAR_D_8005B5A0,sizeof expected);
        memcpy(KAR_D_8005B5A0,initial,sizeof initial);trace=17;calls=0;after_scan();
        /* Original cur/prev leave VECTOR.pad uninitialized. It is copied by
           the resolver but never read by the physics. Compare live fields. */
        for (int p=0;p<3;p++) for (int i=0;i<5;i++) {
            expected[p].row.stones[i].target.pad=0;
            KAR_D_8005B5A0[p].row.stones[i].target.pad=0;
        }
        if (trace!=original || calls!=original_calls || memcmp(expected,KAR_D_8005B5A0,sizeof expected)) {
            fprintf(stderr,"fixture %u, mask %x differs, trace %llx/%llx calls %u/%u\n",
                    fixture,mask,(unsigned long long)original,(unsigned long long)trace,
                    original_calls,calls);
            for (unsigned i=0;i<sizeof expected;i++) if (((uint8_t*)expected)[i]!=((uint8_t*)KAR_D_8005B5A0)[i]) {
                fprintf(stderr,"first byte difference %u\n",i);break;
            }
            return 1;
        }
    }
    puts("40960 fixtures matched");return 0;
}
'''

if __name__ == '__main__':
    unittest.main()
