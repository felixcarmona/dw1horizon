#!/usr/bin/env python3
"""Check every setup section of a built MAPHEAD against its executable and model archive."""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import membudget


def add_arguments(ap):
    ap.add_argument('maphead')
    ap.add_argument('--map', required=True)
    ap.add_argument('--archive', required=True)
    ap.add_argument('--facts', required=True)
    ap.add_argument('--json', help='write every screen budget')


def run(args):
    membudget.configure(env={'DW_MODEL_ARCHIVE': os.path.abspath(args.archive),
                             'DW_EXE_FACTS': os.path.abspath(args.facts)}, heap_map=args.map)
    membudget.TRIMMED = True
    with tempfile.TemporaryDirectory(prefix='story-heap-') as work:
        subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'bytecode' / '__main__.py'),
                        'dis', args.maphead, work], check=True, stdout=subprocess.DEVNULL)
        text = (Path(work) / 'maphead.scn.txt').read_text()
    rows = []
    for screen in sorted({int(x) for x in re.findall(r'^\.section (\d+)', text, re.M) if int(x) < 1000}):
        row = membudget.screen_budget(screen, maphead_text=text)
        row.pop('paths')
        rows.append(row)
    if not rows:
        raise SystemExit('no screen setup sections found')
    rows.sort(key=lambda r: r['margin'])
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1) + '\n')
    for row in rows[:5]:
        print(f"screen {row['screen']:3}: peak {row['peak']:6} B, margin {row['margin']:6} B; "
              + ', '.join(row['worst']))
    failed = [r for r in rows if r['margin'] < 0]
    print(f'{len(rows)} screen setups checked against actual archive bytes; {len(failed)} do not fit')
    return bool(failed)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    add_arguments(ap)
    return run(ap.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
