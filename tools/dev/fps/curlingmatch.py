#!/usr/bin/env python3
"""Drive an already entered DuckStation curling match with the pad.

Usage: DS_MAP=... DS_GDB_PORT=... curlingmatch.py OUT.json [SECONDS]
Works with original and Horizon linker maps. Does not change game physics.
Records state transitions and score/stone outcomes; this is an overclock smoke
test, not a tick-exact determinism check (use curlingcheck.py for that).
"""
from pathlib import Path
import json
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev import duckstation as ds


def main():
    output = Path(sys.argv[1])
    deadline = time.monotonic() + (float(sys.argv[2]) if len(sys.argv) > 2 else 240)
    rows = []
    previous = None
    active = False
    last_press = 0
    began = time.monotonic()
    state_addr = ds.sym('MAIN_D_80135244')
    stones_addr = ds.sym('KAR_D_8005B5A0')
    power_addr = ds.sym('MAIN_D_8013523E')
    try:
        while time.monotonic() < deadline:
            g = ds.GDB()
            try:
                state = struct.unpack('<i', g.read(state_addr, 4))[0]
                power = struct.unpack('<h', g.read(power_addr, 2))[0]
                if 0 <= state < 20:
                    active = True
                if active and state != previous:
                    stones = g.read(stones_addr, 3 * 868)
                    row = dict(seconds=round(time.monotonic()-began, 3), state=state,
                               power=power, scores=[stones[p*868] for p in range(2)],
                               thrown=[stones[p*868+1] for p in range(2)], stones=[])
                    for p in range(3):
                        for i in range(5):
                            off = p*868 + 8 + i*172
                            row['stones'].append(dict(
                                state=struct.unpack_from('<i', stones, off)[0],
                                speed=struct.unpack_from('<h', stones, off+8)[0],
                                angle=struct.unpack_from('<i', stones, off+12)[0],
                                position=struct.unpack_from('<iii', stones, off+156)))
                    rows.append(row)
                    print(json.dumps({k:v for k,v in row.items() if k != 'stones'}), flush=True)
                    output.write_text(json.dumps(rows, indent=2)+'\n')
                    previous = state
            finally:
                g.close()
            if active and state == 20:
                break
            if not active:
                time.sleep(0.1)
                continue
            now = time.monotonic()
            if state != 11 and now-last_press >= 0.5 and (state != 8 or power >= 1200):
                ds.press('CROSS', 3)
                last_press = now
            time.sleep(0.05)
    finally:
        output.write_text(json.dumps(rows, indent=2)+'\n')
    print('completed' if rows and rows[-1]['state'] == 20 else 'time limit; inspect trace')


if __name__ == '__main__':
    main()
