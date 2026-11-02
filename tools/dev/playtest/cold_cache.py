#!/usr/bin/env python3
"""Cold animations with and without RAM above 2 MB, counted on a real toilet trip.

DISPLAY=:141 python3 tools/dev/playtest/cold_cache.py DISC --exe EXE --out build/cold --port 41146 [--ram8]

2 MB: the cache stays off and every cold clip is read without stopping the game. 8 MB: the partner's cold part is read
once, into 0x80200000, and no cold clip reads the disc. Both: every cold clip of the partner starts, also
when another clip replaces it while it is being read.
"""
import argparse
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

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
if CC then CC.a:remove();CC.b:remove();CC.c:remove() end
CC={{clips=0,clip_reads=0,fills=0,async=0}}
CC.a=PCSX.addBreakpoint({e.A('loadColdAnimation')},'Exec',4,'cold-clip',function() CC.clips=CC.clips+1 end)
CC.b=PCSX.addBreakpoint({e.A('readFileSectors')},'Exec',4,'cold-read',function()
 local b=PCSX.getRegisters().GPR.n.a1
 if b=={e.A('COLD_ANIM_BUFFER')} then CC.clip_reads=CC.clip_reads+1 end
 if b=={CACHE} then CC.fills=CC.fills+1 end
end)
CC.c=PCSX.addBreakpoint({e.A('addFileReadRequestSection')},'Exec',4,'cold-async',function() CC.async=CC.async+1 end)
return 'armed'
''')

    def counts(self):
        return json.loads(self.lua("return '{\"clips\":'..CC.clips..',\"clip_reads\":'..CC.clip_reads..',\"fills\":'..CC.fills..',\"async\":'..CC.async..'}'"))


    def wait_clip(self, seconds=12):
        """The toilet's wait for the end of a clip, the shape of everything that waits for one, finishes."""
        e = self.e
        end = time.time() + seconds
        while time.time() < end:
            if e.peek('PARTNER_SUB_STATE', 'B') == 4:
                return True
            time.sleep(.2)
        return False

    def start_clips(self, state, *slots):
        e = self.e
        e.run('load', str(state))
        e.run('pause')
        e.poke('PARTNER_STATE', b'\6')
        e.poke('PARTNER_SUB_STATE', b'\3')
        partner = e.A('PARTNER_ENTITY')
        self.calls([('startAnimation', (partner, slot)) for slot in slots])
        e.run('resume')
        return self.wait_clip()

    def every_clip(self, species):
        state = self.out / f'field-{species}.state'
        model = self.e.peek('PARTNER_ENTITY+8', 'I')
        ram = self.e.ram()
        cold = [s for s in (5, 7, 8, 9, 10, 11, 12, 13)
                if struct.unpack_from('<I', ram, model - 0x80000000 + 4 * s)[0] & 0x80000000]
        got = {s: self.start_clips(state, s) for s in cold}
        got['replaced by a cold clip'] = self.start_clips(state, cold[0], cold[-1])
        got['replaced by a resident clip'] = self.start_clips(state, cold[0], 0)
        got['again after that'] = self.start_clips(state, cold[0], 0, cold[-1])
        print(json.dumps({str(k): v for k, v in got.items()}))
        assert all(got.values()), got


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
        test.every_clip(args.species)
        assert got['clips'] > 0, 'no cold clip started'
        if args.ram8:
            assert got['cached'] == args.species and got['fills'] >= 1 and got['clip_reads'] == 0, got
        else:
            assert got['cached'] == -1 and got['fills'] == 0 and got['clip_reads'] == 0 and got['async'] > 0, got
        print('PASS')
    finally:
        e.stop()


if __name__ == '__main__':
    main()
