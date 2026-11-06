#!/usr/bin/env python3
"""Measure Fast Poop Toss against Tsukaimon using a fresh 2 MB battle.

EMU_PORT and DW_SYMS select the emulator and matching disc executable.
The attack is equipped before combat loads its effect. Trials reload the same
combat snapshot, disable the opponent's attacks and log actual release distances.
No damage or accuracy roll is forced.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev import emulator as E
from tools.dev.playtest import species_proof as P
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.battle_hits import Battle


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cue')
    p.add_argument('out', type=Path)
    p.add_argument('--partner', type=int, default=120)
    p.add_argument('--card', default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    p.add_argument('--seconds', type=float, default=30)
    p.add_argument('--distance', type=int, default=800)
    p.add_argument('--trials', type=int, default=2)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    emu = P.emulator(args.cue)
    try:
        card = field_card(args.card, args.out / 'fixture.mcd', partner_type=args.partner)
        emu.start(str(card))
        if emu.continue_game() != 0:
            raise RuntimeError('Continue failed')
        b = Battle(emu)
        emu.gs('set', 'hour=22', 'minute=0')
        emu.gs('warp', '1', '0')
        b.world(1)
        b.flow(False)
        partner = b.address('PARTNER_ENTITY')
        b.write(partner + 68, 'I', 0xffffff30)
        for off in (72,74,76,78):
            b.write(partner + off, 'h', 30000)
        for off in (56,58,60,62):
            b.write(partner + off, 'h', 400)
        b.write('PARTNER_PARA', 'I', 0)
        b.flow(True)
        emu.gs('warp', '11', '0')
        b.world(11)
        enemy = b.address('NPC_ENTITIES') + 2*104
        b.wait(lambda r: b.read(enemy, 'i', r) == 96 and b.read(b.address('ENTITY_TABLE')+16,'I',r)==enemy)
        b.flow(False)
        b.write(enemy + 72,'h',30000)
        b.write(enemy + 76,'h',30000)
        b.write(enemy + 78,'h',0)
        b.flow(True)
        emu.gs('approach','2')
        b.flow(False)
        r = b.ram()
        tp = b.read(b.address('TAMER_ENTITY') + 4, 'I', r)
        b.position(partner, b.read(tp + 120, 'i', r) - 700,
                   b.read(tp + 128, 'i', r) - 700)
        b.flow(True)
        for _ in range(40):
            E.press('CROSS',4)
            try:
                b.wait(lambda r:b.read('GAME_STATE','B',r)==1,seconds=1)
                break
            except RuntimeError:
                pass
        if b.read('GAME_STATE','B') != 1:
            raise RuntimeError('No Tsukaimon battle')
        b.combat_ready()
        b.flow(False)
        snapshot = (args.out / 'battle.state').resolve()
        E.api('/api/v1/lua/save?file='+urllib.parse.quote(str(snapshot)))
        for trial in range(args.trials):
            E.api('/api/v1/lua/load?file='+urllib.parse.quote(str(snapshot)))
            b.flow(False)
            ram = b.ram()
            combat = b.read('COMBAT_DATA_PTR','I',ram)
            if b.read('ENEMY_COUNT','h',ram) != 1:
                raise RuntimeError('Expected exactly one opponent')
            if b.read(combat+1645,'B',ram) != 4:
                raise RuntimeError('Tsukaimon is not the opponent')
            pp = b.read(partner+4,'I',ram)
            ep = b.read(enemy+4,'I',ram)
            x = b.read(ep+120,'i',ram)
            z = b.read(ep+128,'i',ram)
            b.position(partner, x, z + args.distance)
            for actor in (partner,enemy):
                b.write(actor+76,'h',30000)
                b.write(actor+74,'h',30000)
            b.write(partner+78,'h',30000)
            b.write(enemy+78,'h',0)
            b.write(combat+360+40,'h',30000)
            out = args.out / str(trial+1)
            out.mkdir(exist_ok=True)
            with (out/'recorder.log').open('w') as log:
                recorder = subprocess.Popen(P.E+['record',str(out/'battle.mp4'),str(args.seconds),'20'],stdout=log,stderr=subprocess.STDOUT)
                time.sleep(.3)
                b.flow(True)
                rows=[]
                stop=time.monotonic()+args.seconds
                while time.monotonic()<stop:
                    r=b.ram()
                    effect=b.read(partner+82,'b',r)
                    effects=b.read('EFE_DATA_PTR','I',r)
                    rows.append(dict(frame=b.read('BATTLE_FRAME_COUNT','h',r),anim=b.read(partner+46,'B',r),
                                     anim_frame=b.read(partner+28,'h',r),technique=b.read(partner+80,'h',r),
                                     effect=effect,effect_id=b.read(effects+40*effect,'i',r) if effect>=0 else None,
                                     effects=b.effects(effect,partner,r),
                                     hp=b.read(enemy+76,'h',r),x=b.read(ep+120,'i',r),z=b.read(ep+128,'i',r),
                                     px=b.read(pp+120,'i',r),pz=b.read(pp+128,'i',r)))
                    time.sleep(.05)
                b.flow(False)
                recorder.wait(timeout=30)
            if recorder.returncode:
                raise RuntimeError('Video recorder failed')
            E.shot(str(out/'battle.png'))
            result=dict(partner=args.partner,target=96,ram_bytes=0x200000,starting_gap=args.distance,
                        damage=30000-min(r['hp'] for r in rows),samples=rows)
            result['ok']=result['damage']>0 and any(r['anim']==48 and r['effect_id']==306 for r in rows)
            results.append(result)
            (args.out/'result.json').write_text(json.dumps(results,indent=2)+'\n')
            print(json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
    finally:
        if sys.exc_info()[0] is not None:
            try:
                E.shot(str(args.out / 'failure.png'))
                E.api('/api/v1/lua/save?file=' + urllib.parse.quote(str((args.out / 'failure.state').resolve())))
            except Exception:
                pass
        emu.stop()
    return 0 if results and all(r['ok'] for r in results) else 1


if __name__=='__main__':
    raise SystemExit(main())
