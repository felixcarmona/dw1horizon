#!/usr/bin/env python3
"""Measure MP x5, MP x1, HP x5 and early stops with native Frigimon at 2 MB.

The real gym state machines execute every award. Fixture writes choose the
partner, menu row and care state; cancel skips only the first exercise animation.
--before expects the old extra walk before the second MP award.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.training_care_hud import fixture, care
from tools.dev.playtest.training_evolution import await_value
from tools.langpatch import elf_symbols


def run(e, out, prefix, screen, gym, sessions, food, before):
    fixture(e, out/'boot.state', screen, prefix, gym=gym, sessions=sessions, food=food)
    state = 'TRAINING_STATE' if prefix == 'TRN' else 'MAIN_D_801353BD'
    e.run('resume')
    await_value(e, state, 'b', lambda n: n == (3 if gym == 'Mp' else 2))
    e.run('pause')
    e.run('lua', f'''
MP={{vsync=0,events={{}},last=-1,done=false,bp={{}},opened=false}}
local m=PCSX.getMemPtr()
local function u8(a) return tonumber(m[a%0x200000]) end
local function u32(a) return u8(a)+256*u8(a+1)+65536*u8(a+2)+16777216*u8(a+3) end
local function event(s)
 MP.events[#MP.events+1]={{label=s,vsync=MP.vsync,tick=u32({e.A('MOD_FPS_TICKS')})}}
end
local function hook(a,f) MP.bp[#MP.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'mp-training',f) end
MP.v=PCSX.Events.createEventListener('GPU::Vsync',function() MP.vsync=MP.vsync+1 end)
hook({e.A(prefix+'_tick'+gym+'Training')},function()
 local st=u8({e.A(state)})
 if st~=MP.last then event('state '..st);MP.last=st end
 if MP.opened and MP.vsync>=MP.box+18 then MP.done=true;PCSX.pauseEmulator() end
end)
hook({e.A(prefix+'_modBlockNext')},function() event('award') end)
hook({e.A(prefix+'_modOpenStatsBox')},function()
 event('box');MP.opened=true;MP.box=MP.vsync
end)
hook({e.A('loadColdAnimation')},function() event('cold '..PCSX.getRegisters().GPR.n.a2) end)
''')
    cancel = 'CROSS'  # The fixture selects Circle to confirm.
    e.api('/api/v1/lua/press?button='+cancel)
    e.run('resume')
    deadline = time.monotonic() + 180
    try:
        while e.run('lua', 'return MP.done').strip() != 'true':
            count = int(e.run('lua', "local n=0;for _,v in ipairs(MP.events) do if v.label=='award' then n=n+1 end end;return n").strip())
            if count:
                e.api('/api/v1/lua/release?button='+cancel)
            assert time.monotonic() < deadline, 'no MP stats table'
            time.sleep(.1)
        raw = e.run('lua', "local t={};for _,v in ipairs(MP.events) do t[#t+1]=v.label..'|'..v.vsync..'|'..v.tick end;return table.concat(t,'\\n')")
        events = []
        for line in raw.strip().splitlines():
            label, vsync, tick = line.split('|')
            events.append(dict(label=label, vsync=int(vsync), tick=int(tick)))
        label = f'{prefix}-{gym}-x{sessions}-food{food}'
        result = dict(label=label, events=events, care=care(e))
        e.run('shot', str(out/(label+'.png')))
    finally:
        e.api('/api/v1/lua/release?button='+cancel)
        e.run('lua', 'for _,b in ipairs(MP.bp) do b:remove() end;MP.v:remove()')
    awards = [v for v in events if v['label'] == 'award']
    assert len(awards) == (1 if food == 10 else sessions), result
    assert result['care']['evoTimer'] == len(awards), result
    assert not any(v['label'].startswith('cold ') for v in events), result
    gaps = [b['tick']-a['tick'] for a,b in zip(awards, awards[1:])]
    if gaps:
        if before and gym == 'Mp':
            assert gaps[0] > 22, result
            gaps = gaps[1:]
        assert all(v == 21 for v in gaps), result
    e.run('resume')
    # A single fresh tally skip, then wait for the native walk/cleanup to finish.
    for _ in range(200):
        if e.peek('UI_BOX_DATA+54', 'h') == 1:
            e.press('CONFIRM', 12)
            break
        e.wait(.1)
    assert e.in_control(), 'gym did not return field control'
    print(json.dumps(result), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=42172)
    p.add_argument('--before', action='store_true')
    p.add_argument('--boot-state', type=Path, help='field state from this same disc')
    args = p.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(args.disc, args.exe, args.port, str(out/'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (address, _, _) in elf_symbols(args.exe+'.elf').items():
        e.table.setdefault(name, address)
    try:
        e.start(field_card(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd',
                           out/'field.mcd', partner_type=23))
        if args.boot_state:
            e.run('load', str(args.boot_state.resolve()))
            e.run('resume')
        else:
            assert e.continue_game() == 0
        assert len(e.ram()) == 2097152
        e.poke('MOD_OPT_BUTTONS', struct.pack('<i', 1))
        e.run('save', str(out/'boot.state'))
        results = []
        for case in [('TRN',112,'Mp',1,400), ('TRN',112,'Mp',5,400),
                     ('TRN',112,'Hp',5,400), ('TRN',112,'Mp',5,10),
                     ('TRN2',165,'Mp',5,400)]:
            results.append(run(e, out, *case, args.before))
        (out/'result.json').write_text(json.dumps(dict(ram_bytes=2097152,
                                      before=args.before, runs=results), indent=2)+'\n')
        print('PASS: MP and HP timing, x1/x5, hunger stop, care costs, field return', flush=True)
    finally:
        e.stop()


if __name__ == '__main__':
    main()
