#!/usr/bin/env python3
"""Compile the actual prosperity function on the host with the owned roster.

All legacy flags are set, then each flag is tested alone. Also mutate the bitset
to prove that membership is data, and verify the unchanged original-story sum.
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
    levels = [LEVELS.get(species[i]['level'], 0) for i in range(112)]
    bits = membership_bits()
    prefix = '''#include <stdint.h>
#define NUM_RECRUITABLE_DIGIMON 112
struct Para { int level; } para[112];
#define DIGI_PARA(i) para[i]
uint8_t CITY_RESIDENTS[14], recruited[112], result;
int MOD_OPT_STORY;
int isDigimonRecruited(int i) { return recruited[i]; }
void writePStat(int i, int value) { result = value; }
'''
    with tempfile.TemporaryDirectory() as folder:
        src = Path(folder) / 'city.c'
        lib = Path(folder) / 'city.so'
        src.write_text(prefix + code)
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wall', '-Werror', str(src), '-o', str(lib)], check=True)
        c = ctypes.CDLL(str(lib))
        table = (ctypes.c_uint8 * 14).in_dll(c, 'CITY_RESIDENTS')
        flags = (ctypes.c_uint8 * 112).in_dll(c, 'recruited')
        stage = (ctypes.c_int * 112).in_dll(c, 'para')
        option = ctypes.c_int.in_dll(c, 'MOD_OPT_STORY')
        result = ctypes.c_uint8.in_dll(c, 'result')
        table[:] = bits
        stage[:] = levels
        def count():
            c.recalculateProsperity()
            return result.value
        option.value = 1
        flags[:] = [1] * 112
        assert count() == 170, count()
        option.value = 0
        assert count() == 100, count()
        ids = {r['id'] for r in residents()}
        for original in (False, True):
            option.value = not original
            for i in range(112):
                flags[:] = [0] * 112
                flags[i] = 1
                valid = (3 <= i < 59 and levels[i] >= 3) if original else i in ids
                expected = (1 if i in (11, 39, 53) else levels[i] - 2) if valid else 0
                assert count() == expected, (original, i, count(), expected)
        option.value = 1
        flags[:] = [1] * 112
        for i in ids:
            table[i // 8] ^= 1 << (i % 8)
            weight = 1 if i in (11, 39, 53) else levels[i] - 2
            assert count() == 170 - weight, i
            table[i // 8] ^= 1 << (i % 8)
        print('PASS: actual C; 224 single-flag cases, 90 roster-bit mutations; extended 170, original 100')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    check(parser.parse_args().tree)
