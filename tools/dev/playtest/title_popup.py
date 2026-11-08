#!/usr/bin/env python3
"""Clean-boot the three enhancement-popup cases in DuckStation.

DS_DISPLAY=:177 DS_GDB_PORT=42357 python3 tools/dev/playtest/title_popup.py \
    build/title-popup.cue --exe build/title-popup/exe/SLUS_010.32 \
    --out build/title-popup-proof

Uses real RAM/CPU settings, no detection or renderer pokes. The existing driver
skips movies by patching their call. Memory cards are disconnected for each boot.
Inspect the three PNGs alongside the recorded probe results in evidence.json.
"""
from pathlib import Path
import argparse
import json
import os
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('cue', type=Path)
    ap.add_argument('--exe', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--case', choices=('all', 'normal', '8mb', 'fast'), default='all')
    args = ap.parse_args()
    if not os.environ.get('DS_DISPLAY') or not os.environ.get('DS_GDB_PORT'):
        ap.error('set private DS_DISPLAY and DS_GDB_PORT values')
    os.environ['DS_MAP'] = str(args.exe.resolve()) + '.elf.map'
    from tools.dev import duckstation as d
    from tools.xref import Elf
    symbols = {name: (addr, size) for name, addr, size, *_ in Elf(str(args.exe) + '.elf').syms}
    args.out.mkdir(parents=True, exist_ok=True)
    original_ini = Path(d.INI).read_bytes()
    assert not Path(d.RUN).exists(), 'stop this worktree’s DuckStation instance first'
    cases = [('normal', 2, 100, 3), ('8mb', 8, 100, 2), ('fast', 2, 250, 1)]
    evidence = []
    try:
        for name, ram, oc, expected in cases:
            if args.case not in ('all', name):
                continue
            d.setini('Console', 'Enable8MBRAM', 'true' if ram == 8 else 'false')
            d.setini('MemoryCards', 'Card1Type', 'None')
            d.setini('MemoryCards', 'Card2Type', 'None')
            d.main(['start', str(args.cue), '--oc', str(oc)])
            try:
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    g = d.GDB()
                    def read(n):
                        addr, size = symbols[n]
                        return struct.unpack({1: '<b', 2: '<h', 4: '<i'}[size], g.read(addr, size))[0]
                    values = {n: read(n) for n in (
                        'MOD_NOTICE', 'MOD_CPU_SPINS', 'MOD_FPS_POLICY',
                        'MOD_CAD_LEVEL', 'FIRST_SCREEN_FRAME_COUNTER',
                        'FIRST_SCREEN_PRESSED_START', 'FADE_IN_CURRENT')}
                    g.close()
                    if (values['FIRST_SCREEN_FRAME_COUNTER'] > 3
                            and values['FADE_IN_CURRENT'] == 0):
                        break
                    time.sleep(0.25)
                else:
                    raise AssertionError('Press Start did not become visible')
                assert values['MOD_NOTICE'] == expected, values
                assert values['FIRST_SCREEN_PRESSED_START'] == 0, values
                assert (values['MOD_CPU_SPINS'] >= 8500) == (oc == 250), values
                assert values['MOD_FPS_POLICY'] == 0, values
                screenshot = args.out / (name + '.png')
                d.main(['shot', str(screenshot)])
                row = dict(case=name, ram_mb=ram, cpu_percent=oc,
                           popup_expected=expected != 3, screenshot=screenshot.name,
                           observed=values)
                evidence.append(row)
                (args.out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
                print(json.dumps(row), flush=True)
            finally:
                d.main(['stop'])
    finally:
        Path(d.INI).write_bytes(original_ini)


if __name__ == '__main__':
    main()
