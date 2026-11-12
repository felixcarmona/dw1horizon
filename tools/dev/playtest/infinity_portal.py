#!/usr/bin/env python3
"""Check the Mount Infinity lower portal and three-Vermilimon encounter on 2 MB.

Boots a disposable corpus card and installs fixture partners through evolution.
The portal section, arrival, enemy placements and battle loader are unmodified.
Strong partner stats bound the encounter; --cleanup may zero enemy HP after
observing battle progress, so that mode proves loading rather than combat AI.
"""
import argparse
import bisect
import json
from pathlib import Path
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu, test_card
from tools.dev.playtest.quest_regressions import evolve_fixture
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols
from tools.membudget import Ram, heap_walk


def sample(e):
    ram = e.ram()
    flow = json.loads(e.api('/api/v1/execution-flow'))
    assert flow['8mb'] == e.expanded_ram and len(ram) == 0x200000
    heap = heap_walk(Ram(ram, e.table))
    row = {k: e.peek(k, f, ram) for k, f in (
        ('CURRENT_SCREEN', 'h'), ('TAMER_STATE', 'B'), ('GAME_STATE', 'H'),
        ('ENEMY_COUNT', 'i'), ('BATTLE_FRAME_COUNT', 'i'), ('PARTNER_ENTITY', 'i'),
        ('MOD_OPT_QUICK_BATTLE', 'i'), ('MOD_BATTLE_LOADING', 'b'))}
    row.update(ram_bytes=len(ram), expanded_ram=flow['8mb'], running=flow['running'],
               tamer=e.peek('TAMER_POSITION_DATA+0x78', '3i', ram),
               heap={k: v for k, v in heap.items() if k != 'blocks'})
    row['stream_failures'] = int(e.run('lua', 'return IP.streamFailures').strip())
    row['battle_cold_reads'] = int(e.run('lua', 'return IP.coldReads').strip())
    row['tile_window'] = [e.peek(k, 'b', ram) for k in ('MAP_TILE_X', 'MAP_TILE_Y')]
    frame=e.peek('ACTIVE_FRAMEBUFFER','i',ram)
    row['gpu']={
        'framebuffer': frame,
        'packet_pointer': e.peek('GsOUT_PACKET_P','I',ram),
        'ot_lengths': e.peek('GS_ORDERING_TABLE','I',ram),
        'ot1_length': e.peek('GS_ORDERING_TABLE+20','I',ram),
    }
    row['enemies'] = []
    for slot in range(8):
        ptr = e.peek(f'ENTITY_TABLE+{4*(slot+2)}', 'I', ram)
        if not 0x80000000 < ptr < 0x80200000:
            continue
        pd = e.peek(f'NPC_ENTITIES+{104*slot+4}', 'I', ram)
        row['enemies'].append(dict(slot=slot, species=e.peek(f'NPC_ENTITIES+{104*slot}', 'i', ram),
             position=struct.unpack_from('<3i', ram, (pd & 0x1fffff)+0x78),
             hp=e.peek(f'NPC_ENTITIES+{104*slot+0x4c}', 'h', ram)))
    combat = e.peek('COMBAT_DATA_PTR', 'I', ram)
    row['participants'] = []
    if row['GAME_STATE'] == 1 and 0x80000000 <= combat < 0x80200000 - 1668:
        ids = ram[(combat & 0x1fffff) + 1645:][:row['ENEMY_COUNT']]
        row['participants'] = [n for n in row['enemies'] if n['slot'] + 2 in ids]
    return row


def equip_only(e, technique):
    """Leave the partner one learned and equipped technique (as seam_movesets' fixture)."""
    ram = e.ram()
    species = e.peek('PARTNER_ENTITY', 'i', ram)
    para = e.A('DIGIMON_DATA') - 0x80000000 + species * 52
    moves = list(ram[para + 35:para + 51])
    assert technique in moves, f'species {species} cannot use technique {technique}: {moves}'
    e.poke('PARTNER_ENTITY+0x40', bytes([100, 0, 0, 0, 46 + moves.index(technique), 255, 255, 255]))
    e.poke('PARTNER_ENTITY+0x58', (1 << technique).to_bytes(16, 'little'))


def gpu_monitor(e):
    """Per render pass: packet-area peak and violations; every write to the ordering-table headers in battle."""
    out = e.run('lua', f'''
      local ffi=require('ffi')
      local function word(a) return tonumber(ffi.cast('uint32_t*',PCSX.getMemPtr()+a-0x80000000)[0]) end
      local function battle() return word({e.A('GAME_STATE')})%65536==1 end
      IP.gpu={{passes=0,peak=0,violations=0,first=nil,writers={{}},moves={{}}}}
      IP.bp[3]=PCSX.addBreakpoint({e.A('applyDrawOffset')},'Exec',4,'portal-packets',function()
        local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
        if frame~=0 and frame~=1 then IP.gpu.violations=IP.gpu.violations+1; return end
        local used=word({e.A('GsOUT_PACKET_P')})-({e.A('GS_WORK_BASES')}+frame*0x14000)
        IP.gpu.passes=IP.gpu.passes+1
        if used>IP.gpu.peak then IP.gpu.peak=used end
        if used<0 or used>0x14000 or word({e.A('GS_ORDERING_TABLE')}+frame*20)~=12 then
          IP.gpu.violations=IP.gpu.violations+1
          if not IP.gpu.first then IP.gpu.first=string.format('used=%d frame=%d',used,frame) end
        end
      end)
      IP.bp[4]=PCSX.addBreakpoint({e.A('GS_ORDERING_TABLE')},'Write',40,'portal-ot',function(address,width,cause)
        if not battle() then return end
        local pc=string.format('%08x',PCSX.getRegisters().pc)
        IP.gpu.writers[pc]=(IP.gpu.writers[pc] or 0)+1
      end)
      return 'armed' ''').strip()
    assert out == 'armed', f'GPU monitor: {out!r}'


def gpu_report(e):
    raw = e.run('lua', '''
      local w={} for k,v in pairs(IP.gpu.writers) do w[#w+1]=string.format('"%s":%d',k,v) end
      return string.format('{"passes":%d,"peak":%d,"violations":%d,"first":"%s","writers":{%s}}',
        IP.gpu.passes,IP.gpu.peak,IP.gpu.violations,IP.gpu.first or '',table.concat(w,','))''').strip()
    try:
        report = json.loads(raw)
    except ValueError:
        raise AssertionError(f'GPU monitor report: {raw!r}') from None
    # Only the ordering-table clear may write its headers; any other writer is a packet run past the area
    # (a pass that crashes mid-frame never reaches the peak sample).
    names = sorted((a, n) for n, a in e.table.items()
                   if isinstance(a, int) and 0x80010000 <= a < 0x80200000 and '.' not in n)
    def owner(pc):
        i = bisect.bisect_right(names, (pc, chr(0x10ffff))) - 1
        return names[i][1] if i >= 0 else '?'
    report['strangers'] = {f'{pc}:{owner(int(pc, 16))}': n for pc, n in report['writers'].items()
                           if owner(int(pc, 16)) not in ('GsClearOt', '_otc')}
    return report


def encounter(e, out, species, quick, cleanup, video_seconds=35, all_join=False, city_entrance=False,
              technique=None, offense=999):
    evolve_fixture(e, species)
    # The type changes before the EVL scene releases its overlay and objects.
    # Wait for partner field control before starting another map or overlay.
    for _ in range(180):
        if e.peek('PARTNER_STATE','B') != 13 and e.peek('TAMER_STATE','B') == 0 and not e.peek('IS_IN_MENU','i'):
            break
        if e.peek('IS_IN_MENU','i'):e.press('CANCEL',8)
        elif e.peek('PARTNER_STATE','B') == 13:e.press('START',8)
        else:e.press('CONFIRM',8)
        e.wait(.3)
    else:raise AssertionError('fixture evolution did not release field control')
    e.wait(1)
    e.poke('PAUSE_STATE', b'\0')
    e.gs('set', 'gametime_running=0', 'partner.para.condition=0', 'partner.para.age=1',
         'partner.para.evoTimer=0', 'partner.para.remainingLifetime=1000',
         'partner.stats.hp=9999', 'partner.stats.mp=9999',
         'partner.stats.currentHP=9999', 'partner.stats.currentMP=9999', f'partner.stats.off={offense}',
         'partner.stats.def=999', 'partner.stats.speed=999', 'partner.stats.brain=999')
    e.poke('MOD_OPT_QUICK_BATTLE', struct.pack('<i', quick))
    if technique is not None:
        equip_only(e, technique)
    if all_join:
        # Seed only the join roll; visibility, collision and the three-enemy
        # limit still choose the participants through native encounter code.
        e.poke('FLEE_CHANCES', bytes([100]) * 12)
    for _ in range(12):
        if e.peek('IS_IN_MENU', 'i'):
            e.press('CANCEL', 8)
        elif e.peek('TAMER_STATE', 'B') == 20:
            e.press('CONFIRM', 8)
        else:
            break
        e.wait(.2)
    e.poke('PAUSE_STATE', b'\0')
    assert e.warp(168 if city_entrance else 167, 0), 'source room did not load'
    stem=f'partner-{species}-quick-{quick}'+(f'-tech-{technique}' if technique is not None else '')
    before=sample(e)
    e.run('save', str(out/(stem+'-source.state')))
    rows=[before]
    with ThreadPoolExecutor() as pool:
        video=pool.submit(e.run,'record',str(out/(stem+'.mp4')),str(video_seconds)) if video_seconds else None
        # Step trigger 0 is the portal returning to 166, arrival 1. Move onto
        # its real tile; the game's script performs the walk and warp.
        if city_entrance:
            # Run File City's real Mt. Infinity entrance handler (arrival 0).
            call(e, 'callScriptSection', e.peek('CURRENT_SCRIPT_ID', 'H'), 56, 1)
            e.run('resume')
        else:
            e.gs('move', '1200', '1200')
        end=time.monotonic()+600
        started=False; frame_start=None; auto=False; cleaned=False; window=None
        while time.monotonic()<end:
            row=sample(e);rows.append(row)
            (out/(stem+'-samples.json')).write_text(json.dumps(rows,indent=2)+'\n')
            row['gpu_monitor']=gpu_report(e)
            assert row['heap']['corrupt'] is None, row['heap']
            assert row['gpu_monitor']['violations']==0 and not row['gpu_monitor']['strangers'], row['gpu_monitor']
            assert row['running'] and row['stream_failures'] == 0 and row['battle_cold_reads'] == 0, row
            assert row['gpu']['ot_lengths']==12 and row['gpu']['ot1_length']==12, row['gpu']
            if row['CURRENT_SCREEN']==166 and row['GAME_STATE']==1:
                started=True
                if row['BATTLE_FRAME_COUNT']>=20 and row['MOD_BATTLE_LOADING']==0:
                    if window is None:
                        window = row['tile_window']
                    assert row['tile_window'] == window, 'tile window moved during battle'
                    if frame_start is None:
                        frame_start=row['BATTLE_FRAME_COUNT']
                        e.run('shot',str(out/(stem+'-battle.png')))
                    if row['BATTLE_FRAME_COUNT']-frame_start>=90 and cleanup and not cleaned:
                        for enemy in row['participants']:
                            e.poke(f'NPC_ENTITIES+{104*enemy["slot"]+0x4c}',b'\0\0')
                        cleaned=True
                if not auto:
                    e.press('CONFIRM',8);auto=True
                elif row['participants'] and all(n['hp'] <= 0 for n in row['participants']):
                    e.press('CONFIRM',8)
                else:
                    e.press('CIRCLE',8)
            # The interrupted arrival walk may touch the return portal before
            # the observer's next sample. Both rooms are valid field returns.
            elif started and row['CURRENT_SCREEN'] in (166,168 if city_entrance else 167) and row['GAME_STATE']==0 and row['TAMER_STATE']==0:
                e.run('shot',str(out/(stem+'-after.png')))
                break
            else:
                e.press('CONFIRM',8)
            e.wait(.4)
        else:
            raise AssertionError(f'{stem}: encounter did not return to field')
        assert frame_start is not None, 'battle did not advance'
        if all_join:
            assert any(len(r['participants']) == 3 for r in rows), 'triple battle absent'
        assert any(len([n for n in r['enemies'] if n['species']==88])>=3 for r in rows), 'three Vermilimon absent'
        if video is not None:
            video.result()
    result=dict(species=species,quick=quick,technique=technique,forced_cleanup=cleaned,all_join=all_join,
                city_entrance=city_entrance,gpu=gpu_report(e),samples=rows)
    (out/(stem+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('PASS',stem,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=39711)
    p.add_argument('--card',type=Path);p.add_argument('--state',type=Path);p.add_argument('--species',type=int,nargs='+',default=[3,407])
    p.add_argument('--quick',type=int,nargs='+',default=[0,1]);p.add_argument('--cleanup',action='store_true')
    p.add_argument('--city-entrance', action='store_true', help='enter from File City instead of the lower return portal')
    p.add_argument('--ram8', action='store_true', help='repeat the same encounter with expanded emulator RAM')
    p.add_argument('--video-seconds', type=int, default=35, help='set 0 to keep samples and screenshots only')
    p.add_argument('--all-join', action='store_true', help='seed bystander join chances to require a triple battle')
    p.add_argument('--technique', type=int, help='leave the partner only this learned and equipped technique')
    p.add_argument('--offense', type=int, default=999, help='partner Offense (lower keeps the battle going longer)')
    p.add_argument('--repeat', type=int, default=1, help='run every combination this many times')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'))
    e.expanded_ram = a.ram8
    e.env['EMU_ARGS'] = '-interpreter -debugger' + (' -8mb' if a.ram8 else '')
    if a.ram8:
        # Heap and gameplay addresses remain in the original 2 MB region.
        e.ram = lambda: e.api('/api/v1/cpu/ram/raw')[:0x200000]
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    try:
        e.start(str(a.card.resolve()) if a.card else test_card(out))
        if a.state:
            e.run('load',str(a.state.resolve()));e.run('resume')
        else:assert e.continue_game()==0, 'Continue failed'
        e.run('lua', f'''IP={{streamFailures=0,coldReads=0,bp={{}}}}
          local m=PCSX.getMemPtr()
          local function battle() return tonumber(m[{e.A('GAME_STATE') & 0x1fffff}])~=0 end
          IP.bp[1]=PCSX.addBreakpoint({e.A('tfsStreamOpen')},'Exec',4,'portal-stream',function()
            if battle() then IP.streamFailures=IP.streamFailures+1 end
          end)
          IP.bp[2]=PCSX.addBreakpoint({e.A('loadColdAnimation')},'Exec',4,'portal-cold',function()
            if battle() then IP.coldReads=IP.coldReads+1 end
          end)''')
        gpu_monitor(e)
        base=out/'base.state';e.run('save',str(base))
        for run in range(a.repeat):
          for species in a.species:
            for quick in a.quick:
                e.run('load',str(base));e.run('resume')
                e.run('lua','IP.gpu.passes=0;IP.gpu.peak=0;IP.gpu.violations=0;IP.gpu.first=nil;IP.gpu.writers={}')
                encounter(e,out,species,quick,a.cleanup,a.video_seconds,a.all_join,a.city_entrance,a.technique,a.offense)
                print('gpu', json.dumps(gpu_report(e)), flush=True)
    except BaseException:
        e.run('shot',str(out/'failure.png'),check=False)
        try:print('gpu at failure', json.dumps(gpu_report(e)), flush=True)
        except Exception as error:print('gpu report failed', error, flush=True)
        e.run('save',str(out/'failure.state'),check=False)
        raise
    finally:e.stop()


if __name__=='__main__':main()
