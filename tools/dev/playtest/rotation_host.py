#!/usr/bin/env python3
"""Exercise the engine's turn completion for every pair of 12-bit headings on the host."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=Path('build/decomp-dev'))
    args = parser.parse_args()
    source = (args.tree / 'src/main/overworld.c').read_text()
    function = re.search(r'int32_t rotateEntity\([^;{]+\)\s*\{.*?\n\}', source, re.S)
    if not function:
        raise SystemExit('rotateEntity definition not found')
    host = r'''
#include <stdint.h>
#include <stdio.h>
typedef struct { int16_t vx, vy, vz, pad; } SVECTOR;
FUNCTION
int main(void) {
    int failures = 0;
    for (int start = 0; start < 4096; ++start) {
        for (int goal = 0; goal < 4096; ++goal) {
            SVECTOR rotation = {0, start, 0, 0};
            int done = 0;
            for (int tick = 0; tick < 10 && !done; ++tick) {
                int16_t target = goal, cc, cw;
                if (target > rotation.vy) {
                    cw = target - rotation.vy;
                    cc = rotation.vy + (4096 - target);
                } else {
                    cw = target + (4096 - rotation.vy);
                    cc = rotation.vy - target;
                }
                done = rotateEntity(&rotation, &target, &cc, &cw, 512);
            }
            if (!done || rotation.vy != goal) {
                if (failures < 4) printf("stuck: %d -> %d, last %d\n", start, goal, rotation.vy);
                ++failures;
            }
        }
    }
    printf("16777216 heading pairs, %d failures\n", failures);
    return failures != 0;
}
'''.replace('FUNCTION', function.group())
    Path('build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rotation-host-', dir='build') as temp:
        c = Path(temp) / 'rotation.c'
        c.write_text(host)
        exe = Path(temp) / 'rotation'
        subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-std=c99', str(c), '-o', str(exe)], check=True)
        return subprocess.run([str(exe)]).returncode


if __name__ == '__main__':
    raise SystemExit(main())
