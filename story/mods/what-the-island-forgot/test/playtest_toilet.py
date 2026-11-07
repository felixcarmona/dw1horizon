#!/usr/bin/env python3
"""Run real File City toilet visits with imported partners on original 2 MB RAM.

Care values, approach positions and optional snapshot are fixtures. The map's
actual toilet tile starts the normal script; no state-machine phase is skipped.
Each visit must play slot 10, restore care and control, then permit pad movement.
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
from tools.membudget import Ram, heap_walk
import species
from playtest_feeding import put


def position(e, entity):
    p = e.peek(entity + '+4', 'I')
    return struct.unpack_from('<3i', e.ram(), (p & 0x1fffff) + 0x78)


def place(e, entity, x, z):
    p = e.peek(entity + '+4', 'I')
    e.run('poke', hex(p + 0x78), struct.pack('<3i', x, 0, z).hex())
    e.poke(entity + '+0x10', struct.pack('<3i', x << 15, 0, z << 15))


def stage(e, sleep_due=False):
    e.run('pause')
    e.gs('set', 'gametime_running=0', 'hour=20', 'minute=50',
         'partner.para.condition=0', 'partner.para.foodLevel=100',
         'partner.para.poopLevel=100', 'partner.para.poopingTimer=2000',
         'partner.para.tiredness=0', 'partner.para.energyLevel=100',
         'partner.para.evoTimer=0', 'partner.para.remainingLifetime=1000',
         f'partner.para.sleepyHour={20 if sleep_due else 23}', 'partner.para.wakeupHour=1')
    ram = e.ram()
    off = e.A('MAP_COLLISION_DATA') & 0x1fffff
    cells = [(i % 100 * 100 - 4950, 4950 - i // 100 * 100)
             for i, v in enumerate(ram[off:off + 10000]) if v == 120]
    assert cells, 'map has no native toilet trigger'
    tx, tz, _, _ = e.peek('TOILET_DATA+64', '4h')  # File City's toilet, index 9.
    x, z = min(cells, key=lambda p: (p[0] - tx)**2 + (p[1] - tz)**2)
    # Frame the setup without entering the trigger while the need is active.
    place(e, 'TAMER_ENTITY', x, z)
    place(e, 'PARTNER_ENTITY', tx + 200, tz - 650)
    call(e, 'createCameraMovement', e.peek('TAMER_ENTITY+4', 'I') + 0x78, 10)
    put(e, 'CAMERA_REACHED_TARGET', 'i', 0)
    e.run('resume')
    for _ in range(120):
        if e.peek('CAMERA_REACHED_TARGET', 'i') == 1:
            break
        e.wait(.2)
    else:
        raise AssertionError('setup camera did not finish')
    e.run('pause')
    place(e, 'TAMER_ENTITY', x, z)
    e.gs('set', 'partner.para.condition=8', 'partner.para.poopLevel=0',
         'partner.para.poopingTimer=2000')
    return (x, z)


def watch(e, bones):
    start, size, _ = elf_symbols(e.exe + '.elf')['tickPartnerToilet']
    addresses = {k: e.A(k) & 0x1fffff for k in
                 ('PARTNER_ENTITY', 'PARTNER_STATE', 'PARTNER_SUB_STATE', 'TAMER_STATE',
                  'MOD_FPS_TICKS', 'MOD_COLD_PENDING', 'IS_SCRIPT_PAUSED', 'ACTIVE_INSTRUCTION')}
    e.run('lua', f'''
      TV={{samples={{}},lookCalls=0,wrongTargets=0,lookExample=''}}
      local m=PCSX.getMemPtr()
      local function u16(o) return m[o]+256*m[o+1] end
      local function u32(o) return u16(o)+65536*u16(o+2) end
      local function i32(o) local v=u32(o);if v>=2147483648 then v=v-4294967296 end;return v end
      local a={{{','.join(k+'='+str(v) for k,v in addresses.items())}}}
      TV.look=PCSX.addBreakpoint({e.A('entityLookAtLocation')},'Exec',4,'toilet-return-target',function()
        local r=PCSX.getRegisters().GPR.n
        if m[a.PARTNER_STATE]==6 and m[a.PARTNER_SUB_STATE]==4 and
           r.a0=={e.A('TAMER_ENTITY')} and r.ra>={start} and r.ra<{start+size} then
          local expected=u32(a.PARTNER_ENTITY+4)+120
          TV.lookCalls=TV.lookCalls+1
          if r.a1~=expected then TV.wrongTargets=TV.wrongTargets+1 end
          TV.lookExample=string.format('%u,%u',r.a1,expected)
        end
      end)
      TV.listener=PCSX.Events.createEventListener('GPU::Vsync',function()
        if #TV.samples>=12000 then return end
        local ent=a.PARTNER_ENTITY
        local p=u32(ent+4)%2097152
        local meshes=0
        for b=0,{bones}-1 do
          local mesh=u32(p+136*b+8)
          if mesh>=2147483648 and mesh<2149580800 then meshes=meshes+1 end
        end
        TV.samples[#TV.samples+1]=string.format('%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d',
          u32(a.MOD_FPS_TICKS),m[a.PARTNER_STATE],m[a.PARTNER_SUB_STATE],m[ent+46],
          u16(ent+28),u16(ent+30),m[a.TAMER_STATE],u32(a.MOD_COLD_PENDING),
          u32(a.IS_SCRIPT_PAUSED),m[a.ACTIVE_INSTRUCTION],i32(p+120),i32(p+124),i32(p+128),
          meshes,m[ent+52],m[ent+53],m[ent+54])
      end)
    ''')


def visit(e, out, sid, bones, max_ticks, record=False, sleep_due=False, allow_wrong_target=False):
    assert e.peek('PARTNER_ENTITY', 'i') == sid, 'fixture loaded another partner'
    trigger = stage(e, sleep_due)
    e.run('shot', str(out / f'{sid}-before.png'))
    watch(e, bones)
    rec = None
    try:
        if record:
            rec = subprocess.Popen([sys.executable, str(ROOT / 'tools/dev/emulator.py'),
                'record', str(out / f'{sid}-toilet.mp4'), '25', '20'], env=e.env,
                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        e.run('resume')
        e.press('UP', 8)
        deadline = time.monotonic() + 100
        captured = False
        start = e.peek('MOD_FPS_TICKS', 'I')
        while time.monotonic() < deadline:
            ram = e.ram()
            state = e.peek('PARTNER_STATE', 'B', ram)
            clip = e.peek('PARTNER_ENTITY+0x2e', 'B', ram)
            frame = e.peek('PARTNER_ENTITY+0x1c', 'h', ram)
            if state == 6 and clip == 10 and frame >= 2 and not captured:
                captured = True
                e.run('shot', str(out / f'{sid}-toilet-clip.png'))
            if captured and e.peek('TAMER_STATE', 'B', ram) == 0 and e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1:
                break
            if (e.peek('MOD_FPS_TICKS', 'I', ram) - start) & 0xffffffff > max_ticks:
                raise AssertionError(f'{sid}: toilet did not restore control within {max_ticks} logic ticks')
            e.wait(.1)
        else:
            raise AssertionError(f'{sid}: toilet stalled')
        raw = e.run('lua', "TV.listener:remove();return table.concat(TV.samples,'\\n')")
        header = 'tick,state,sub,clip,frame,count,tamer,cold_pending,script_paused,instruction,x,y,z,meshes,on_map,on_screen,flat\n'
        (out / f'{sid}-toilet.csv').write_text(header + raw)
        rows = [list(map(int, s.split(','))) for s in raw.strip().splitlines()]
        played = [r for r in rows if r[1] == 6 and r[3] == 10 and r[4] >= 2 and r[5] != 32767]
        assert played and min(r[13] for r in played) > 0, 'toilet clip lost resident geometry'
        # Buildings can legitimately hide the partner during the toilet clip.
        # The exit must restore both control and actual movement on open ground.
        para = json.loads(e.gs('dump'))['partner']['para']
        assert not para['condition'] & 8 and para['poopLevel'] > 0, para
        before = position(e, 'TAMER_ENTITY')
        moved = 0
        for direction in ('DOWN', 'RIGHT', 'LEFT', 'UP'):
            e.press(direction, 16)
            after = position(e, 'TAMER_ENTITY')
            moved = abs(after[0] - before[0]) + abs(after[2] - before[2])
            if moved >= 30:
                break
        assert moved >= 30, ('control returned but pad did not move', before, after)
        heap = heap_walk(Ram(e.ram(), e.table))
        assert heap['corrupt'] is None, heap
        look = list(map(int, e.run('lua', "return TV.lookCalls..','..TV.wrongTargets..','..TV.lookExample").strip().split(',')))
        result = dict(species=sid, ram_bytes=len(e.ram()), trigger=trigger,
                      samples=len(played), elapsed_ticks=rows[-1][0] - rows[0][0],
                      phases=sorted({r[2] for r in rows if r[1] == 6}),
                      cold_pending_seen=any(r[7] for r in rows),
                      minimum_resident_meshes=min(r[13] for r in played),
                      movement=moved, movement_direction=direction,
                      return_look_calls=look[0], wrong_return_targets=look[1],
                      return_target=look[2], expected_return_target=look[3],
                      poopLevel=para['poopLevel'], condition=para['condition'],
                      heap={k: v for k, v in heap.items() if k != 'blocks'})
        e.run('shot', str(out / f'{sid}-after.png'))
        (out / f'{sid}-result.json').write_text(json.dumps(result, indent=2) + '\n')
        assert look[0] > 0, 'toilet exit look was not observed'
        assert allow_wrong_target or look[1] == 0, ('toilet exit reads the wrong position', result)
        if rec:
            rec.wait(timeout=40)
            rec = None
        return result
    finally:
        path = out / f'{sid}-toilet.csv'
        if not path.exists():
            raw = e.run('lua', "if TV.samples then return table.concat(TV.samples,'\\n') end", check=False)
            path.write_text('tick,state,sub,clip,frame,count,tamer,cold_pending,script_paused,instruction,x,y,z,meshes,on_map,on_screen,flat\n' + raw)
        e.run('shot', str(out / f'{sid}-last.png'), check=False)
        e.run('lua', 'if TV.listener then TV.listener:remove() end', check=False)
        e.run('lua', 'if TV.look then TV.look:remove() end', check=False)
        if rec:
            rec.terminate()
            rec.wait(timeout=10)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=42611)
    p.add_argument('--ids', type=int, nargs='+', default=[307])
    p.add_argument('--all', action='store_true')
    p.add_argument('--state', type=Path)
    p.add_argument('--record', action='store_true')
    p.add_argument('--sleep-due', action='store_true')
    p.add_argument('--max-ticks', type=int, default=400)
    p.add_argument('--allow-wrong-target', action='store_true', help='record the known pre-fix invalid return pointer')
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    _, _, records = species.read_archive(a.archive)
    ids = [i for i, r in enumerate(records) if 180 <= i < 470 and r['flags'] & species.FLAG_PARTNER] if a.all else a.ids
    e = ProofEmu(a.disc, a.exe, a.port, str(out))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for n, (addr, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(n, addr)
    results = []
    try:
        e.start(test_card(out))
        e.run('lua', f"PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'skip-intro',function() PCSX.getRegisters().GPR.n.a1=0 end)")
        if a.state:
            e.run('load', str(a.state.resolve()))
            e.run('resume')
            e.wait(1)
        else:
            assert e.continue_game() == 0
        assert len(e.ram()) == 2097152
        put(e, 'MOD_OPT_STORY', 'i', 1)
        for opt in ('MOD_OPT_CHEATS', 'MOD_OPT_SHORTCUTS', 'MOD_OPT_NEW_DIGIMON'):
            put(e, opt, 'i', 1)
        if e.peek('CURRENT_SCREEN', 'h') != 168:
            assert e.warp(168)
        for sid in ids:
            print(f'Loading partner {sid}', flush=True)
            previous = e.peek('PARTNER_ENTITY', 'i')
            if sid != previous:
                e.chord('SELECT', 'L1', 8)
                e.wait(.4)
            if e.peek('PARTNER_ENTITY', 'i') != sid:
                fixture_partner(e, sid)
            result = visit(e, out, sid, records[sid]['para']['boneCount'], a.max_ticks,
                           record=a.record, sleep_due=a.sleep_due, allow_wrong_target=a.allow_wrong_target)
            results.append(result)
            (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
            e.run('save', str(out / 'resume.state'))
            print(json.dumps(result), flush=True)
    finally:
        e.stop()


if __name__ == '__main__':
    main()
