#!/usr/bin/env python3
"""Plays species of a disc in the emulator, one after the other, unattended: the proof of a species change
(docs/developing.md).

  EMU_PORT=38330 DW_SYMS=EXE tools/dev/playtest/species_proof.py DISC.cue DIGI.DAT OUTDIR ID [ID ...] [--save ID] [--card CARD.mcd]

For each ID, from a fresh boot of CARD (default build/states/file-city.mcd; DW_SYMS is the disc's executable, next to its .elf.map):
  1. the Cheats menu (pause, SELECT), Evolve, the species: screenshot lab-ID.png; evolve
     (the full evolution scene): screenshot evolved-ID.png; the partner's type must be ID;
  2. a wild battle in Native Forest (screen 0, NPC slot 0) with the partner's battle moves set to its first three
     techniques and its finisher (the finisher charged), the enemy finished, the results: battle-ID.png, after-ID.png;
     checks from RAM: in battle, the partner played technique slots (>= 0x2E), frames advance, back in the world;
     finisher_damage: the first HP an enemy loses after the finisher's clip began; both must pass when the species has a finisher;
  3. with --feed: its favourite food (species file) put in the bag and given through the item menu (TRIANGLE, Item, the
     food, Use): fed-ID.png; checks from RAM: happiness and energy before and after, whether the joy clip (slot 0x0B,
     what the game plays after a favourite food) played;
  4. the status screen (status-ID.png) and its technique page (tech-ID.png);
  5. with --save ID (that species only): Save Game in the Cheats menu; the card is copied to OUTDIR/save-ID.mcd.
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
NPC_SLOTS = 8                                # NPC_ENTITIES: any of them can be the fight's enemy
ENEMY_HP = [f'NPC_ENTITIES[{k}].digimonEntity.stats.current.currentHP' for k in range(NPC_SLOTS)]
ENEMY_MAX = [f'NPC_ENTITIES[{k}].digimonEntity.stats.base.hp' for k in range(NPC_SLOTS)]
SAVE_MENU = 43                               # the card menu of Save Game; 23-25 would be Load Game
EMU = None                                   # set by boot()
ANIM = 'PARTNER_ENTITY.digimonEntity.entity.anim.animId'
FRAME = 'PARTNER_ENTITY.digimonEntity.entity.anim.animFrame'


def run(cmd, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=timeout)
    return r.stdout + r.stderr


def seq(s):
    """CONFIRM and CANCEL follow the save's JAPANESE CONTROLS option, like the game (dw/input.h)."""
    japanese = EMU and EMU.has('MOD_OPT_BUTTONS') and EMU.peek('MOD_OPT_BUTTONS', 'i') != 0
    for word_, button in (('CONFIRM', 'CIRCLE' if japanese else 'CROSS'), ('CANCEL', 'CROSS' if japanese else 'TRIANGLE')):
        s = s.replace(word_, button)
    return run(E + ['seq', s])


def mem(*names):
    """Values by name. A read that returns nothing is the harness failing (no types for a field, an emulator that is gone),
    never a game result: it raises, so no check can pass or fail on missing data (2026-11-03: without the build's objects
    every field read came back empty and the battle checks failed for every species, Kotemon and Vemmon included)."""
    out, text = {}, run(M + ['show'] + list(names))
    for line in text.splitlines():
        if ' = ' in line:
            k, v = line.split(' = ', 1)
            try:
                out[k.strip()] = int(v.split()[0])
            except ValueError:
                out[k.strip()] = v
    if names and not out:
        raise RuntimeError(f'memory_inspector read nothing for {", ".join(names)}: {text.strip()[-300:]}')
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


def emulator(cue):
    """The save tools' driver on this port and card home; it knows the real menus and the confirm button of the save."""
    from tools.dev.saves.releases import Emu
    exe = os.environ.get('DW_SYMS') or os.path.join(ROOT, 'build/decomp-int/build/us/psx/gcc/SLUS_010.32')
    emu = Emu(cue, exe, int(os.environ['EMU_PORT']), os.path.join(ROOT, 'build/species-proof'))
    emu.home = os.environ.get('EMU_HOME') or os.path.join(ROOT, '.tools/emu/home-' + os.environ['EMU_PORT'])
    emu.env['EMU_HOME'] = emu.home
    return emu


def boot(cue, card):
    """A fresh boot with the card, CONTINUE, until the Tamer has control. True only when the game really is in the world."""
    global EMU
    for _ in range(3):
        EMU = emulator(cue)
        EMU.start(card)
        if EMU.continue_game() == 0:
            return True
    return False


def sample(secs, every=0.4):
    out, t0 = [], time.time()
    while time.time() - t0 < secs:
        out.append(mem(ANIM, FRAME, 'GAME_STATE'))
        out[-1]['GAME_STATE'] = game_state(out[-1])
        time.sleep(every)
    return out


def game_state(values=None):
    """GAME_STATE is one byte; without the build's types the inspector reads a word with the fields beside it."""
    value = (values or mem('GAME_STATE')).get('GAME_STATE')
    return value & 0xFF if isinstance(value, int) else None


def lab_list():
    """The species of the open evolve list, read from the menu's own array (its order changes with the roster)."""
    ram = EMU.ram()
    count = word(ram, static_symbol('labCount'))
    choices = word(ram, static_symbol('labChoices'))
    return [int.from_bytes(ram[(choices & 0x1FFFFF) + 2 * k:(choices & 0x1FFFFF) + 2 * k + 2], 'little') for k in range(count)]


def word(ram, address):
    return int.from_bytes(ram[(address & 0x1FFFFF):(address & 0x1FFFFF) + 4], 'little')


def static_symbol(name):
    """A file-local variable (`static` in the C): the harness's symbol table reads it from the executable's ELF symbols."""
    return EMU.A(name)


def press(*buttons):
    """One by one: the paused menu drops the chained presses of `seq`."""
    for button in buttons:
        EMU.press(button, 8); EMU.wait(0.6)


def open_cheats(row):
    """Pause, SELECT, the cursor on a row of the Cheats menu. Just after a load the world ignores START for a few seconds."""
    EMU.poke('MOD_OPT_CHEATS', (1).to_bytes(4, 'little'))
    for _ in range(10):
        if mem('MOD_LAB_ACTIVE').get('MOD_LAB_ACTIVE'): break
        if not mem('PAUSE_STATE').get('PAUSE_STATE'): press('START'); EMU.wait(1)
        if mem('PAUSE_STATE').get('PAUSE_STATE'): press('SELECT'); EMU.wait(1.5)
        else: EMU.wait(2)
    EMU.poke('MOD_LAB_CURSOR', row.to_bytes(4, 'little'))
    press('DOWN', 'UP')                  # draws the row; a dropped press would leave the cursor on its neighbour
    EMU.poke('MOD_LAB_CURSOR', row.to_bytes(4, 'little'))


def lab_evolve(t, out):
    """The Cheats menu (pause, SELECT), Evolve, the species, confirm: the same evolution a player gets from it, scene
    included. The list reads the disc while it fills (about 13 s). Writes evolution-confirmation-ID.json."""
    if partner_type() == t: return       # the card's partner already is the species
    open_cheats(3)
    press('CONFIRM')
    choices, previous, steady = [], -1, 0
    for _ in range(60):                  # the list fills while the disc reads: done once it stops growing (the menu puts
        EMU.wait(1)                      # its cursor back when the fill ends, so a species found early must wait too)
        choices = lab_list() if mem('MOD_LAB_VIEW').get('MOD_LAB_VIEW') == 3 else []
        steady = steady + 1 if choices and len(choices) == previous else 0
        if steady >= 3: break
        previous = len(choices)
    if t not in choices:
        press('CANCEL', 'CANCEL', 'START')
        return
    EMU.poke('MOD_LAB_CURSOR', choices.index(t).to_bytes(4, 'little'))
    press('DOWN', 'UP')                  # draws the row; the last row does not move DOWN, so the cursor is put back
    EMU.poke('MOD_LAB_CURSOR', choices.index(t).to_bytes(4, 'little'))
    run(E + ['shot', f'{out}/lab-{t}.png'])
    press('CONFIRM')
    EMU.wait(1)
    confirmation = mem('EVOLUTION_TARGET')
    with open(os.path.join(out, f'evolution-confirmation-{t}.json'), 'w') as stream:
        json.dump(confirmation, stream, indent=2)
    for _ in range(40):                     # START skips the scene; only while it runs, or it would pause the game
        ram = EMU.ram()
        tamer = EMU.peek('TAMER_STATE', 'b', ram)
        if tamer == 0 and EMU.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1 and partner_type() == t: break
        if tamer == 6: EMU.press('START', 6)
        EMU.wait(3)
    seq(f'wait 4, shot {out}/evolved-{t}.png')


def save_game(t, out):
    """Save Game in the Cheats menu: the card screens of the game, on any disc. The card is copied to OUTDIR."""
    seen = []
    for _ in range(3):                   # the world can ignore the pause, and the menu can answer "not now"
        open_cheats(7)
        press('CONFIRM', 'CONFIRM')
        seen = []
        for _ in range(20):
            EMU.wait(1.5)
            menu = EMU.peek('CURRENT_MENU', 'i')
            if menu not in seen[-1:]: seen.append(menu)
            active = mem('MOD_LAB_ACTIVE').get('MOD_LAB_ACTIVE')
            if menu == -1 and len(seen) > 1 and not active: break
            if menu != -1 or active: EMU.press('CONFIRM', 8)
        if SAVE_MENU in seen and seen[-1] == -1 and not active: break
        press('CANCEL', 'CANCEL', 'START')
    else:
        raise RuntimeError(f'the save never finished: {seen}')
    EMU.wait(3)
    run(E + ['shot', f'{out}/saved-{t}.png'])
    EMU.stop()                           # the emulator writes the card file when it stops
    shutil.copy(EMU.card_out(), os.path.join(out, f'save-{t}.mcd'))
    return seen


def status_drawn(png):
    """The status screen's 'Status' tab (top left) is bright; the overworld or a half-drawn menu there is dark."""
    from tools.image import Image, ImageStat
    im = Image.open(png).convert('L').crop((22, 12, 62, 26))
    return ImageStat.Stat(im).mean[0] > 100


def field_menu():
    """Opens the triangle menu, whatever a dropped press did; True once it is open."""
    for _ in range(5):
        if EMU.peek('IS_IN_MENU', 'i'): return True
        press('TRIANGLE'); EMU.wait(1.5)
    return bool(EMU.peek('IS_IN_MENU', 'i'))


def close_menus():
    """Back to the world, from any depth of the triangle menu."""
    for _ in range(8):
        if not EMU.peek('IS_IN_MENU', 'i'): return True
        press('CANCEL'); EMU.wait(1)
    return not EMU.peek('IS_IN_MENU', 'i')


def status(t, out, r):
    """The status screen and its technique page. r['status_drawn'] says the status screen really showed."""
    png = f'{out}/status-{t}.png'
    r['status_drawn'] = False
    for attempt in range(3):
        if field_menu():
            press('RIGHT', 'CONFIRM'); EMU.wait(2 + 2 * attempt)
            run(E + ['shot', png])
            if status_drawn(png):
                r['status_drawn'] = True
                break
        close_menus()
    press('RIGHT'); EMU.wait(1)
    run(E + ['shot', f'{out}/tech-{t}.png'])
    close_menus()


def finisher_watch(slot, secs):
    """Samples the fight for at most `secs`, or 10 s when the clip never starts; returns the samples and the finisher's damage: the first HP an enemy loses
    after the clip began. Everyone else stands still during a finisher, and its hit lands seconds after the clip ends."""
    out, start, damage, t0 = [], None, None, time.time()
    while time.time() - t0 < (secs if start else 10) and not damage:
        values = mem(ANIM, FRAME, 'GAME_STATE', *ENEMY_HP)
        values['GAME_STATE'] = game_state(values)
        out.append(values)
        hp = [values.get(key) for key in ENEMY_HP]
        if start is None and values.get(ANIM) == slot: start = hp
        elif start is not None:
            damage = max([a - b for a, b in zip(start, hp) if isinstance(a, int) and isinstance(b, int)], default=None)
    return out, damage


def battle(t, moves, out, r):
    fin = next((0x2E + j for j, x in enumerate(moves) if x != 255 and 58 <= x <= 112), None)
    r['finisher_expected'] = bool(fin)
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
    run(G + ['approach', '0']); seq('wait 1, CONFIRM 4, wait 4')
    mset(*[f'{key}=2500' for key in ENEMY_MAX + ENEMY_HP])
    seq('CONFIRM 4, wait 1')
    smp = sample(16)
    seq(f'shot {out}/battle-{t}.png')
    if fin:
        for _ in range(3):               # a dropped SQUARE leaves the gauge full and the prompt on screen
            mset(*[f'{key}=2500' for key in ENEMY_HP])
            g = mem('COMBAT_DATA.fighter[0].finisherGoal').get('COMBAT_DATA.fighter[0].finisherGoal', 0)
            mset(f'COMBAT_DATA.fighter[0].finisherProgress={g}')
            seq('wait 1'); EMU.press('SQUARE', 8); seq('wait 1, L1 2, R1 2, L1 2, R1 2, L1 2, R1 2')
            mset('COMBAT_DATA.player.finisherChargeup[0]=80')
            watched, r['finisher_damage'] = finisher_watch(fin, 30)
            smp += watched
            if any(s.get(ANIM) == fin for s in watched): break
        seq(f'shot {out}/finisher-{t}.png')
    ids = sorted({s.get(ANIM) for s in smp if isinstance(s.get(ANIM), int)})
    r['techniques_played'] = [hex(x) for x in ids if x >= 0x2E]
    r['finisher_played'] = bool(fin) and fin in ids
    r['in_battle'] = any(s.get('GAME_STATE') == 1 for s in smp)
    r['frames_advance'] = len({s.get(FRAME) for s in smp}) > 3
    for _ in range(40):
        mset(*[f'{key}=0' for key in ENEMY_HP])
        seq('wait 6, CONFIRM 4, wait 3, CONFIRM 4, wait 3, CONFIRM 4, wait 3')
        if game_state() == 0:
            break
    after = sample(2)
    r['game_state_after'] = after[-1].get('GAME_STATE')
    seq(f'shot {out}/after-{t}.png')


def battle_failures(r):
    """What a species must show in its fight; a check that does not apply (no finisher) is not asked of it."""
    failed = [k for k in ('evolved', 'in_battle', 'frames_advance', 'techniques_played') if not r.get(k)]
    if r.get('game_state_after') != 0: failed.append('back_in_world')
    if r.get('finisher_expected'):
        if not r.get('finisher_played'): failed.append('finisher_played')
        if not (r.get('finisher_damage') or 0) > 0: failed.append('finisher_damage')
    return failed


def feed(t, out, r):
    """Give the species' favourite food through the item menu (bag slot 0) and watch the reaction."""
    s = species.load_content(ids=[t])[t]
    name = s['partner']['favorite_food']; item = species.id_of('items', name, 'favorite_food')
    run(G + ['set', 'inventory.types=[%d%s]' % (item, ',-1' * 29), 'inventory.amounts=[2%s]' % (',0' * 29)])
    k = ['PARTNER_PARA.happiness', 'PARTNER_PARA.energyLevel']
    mset(f'{k[1]}=10')                   # a full partner refuses food, and then there is nothing to measure
    b = mem(*k); smp = []
    for attempt in range(3):           # a dropped press leaves a menu open: close it and try again
        if field_menu():
            press('CONFIRM'); EMU.wait(1 + attempt)
            press('CONFIRM'); EMU.wait(1 + attempt)
            press('CONFIRM')
        smp += sample(4, 0.25)
        now = mem(k[1]).get(k[1])
        if isinstance(now, int) and isinstance(b.get(k[1]), int) and now > b[k[1]]: break   # hunger only lowers it
        close_menus()
    seq(f'shot {out}/fed-{t}.png')
    smp += sample(10, 0.3)             # eating, then the joy clip (0x0B) after a favourite food
    a = mem(*k)
    r['feed'] = dict(food=name, happiness=[b.get(k[0]), a.get(k[0])], energy=[b.get(k[1]), a.get(k[1])],
                     joy_clip=any(x.get(ANIM) == 0x0B for x in smp), anims=sorted({x.get(ANIM) for x in smp if isinstance(x.get(ANIM), int)}))
    r['fed'] = isinstance(a.get(k[1]), int) and isinstance(b.get(k[1]), int) and a[k[1]] > b[k[1]]
    close_menus()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cue'); ap.add_argument('digi'); ap.add_argument('out')
    ap.add_argument('ids', nargs='+', type=int)
    ap.add_argument('--save', type=int)
    ap.add_argument('--card', default='build/states/file-city.mcd')
    ap.add_argument('--no-battle', action='store_true')
    ap.add_argument('--feed', action='store_true', help='also give its favourite food (step 3)')
    a = ap.parse_args()
    assert os.environ.get('EMU_PORT'), 'set EMU_PORT (38330..38339)'
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    _, _, recs = species.read_archive(a.digi)
    results, ok = {}, True
    try:
        for t in a.ids:
            r = dict(id=t, name=recs[t]['para']['name'])
            for attempt in range(2):         # a menu press the emulator drops under load: boot and try once more
                r['booted'] = boot(a.cue, a.card)
                if not r['booted']: continue
                lab_evolve(t, out)
                r['type_after_evolution'] = partner_type()
                if r['type_after_evolution'] == t: break
            r['evolved'] = r.get('type_after_evolution') == t
            if not r['evolved']:
                r.update(ok=False, error='never reached the world' if not r['booted'] else
                         'evolution failed; battle, feeding and status checks skipped')
                results[t] = r
                ok = False
                print(json.dumps(r), flush=True)
                continue
            if not a.no_battle:
                battle(t, recs[t]['para']['moves'], out, r)
                r['failed'] = battle_failures(r)
                r['ok'] = not r['failed']
            else:
                r['ok'] = r['evolved']
            if a.feed:
                feed(t, out, r)
                r['ok'] = r['ok'] and r['fed']
            results[t] = r
            status(t, out, r)
            r['ok'] = r['ok'] and r['status_drawn']
            if a.save == t:
                try:
                    r['save_menus'] = save_game(t, out)
                    r['saved'] = True
                except RuntimeError as error:
                    r.update(saved=False, ok=False, error=str(error))
            ok &= r['ok']
            results[t] = r
            print(json.dumps(r), flush=True)
        if a.save and results.get(a.save, {}).get('saved'):
            r = results.setdefault(a.save, {})
            r['reload_booted'] = boot(a.cue, os.path.join(out, f'save-{a.save}.mcd'))
            seq(f'wait 2, shot {out}/reload-{a.save}.png')
            r['type_after_reload'] = partner_type()
            r['reloaded'] = bool(r['reload_booted']) and r['type_after_reload'] == a.save
            r['ok'] = r.get('ok', False) and r['reloaded']
            ok &= r['reloaded']
            print(json.dumps({'reload': a.save, 'type_after_reload': r['type_after_reload'], 'ok': r['reloaded']}), flush=True)
    finally:
        run(E + ['stop'])
        with open(os.path.join(out, 'result.json'), 'w') as stream:
            json.dump(results, stream, indent=1)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
