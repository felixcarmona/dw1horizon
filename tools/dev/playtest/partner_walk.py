#!/usr/bin/env python3
"""Frame traces for intermittent partner toilet and scripted-walk stalls.

DISPLAY=:141 python3 tools/dev/playtest/partner_walk.py DISC --exe EXE \
    --out build/walk-proof --port 41145 --species 373 3 --runs 30

Boots a card in original 2 MB RAM, loads the real partner model, and varies
position, heading and tamer placement. Each disc boots independently; states
are reused only within that disc. Logs and screenshots remain under --out.
--attach uses an instance already started by this test session on --port.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import socket
import struct
import sys
import time
import urllib.parse

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu


class WalkTest:
    def __init__(self, args):
        self.args = args
        self.out = args.out.resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        self.e = Emu(args.disc, args.exe, args.port, str(self.out))
        self.e.env['EMU_ARGS'] = '-interpreter -debugger'

    def lua(self, code):
        path = self.out / 'command.lua'
        path.write_text(code)
        result = self.e.api('/api/v1/lua/eval?file=' + urllib.parse.quote(str(path))).decode()
        if result.startswith('error:'):
            raise RuntimeError(result)
        return result

    def calls(self, calls):
        """Call from gameLoop, preserving its return address across the queue."""
        e = self.e
        queue = [[e.A(name)] + [v & 0xffffffff for v in values] + [0]*(4-len(values)) for name, values in calls]
        q = '{' + ','.join('{' + ','.join(map(str, row)) + '}' for row in queue) + '}'
        self.lua(f'''
if WC and WC.bp then WC.bp:remove() end
WC={{done=false,q={q}}}
WC.bp=PCSX.addBreakpoint({e.A('gameLoop')},'Exec',4,'walk-call',function()
 local r=PCSX.getRegisters()
 if not WC.ra then WC.ra=r.GPR.n.ra end
 if #WC.q>0 then
  local c=table.remove(WC.q,1)
  r.GPR.n.a0=c[2];r.GPR.n.a1=c[3];r.GPR.n.a2=c[4];r.GPR.n.a3=c[5]
  r.GPR.n.ra={e.A('gameLoop')};r.pc=c[1]
 else r.GPR.n.ra=WC.ra;WC.done=true;WC.bp:remove();PCSX.pauseEmulator() end
end)
PCSX.resumeEmulator();return 'armed'
''')
        self.until('WC.done', 180)

    def until(self, expression, seconds):
        deadline = time.monotonic() + seconds
        while self.lua('return ' + expression) != 'true':
            if time.monotonic() > deadline:
                raise RuntimeError('emulator wall timeout: ' + expression)
            time.sleep(.3)

    def place(self, entity, x, z, heading=0):
        e = self.e
        pos = e.peek(entity + '+4', 'I')
        e.run('poke', hex(pos + 0x78), struct.pack('<3i', x, 0, z).hex())
        e.poke(entity + '+0x10', struct.pack('<3i', x*32768, 0, z*32768))
        e.run('poke', hex(pos + 0x72), struct.pack('<h', heading).hex())

    def switch(self, species):
        e = self.e
        # A preceding failed fixture may still own an arrival wait. Clear that
        # test script before loading the next partner or preparing its map.
        e.poke('IS_SCRIPT_PAUSED', struct.pack('<i', 1))
        e.poke('TAMER_STATE', b'\0')
        e.poke('PARTNER_STATE', b'\1')
        e.poke('SOME_SCRIPT_SYNC_BIT', struct.pack('<i', 1))
        e.poke('SCRIPT_MOVEMENT', (b'\xff' + bytes(11))*22)
        e.poke('PARTNER_PARA', struct.pack('<I', 0))
        e.poke('PARTNER_PARA+0x18', struct.pack('<h', 48))
        old = e.peek('PARTNER_ENTITY', 'I')
        screen = e.peek('CURRENT_SCREEN', 'h')
        # Same loading/handover as modRosterSwitch, whose static body is inlined.
        self.calls([
            ('removeEntity', (old, 1)), ('thunkLoadMMD', (species, 3)),
            ('initializeDigimonObject', (species, 1, e.A('partnerTick'))),
            ('setEntityPosition', (1, -800, 0, -900)), ('setupEntityMatrix', (1,)),
            ('startAnimation', (e.A('PARTNER_ENTITY'), 0)),
            ('loadPartnerSounds', (species,)), ('readMapTFS', (screen,)),
        ])
        e.poke('PARTNER_ENTITY+0x54', struct.pack('<h', 4))
        e.poke('PARTNER_ENTITY+0x34', b'\1')
        e.poke('PARTNER_STATE', b'\1')
        e.poke('PARTNER_SUB_STATE', b'\0')
        # Prepare the checkpoint without triggering a toilet on the warp tile.
        e.poke('PARTNER_PARA', struct.pack('<I', 0))
        e.poke('PARTNER_PARA+0x18', struct.pack('<h', 48))
        e.poke('PARTNER_PARA+0x20', struct.pack('<h', -1))
        assert e.peek('PARTNER_ENTITY', 'I') == species

    def trace(self, path, limit, freeze=False):
        a = self.e.A
        header = 'tick,state,substate,x,z,heading,m02,m22,anim,flags,delta8,tamer,sync,script_paused,npc2x,npc2z,npc3x,npc3z'
        code = fr'''
if WT and WT.bp then WT.bp:remove() end
WT={{n=0,done=false,lines={{}},seen=false}}
local m=PCSX.getMemPtr()
local function u8(a) return tonumber(m[a%0x200000]) end
local function u16(a) return u8(a)+256*u8(a+1) end
local function s16(a) local x=u16(a);if x>=32768 then x=x-65536 end;return x end
local function u32(a) return u16(a)+65536*u16(a+2) end
local function s32(a) local x=u32(a);if x>=2147483648 then x=x-4294967296 end;return x end
local function w32(a,v) for i=0,3 do m[(a+i)%0x200000]=v%256;v=math.floor(v/256) end end
WT.bp=PCSX.addBreakpoint({a('gameLoop')},'Exec',4,'walk-trace',function()
 WT.n=WT.n+1
 local npc=u32({a('ENTITY_TABLE')}+8)
 if npc>=0x80000000 and npc<0x80200000 then
  if '{self.args.npc}'=='absent' then m[(npc+52)%0x200000]=0 end
  if '{self.args.npc}'=='obstruct' then
   local np=u32(npc+4)
   w32(np+120,{self.args.target[0]});w32(np+128,{self.args.target[1]})
   w32(npc+16,{self.args.target[0]}*32768);w32(npc+24,{self.args.target[1]}*32768)
  end
 end
 local p=u32({a('PARTNER_ENTITY')}+4);local mom=u32({a('PARTNER_ENTITY')}+12)
 local st=u8({a('PARTNER_STATE')});local sub=u8({a('PARTNER_SUB_STATE')})
 if st==6 or st==12 then WT.seen=true end
 local row={{WT.n,st,sub,s32(p+120),s32(p+128),s16(p+114),s16(p+24),s16(p+36),u8({a('PARTNER_ENTITY')}+46),u8({a('PARTNER_ENTITY')}+48),s16(mom+52),u8({a('TAMER_STATE')}),u32({a('SOME_SCRIPT_SYNC_BIT')}),u32({a('IS_SCRIPT_PAUSED')})}}
 for slot=2,3 do
  local e=u32({a('ENTITY_TABLE')}+slot*4)
  if e>=0x80000000 and e<0x80200000 then
   local pos=u32(e+4);row[#row+1]=s32(pos+120);row[#row+1]=s32(pos+128)
  else row[#row+1]=0;row[#row+1]=0 end
 end
 WT.lines[#WT.lines+1]=table.concat(row,',')
 if WT.n>={limit} or (WT.seen and st==1 and u8({a('TAMER_STATE')})==0 and u32({a('IS_SCRIPT_PAUSED')})==1) then
  local f=assert(io.open('{path}','w'));f:write('{header}',string.char(10));f:write(table.concat(WT.lines,string.char(10)));f:close();WT.done=true;WT.bp:remove();PCSX.pauseEmulator()
 elseif {str(freeze).lower()} then
  -- Hold translation while leaving the game, animation and watchdog running.
  WT.x=WT.x or s32(p+120);WT.z=WT.z or s32(p+128)
  w32(p+120,WT.x);w32(p+128,WT.z)
  w32({a('PARTNER_ENTITY')}+16,WT.x*32768);w32({a('PARTNER_ENTITY')}+24,WT.z*32768)
 end
end)
PCSX.resumeEmulator();return 'tracing'
'''
        self.lua(code)
        self.until('WT.done', limit/3 + 90)
        rows = list(csv.DictReader(path.open()))
        final = rows[-1]
        complete = final['state'] == '1' and final['tamer'] == '0' and final['script_paused'] == '1'
        return rows, complete

    def run_cases(self, species):
        e, args = self.e, self.args
        e.run('pause')
        self.switch(species)
        e.run('resume')
        assert e.warp(args.screen) and e.in_control(), 'screen did not load with control'
        time.sleep(5)  # A free tamer can precede the final fade/caption render.
        e.run('pause')
        state = self.out / f'field-{species}.state'
        e.run('save', str(state))
        # Two identical screenshots prove that this checkpoint is paused.
        e.run('shot', str(self.out / f'field-{species}-a.png'))
        e.run('shot', str(self.out / f'field-{species}-b.png'))
        assert (self.out / f'field-{species}-a.png').read_bytes() == (self.out / f'field-{species}-b.png').read_bytes()
        results = []
        for i in range(args.start, args.runs):
            e.run('load', str(state))
            e.run('pause')
            angle = 2*math.pi*(i % 10)/10
            radius = 250 + 125*(i//10)
            tx, tz = args.target
            x, z = tx + int(radius*math.cos(angle)), tz + int(radius*math.sin(angle))
            heading = i*701 % 4096
            self.place('PARTNER_ENTITY', x, z, heading)
            tamer = [(tx+350, tz+125), (tx-300, tz+225), (tx-600, tz-10)][i % 3]
            self.place('TAMER_ENTITY', *tamer)
            e.poke('PARTNER_PARA', struct.pack('<I', 0 if args.scripted else 8))
            e.poke('PARTNER_PARA+0x18', struct.pack('<h', 48 if args.scripted else 0))
            e.poke('PARTNER_PARA+0x20', struct.pack('<h', 30000))
            self.calls([('callScriptSection', (0, 1250, 0))])
            if args.scripted:
                # Runtime fixture of ENTITY_WALK_TO; WAIT_FOR_ENTITY; END.
                # This is exactly the instruction path used by partner.walk/arrived.
                code = bytes([0x4e, 0xfc]) + struct.pack('<hh', tx, tz) + bytes([1, 0, 0x4a, 0xfc, 0xfe])
                e.poke('MAP_SCRIPT_BUFFER', code)
                e.poke('SCRIPT_POINTER', struct.pack('<I', e.A('MAP_SCRIPT_BUFFER')))
                # The debugger may finish the current logic tick on pause, so
                # replace the pending routine's state as well as its bytecode.
                e.poke('ACTIVE_INSTRUCTION', b'\0')
                e.poke('PARTNER_STATE', b'\1')
                e.poke('PARTNER_SUB_STATE', b'\0')
                e.poke('TAMER_STATE', b'\0')
                e.poke('SOME_SCRIPT_SYNC_BIT', struct.pack('<i', 1))
            stem = f'{species}-{i:02d}'
            rows, complete = self.trace(self.out / (stem + '.csv'), args.limit, args.freeze)
            e.run('shot', str(self.out / (stem + '.png')))
            if not complete:
                e.run('save', str(self.out / (stem + '.state')))
            counts = {}
            for row in rows:
                if row['state'] == '6':
                    counts[row['substate']] = counts.get(row['substate'], 0) + 1
            ram = e.ram()
            condition = e.peek('PARTNER_PARA', 'I', ram)
            poop_level = e.peek('PARTNER_PARA+0x18', 'h', ram)
            if complete and not args.scripted:
                assert condition & 8 == 0 and poop_level > 0, 'toilet did not clear the need'
            result = dict(species=species, case=i, start=[x,z], heading=heading,
                          tamer=tamer, complete=complete, ticks=len(rows), toilet_substate_ticks=counts,
                          condition=condition, poop_level=poop_level)
            results.append(result)
            print(json.dumps(result), flush=True)
            (self.out / f'results-{species}.json').write_text(json.dumps(results, indent=2)+'\n')
        return all(r['complete'] for r in results)

    def follow(self, species):
        """Ordinary partnerTickWalking and actual pad control after the toilet."""
        e = self.e
        e.run('load', str(self.out / f'field-{species}.state'))
        e.run('pause')
        self.place('PARTNER_ENTITY', -850, -1500)
        self.place('TAMER_ENTITY', -850, -800)
        e.poke('STORED_TAMER_POS', struct.pack('<3i', -850, 0, -800))
        self.calls([('initializePartnerWaypoint', ()), ('partnerSetState', (1,)), ('tamerSetState', (0,))])
        before = e.ram()
        a = e.A
        self.lua(f'''
if WF and WF.bp then WF.bp:remove() end
WF={{n=0,done=false}}
local button=PCSX.CONSTS.PAD.BUTTON.DOWN
WF.bp=PCSX.addBreakpoint({a('gameLoop')},'Exec',4,'walk-follow',function()
 WF.n=WF.n+1
 if WF.n==1 then PCSX.SIO0.slots[1].pads[1].setOverride(button) end
 if WF.n==9 then PCSX.SIO0.slots[1].pads[1].clearOverride(button) end
 if WF.n==80 then WF.bp:remove();WF.done=true;PCSX.pauseEmulator() end
end)
PCSX.resumeEmulator();return 'following'
''')
        self.until('WF.done', 90)
        after = e.ram()
        result = {}
        for entity in ('PARTNER_ENTITY', 'TAMER_ENTITY'):
            start = e.peek(entity + '+0x10', '3i', before)
            end = e.peek(entity + '+0x10', '3i', after)
            result[entity] = dict(before=start, after=end, moved=start != end)
        result['control'] = e.peek('TAMER_STATE', 'b', after) == 0 and e.peek('IS_SCRIPT_PAUSED', 'i', after) == 1
        result['screen'] = e.peek('CURRENT_SCREEN', 'h', after)
        (self.out / f'follow-{species}.json').write_text(json.dumps(result, indent=2)+'\n')
        e.run('shot', str(self.out / f'follow-{species}.png'))
        assert result['control'] and result['screen'] == self.args.screen
        assert all(result[x]['moved'] for x in ('PARTNER_ENTITY', 'TAMER_ENTITY'))
        print('FOLLOW ' + json.dumps(result), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc')
    ap.add_argument('--exe', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=41145)
    ap.add_argument('--card', default=str(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd'))
    ap.add_argument('--species', nargs='+', type=int, default=[373,3])
    ap.add_argument('--runs', type=int, default=30)
    ap.add_argument('--start', type=int, default=0, help='first case index, for resuming a sweep')
    ap.add_argument('--screen', type=int, default=44)
    ap.add_argument('--target', nargs=2, type=int, default=[-1200,-925])
    ap.add_argument('--limit', type=int, default=1200)
    ap.add_argument('--attach', action='store_true')
    ap.add_argument('--checkpoint', type=Path, help='clean state from this same disc when attaching')
    ap.add_argument('--scripted', action='store_true')
    ap.add_argument('--freeze', action='store_true')
    ap.add_argument('--npc', choices=['natural', 'obstruct', 'absent'], default='natural')
    args = ap.parse_args()
    test = WalkTest(args)
    e = test.e
    started = False
    try:
        if not args.attach:
            with socket.socket() as sk:
                if sk.connect_ex(('127.0.0.1', args.port)) == 0:
                    raise RuntimeError('port is already in use; choose a distinct EMU_PORT')
            e.start(args.card)
            started = True
            if not args.checkpoint:
                assert e.continue_game() == 0 and e.in_control(), 'boot did not reach control'
        assert len(e.ram()) == 0x200000
        test.lua("for _,n in ipairs({'WT','WF','TT'}) do local v=_G[n];if v and v.bp then v.bp:remove() end end;return 'clean'")
        e.run('pause')
        if args.checkpoint:
            e.run('load', str(args.checkpoint.resolve()))
        boot = test.out / 'boot.state'
        e.run('save', str(boot))
        ok = True
        for species_id in args.species:
            e.run('load', str(boot))
            ok = test.run_cases(species_id) and ok
            if not args.scripted and not args.freeze:
                test.follow(species_id)
        if not ok:
            raise SystemExit('FAIL: an arrival wait did not finish before the tick limit')
    finally:
        if started:
            e.stop()


if __name__ == '__main__':
    main()
