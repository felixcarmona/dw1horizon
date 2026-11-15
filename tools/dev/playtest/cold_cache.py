#!/usr/bin/env python3
"""Cold animations with and without RAM above 2 MB, counted on a real toilet trip.

DISPLAY=:141 python3 tools/dev/playtest/cold_cache.py DISC --exe EXE --out build/cold --port 41146 [--ram8]

2 MB: the last cold clip stays in the 8 KB buffer until overwritten. 8 MB: the partner's whole cold part
(up to 64 KB) is read once into 0x80200000. Both: every cold clip of the partner starts, also
when another clip replaces it while it is being read.
"""
import argparse
import json
import csv
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from partner_walk import ROOT, WalkTest
from tools.coldsplit import COLD_SLOTS

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

    def start_clips(self, state, *slots, training=False):
        e = self.e
        e.run('load', str(state))
        e.run('pause')
        e.poke('PARTNER_STATE', b'\6')
        e.poke('PARTNER_SUB_STATE', b'\3')
        partner = e.A('PARTNER_ENTITY')
        self.calls([('startAnimation', (partner, slot)) for slot in slots])
        e.run('resume')
        if training:
            # Training clips may loop; the gym's timer ends the session.
            # Check playback itself here, and full sessions in cold_training.py.
            end = time.time() + 12
            while time.time() < end:
                ram = e.ram()
                if (e.peek('MOD_COLD_PENDING', 'I', ram) == 0 and
                    e.peek('PARTNER_ENTITY+0x2e', 'B', ram) == slots[-1] and
                    e.peek('PARTNER_ENTITY+0x1c', 'h', ram) > 1):
                    return True
                time.sleep(.05)
            return False
        return self.wait_clip()

    def every_clip(self, species):
        state = self.out / f'field-{species}.state'
        model = self.e.peek('PARTNER_ENTITY+8', 'I')
        ram = self.e.ram()
        cold = [s for s in COLD_SLOTS
                if struct.unpack_from('<I', ram, model - 0x80000000 + 4 * s)[0] & 0x80000000]
        got = {s: self.start_clips(state, s, training=s >= 0x14) for s in cold}
        care = [s for s in cold if s < 0x14]
        got['replaced by a cold clip'] = self.start_clips(state, care[0], care[-1])
        got['replaced by a resident clip'] = self.start_clips(state, cold[0], 0)
        got['again after that'] = self.start_clips(state, care[0], 0, care[-1])
        print(json.dumps({str(k): v for k, v in got.items()}))
        assert all(got.values()), got

    def eating(self, species):
        """Run the actual item-feeding states through consumption and food effects."""
        e, a = self.e, self.e.A
        e.run('load', str(self.out / f'field-{species}.state'))
        e.run('pause')
        self.place('PARTNER_ENTITY', -800, -900)
        self.place('TAMER_ENTITY', -600, -900)
        e.gs('set', 'partner.para.condition=4', 'partner.para.energyLevel=0',
             'partner.para.foodLevel=0', 'partner.para.discipline=100')
        # An isolated fixture bag slot containing two pieces of meat.
        e.poke('INVENTORY', struct.pack('<h', 38))
        e.poke('INVENTORY+60', b'\2')
        e.poke('INVENTORY_POINTER', b'\0')
        e.poke('TAMER_ITEM+8', struct.pack('<i', -1))
        e.poke('PARTNER_STATE', b'\1')
        e.poke('PARTNER_SUB_STATE', b'\0')
        e.poke('TAMER_STATE', b'\0')
        self.count_reads()
        self.lua(f'''
if CE then CE.v:remove() end
CE={{n=0,seen=false,played=false,done=false,wait=0,maxwait=0,lines={{'vsync,state,substate,anim,frame,frames,flags,pending'}}}}
local m=PCSX.getMemPtr()
local function u8(a) return tonumber(m[a%0x200000]) end
local function u16(a) return u8(a)+256*u8(a+1) end
local function u32(a) return u16(a)+65536*u16(a+2) end
CE.v=PCSX.Events.createEventListener('GPU::Vsync',function()
 CE.n=CE.n+1
 local st=u8({a('PARTNER_STATE')});local sub=u8({a('PARTNER_SUB_STATE')})
 local p={a('PARTNER_ENTITY')};local anim=u8(p+46);local frame=u16(p+28)
 local pending=u32({a('MOD_COLD_PENDING')})
 if st==5 then CE.seen=true end
 if st==5 and anim==8 and frame>1 and pending==0 then CE.played=true end
 if pending~=0 then CE.wait=CE.wait+1;CE.maxwait=math.max(CE.maxwait,CE.wait) else CE.wait=0 end
 CE.lines[#CE.lines+1]=table.concat({{CE.n,st,sub,anim,frame,u16(p+30),u8(p+48),pending}},',')
 if CE.seen and st==1 and u8({a('TAMER_STATE')})==0 then
  CE.done=true;CE.v:remove();PCSX.pauseEmulator()
 end
end)
return true
''')
        e.run('save', str(self.out / 'eating-before.state'))
        self.calls([('startFeedingItem', (38,))])
        e.run('resume')
        self.until('CE.done', 120)
        e.run('save', str(self.out / 'eating-after.state'))
        e.run('shot', str(self.out / 'eating-after.png'))
        trace = self.lua("return table.concat(CE.lines,'\\n')") + '\n'
        (self.out / 'eating.csv').write_text(trace)
        rows = list(csv.DictReader(trace.splitlines()))
        pending = [r for r in rows if int(r['pending'])]
        result = dict(played=self.lua('return CE.played') == 'true',
                      vsyncs=int(self.lua('return CE.n')), max_queued_wait_vsyncs=int(self.lua('return CE.maxwait')),
                      reads=self.counts(), remaining=e.peek('INVENTORY+60', 'B'),
                      energy=e.peek('PARTNER_PARA+0x3c', 'h'))
        assert result['played'] and result['remaining'] == 1 and result['energy'] > 0, result
        assert result['reads']['clip_reads'] == 0, result
        assert all(int(r['frames']) == 0x7fff and not int(r['flags']) & 1 for r in pending)
        assert (not pending and result['reads']['async'] == 0) if self.args.ram8 else (pending and result['reads']['async'] == 1), result
        (self.out / 'eating.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(dict(eating=result)), flush=True)


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
        test.eating(args.species)
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
