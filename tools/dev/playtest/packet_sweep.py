#!/usr/bin/env python3
"""Sweep the Mount Infinity triple battle over techniques and report the GPU packet area peaks.

Runs tools/dev/playtest/infinity_portal.py (2 MB RAM, stock CPU) once per SPECIES:TECHNIQUE pair, several at a
time, each with --profile, and prints one table row per run: the largest packet use of any presented frame
(`peak`, of the 81,920-byte area), the packet-ordering-table violations and strangers, and the renderers that
added the most packets in one frame (`name=per-frame/per-call` bytes). The run fails when a pair has a
violation, a stranger writing the ordering-table headers, or a peak above LIMIT - MARGIN.

  tools/dev/playtest/packet_sweep.py DISC --exe EXE --out DIR --jobs 8 115:25 88:5
  tools/dev/playtest/packet_sweep.py DISC --exe EXE --out DIR --pad-packets 24000 115:25   # stress load

A species below 180 or a new species both work; the technique number is the game's (docs/data/techs.csv).
Without pairs it runs the default set: the heaviest techniques of the heaviest species.
"""
import argparse
import json
import queue
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AREA = 81920
# Machinedramon All Range Beam, Vermilimon Heat Laser and Meltdown, Omnimon Mail Strome, Magnadramon Heat Laser,
# Armageddemon Crimson Flare, Phoenixmon Crimson Flare, Suijinmon Infinity Cannon, Machinedramon Infinity Cannon.
DEFAULT_PAIRS = ['115:25', '88:5', '88:7', '461:111', '215:5', '407:109', '59:109', '408:106', '115:106']


def run_pair(args, ports, pair):
    species, technique = pair.split(':')
    out = args.out / f's{species}-t{technique}'
    out.mkdir(parents=True, exist_ok=True)
    slot = ports.get()
    try:
        if args.tournament:
            cmd = [sys.executable, str(ROOT / 'tools/dev/playtest/packet_tournament.py'), str(args.disc), '--exe',
                   args.exe, '--out', str(out), '--port', str(args.port + slot), '--species', species,
                   '--technique', technique, '--cup', str(args.cup), '--timeout', str(args.timeout),
                   '--pad-packets', str(args.pad_packets)]
        else:
            cmd = [sys.executable, str(ROOT / 'tools/dev/playtest/infinity_portal.py'), str(args.disc), '--exe', args.exe,
                   '--out', str(out), '--port', str(args.port + slot), '--species', species, '--technique', technique,
                   '--quick', '1', '--all-join', '--offense', str(args.offense), '--cleanup',
                   '--cleanup-frames', str(args.cleanup_frames), '--timeout', str(args.timeout), '--profile',
                   '--video-seconds', '0', '--pad-packets', str(args.pad_packets)]
            if args.items:
                cmd += ['--items', args.items]
            if args.ram8:
                cmd += ['--ram8']
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    finally:
        ports.put(slot)
    (out / 'stdout.txt').write_text(result.stdout + '\n----\n' + result.stderr[-4000:])
    if not args.keep_logs:
        for log in out.glob('*.mp4'):
            log.unlink()
    found = re.findall(r'^gpu(?: at failure)? (\{.*\})$', result.stdout, re.M)
    report = json.loads(found[-1]) if found else None
    if report:
        (out / 'report.json').write_text(json.dumps(report, indent=1))
    return pair, result.returncode, report, time.time() - start


def row(pair, code, report, seconds, limit):
    if report is None:
        return f'{pair:>8} rc={code} NO REPORT ({seconds:.0f}s)', False
    top = sorted(report['profile'].items(), key=lambda kv: -kv[1]['max_frame'])[:4]
    names = ' '.join(f"{k.replace('BTL_', '').replace('render', '')}={v['max_frame']}/{v['max_call']}" for k, v in top)
    ok = (code == 0 and report['violations'] == 0 and not report['strangers'] and report['swap_peak'] <= limit)
    return (f"{pair:>8} {'ok  ' if ok else 'FAIL'} peak={report['swap_peak']:6} left={AREA - report['swap_peak']:6} "
            f"viol={report['violations']} strangers={len(report['strangers'])} ({seconds:.0f}s) {names}"
            + f" worst-frame-other={report.get('worst_frame', {}).get('other', 0)}" + ' | objects: ' + ' '.join(f"{k}={v['max_frame']}" for k, v in sorted(
                report.get('renderers', {}).items(), key=lambda kv: -kv[1]['max_frame'])[:7])), ok


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('disc', type=Path)
    p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--port', type=int, default=39800)
    p.add_argument('--offense', type=int, default=30)
    p.add_argument('--cleanup-frames', type=int, default=900)
    p.add_argument('--timeout', type=int, default=1500)
    p.add_argument('--pad-packets', type=int, default=0, help='test load: every render pass starts this many bytes in')
    p.add_argument('--items', choices=['open', 'throw'], help='battle item menu open (full bag) during the fight')
    p.add_argument('--ram8', action='store_true', help='emulator with 8 MB RAM instead of the stock 2 MB')
    p.add_argument('--tournament', action='store_true', help='fight in the Arena Lobby tournament (STD overlay)')
    p.add_argument('--cup', type=int, default=0)
    p.add_argument('--keep-logs', action='store_true', help='keep the videos of each run')
    p.add_argument('--margin', type=int, default=0, help='fail when fewer bytes than this are left in the area')
    p.add_argument('pairs', nargs='*', help='SPECIES:TECHNIQUE (default: the heaviest)')
    args = p.parse_args()
    args.out = args.out.resolve()
    args.disc = args.disc.resolve()
    pairs = args.pairs or DEFAULT_PAIRS
    ports = queue.Queue()
    for slot in range(args.jobs):
        ports.put(slot)
    limit = AREA - args.margin
    failed = 0
    with ThreadPoolExecutor(args.jobs) as pool:
        for pair, code, report, seconds in pool.map(lambda x: run_pair(args, ports, x), pairs):
            line, ok = row(pair, code, report, seconds, limit)
            print(line, flush=True)
            failed += not ok
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
