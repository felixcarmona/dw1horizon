#!/usr/bin/env python3
"""Reproduce a wild encounter beside the new Freezeland/Drill Tunnel recruit NPCs on 2 MB.

Usage: EMU_PORT=N DW_SYMS=EXE xvfb-run -a python3 tools/dev/playtest/passive_encounters.py DISC OUT --card CARD
The join-probability table is raised to 100 to make each eligible visible bystander join deterministically.
The selected quick-battle settings and the NPCs' own scripted solo fights are checked.
"""
from pathlib import Path
import argparse, json, os, struct, sys
ROOT = next(p for p in Path(__file__).resolve().parents if (p/'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT/'tools'), str(ROOT/'tools/dev/playtest')]
import species_proof as P
from flat_sprites import boot, call


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('out'); ap.add_argument('--card', required=True)
    ap.add_argument('--before', action='store_true')
    ap.add_argument('--state',type=Path,help='reuse a field state from this same disc')
    ap.add_argument('--screens',default='94,24')
    ap.add_argument('--quick',default='1')
    ap.add_argument('--modes',default='wild,solo')
    a=ap.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    result={'cases':[], 'expected_passive_join':a.before}
    try:
        if a.state:
            P.EMU=P.emulator(a.disc);P.EMU.env['EMU_ARGS']='-interpreter -debugger'
            P.EMU.start(a.card);P.EMU.wait(3);P.EMU.run('load',str(a.state.resolve()));P.EMU.wait(1)
        else:assert boot(a.disc,a.card), 'Continue failed'
        e=P.EMU; result['ram_bytes']=len(e.ram())
        if P.mem('PAUSE_STATE')['PAUSE_STATE']:e.press('START',20);e.wait(1)
        e.run('pause')
        P.mset('IS_GAMETIME_RUNNING=0','HOUR=12','CURRENT_FRAME=14400','LAST_HANDLED_FRAME=14400',
               'MOD_OPT_STORY=1','PARTNER_PARA.age=1','PARTNER_PARA.evoTimer=0')
        e.run('resume')
        e.gs('trigger','1','0')
        # Neither recruit has joined; don't depend on the supplied card's roster.
        bits=bytearray(e.ram()[e.A('SPECIES_RECRUITED_BITS')&0x1fffff:][:128])
        for species in (193,267):bits[species//8]&=~(1<<(species%8))
        e.poke('SPECIES_RECRUITED_BITS',bits)
        assert e.in_control(); e.run('save',str(out/'base.state'))
        for quick in map(int,a.quick.split(',')):
            for screen,slot,species in ((94,4,267),(24,1,193)):
                if str(screen) not in a.screens.split(','):continue
                for mode in a.modes.split(','):
                    scripted=mode=='solo'
                    e.run('load',str(out/'base.state'));e.wait(1)
                    P.mset(f'MOD_OPT_QUICK_BATTLE={quick}','HOUR=12','IS_GAMETIME_RUNNING=0')
                    if not quick:call('modBtlPreloadDrop')
                    assert e.warp(screen) and e.in_control(), f'screen {screen} did not load'
                    P.mset('PARTNER_ENTITY.digimonEntity.stats.base.hp=9999',
                           'PARTNER_ENTITY.digimonEntity.stats.current.currentHP=9999',
                           'PARTNER_ENTITY.digimonEntity.stats.base.def=999',
                           'PARTNER_ENTITY.digimonEntity.stats.base.off=1',
                           'PARTNER_PARA.condition=0','PARTNER_PARA.tiredness=0',
                           'PARTNER_PARA.age=1','PARTNER_PARA.evoTimer=0')
                    e.poke('FLEE_CHANCES',bytes([100])*12)
                    P.mset(*[f'{k}=9999' for k in P.ENEMY_MAX+P.ENEMY_HP])
                    types=P.mem(*[f'NPC_ENTITIES[{i}].digimonEntity.entity.type' for i in (0,slot)],
                                f'NPC_ENTITIES[{slot}].autotalk')
                    assert types[f'NPC_ENTITIES[{slot}].digimonEntity.entity.type']==species, types
                    assert types[f'NPC_ENTITIES[{slot}].autotalk']==0, types
                    target=slot if scripted else 0
                    e.gs('approach',str(target));e.wait(.5)
                    ram=e.ram(); positions=[]
                    for which in (0,slot):
                        ptr=struct.unpack_from('<I',ram,(e.A('NPC_ENTITIES')&0x1fffff)+which*0x68+4)[0]&0x1fffff
                        positions.append(struct.unpack_from('<3i',ram,ptr+0x78))
                    call('unsetCameraFollowPlayer')
                    call('tickCameraMoveTo',sum(p[0] for p in positions)//2,sum(p[2] for p in positions)//2,30)
                    e.wait(2)
                    visible=P.mem(f'NPC_ENTITIES[{slot}].digimonEntity.entity.isOnScreen')[f'NPC_ENTITIES[{slot}].digimonEntity.entity.isOnScreen']
                    assert visible, f'passive slot {slot} outside camera'
                    e.run('shot',str(out/f'{screen}-quick{quick}-before-talk.png'))
                    if P.mem('IS_SCRIPT_PAUSED')['IS_SCRIPT_PAUSED']==1:
                        P.mset(f'TALKED_TO_ENTITY={target+2}')
                        section=P.mem(f'NPC_ENTITIES[{target}].scriptId')[f'NPC_ENTITIES[{target}].scriptId']
                        script=P.mem('CURRENT_SCRIPT_ID')['CURRENT_SCRIPT_ID']
                        call('callScriptSection',script,section,1)
                    for _ in range(180):
                        if P.game_state()==1:break
                        if P.mem('IS_SCRIPT_PAUSED')['IS_SCRIPT_PAUSED']==1: e.gs('approach',str(target))
                        e.press('CONFIRM',12);e.wait(.5)
                    assert P.game_state()==1, 'talk did not start a battle'
                    for _ in range(120):
                        ready=P.mem('GAME_STATE','BATTLE_FRAME_COUNT','MOD_BATTLE_LOADING')
                        if (ready['GAME_STATE']&255)==1 and ready['BATTLE_FRAME_COUNT']>=20 and ready['MOD_BATTLE_LOADING']==0:break
                        e.wait(.5)
                    else:raise AssertionError('battle setup never completed')
                    P.mset('NO_AI_FLAG=1')
                    n=P.mem('ENEMY_COUNT')['ENEMY_COUNT']
                    ids=[P.mem(f'COMBAT_DATA.player.entityIds[{i}]')[f'COMBAT_DATA.player.entityIds[{i}]'] for i in range(1,n+1)]
                    names=[P.mem(f'NPC_ENTITIES[{i-2}].digimonEntity.entity.type')[f'NPC_ENTITIES[{i-2}].digimonEntity.entity.type'] for i in ids]
                    r=dict(screen=screen,quick=quick,quick_actual=P.mem('MOD_OPT_QUICK_BATTLE')['MOD_OPT_QUICK_BATTLE'],talk_entry='map NPC script',scripted=scripted,enemy_count=n,entity_ids=ids,species=names)
                    if scripted:r['ok']=names==[species]
                    else:r['ok']=(species in names)==a.before and len(names)>=1
                    stem=f'{screen}-quick{quick}-'+('solo' if scripted else 'wild')
                    e.run('shot',str(out/(stem+'.png')))
                    e.run('save',str(out/(stem+'.state')))
                    for _ in range(40):
                        P.mset('NO_AI_FLAG=0',*[f'{k}=0' for k in P.ENEMY_HP])
                        P.seq('wait 3, CONFIRM 12, wait 1, CONFIRM 12, wait 1')
                        if P.game_state()==0:break
                    r['returned_to_world']=P.game_state()==0
                    r['ok'] &= r['returned_to_world'];result['cases'].append(r)
                    print(json.dumps(r),flush=True)
        result['ok']=all(r['ok'] for r in result['cases'])
    except BaseException as error:
        result['error']=str(error)
        if P.EMU:
            P.EMU.run('shot',str(out/'failure.png'),check=False)
            P.EMU.run('save',str(out/'failure.state'),check=False)
            result['failure_state']=P.mem('CURRENT_SCREEN','TAMER_STATE','IS_SCRIPT_PAUSED','GAME_STATE','TALKED_TO_ENTITY','LOAD_EFE_STATE','MOD_LOAD_PUMP','MOD_BTL_PRELOAD','PAUSE_STATE','IS_IN_MENU','FILE_READ_QUEUE_HEAD')
        raise
    finally:
        P.run(P.E+['stop'])
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['ok'],result


if __name__=='__main__':main()
