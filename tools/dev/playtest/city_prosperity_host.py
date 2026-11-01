#!/usr/bin/env python3
"""Compile the actual prosperity function on the host with the owned roster.

All flags are set, then each is tested alone, including seven temporary high
residents. Also mutate the bitset to prove that membership is data, and verify
the unchanged original-story sum.
"""
import argparse
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.city_residents import membership_bits, residents, LEVELS


def function(source, name):
    start = source.index('void ' + name + '(void)')
    begin = source.index('{', start)
    depth = 1
    end = begin + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def check(tree):
    code = function((tree / 'src/main/main.c').read_text(), 'recalculateProsperity')
    species = {s['id']: s for p in (ROOT / 'content/species').glob('*.json')
               for s in [json.loads(p.read_text())]}
    levels = [LEVELS.get(species.get(i, {}).get('level'), 0) for i in range(1024)]
    bits = membership_bits()
    prefix = '''#include <stdint.h>
#define NUM_RECRUITABLE_DIGIMON 112
struct Para { int level; } para[1024];
#define DIGI_PARA(i) para[i]
uint8_t CITY_RESIDENTS[14], recruited[1024], result;
int MOD_OPT_STORY;
int isDigimonRecruited(int i) { return recruited[i]; }
void writePStat(int i, int value) { result = value; }
'''
    extra = [112, 124, 179, 241, 273, 290, 294]
    prefix += '#define CITY_RESIDENTS_EXTRA_COUNT 7\nstatic const uint16_t CITY_RESIDENTS_EXTRA[] = {112,124,179,241,273,290,294};\n'
    with tempfile.TemporaryDirectory() as folder:
        src = Path(folder) / 'city.c'
        lib = Path(folder) / 'city.so'
        src.write_text(prefix + code)
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wall', '-Werror', str(src), '-o', str(lib)], check=True)
        c = ctypes.CDLL(str(lib))
        table = (ctypes.c_uint8 * 14).in_dll(c, 'CITY_RESIDENTS')
        flags = (ctypes.c_uint8 * 1024).in_dll(c, 'recruited')
        stage = (ctypes.c_int * 1024).in_dll(c, 'para')
        option = ctypes.c_int.in_dll(c, 'MOD_OPT_STORY')
        result = ctypes.c_uint8.in_dll(c, 'result')
        table[:] = bits
        stage[:] = levels
        def count():
            c.recalculateProsperity()
            return result.value
        option.value = 1
        flags[:] = [1] * 1024
        total = 169 + sum(levels[i] - 2 for i in extra)
        assert count() == total, count()
        option.value = 0
        assert count() == 100, count()
        ids = {r['id'] for r in residents()} | set(extra)
        for original in (False, True):
            option.value = not original
            for i in range(1024):
                flags[:] = [0] * 1024
                flags[i] = 1
                valid = (3 <= i < 59 and levels[i] >= 3) if original else i in ids
                expected = (1 if i in (11, 39, 53) else levels[i] - 2) if valid else 0
                assert count() == expected, (original, i, count(), expected)
        option.value = 1
        flags[:] = [1] * 1024
        for i in ids - set(extra):
            table[i // 8] ^= 1 << (i % 8)
            weight = 1 if i in (11, 39, 53) else levels[i] - 2
            assert count() == total - weight, i
            table[i // 8] ^= 1 << (i % 8)
        print(f'PASS: actual C; 2048 single-flag cases, 89 roster-bit mutations; extended {total} (7 temporary high ids), original 100')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    check(parser.parse_args().tree)
