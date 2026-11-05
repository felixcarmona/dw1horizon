#!/usr/bin/env python3
"""Reproduce the reported Ancient Glacial Region battle on an original 2 MB boot.

EMU_PORT=N DW_SYMS=EXE xvfb-run -a python3 tools/dev/playtest/flat_scene.py DISC ASSETS OUT --card CARD
Devidramon faces the screen's real Yanmamon/Vermilimon placements and finishes the flattened Yanmamon.
Use flat_sprites.py --partner 216 --opponent 51 --finisher for the separate imported-partner comparison.
"""
from pathlib import Path
import argparse, json, os, struct, sys, time
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools').is_dir())
sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(ROOT/'tools/dev/playtest')]
import species_proof as P
import flat_sprites as F


def flatten(fighter, entity):
    P.mset(f'COMBAT_DATA.fighter[{fighter}].flatTimer=-1')
    for _ in range(50):
        m=P.mem(f'{entity}.flatSprite',f'COMBAT_DATA.fighter[{fighter}].flags')
        if 0<=m[f'{entity}.flatSprite']<=3 and m[f'COMBAT_DATA.fighter[{fighter}].flags']&8:return
        time.sleep(.25)
    raise AssertionError(f'{entity} never became flat')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc');ap.add_argument('assets',type=Path);ap.add_argument('out',type=Path)
    ap.add_argument('--card',required=True)
    ap.add_argument('--expect-stall',action='store_true',help='verify the pre-fix flat-spit AI lock')
    ap.add_argument('--state',type=Path,help='reuse this fixture’s base.state from the same disc')
    a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    result={'screen':80,'partner':216,'cases':[],'expected_stall':a.expect_stall}
    try:
        if a.state:
            P.EMU=P.emulator(a.disc);P.EMU.env['EMU_ARGS']='-interpreter -debugger'
            P.EMU.start(a.card);P.EMU.wait(3);P.EMU.run('load',str(a.state.resolve()));P.EMU.wait(1)
        else:
            assert F.boot(a.disc,a.card),'Continue failed'
            P.lab_evolve(216,str(out))
        e=P.EMU;result['ram_bytes']=len(e.ram())
        result['language']=P.mem('MOD_LANG')['MOD_LANG']
        assert result['language']==0, 'fixture expects the base English language'
        assert P.partner_type()==216 and e.in_control()
        for _ in range(8):
            ui=P.mem('MOD_LAB_ACTIVE','PAUSE_STATE')
            if ui['MOD_LAB_ACTIVE']:e.press('CANCEL',20)
            elif ui['PAUSE_STATE']:e.press('START',20)
            else:break
            e.wait(1)
        assert P.mem('PAUSE_STATE')['PAUSE_STATE']==0, 'field is still paused'
        e.run('pause')
        P.mset('IS_GAMETIME_RUNNING=0','HOUR=12','CURRENT_FRAME=14400','LAST_HANDLED_FRAME=14400',
               'PARTNER_PARA.age=1','PARTNER_PARA.evoTimer=0','PARTNER_PARA.condition=0','PARTNER_PARA.tiredness=0',
               'MOD_OPT_STORY=1','MOD_OPT_QUICK_BATTLE=1',
               'PARTNER_ENTITY.digimonEntity.stats.base.hp=9999','PARTNER_ENTITY.digimonEntity.stats.current.currentHP=9999',
               'PARTNER_ENTITY.digimonEntity.stats.base.mp=9999','PARTNER_ENTITY.digimonEntity.stats.current.currentMP=9999',
               'PARTNER_ENTITY.digimonEntity.stats.base.off=400','PARTNER_ENTITY.digimonEntity.stats.base.def=400',
               'PARTNER_ENTITY.digimonEntity.stats.base.speed=400',
               f'PARTNER_ENTITY.digimonEntity.stats.base.moves[3]={F.finisher_slot(a.assets,216)}')
        e.run('resume');e.run('save',str(out/'base.state'))
        assert e.warp(80) and e.in_control()
        result['original_yanmamon_moves']=P.mem(*[f'NPC_ENTITIES[1].digimonEntity.stats.base.moves[{i}]' for i in range(4)])
        P.mset(*[f'{k}=9999' for k in P.ENEMY_MAX+P.ENEMY_HP])
        e.poke('FLEE_CHANCES',bytes([100])*12)
        e.gs('approach','1');F.call('unsetCameraFollowPlayer')
        ram=e.ram();positions=[]
        for slot in (1,2):
            ptr=struct.unpack_from('<I',ram,(e.A('NPC_ENTITIES')&0x1fffff)+slot*0x68+4)[0]&0x1fffff
            positions.append(struct.unpack_from('<3i',ram,ptr+0x78))
        F.call('tickCameraMoveTo',sum(p[0] for p in positions)//2,sum(p[2] for p in positions)//2,30)
        e.wait(2);e.run('shot',str(out/'scene80-field.png'))
        if P.mem('IS_SCRIPT_PAUSED')['IS_SCRIPT_PAUSED']==1:
            P.mset('TALKED_TO_ENTITY=3')
            script=P.mem('CURRENT_SCRIPT_ID')['CURRENT_SCRIPT_ID']
            section=P.mem('NPC_ENTITIES[1].scriptId')['NPC_ENTITIES[1].scriptId']
            F.call('callScriptSection',script,section,1)
        for _ in range(100):
            m=P.mem('GAME_STATE','BATTLE_FRAME_COUNT','MOD_BATTLE_LOADING')
            if m['GAME_STATE']&255==1 and m['BATTLE_FRAME_COUNT']>=20 and m['MOD_BATTLE_LOADING']==0:break
            if m['GAME_STATE']&255!=1:e.press('CONFIRM',12)
            e.wait(.5)
        else:raise AssertionError('battle setup did not finish')
        n=P.mem('ENEMY_COUNT')['ENEMY_COUNT']
        ids=[P.mem(f'COMBAT_DATA.player.entityIds[{i}]')[f'COMBAT_DATA.player.entityIds[{i}]'] for i in range(n+1)]
        assert 3 in ids,ids
        result['entity_ids']=ids
        result['enemy_species']=[P.mem(f'NPC_ENTITIES[{i-2}].digimonEntity.entity.type')[f'NPC_ENTITIES[{i-2}].digimonEntity.entity.type'] for i in ids[1:]]
        assert 67 in result['enemy_species'] and 88 in result['enemy_species'],result
        insect=ids.index(3);who='NPC_ENTITIES[1].digimonEntity.entity'
        e.run('shot',str(out/'scene80-before-flat.png'))
        assert P.mem('NO_AI_FLAG')['NO_AI_FLAG']==0, 'another finisher already owns the scene'
        flatten(insect,who);e.run('shot',str(out/'scene80-yanmamon-flat.png'))
        r={'flat_species':67}
        F.finish_while_flat(a.assets,insect,who,out,'scene80-yanmamon',r,
                            target_hp='NPC_ENTITIES[1].digimonEntity.stats.current.currentHP')
        result['cases'].append(r)
        print(json.dumps(r),flush=True)
        if a.expect_stall:
            P.mset('NO_AI_FLAG=0','FINISHING_ENTITY=0')
        else:
            assert P.mem('NO_AI_FLAG')['NO_AI_FLAG']==0, 'AI stayed locked after the finisher'
        for _ in range(40):
            P.mset(*[f'{k}=0' for k in P.ENEMY_HP])
            P.seq('wait 3, CONFIRM 12, wait 1, CONFIRM 12, wait 1')
            if P.game_state()==0:break
        assert P.game_state()==0, 'glacial encounter did not finish'
        e.run('shot',str(out/'scene80-after.png'))
        result['back_in_world']=P.game_state()==0
        first=result['cases'][0]
        first_ok=(first['flat_spit_stall'] and 58<=first['flat_move_lookup']<113) if a.expect_stall else (
                   first['finisher_played'] and first['finisher_damage']>0 and first['flat_during_finisher']
                   and not first['flat_spit_stall'] and first['flat_move_lookup']==121)
        result['first_battle_forced_cleanup']=a.expect_stall
        result['ok']=result['back_in_world'] and first_ok and first['battle_frames_advanced']
    except BaseException as error:
        result['error']=str(error)
        if P.EMU:P.EMU.run('shot',str(out/'failure.png'),check=False)
        raise
    finally:
        P.run(P.E+['stop']);(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['ok'],result


if __name__=='__main__':main()
