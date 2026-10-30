#!/usr/bin/env python3
"""Plays every species of a batch list in the emulator, one after the other, unattended.

  EMU_PORT=38084 python3 tools/dev/playtest/batch_import.py LIST.json [--cue build/batch.cue]
         [--only NAME ...] [--out build/batch/play]

For each species, from a fresh boot of build/states/file-city.mcd (Agumon, Jijimon's house): forced
evolution (EVOLUTION_TARGET + partner/tamer state 13/6, the full EVL scene), a walk in
File City, then a wild battle in Native Forest (ModokiBetamon, its HP raised) with the
partner's four battle moves set to the techniques that carry the source game's own
attacks (finisher included, charged through COMBAT_DATA), the enemy finished, the
results screen. Checks from RAM: partner type after the evolution, the animation the
partner plays (technique slots >= 0x2E seen during the battle), frames advancing (no
hang), back in the world after the battle; screenshots and clips (walk, battle) per
species in OUT, and OUT/result.json.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, json, os, subprocess, sys, time
ROOT = _DEV_ROOT
E = [sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py')]
M = [sys.executable, os.path.join(ROOT, 'tools/dev/memory_inspector.py')]
G = [sys.executable, os.path.join(ROOT, 'tools/dev/game_state.py')]
assert os.environ.get('EMU_PORT'), 'set EMU_PORT'


def run(cmd, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=timeout)
    return r.stdout + r.stderr


def seq(s):
    return run(E + ['seq', s])


def mem(*names):
    out = {}
    for line in run(M + ['show'] + list(names)).splitlines():
        if ' = ' in line:
            k, v = line.split(' = ', 1)
            try:
                out[k.strip()] = int(v.split()[0])
            except ValueError:
                out[k.strip()] = v
    return out


def mset(*kv):
    return run(M + ['set'] + list(kv))


ANIM = 'PARTNER_ENTITY.digimonEntity.entity.anim.animId'
FRAME = 'PARTNER_ENTITY.digimonEntity.entity.anim.animFrame'


def record(path, secs):
    return subprocess.Popen(E + ['record', path, str(secs)], cwd=ROOT, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def sample(secs, every=0.4):
    """animId/animFrame/GAME_STATE samples for secs seconds."""
    out, t0 = [], time.time()
    while time.time() - t0 < secs:
        out.append(mem(ANIM, FRAME, 'GAME_STATE'))
        time.sleep(every)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('list')
    ap.add_argument('--cue', default='build/batch.cue')
    ap.add_argument('--card', default='build/states/file-city.mcd')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--out', default='build/batch/play')
    a = ap.parse_args()
    L = json.load(open(a.list))
    out = os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    res_path = os.path.join(out, 'result.json')
    results = json.load(open(res_path)) if os.path.exists(res_path) else {}
    try:
        for i, e in enumerate(L['digimon']):
            typ, name = L['first_id'] + i, e['name']
            if a.only and name not in a.only:
                continue
            # a fresh boot for each species (one species' leftovers do not reach the next)
            run(E + ['stop'])
            print(run(E + ['start', a.cue, '--card', a.card]).strip(), flush=True)
            seq('wait 45, START 20, wait 6, START 20, wait 6')
            seq('DOWN 8, wait 1, CROSS 10, wait 5, CROSS 10, wait 5, CROSS 10, wait 4, CROSS 10, wait 12')
            r = dict(id=typ)
            fn = f'{typ}-{name.lower()}.json'
            d = next((d for d in (os.environ.get('SPECIES_CONTENT'), os.path.join(ROOT, 'content/species')) if d and os.path.exists(os.path.join(d, fn))), None)
            sp = json.load(open(os.path.join(d, fn)))     # SPECIES_CONTENT: a species folder outside content/ (a species not committed yet)
            spec = json.load(open(os.path.join(ROOT, 'content/imports/specs', name + '.json')))
            sys.path.insert(0, os.path.join(ROOT, 'tools'))
            import species as _sp
            if 'para' in sp and 'moves' in sp['para']:
                moves = sp['para']['moves']
            elif 'techniques' in sp:        # the complete species file (docs/mods/species.md)
                moves = _sp.species_record(sp)['para']['moves']
            else:       # a DW1 wild-enemy species keeps its enemy's own technique list (native slots, no clips)
                sys.path.insert(0, os.path.join(ROOT, 'tools'))
                import species as _sp
                moves = _sp.originals().rec[sp['base']]['para']['moves']
            # 1. evolution
            mset(f'EVOLUTION_TARGET={typ}', 'PARTNER_SUB_STATE=0', 'PARTNER_STATE=13', 'TAMER_SUB_STATE=0',
                 'TAMER_STATE=6')
            seq(f'wait 38, CROSS 4, wait 3, CROSS 4, wait 3, shot {out}/{name}-evolved.png')
            pt = run(G + ['show', 'partner.type']).split()
            r['type_after_evolution'] = int(pt[-1]) if pt and pt[-1].isdigit() else pt
            r['evolved'] = r['type_after_evolution'] == typ
            print(name, 'evolved' if r['evolved'] else f'NOT evolved ({pt})', flush=True)
            # 2. walk in File City
            run(G + ['warp', '168', '2']); seq('wait 9')
            mset('PARTNER_PARA.condition=0', 'PARTNER_PARA.tiredness=0')
            p = record(f'{out}/{name}-walk.mp4', 12)
            time.sleep(1)
            seq('DOWN 40, wait 1, RIGHT 50, wait 1, LEFT 70, wait 3')
            p.wait()
            # 3. battle: the four moves = clip techniques first, then the finisher
            clip_slots = sorted(int(k, 16) for k in spec.get('clips', {}) if int(k, 16) >= 0x2E)
            fin = next((0x2E + j for j, x in enumerate(moves) if x != 255 and x >= 58), None)
            techs = [s for s in clip_slots if s != fin] + [0x2E + j for j, x in enumerate(moves)
                                                         if x != 255 and x < 58 and 0x2E + j not in clip_slots]
            techs = (techs + [255, 255, 255])[:3]
            words = [0, 0]
            for s in techs:
                if s != 255:
                    t = moves[s - 0x2E]
                    words[t // 32] |= 1 << (t % 32)
            r['battle_moves'] = [hex(x) if x != 255 else None for x in techs + [fin or 255]]
            sets = [f'PARTNER_ENTITY.digimonEntity.stats.base.moves[{k}]={x}' for k, x in enumerate(techs + [fin or 255])]
            mset(*sets, f'PARTNER_ENTITY.learnedMoves[0]={words[0]}', f'PARTNER_ENTITY.learnedMoves[1]={words[1]}',
                 'PARTNER_ENTITY.digimonEntity.stats.base.off=400', 'PARTNER_ENTITY.digimonEntity.stats.base.speed=400',
                 'PARTNER_ENTITY.digimonEntity.stats.base.brain=400', 'PARTNER_ENTITY.digimonEntity.stats.base.hp=4000',
                 'PARTNER_ENTITY.digimonEntity.stats.current.currentHP=4000',
                 'PARTNER_ENTITY.digimonEntity.stats.base.mp=4000',
                 'PARTNER_ENTITY.digimonEntity.stats.current.currentMP=4000')
            run(G + ['warp', '1', '0']); seq('wait 6'); run(G + ['warp', '0', '0']); seq('wait 8')
            run(G + ['approach', '0']); seq('wait 1')
            p = record(f'{out}/{name}-battle.mp4', 40)
            time.sleep(1)
            seq('CROSS 4, wait 4')
            mset('NPC_ENTITIES[0].digimonEntity.stats.base.hp=2500',
                 'NPC_ENTITIES[0].digimonEntity.stats.current.currentHP=2500')
            seq('CROSS 4, wait 1')
            smp = sample(16)
            seq(f'shot {out}/{name}-battle.png')
            # the finisher (meter full, charge)
            if fin:
                g = mem('COMBAT_DATA.fighter[0].finisherGoal').get('COMBAT_DATA.fighter[0].finisherGoal', 0)
                mset(f'COMBAT_DATA.fighter[0].finisherProgress={g}')
                seq('wait 1, SQUARE 4, wait 1, L1 2, R1 2, L1 2, R1 2, L1 2, R1 2')
                mset('COMBAT_DATA.player.finisherChargeup[0]=80')
                smp += sample(10)
            p.wait()
            ids = sorted({s.get(ANIM) for s in smp if isinstance(s.get(ANIM), int)})
            frames = [s.get(FRAME) for s in smp]
            r['anims_seen'] = [hex(x) for x in ids]
            r['techniques_played'] = [hex(x) for x in ids if x >= 0x2E]
            r['in_battle'] = any(s.get('GAME_STATE') == 1 for s in smp)
            r['frames_advance'] = len(set(frames)) > 3
            # finish it: enemy HP 0, results, back to the world
            mset('NPC_ENTITIES[0].digimonEntity.stats.current.currentHP=0')
            seq('wait 8, CROSS 4, wait 3, CROSS 4, wait 3, CROSS 4, wait 3, CROSS 4, wait 3')
            # a scripted battle can take longer to end (Bulbmon's was still running): keep confirming the
            # results screens until the world is back (GAME_STATE 0), up to ~2 minutes
            for _ in range(40):
                if mem('GAME_STATE').get('GAME_STATE') == 0:
                    break
                mset('NPC_ENTITIES[0].digimonEntity.stats.current.currentHP=0')     # the quick win, again
                seq('CROSS 4, wait 3, CROSS 4, wait 20')
            after = sample(2)
            r['game_state_after'] = after[-1].get('GAME_STATE')
            r['frames_after'] = len({s.get(FRAME) for s in after}) > 1
            seq(f'shot {out}/{name}-after.png')
            r['ok'] = bool(r['evolved'] and r['in_battle'] and r['frames_advance'] and r['techniques_played']
                           and r['game_state_after'] == 0)
            print(name, json.dumps(r), flush=True)
            results[name] = r
            json.dump(results, open(res_path, 'w'), indent=1)
    finally:
        run(E + ['stop'])


if __name__ == '__main__':
    main()
