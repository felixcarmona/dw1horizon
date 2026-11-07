#!/usr/bin/env python3
"""Exercise real inventory feeding with imported models on original 2 MB RAM.

Models load through the game's evolution or roster shortcut; feeding uses pad input. Captures and
per-refresh pose/visibility traces stay under --out. --all checks every imported
partner carried by the supplied archive. Care/time writes isolate the sequence.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu, test_card
from tools.dev.playtest.frigimon_recruitment import fixture_partner
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols
import species
import dwmap
from tools.membudget import Ram, heap_walk


def put(e, symbol, fmt, value):
    e.poke(symbol, struct.pack('<' + fmt, value))


def flag(e, number, value):
    expr = f'SCRIPT_STATE+{245 + number // 8}'
    old = e.peek(expr, 'B')
    put(e, expr, 'B', old | 1 << (number % 8) if value else old & ~(1 << (number % 8)))


def stage(e, x, z, item=38, discipline=100):
    e.run('pause')
    e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0', 'partner.para.evoTimer=0',
         'partner.para.remainingLifetime=1000', 'partner.para.condition=4',
         'partner.para.energyLevel=0', f'partner.para.discipline={discipline}',
         'partner.para.foodLevel=0', 'partner.para.happiness=50',
         f'inventory.types=[{item}' + ',-1' * 29 + ']',
         'inventory.amounts=[2' + ',0' * 29 + ']',
         'inventory.names=[0' + ',255' * 29 + ']')
    put(e, 'INVENTORY_POINTER', 'B', 0)
    put(e, 'ITEM_SCOLD_FLAG', 'B', 0)
    for entity, nx in [('TAMER_ENTITY', x), ('PARTNER_ENTITY', x - 350)]:
        ptr = e.peek(entity + '+4', 'I')
        e.run('poke', hex(ptr + 0x78), struct.pack('<3i', nx, 0, z).hex())
        e.poke(entity + '+0x10', struct.pack('<3i', nx << 15, 0, z << 15))
    e.poke('STORED_TAMER_POS', struct.pack('<3i', x, 0, z))
    e.run('resume')
    # Pan through the engine so its tile ring follows the setup position.
    call(e,'createCameraMovement',e.peek('TAMER_ENTITY+4','I')+0x78,10)
    put(e,'CAMERA_REACHED_TARGET','i',0)
    e.run('resume')
    for _ in range(120):
        if e.peek('CAMERA_REACHED_TARGET','i') == 1: break
        e.wait(.2)
    else: raise AssertionError('setup camera pan did not finish')
    e.wait(.5)


def watch(e):
    e.run('lua', f'''
      FV={{samples={{}},n=0}}
      local m=PCSX.getMemPtr()
      local function u32(o) return m[o]+256*m[o+1]+65536*m[o+2]+16777216*m[o+3] end
      local function i32(o) local v=u32(o); if v>=2147483648 then v=v-4294967296 end; return v end
      local function u16(o) return m[o]+256*m[o+1] end
      local ent={e.A('PARTNER_ENTITY') & 0x1fffff}
      FV.listener=PCSX.Events.createEventListener('GPU::Vsync',function()
        if #FV.samples>=6000 then return end
        FV.n=FV.n+1
        local p=u32(ent+4)%2097152
        FV.samples[#FV.samples+1]=string.format('%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d',
          FV.n,m[ent+46],u16(ent+28),m[ent+52],m[ent+53],m[ent+54],
          i32(p+136+96),i32(p+136+100),i32(p+136+104),
          i32(p+120),i32(p+124),i32(p+128),m[{e.A('PARTNER_STATE') & 0x1fffff}])
      end)
    ''')


def feed(e, out, sid, item=38, discipline=100, record=False, handoff=False):
    label = f'{sid}-item-{item}'
    watch(e)
    rec = None
    try:
        if record:
            rec = subprocess.Popen([sys.executable, str(ROOT / 'tools/dev/emulator.py'),
                'record', str(out / (label + '.mp4')), '18', '20'], env=e.env,
                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        e.press('TRIANGLE', 12)
        for _ in range(12):
            if e.peek('PARTNER_STATE', 'B') == 5:
                break
            e.press('CONFIRM', 12)
            e.wait(.2)
        else:
            raise AssertionError('inventory never started feeding')
        handoff = handoff and e.peek('PARTNER_SUB_STATE','B') in (0,1,2)
        if handoff:
            # Isolate the clip from large models' approach clearance. The real
            # handover, cold read, reaction and item effect still run normally.
            put(e,'PARTNER_SUB_STATE','B',3)
        seen = set()
        deadline = time.monotonic() + 80
        while time.monotonic() < deadline:
            ram = e.ram()
            state = e.peek('PARTNER_STATE', 'B', ram)
            anim = e.peek('PARTNER_ENTITY+0x2e', 'B', ram)
            frame = e.peek('PARTNER_ENTITY+0x1c', 'h', ram)
            if state == 5 and anim in (8, 13) and anim not in seen:
                seen.add(anim)
                e.run('shot', str(out / f'{label}-clip-{anim}.png'))
            if state != 5 and seen:
                break
            e.wait(.1)
        else:
            raise AssertionError('feeding did not finish')
        text = e.run('lua', "FV.listener:remove();return table.concat(FV.samples,'\\n')")
        (out / (label + '.csv')).write_text('refresh,clip,frame,on_map,on_screen,flat,scale_x,scale_y,scale_z,x,y,z,partner_state\n'+text)
        samples = [list(map(int, line.split(','))) for line in text.strip().splitlines()]
        played = [row for row in samples if row[1] in (8, 13) and row[-1] == 5]
        hidden = [row for row in played if not row[3] or not row[4] or row[5] != 255 or min(row[6:9]) <= 0]
        amount = e.peek('INVENTORY+60', 'B')
        heap = heap_walk(Ram(e.ram(),e.table))
        assert heap['corrupt'] is None, heap
        result = dict(species=sid, item=item, clips=sorted(seen), samples=len(played),
                      handoff_fixture=handoff, cold_cache_type=e.peek('MOD_COLD_CACHE_TYPE','i'),
                      render_mode=e.peek('MOD_FPS_MODE_RUN','i'),
                      hidden_samples=len(hidden), remaining=amount, ram_bytes=len(e.ram()),
                      heap={k:v for k,v in heap.items() if k != 'blocks'})
        e.run('shot', str(out / (label + '-after.png')))
        if rec:
            rec.wait(timeout=40)
            rec = None
        return result
    finally:
        e.run('lua', 'if FV.listener then FV.listener:remove() end', check=False)
        if rec:
            rec.terminate()
            rec.wait(timeout=10)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc')
    ap.add_argument('--exe', required=True)
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--map', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=42611)
    ap.add_argument('--pixel', nargs=2, type=int, default=[650,150])
    ap.add_argument('--ids', nargs='+', type=int, default=[307])
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--record', action='store_true')
    ap.add_argument('--item', type=int, default=38)
    ap.add_argument('--discipline', type=int, default=100)
    ap.add_argument('--require-clip', type=int, choices=(8,13))
    ap.add_argument('--handoff-fixture', action='store_true', help='skip only the approach walk after selecting Use')
    a = ap.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    _, _, records = species.read_archive(a.archive)
    ids = [t for t,r in enumerate(records) if 180 <= t < 470 and r['flags'] & species.FLAG_PARTNER] if a.all else a.ids
    m = dwmap.MapFile(a.map.read_bytes())
    sys.path.insert(0, str(ROOT / 'story/mods/what-the-island-forgot/maps'))
    from mapbase import Cam
    x,z = Cam(m).world(*a.pixel)
    e = ProofEmu(a.disc, a.exe, a.port, str(out))
    for name,(addr,_,_) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name,addr)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    results = []
    try:
        e.start(test_card(out))
        e.run('lua', f"PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'skip-intro',function() PCSX.getRegisters().GPR.n.a1=0 end)")
        assert e.continue_game() == 0
        print('Continued on 2 MB',flush=True)
        put(e,'MOD_OPT_STORY','i',1)
        e.gs('set','gametime_running=0','hour=10','partner.para.condition=0',
             'partner.para.foodLevel=100','partner.para.energyLevel=100',
             'partner.para.poopLevel=0','partner.para.tiredness=0',
             'partner.para.sleepyHour=23','partner.para.wakeupHour=1',
             'partner.para.nextHungerHour=23','partner.para.remainingLifetime=1000')
        flag(e,735,True)
        assert e.warp(309)
        print('Loaded Drowned Shore',flush=True)
        e.gs('set', 'gametime_running=0', 'hour=10')
        previous = None
        put(e,'MOD_OPT_CHEATS','i',1)
        put(e,'MOD_OPT_SHORTCUTS','i',1)
        put(e,'MOD_OPT_NEW_DIGIMON','i',1)
        for sid in ids:
            print(f'Loading partner {sid}',flush=True)
            if previous is not None and sid > previous:
                for _ in range(5):
                    e.chord('SELECT','L1',8);e.wait(.4)
                    if e.peek('PARTNER_ENTITY','i') != previous: break
            if e.peek('PARTNER_ENTITY','i') != sid:
                fixture_partner(e,sid)
            previous = sid
            stage(e,x,z,a.item,a.discipline)
            assert e.peek('PARTNER_ENTITY','i') == sid
            result = feed(e,out,sid,a.item,a.discipline,record=a.record,handoff=a.handoff_fixture)
            results.append(result)
            (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
            print(json.dumps(result),flush=True)
            assert result['clips'] in ([8],[13]), result
            assert result['remaining'] == (2 if result['clips']==[13] else 1), result
            if a.require_clip is not None: assert a.require_clip in result['clips'], result
            assert result['cold_cache_type'] == -1, result
            for _ in range(8):
                if not e.peek('IS_IN_MENU','i'): break
                e.press('CANCEL',12);e.wait(.3)
            assert not e.peek('IS_IN_MENU','i')
            assert result['samples'] and not result['hidden_samples'], result
    finally:
        e.stop()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
