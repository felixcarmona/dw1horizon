#!/usr/bin/env python3
"""Plays species of a disc in the emulator, one after the other, unattended: the proof of a species change
(docs/developing.md).

  EMU_PORT=38330 tools/dev/playtest/species_proof.py DISC.cue DIGI.DAT OUTDIR ID [ID ...] [--save ID] [--card CARD.mcd]

For each ID, from a fresh boot of CARD (default build/states/file-city.mcd: Agumon in Jijimon's house):
  1. the lab menu (pause, SELECT) on the "To <name>" entry of the species: screenshot lab-ID.png; evolve
     (the full evolution scene): screenshot evolved-ID.png; the partner's type must be ID;
  2. with --save ID (that species only): talk to Jijimon (the dev-save script opens the save machine), the battle
     registration screen (registration-ID.png), No, Yes (save); the card is copied to OUTDIR/save-ID.mcd;
  3. a wild battle in Native Forest (screen 0, NPC slot 0) with the partner's battle moves set to its first three
     techniques and its finisher (the finisher charged), the enemy finished, the results: battle-ID.png, after-ID.png;
     checks from RAM: in battle, the partner played technique slots (>= 0x2E), frames advance, back in the world;
     finisher_damage: the enemy's HP lost while the finisher played (its effect hit);
  4. with --feed: its favourite food (species file) put in the bag and given through the item menu (TRIANGLE, Item, the
     food, Use): fed-ID.png; checks from RAM: happiness and energy before and after, whether the joy clip (slot 0x0B,
     what the game plays after a favourite food) played;
  5. the status screen (status-ID.png) and its technique page (tech-ID.png).
Then, with --save: a fresh boot of OUTDIR/save-ID.mcd, continue: the partner's type must be ID (reload-ID.png).
Prints one JSON line per species and writes OUTDIR/result.json; exit 1 when a check failed.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse, json, os, shutil, subprocess, sys, time
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species

PY = sys.executable
E = [PY, os.path.join(ROOT, 'tools/dev/emulator.py')]
M = [PY, os.path.join(ROOT, 'tools/dev/memory_inspector.py')]
G = [PY, os.path.join(ROOT, 'tools/dev/game_state.py')]
FIXED = 11                                   # MOD_LAB_EVO_FIXED in mod_lab.c (the NPC partners before DIGI.DAT's list)
NPC_PARTNERS = [124, 121, 120, 94, 113, 70, 66, 119, 115, 117, 116]   # MOD_LAB_EVO_TARGETS, in the menu's order
ANIM = 'PARTNER_ENTITY.digimonEntity.entity.anim.animId'
FRAME = 'PARTNER_ENTITY.digimonEntity.entity.anim.animFrame'


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


def partner_type():
    for line in run(G + ['show', 'partner.type']).splitlines():   # stderr may add a dwsyms line
        pt = line.split()
        if len(pt) == 2 and pt[0] == 'partner.type' and pt[1].lstrip('-').isdigit(): return int(pt[1])
    return None


def in_world():
    """The title menu counts MAIN_MENU_TICKS; in the world it stands still (the save's RAM is loaded before)."""
    a = mem('MAIN_MENU_TICKS').get('MAIN_MENU_TICKS'); time.sleep(1.0); b = mem('MAIN_MENU_TICKS').get('MAIN_MENU_TICKS')
    return a is not None and a == b


def boot(cue, card):
    """A fresh boot with the card, CONTINUE: in the world (Jijimon's house for the default card)."""
    for _ in range(3):
        run(E + ['stop'])
        run(E + ['start', cue, '--card', card])
        seq('wait 45, START 20, wait 6, START 20, wait 6')
        seq('DOWN 8, wait 1, CROSS 10, wait 5, CROSS 10, wait 5, CROSS 10, wait 4, CROSS 10, wait 14')
        for _ in range(4):                  # a dropped press leaves the continue menu open: confirm again
            if in_world():
                seq('wait 12')                 # the map fades in and the Tamer gets control
                return True
            seq('CROSS 10, wait 12')
    return False


def sample(secs, every=0.4):
    out, t0 = [], time.time()
    while time.time() - t0 < secs:
        out.append(mem(ANIM, FRAME, 'GAME_STATE'))
        time.sleep(every)
    return out


def lab_evolve(t, partners, out):
    """The lab menu (pause, SELECT) on its evolve entry (MOD_LAB_CURSOR 3) with the choice one before the species', then
    RIGHT: the entry redraws "To <name>" of the species; checked in RAM, pressed again when the emulator dropped it."""
    choice = NPC_PARTNERS.index(t) if t in NPC_PARTNERS else FIXED + partners.index(t)
    seq('START 30, wait 3, SELECT 30, wait 3')
    for _ in range(5):
        run(E + ['poke', 'MOD_LAB_CURSOR', (3).to_bytes(4, 'little').hex()])
        first = choice == 0                  # the first entry: from the second, LEFT
        run(E + ['poke', 'MOD_LAB_EVO_CHOICE', (choice + 1 if first else choice - 1).to_bytes(4, 'little').hex()])
        seq('LEFT 6, wait 2' if first else 'RIGHT 6, wait 2')
        if mem('MOD_LAB_EVO_CHOICE').get('MOD_LAB_EVO_CHOICE') == choice: break
    seq(f'shot {out}/lab-{t}.png')
    confirmations = []
    for _ in range(3):
        seq('CROSS 60, wait 2')
        confirmation = mem('EVOLUTION_TARGET', 'PARTNER_STATE', 'TAMER_STATE')
        confirmations.append(confirmation)
        if confirmation.get('EVOLUTION_TARGET') == t or partner_type() == t:
            break
    with open(os.path.join(out, f'evolution-confirmation-{t}.json'), 'w') as stream:
        json.dump(confirmations, stream, indent=2)
    seq('TRIANGLE 30, wait 3, START 30, wait 3')
    seq(f'wait 38, CROSS 4, wait 3, CROSS 4, wait 3, shot {out}/evolved-{t}.png')


def save_game(t, out):
    """Jijimon (NPC slot 0 of his house) opens the save machine (tools/dws/examples/dev-save.dws)."""
    run(G + ['approach', '0'])
    seq(f'wait 1, CROSS 6, wait 4, shot {out}/registration-{t}.png')
    seq('DOWN 4, wait 1, CROSS 6, wait 4, CROSS 6, wait 14')
    home = os.environ.get('EMU_HOME') or os.path.join(ROOT, '.tools/emu/home-' + os.environ['EMU_PORT'])
    shutil.copy(os.path.join(home, 'memcard1.mcd'), os.path.join(out, f'save-{t}.mcd'))


def status_drawn(png):
    """The status screen's 'Status' tab (top left) is bright; the overworld or a half-drawn menu there is dark."""
    from tools.image import Image, ImageStat
    im = Image.open(png).convert('L').crop((22, 12, 62, 26))
    return ImageStat.Stat(im).mean[0] > 100


def status(t, out):
    """Open the status screen and shoot it; a menu press dropped or a menu still opening (seen once after a
    battle) leaves the overworld with empty boxes: close it, wait longer and try again (up to 3 times)."""
    png = f'{out}/status-{t}.png'
    for attempt in range(3):
        seq(f'wait {2 + 3 * attempt}, TRIANGLE 8, wait {4 + 2 * attempt}, RIGHT 4, wait 3, CROSS 8, wait {6 + 4 * attempt}')
        seq(f'shot {png}')
        if status_drawn(png): break
        seq('CIRCLE 8, wait 4, CIRCLE 8, wait 4')
    seq(f'RIGHT 4, wait 3, shot {out}/tech-{t}.png')


def battle(t, moves, out, r):
    fin = next((0x2E + j for j, x in enumerate(moves) if x != 255 and 58 <= x <= 112), None)
    techs = [0x2E + j for j, x in enumerate(moves) if x != 255 and not 58 <= x <= 112][:3]
    techs = (techs + [255, 255, 255])[:3]
    words = [0, 0, 0, 0]
    for s in techs + ([fin] if fin else []):
        if s != 255:
            m = moves[s - 0x2E]
            words[m // 32] |= 1 << (m % 32)
    r['battle_moves'] = [hex(x) if x != 255 else None for x in techs + [fin or 255]]
    mset(*[f'PARTNER_ENTITY.digimonEntity.stats.base.moves[{k}]={x}' for k, x in enumerate(techs + [fin or 255])],
         f'PARTNER_ENTITY.learnedMoves[0]={words[0]}', f'PARTNER_ENTITY.learnedMoves[1]={words[1]}',
         'PARTNER_ENTITY.digimonEntity.stats.base.off=400', 'PARTNER_ENTITY.digimonEntity.stats.base.speed=400',
         'PARTNER_ENTITY.digimonEntity.stats.base.brain=400', 'PARTNER_ENTITY.digimonEntity.stats.base.hp=4000',
         'PARTNER_ENTITY.digimonEntity.stats.current.currentHP=4000', 'PARTNER_ENTITY.digimonEntity.stats.base.mp=4000',
         'PARTNER_ENTITY.digimonEntity.stats.current.currentMP=4000', 'PARTNER_PARA.condition=0', 'PARTNER_PARA.tiredness=0')
    run(G + ['warp', '1', '0']); seq('wait 6'); run(G + ['warp', '0', '0']); seq('wait 8')
    run(G + ['approach', '0']); seq('wait 1, CROSS 4, wait 4')
    mset('NPC_ENTITIES[0].digimonEntity.stats.base.hp=2500', 'NPC_ENTITIES[0].digimonEntity.stats.current.currentHP=2500')
    seq('CROSS 4, wait 1')
    smp = sample(16)
    seq(f'shot {out}/battle-{t}.png')
    if fin:
        HPK = 'NPC_ENTITIES[0].digimonEntity.stats.current.currentHP'
        mset(f'{HPK}=2500')
        hp0 = mem(HPK).get(HPK)
        g = mem('COMBAT_DATA.fighter[0].finisherGoal').get('COMBAT_DATA.fighter[0].finisherGoal', 0)
        mset(f'COMBAT_DATA.fighter[0].finisherProgress={g}')
        seq('wait 1, SQUARE 4, wait 1, L1 2, R1 2, L1 2, R1 2, L1 2, R1 2')
        mset('COMBAT_DATA.player.finisherChargeup[0]=80')
        smp += sample(10)
        seq(f'shot {out}/finisher-{t}.png')
        hp1 = mem(HPK).get(HPK)
        r['finisher_damage'] = (hp0 - hp1) if isinstance(hp0, int) and isinstance(hp1, int) else None
    ids = sorted({s.get(ANIM) for s in smp if isinstance(s.get(ANIM), int)})
    r['techniques_played'] = [hex(x) for x in ids if x >= 0x2E]
    r['finisher_played'] = bool(fin) and fin in ids
    r['in_battle'] = any(s.get('GAME_STATE') == 1 for s in smp)
    r['frames_advance'] = len({s.get(FRAME) for s in smp}) > 3
    for _ in range(40):
        mset('NPC_ENTITIES[0].digimonEntity.stats.current.currentHP=0')
        seq('wait 6, CROSS 4, wait 3, CROSS 4, wait 3, CROSS 4, wait 3')
        if mem('GAME_STATE').get('GAME_STATE') == 0:
            break
    after = sample(2)
    r['game_state_after'] = after[-1].get('GAME_STATE')
    seq(f'shot {out}/after-{t}.png')


def feed(t, out, r):
    """Give the species' favourite food through the item menu (bag slot 0) and watch the reaction."""
    s = species.load_content(ids=[t])[t]
    name = s['partner']['favorite_food']; item = species.id_of('items', name, 'favorite_food')
    run(G + ['set', 'inventory.types=[%d%s]' % (item, ',-1' * 29), 'inventory.amounts=[2%s]' % (',0' * 29)])
    k = ['PARTNER_PARA.happiness', 'PARTNER_PARA.energyLevel']
    b = mem(*k); smp = []
    for attempt in range(3):           # a dropped press leaves a menu open: close it and try again
        seq(f'wait {2 + 2 * attempt}, TRIANGLE 8, wait {5 + attempt}, CROSS 8, wait {5 + attempt}, CROSS 8, wait {5 + attempt}, '
            'wait 2, CROSS 4, wait 3')
        smp += sample(4, 0.25)
        if mem(k[1]).get(k[1]) != b.get(k[1]): break
        seq('CIRCLE 8, wait 4, CIRCLE 8, wait 4, CIRCLE 8, wait 4')
    seq(f'shot {out}/fed-{t}.png')
    smp += sample(10, 0.3)             # eating, then the joy clip (0x0B) after a favourite food
    a = mem(*k)
    r['feed'] = dict(food=name, happiness=[b.get(k[0]), a.get(k[0])], energy=[b.get(k[1]), a.get(k[1])],
                     joy_clip=any(x.get(ANIM) == 0x0B for x in smp), anims=sorted({x.get(ANIM) for x in smp if isinstance(x.get(ANIM), int)}))
    r['fed'] = isinstance(a.get(k[1]), int) and isinstance(b.get(k[1]), int) and a[k[1]] > b[k[1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cue'); ap.add_argument('digi'); ap.add_argument('out')
    ap.add_argument('ids', nargs='+', type=int)
    ap.add_argument('--save', type=int)
    ap.add_argument('--card', default='build/states/file-city.mcd')
    ap.add_argument('--no-battle', action='store_true')
    ap.add_argument('--feed', action='store_true', help='also give its favourite food (step 4)')
    a = ap.parse_args()
    assert os.environ.get('EMU_PORT'), 'set EMU_PORT (38330..38339)'
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    d, _, recs = species.read_archive(a.digi)
    partners, _, _ = species.read_index(d)
    results, ok = {}, True
    try:
        for t in a.ids:
            r = dict(id=t, name=recs[t]['para']['name'])
            if t not in partners and t not in NPC_PARTNERS:
                r['error'] = 'not a partner species of this DIGI.DAT'; ok = False; print(json.dumps(r)); continue
            for attempt in range(2):         # a menu press the emulator drops under load: boot and try once more
                r['booted'] = boot(a.cue, a.card)
                lab_evolve(t, partners, out)
                r['type_after_evolution'] = partner_type()
                if r['type_after_evolution'] == t: break
            r['evolved'] = r['type_after_evolution'] == t
            if not r['evolved']:
                r.update(ok=False, error='evolution failed; battle, feeding and status checks skipped')
                results[t] = r
                ok = False
                print(json.dumps(r), flush=True)
                continue
            if a.save == t:
                save_game(t, out)
            if not a.no_battle:
                battle(t, recs[t]['para']['moves'], out, r)
                r['ok'] = bool(r['evolved'] and r['in_battle'] and r['frames_advance'] and r['techniques_played']
                               and r['game_state_after'] == 0)
            else:
                r['ok'] = r['evolved']
            if a.feed:
                feed(t, out, r)
                r['ok'] = r['ok'] and r['fed']
            status(t, out)                       # last: a menu left open does not disturb the next step
            ok &= r['ok']
            results[t] = r
            print(json.dumps(r), flush=True)
        if a.save and results.get(a.save, {}).get('evolved'):
            r = results.setdefault(a.save, {})
            boot(a.cue, os.path.join(out, f'save-{a.save}.mcd'))
            seq(f'wait 2, shot {out}/reload-{a.save}.png')
            r['type_after_reload'] = partner_type()
            r['reloaded'] = r['type_after_reload'] == a.save
            ok &= r['reloaded']
            print(json.dumps({'reload': a.save, 'type_after_reload': r['type_after_reload'], 'ok': r['reloaded']}), flush=True)
    finally:
        run(E + ['stop'])
        with open(os.path.join(out, 'result.json'), 'w') as stream:
            json.dump(results, stream, indent=1)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
