#!/usr/bin/env python3
"""Run the prepared pile routine and check collision at the visual cutoff."""
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    source = (Path(sys.argv[1]) / 'src/main/map_object.c').read_text()
    start = source.index('void decreaseDirtPileSize(void)\n{')
    end = source.index('\n}\n', start) + 3
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef struct { int16_t vx, vy, vz, pad; } SVECTOR;
typedef struct { int32_t vx, vy, vz, pad; } VECTOR;
static SVECTOR DIRT_PILE_SIZE_ROTATION;
static int8_t DIRT_PILE_SIZE_COUNTER;
static struct { int coord, flg; } GENERAL_COORDS3;
uint8_t MAP_COLLISION_DATA[10000];
static void RotMatrix(void *a, void *b) {}
static void ScaleMatrix(void *a, void *b) {}
''' + source[start:end] + r'''
int main(void) {
    memset(MAP_COLLISION_DATA, 52, sizeof(MAP_COLLISION_DATA));
    for (int y=41; y<43; y++) for (int x=69; x<72; x++) MAP_COLLISION_DATA[y*100+x]=128;
    DIRT_PILE_SIZE_COUNTER=7;
    decreaseDirtPileSize();
    assert(DIRT_PILE_SIZE_COUNTER==6 && MAP_COLLISION_DATA[4169]==128);
    decreaseDirtPileSize();
    assert(DIRT_PILE_SIZE_COUNTER==5);
    for (int y=0; y<100; y++) for (int x=0; x<100; x++) {
        assert(MAP_COLLISION_DATA[y*100+x] == (x>=69 && x<72 && y>=41 && y<43 ? 81 : 52));
    }
    decreaseDirtPileSize();
    assert(MAP_COLLISION_DATA[4169]==81);
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='pile-collision-') as work:
        src = Path(work) / 'test.c'
        src.write_text(code)
        exe = Path(work) / 'test'
        subprocess.run(['cc', '-std=c99', '-O2', str(src), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print('PASS: pile collision clears at the render cutoff, preserves use trigger and neighboring tiles')


if __name__ == '__main__':
    main()
