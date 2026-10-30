#!/usr/bin/env python3
"""Every technique of a species hits: evolves into each species (lab menu), starts a wild battle and equips its
techniques one at a time, then charges and fires its finisher.

  EMU_PORT=38910 DW_SYMS=decomp-eo tools/playtest/technique_proof.py DISC.cue DIGI.DAT OUTDIR ID [ID ...] [--card CARD.mcd]
        [--only N]          only the first N techniques of each list (default: all)
        [--slots 0x31,0x33] only these slots (a technique or the finisher to try again)
        [--tries N]         tries per technique (default 3; a technique of accuracy 60 misses often)

For each ID, from a fresh boot of CARD (default build/states/file-city.mcd):
  1. evolve through the lab menu (species_proof.py's lab_evolve); the partner's type must be ID;
  2. a wild battle in Native Forest (screen 0, NPC slot 0) with the partner strong and the enemy's HP refilled;
  3. for each technique of its list (slot 0x2E + i): it alone is equipped (stats.base.moves[0]); the partner uses it
     (its animation slot played) and the enemy's HP must drop: damage > 0 (a self technique, range 4: played,
     "ok_self"; the fighter gets buffsRemaining 5 so the AI may use it). Screenshots tech-ID-SLOT-0..3.png
     from the clip's start, about 0.4 s apart (the effect leaving the Digimon), and tech-ID-SLOT-hit.png when the HP first drops;
  4. the finisher (charged, as species_proof.py fires it): finisher damage, screenshots fin-ID-0..3.png (the charge) and fin-ID-hit.png (the effect).
Each technique gets up to --tries (3) tries of 20 s (the partner may move first, be on cooldown, or the enemy may dodge),
then as many again in a fresh battle (the enemy may have wandered out of reach of an area technique; listed in
"fresh_battles"); a technique never seen played is "not_played" (retry it with the species alone, --slots), one played
every try with no HP lost is "no_damage" (the failure this checks: the effect dropped, nothing hits). Prints one JSON line per species, writes OUTDIR/result.json; exit 1 when a technique failed.
"""
import sys as _sys
if __name__ == '__main__' and _sys.argv[1:2] in (['-h'], ['--help']): print(__doc__); _sys.exit(0)
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'tools'))
import species, balance
import species_proof as P
TD = balance.original_doc()['techniques']

HPK = 'NPC_ENTITIES[0].digimonEntity.stats.current.currentHP'
MOVES = 'PARTNER_ENTITY.digimonEntity.stats.base.moves'


def start_battle(moves):
    """The partner strong, every technique of its list learned; a wild battle with NPC slot 0 of Native Forest."""
    words = [0, 0, 0, 0]
    for m in moves:
        if m != 255: words[m // 32] |= 1 << (m % 32)
    P.mset(*[f'PARTNER_ENTITY.learnedMoves[{k}]={words[k]}' for k in range(4)],
           'PARTNER_ENTITY.digimonEntity.stats.base.off=400', 'PARTNER_ENTITY.digimonEntity.stats.base.speed=400',
           'PARTNER_ENTITY.digimonEntity.stats.base.brain=400', 'PARTNER_ENTITY.digimonEntity.stats.base.hp=4000',
           'PARTNER_ENTITY.digimonEntity.stats.current.currentHP=4000', 'PARTNER_ENTITY.digimonEntity.stats.base.mp=4000',
           'PARTNER_ENTITY.digimonEntity.stats.current.currentMP=4000', 'PARTNER_PARA.condition=0', 'PARTNER_PARA.tiredness=0')
    P.run(P.G + ['warp', '1', '0']); P.seq('wait 6'); P.run(P.G + ['warp', '0', '0']); P.seq('wait 8')
    P.run(P.G + ['approach', '0']); P.seq('wait 1, CROSS 4, wait 4')
    P.mset(f'NPC_ENTITIES[0].digimonEntity.stats.base.hp=9999', f'{HPK}=9999')
    P.seq('CROSS 4, wait 1')
    for _ in range(20):                      # a press dropped leaves the battle intro (3) or the world (0): press on
        g = P.mem('GAME_STATE').get('GAME_STATE')
        if g == 1: return True
        if g == 0:
            P.run(P.G + ['approach', '0']); P.seq('wait 1, CROSS 4, wait 4')
            P.mset(f'NPC_ENTITIES[0].digimonEntity.stats.base.hp=9999', f'{HPK}=9999')
        P.seq('CROSS 4, wait 2')
    return False


def end_battle():
    """The enemy finished and the results closed (species_proof.py's way): back in the world."""
    for _ in range(40):
        P.mset(f'{HPK}=0')
        P.seq('wait 6, CROSS 4, wait 3, CROSS 4, wait 3, CROSS 4, wait 3')
        if P.mem('GAME_STATE').get('GAME_STATE') == 0: return True
    return False


def equip(slot, fin=255):
    P.mset(f'{MOVES}[0]={slot}', f'{MOVES}[1]=255', f'{MOVES}[2]=255', f'{MOVES}[3]={fin}',
           'COMBAT_DATA.fighter[0].buffsRemaining=5',      # a self technique (range 4) needs one left
           'PARTNER_ENTITY.digimonEntity.stats.current.currentMP=4000', f'{HPK}=9999',
           'PARTNER_ENTITY.digimonEntity.stats.current.currentHP=4000')
    # the enemy hittable: invulnerable, flattened or stunned it may take no damage (its flags are left alone: clearing
    # them kept the battle from ending)
    P.mset('COMBAT_DATA.fighter[1].invulnerableTimer=0', 'COMBAT_DATA.fighter[1].flatTimer=0',
           'COMBAT_DATA.fighter[1].stunTimer=0')


def watch(slot, out, tag, secs=20.0, shots=4):
    """Waits for the partner's clip `slot`, shoots the screen `shots` times from its start and once when the enemy's HP
    first drops (TAG-hit.png), and returns (played, damage)."""
    t0 = time.time(); played = False; hp0 = None
    while time.time() - t0 < secs:
        m = P.mem(P.ANIM, HPK)
        if m.get(P.ANIM) == slot:
            played = True; break
        hp0 = m.get(HPK)
        time.sleep(0.15)
    if not played: return False, None
    hp0 = hp0 if isinstance(hp0, int) else 9999
    for k in range(shots):                   # from the clip's start: the effect leaving the Digimon, then landing
        time.sleep(0.15); P.seq(f'shot {out}/{tag}-{k}.png')
    hp1 = hp0
    for _ in range(40):                      # the hit lands while the clip plays or right after it
        h = P.mem(HPK).get(HPK)
        if isinstance(h, int):
            if h < hp0 and hp1 == hp0:       # the first damage: the effect where it lands
                P.seq(f'shot {out}/{tag}-hit.png')
            hp1 = min(hp1, h)
        if P.mem(P.ANIM).get(P.ANIM) != slot and hp1 < hp0: break
        time.sleep(0.2)
    return True, hp0 - hp1


def finisher(fin_slot, out, t, tech_slot=255):
    equip(tech_slot, fin_slot)
    P.mset(f'{HPK}=9999'); hp0 = 9999
    g = P.mem('COMBAT_DATA.fighter[0].finisherGoal').get('COMBAT_DATA.fighter[0].finisherGoal', 0)
    P.mset(f'COMBAT_DATA.fighter[0].finisherProgress={g}')
    P.seq('wait 1, SQUARE 4, wait 1, L1 2, R1 2, L1 2, R1 2, L1 2, R1 2')
    P.mset('COMBAT_DATA.player.finisherChargeup[0]=80')
    played, dmg = watch(fin_slot, out, f'fin-{t}', 14.0, 4)   # the charge; fin-ID-hit.png the effect
    if not played:                           # the charge may have been sampled late: the HP tells
        h = P.mem(HPK).get(HPK); dmg = hp0 - h if isinstance(h, int) else None
    return played, dmg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cue'); ap.add_argument('digi'); ap.add_argument('out')
    ap.add_argument('ids', nargs='+', type=int)
    ap.add_argument('--card', default='build/states/file-city.mcd')
    ap.add_argument('--only', type=int)
    ap.add_argument('--slots', help='only these technique slots, e.g. 0x31,0x33 (the finisher is fired when its slot is listed)')
    ap.add_argument('--tries', type=int, default=3, help='tries per technique (a miss: the enemy dodged)')
    a = ap.parse_args()
    assert os.environ.get('EMU_PORT'), 'set EMU_PORT'
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    d, _, recs = species.read_archive(a.digi)
    partners, _, _ = species.read_index(d)
    names = species.names('techs'); results = {}; ok = True
    try:
        for t in a.ids:
            moves = recs[t]['para']['moves']
            r = dict(id=t, name=recs[t]['para']['name'], techniques={})
            for attempt in range(2):
                r['booted'] = P.boot(a.cue, a.card)
                P.lab_evolve(t, partners, out)
                if P.partner_type() == t: break
            r['evolved'] = P.partner_type() == t
            if not r['evolved']:
                ok = False; print(json.dumps(r), flush=True); results[t] = r; continue
            techs = [(0x2E + j, m) for j, m in enumerate(moves) if m != 255 and not 58 <= m <= 112]
            fin = next((0x2E + j for j, m in enumerate(moves) if m != 255 and 58 <= m <= 112), None)
            start_battle(moves)
            if a.slots:
                want = {int(x, 16) for x in a.slots.split(',')}
                techs = [x for x in techs if x[0] in want]
                if fin not in want: fin = None
            for slot, m in techs[:a.only]:
                tries = 0
                for tries in range(1, 2 * a.tries + 1):  # a cooldown or a long walk (not played), a dodge (no damage): again
                    if tries == a.tries + 1:             # the enemy wandered off (an area technique around the Digimon cannot
                        end_battle(); start_battle(moves)  # reach it): a fresh battle starts next to it
                        r.setdefault('fresh_battles', []).append(names[m])
                    equip(slot)
                    played, dmg = watch(slot, out, f'tech-{t}-{slot:02x}')
                    if played and (dmg and dmg > 0 or TD[str(m)]['range'] == 4): break
                if played and TD[str(m)]['range'] == 4:   # a self technique (Muscle Charge, War Cry...): no damage to do
                    st = 'ok_self'
                else:
                    st = 'ok' if played and dmg and dmg > 0 else ('not_played' if not played else 'no_damage')
                r['techniques'][names[m]] = dict(slot=hex(slot), status=st, damage=dmg, tries=tries)
                ok &= st.startswith('ok')
            if fin:
                for tries in range(1, 2 * a.tries + 1):
                    if tries == a.tries + 1:
                        end_battle(); start_battle(moves); r.setdefault('fresh_battles', []).append('finisher')
                    played, dmg = finisher(fin, out, t, techs[0][0] if techs else 255)
                    if dmg and dmg > 0: break
                st = 'ok' if dmg and dmg > 0 else ('not_played' if not played else 'no_damage')
                r['finisher'] = dict(name=names[moves[fin - 0x2E]], slot=hex(fin), status=st, damage=dmg, played=played)
                ok &= st == 'ok'
            r['ok'] = all(x['status'].startswith('ok') for x in r['techniques'].values()) and (not fin or r['finisher']['status'] == 'ok')
            results[t] = r
            print(json.dumps(r), flush=True)
    finally:
        P.run(P.E + ['stop'])
        json.dump(results, open(os.path.join(out, 'result.json'), 'w'), indent=1)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
