#!/usr/bin/env python3
"""Check the Mount Infinity lower portal and three-Vermilimon encounter on 2 MB.

Boots a disposable corpus card and installs fixture partners through evolution.
The portal section, arrival, enemy placements and battle loader are unmodified.
Strong partner stats bound the encounter; --cleanup may zero enemy HP after
observing battle progress, so that mode proves loading rather than combat AI.
"""
import argparse
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
from tools.langpatch import elf_symbols
from tools.membudget import Ram, heap_walk


def sample(e):
    ram = e.ram()
    flow = json.loads(e.api('/api/v1/execution-flow'))
    assert not flow['8mb'] and len(ram) == 0x200000
    heap = heap_walk(Ram(ram, e.table))
    row = {k: e.peek(k, f, ram) for k, f in (
        ('CURRENT_SCREEN', 'h'), ('TAMER_STATE', 'B'), ('GAME_STATE', 'H'),
        ('ENEMY_COUNT', 'i'), ('BATTLE_FRAME_COUNT', 'i'), ('PARTNER_ENTITY', 'i'),
        ('MOD_OPT_QUICK_BATTLE', 'i'), ('MOD_BATTLE_LOADING', 'b'))}
    row.update(ram_bytes=len(ram), expanded_ram=flow['8mb'], running=flow['running'],
               tamer=e.peek('TAMER_POSITION_DATA+0x78', '3i', ram),
               heap={k: v for k, v in heap.items() if k != 'blocks'})
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
    return row


def encounter(e, out, species, quick, cleanup):
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
         'partner.stats.currentHP=9999', 'partner.stats.currentMP=9999', 'partner.stats.off=999',
         'partner.stats.def=999', 'partner.stats.speed=999', 'partner.stats.brain=999')
    e.poke('MOD_OPT_QUICK_BATTLE', struct.pack('<i', quick))
    for _ in range(12):
        if e.peek('IS_IN_MENU', 'i'):
            e.press('CANCEL', 8)
        elif e.peek('TAMER_STATE', 'B') == 20:
            e.press('CONFIRM', 8)
        else:
            break
        e.wait(.2)
    e.poke('PAUSE_STATE', b'\0')
    assert e.warp(167, 0), 'source room did not load'
    stem=f'partner-{species}-quick-{quick}'
    before=sample(e)
    e.run('save', str(out/(stem+'-source.state')))
    rows=[before]
    with ThreadPoolExecutor() as pool:
        video=pool.submit(e.run,'record',str(out/(stem+'.mp4')),'35')
        # Step trigger 0 is the portal returning to 166, arrival 1. Move onto
        # its real tile; the game's script performs the walk and warp.
        e.gs('move', '1200', '1200')
        end=time.monotonic()+150
        started=False; frame_start=None; auto=False; cleaned=False
        while time.monotonic()<end:
            row=sample(e);rows.append(row)
            (out/(stem+'-samples.json')).write_text(json.dumps(rows,indent=2)+'\n')
            assert row['heap']['corrupt'] is None, row['heap']
            assert row['gpu']['ot_lengths']==12 and row['gpu']['ot1_length']==12, row['gpu']
            if row['CURRENT_SCREEN']==166 and row['GAME_STATE']==1:
                started=True
                if row['BATTLE_FRAME_COUNT']>=20 and row['MOD_BATTLE_LOADING']==0:
                    if frame_start is None:
                        frame_start=row['BATTLE_FRAME_COUNT']
                        e.run('shot',str(out/(stem+'-battle.png')))
                    if row['BATTLE_FRAME_COUNT']-frame_start>=90 and cleanup and not cleaned:
                        for enemy in row['enemies']:
                            e.poke(f'NPC_ENTITIES+{104*enemy["slot"]+0x4c}',b'\0\0')
                        cleaned=True
                if not auto:
                    e.press('CONFIRM',8);auto=True
                elif all(n['hp'] <= 0 for n in row['enemies']):
                    e.press('CONFIRM',8)
                else:
                    e.press('CIRCLE',8)
            elif started and row['CURRENT_SCREEN']==166 and row['GAME_STATE']==0 and row['TAMER_STATE']==0:
                e.run('shot',str(out/(stem+'-after.png')))
                break
            else:
                e.press('CONFIRM',8)
            e.wait(.4)
        else:
            raise AssertionError(f'{stem}: encounter did not return to field')
        assert frame_start is not None, 'battle did not advance'
        assert any(len([n for n in r['enemies'] if n['species']==88])>=3 for r in rows), 'three Vermilimon absent'
        video.result()
    result=dict(species=species,quick=quick,forced_cleanup=cleaned,samples=rows)
    (out/(stem+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('PASS',stem,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=39711)
    p.add_argument('--card',type=Path);p.add_argument('--state',type=Path);p.add_argument('--species',type=int,nargs='+',default=[3,407])
    p.add_argument('--quick',type=int,nargs='+',default=[0,1]);p.add_argument('--cleanup',action='store_true')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'))
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    try:
        e.start(str(a.card.resolve()) if a.card else test_card(out))
        if a.state:
            e.run('load',str(a.state.resolve()));e.run('resume')
        else:assert e.continue_game()==0, 'Continue failed'
        base=out/'base.state';e.run('save',str(base))
        for species in a.species:
            for quick in a.quick:
                e.run('load',str(base));e.run('resume')
                encounter(e,out,species,quick,a.cleanup)
    except BaseException:
        e.run('shot',str(out/'failure.png'),check=False)
        e.run('save',str(out/'failure.state'),check=False)
        raise
    finally:e.stop()


if __name__=='__main__':main()
