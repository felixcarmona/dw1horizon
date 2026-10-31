#!/usr/bin/env python3
"""Record the high-stat target matrix from a field snapshot beside NPC slot 0.

Run on a private, standard 2 MB emulator already booted with tools/dev/emulator.py:
  EMU_PORT=... DW_SYMS=decomp-dev .venv/bin/python tools/dev/playtest/target_score.py CONTACT.state OUT.json

Prepare with game_state.py trigger 1 1, warp 0 0, approach 0. Wait for the
dialogue text to finish revealing (one CROSS may only finish the text), then
save before dismissing it. Each case reloads this snapshot and starts normally.
The elemental fixture sets only the two native species' first specialties to
Battle/Air (TYPE_FACTORS=2, inverse 20) or Battle/Battle (neutral 10), keeping
models, species ids, moves and the remaining specialties intact. Other tested
stats stay at 999; HP/MP at 30000, Offense at 100, condition/tiredness clear,
discipline 100. Results include all sampled fighter states, not just attacks.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.dev import emulator as e, memory_inspector as m

v, t = {}, {}


def loc(name):
    address, kind = m.resolve_expr(name, v, t)
    return address, kind['size'], kind.get('signed', False)


def get(ram, name):
    address, size, signed = loc(name)
    offset = address - 0x80000000
    return int.from_bytes(ram[offset:offset+size], 'little', signed=signed)


def put(name, value):
    address, size, signed = loc(name)
    e.api(f'/api/v1/cpu/ram/raw?offset={address-0x80000000}&size={size}',
          int(value).to_bytes(size, 'little', signed=signed))


def load(path):
    return e.api('/api/v1/lua/load?file=' + urllib.parse.quote(str(Path(path).resolve())))


def main():
    global v, t
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seconds', type=float, default=20)
    parser.add_argument('--interval', type=float, default=.2)
    parser.add_argument('--expect-fixed', action='store_true')
    args = parser.parse_args()
    if args.seconds <= 0 or args.interval <= 0:
        parser.error('seconds and interval must be positive')
    v, t = m.build_index()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    prefix='PARTNER_ENTITY.digimonEntity.'
    fields={x:'COMBAT_DATA.fighter[0].'+x for x in ('targetId','queuedAnim','moveRange')}
    fields['animId']=prefix+'entity.anim.animId'
    fields['gameState']='GAME_STATE'
    fields['flags']='COMBAT_DATA.fighter[0].flags'
    fields['battleFrame']='BATTLE_FRAME_COUNT'
    fields['animFrame']=prefix+'entity.anim.animFrame'
    fields['hp']=prefix+'stats.current.currentHP'
    fields['mp']=prefix+'stats.current.currentMP'
    fields['enemyHP']='NPC_ENTITIES[0].digimonEntity.stats.current.currentHP'
    rows=[]
    for inv in (20,10):
        for stat in ('def','brain','speed','all'):
            for value in (999,9999,12000):
                response = load(args.snapshot).decode()
                if not response.startswith('ok '): raise RuntimeError(response)
                time.sleep(.15)
                e.api('/api/v1/execution-flow?function=pause')
                r=e.api('/api/v1/cpu/ram/raw');partner=get(r,prefix+'entity.type');enemy=get(r,'NPC_ENTITIES[0].digimonEntity.entity.type')
                # Controlled elemental fixture, leaving models, species ids and moves intact.
                put(f'DIGIMON_DATA[{partner}].special[0]',1)
                put(f'DIGIMON_DATA[{enemy}].special[0]',2 if inv==20 else 1)
                for key in ('def','brain','speed'):put(prefix+'stats.base.'+key,value if stat in (key,'all') else 999)
                put(prefix+'stats.base.hp',30000);put(prefix+'stats.current.currentHP',30000)
                put(prefix+'stats.base.mp',30000);put(prefix+'stats.current.currentMP',30000)
                put(prefix+'stats.base.off',100)
                put('PARTNER_PARA.condition',0)
                put('PARTNER_PARA.tiredness',0)
                put('PARTNER_PARA.discipline',100)
                put('NPC_ENTITIES[0].digimonEntity.stats.base.hp',30000)
                put('NPC_ENTITIES[0].digimonEntity.stats.current.currentHP',30000)
                r = e.api('/api/v1/cpu/ram/raw')
                stats = {key: get(r, prefix+'stats.base.'+key) for key in ('def','brain','speed')}
                factor = get(r, f'TYPE_FACTORS[1][{2 if inv == 20 else 1}]')
                assert factor == (2 if inv == 20 else 10), factor
                e.api('/api/v1/execution-flow?function=start')
                e.press('CROSS',20)
                samples=[];start=time.monotonic()
                for _ in range(max(1, round(args.seconds / args.interval))):
                    r=e.api('/api/v1/cpu/ram/raw')
                    samples.append(dict(seconds=round(time.monotonic()-start,3),**{k:get(r,n) for k,n in fields.items()}))
                    time.sleep(args.interval)
                row=dict(inv=inv,stat=stat,value=value,partner=partner,enemy=enemy,
                         stats=stats,typeFactor=factor,samples=samples)
                rows.append(row)
                args.output.write_text(json.dumps(rows,indent=2)+'\n')
                combat = [sample for sample in samples if sample['gameState'] == 1]
                summary = {key: sorted({sample[key] for sample in combat})
                           for key in ('targetId', 'queuedAnim', 'moveRange', 'animId')}
                summary['invalidTargetSamples'] = sum(sample['targetId'] == 255 for sample in combat)
                summary['combatSamples'] = len(combat)
                print(inv,stat,value,json.dumps(summary),flush=True)
                if not combat:
                    raise RuntimeError('CROSS did not start combat; check the contact snapshot')

    if args.expect_fixed:
        for row in rows:
            combat = [sample for sample in row['samples'] if sample['gameState'] == 1]
            assert combat, (row['inv'], row['stat'], row['value'], 'no battle')
            assert any(0x2e <= sample['animId'] < 0xff for sample in combat), (row['inv'], row['stat'], row['value'], 'no technique animation')
            assert any(sample['targetId'] == 1 for sample in combat), (row['inv'], row['stat'], row['value'], 'no enemy target')
            assert all(sample['targetId'] != 255 for sample in combat if sample['battleFrame'] >= 10), (row['inv'], row['stat'], row['value'], 'invalid target')
            assert min(sample['mp'] for sample in combat) < 30000, (row['inv'], row['stat'], row['value'], 'no technique MP spent')
            assert min(sample['enemyHP'] for sample in combat) < 30000, (row['inv'], row['stat'], row['value'], 'no damage dealt')


if __name__ == '__main__':
    main()
