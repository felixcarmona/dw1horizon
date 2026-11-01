#!/usr/bin/env python3
"""Cold animations with and without RAM above 2 MB, counted on a real toilet trip.

DISPLAY=:141 python3 tools/dev/playtest/cold_cache.py DISC --exe EXE --out build/cold --port 41146 [--ram8]

2 MB: the cache stays off and every cold clip reads the disc. 8 MB: the partner's cold part is read
once, into 0x80200000, and no cold clip reads the disc.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from partner_walk import ROOT, WalkTest

CACHE = 0x80200000


class ColdTest(WalkTest):
    def __init__(self, args):
        super().__init__(args)
        if args.ram8:
            self.e.env['EMU_ARGS'] += ' -8mb'
            self.e.ram = self.low_ram

    def low_ram(self):
        """The harness reads what lies below 2 MB; the game's state is all there."""
        return subprocess.run([sys.executable, str(ROOT / 'tools/dev/emulator.py'), 'ramdump'], env=self.e.env,
                              capture_output=True, check=True).stdout[:0x200000]

    def count_reads(self):
        e = self.e
        self.lua(f'''
if CC then CC.a:remove();CC.b:remove() end
CC={{clips=0,clip_reads=0,fills=0}}
CC.a=PCSX.addBreakpoint({e.A('loadColdAnimation')},'Exec',4,'cold-clip',function() CC.clips=CC.clips+1 end)
CC.b=PCSX.addBreakpoint({e.A('readFileSectors')},'Exec',4,'cold-read',function()
 local b=PCSX.getRegisters().GPR.n.a1
 if b=={e.A('COLD_ANIM_BUFFER')} then CC.clip_reads=CC.clip_reads+1 end
 if b=={CACHE} then CC.fills=CC.fills+1 end
end)
return 'armed'
''')

    def counts(self):
        return json.loads(self.lua("return '{\"clips\":'..CC.clips..',\"clip_reads\":'..CC.clip_reads..',\"fills\":'..CC.fills..'}'"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc')
    ap.add_argument('--exe', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=41146)
    ap.add_argument('--card', default=str(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd'))
    ap.add_argument('--species', type=int, default=373)
    ap.add_argument('--ram8', action='store_true')
    args = ap.parse_args()
    args.runs, args.start, args.screen, args.target = 1, 0, 44, [-1200, -925]
    args.limit, args.scripted, args.freeze, args.npc = 1200, False, False, 'natural'
    test = ColdTest(args)
    e = test.e
    with socket.socket() as sk:
        if sk.connect_ex(('127.0.0.1', args.port)) == 0:
            raise RuntimeError('port is already in use; choose a distinct EMU_PORT')
    e.start(args.card)
    try:
        assert e.continue_game() == 0 and e.in_control(), 'boot did not reach control'
        test.count_reads()
        assert test.run_cases(args.species), 'the toilet trip did not finish'
        got = test.counts()
        got['cached'] = e.peek('MOD_COLD_CACHE_TYPE', 'i')
        print(json.dumps(got))
        assert got['clips'] > 0, 'no cold clip started'
        if args.ram8:
            assert got['cached'] == args.species and got['fills'] >= 1 and got['clip_reads'] == 0, got
        else:
            assert got['cached'] == -1 and got['fills'] == 0 and got['clip_reads'] == got['clips'], got
        print('PASS')
    finally:
        e.stop()


if __name__ == '__main__':
    main()
