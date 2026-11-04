#!/usr/bin/env python3
"""Flattens species in a wild fight and photographs them: the proof of tools/flatsprite.py on a disc.

  EMU_PORT=38331 EMU_HOME=DIR DW_SYMS=EXE tools/dev/playtest/flat_sprites.py DISC.cue OUTDIR
      [--partner ID ...] [--enemy ID ...] [--card CARD.mcd] [--technique]

From a fresh boot of CARD (Continue), for each case a wild fight in Native Forest (screen 0, placed Digimon slot 0):
  --partner ID   the partner made ID with the Cheats menu's Evolve (tools/dev/playtest/species_proof.py), then flattened;
  --enemy ID     slot 0's Digimon replaced by ID before the fight (the screen script's own calls: scriptLoadModel, the
                 placement's typeId, scriptSetDigimon), then flattened; the partner stays the card's.
A Digimon is flattened the way a technique flattens it (battle_main.c: status 4 sets flatTimer to -1, the fighter's next
tick starts the 65-tick squash); with --technique the enemy is flattened by the partner's own Tear Drop (status 4) with
its status chance raised to 100. Shots: NAME-ID-before.png (in the fight), NAME-ID-flat.png and NAME-ID-flat2.png
(flat, a second apart). Checks from RAM: the fight started, the Digimon is flat (`flatSprite` 0..3, or the squashed model:
its texture's trailer says 0xFF) and its slot's frames (`getFlatSprite`) are the ones its texture names.
Prints one JSON line per case, writes OUTDIR/result.json; exit 1 when a check failed.
"""
from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools" / "dev" / "playtest"))
import argparse, json, os, sys, time
import species_proof as P

TEAR_DROP = 23                       # Ice, ranged, status 4 (docs/reference/combat.md)
PARTNER = 'PARTNER_ENTITY.digimonEntity.entity'
ENEMY = 'NPC_ENTITIES[0].digimonEntity.entity'


def call(name, *args):
    """A game function called from gameLoop's entry (tools/dev/playtest/call_function.py's hook); its v0."""
    addr, gl = P.EMU.A(name), P.EMU.A('gameLoop')
    a = [x & 0xFFFFFFFF for x in args] + [0] * (4 - len(args))
    lua = f"""
if CF and CF.bp then CF.bp:remove() end
CF = {{ out = nil, phase = 0, saved = 0 }}
CF.bp = PCSX.addBreakpoint({gl}, 'Exec', 4, 'callfn', function()
  local r = PCSX.getRegisters()
  if CF.phase == 1 then CF.out = r.GPR.n.v0; r.GPR.n.ra = CF.saved; CF.phase = 2; return end
  if CF.phase == 0 then
    CF.saved = r.GPR.n.ra
    r.GPR.n.a0 = {a[0]}; r.GPR.n.a1 = {a[1]}; r.GPR.n.a2 = {a[2]}; r.GPR.n.a3 = {a[3]}
    r.GPR.n.ra = {gl}; r.pc = {addr}; CF.phase = 1
  end
end)
return 'armed'
"""
    path = os.path.join(P.EMU.home, 'callfn.lua')
    with open(path, 'w') as f:
        f.write(lua)
    P.run(P.E + ['lua', f"dofile('{path}')"])
    for _ in range(300):                 # the interpreter is slow, and a model load takes its time
        time.sleep(0.2)
        v = P.run(P.E + ['lua', 'return CF.out and tostring(CF.out) or "-"']).strip().splitlines()[-1:]
        if v and v[0] not in ('-', 'nil'):
            P.run(P.E + ['lua', 'CF.bp:remove() CF.bp = nil'])
            return int(float(v[0]))
    raise RuntimeError(f'{name}{args}: no return')


def boot(cue, card):
    """species_proof.boot with the emulator's debugger on (the breakpoint `call` needs; its driver clears EMU_ARGS)."""
    for _ in range(3):
        P.EMU = P.emulator(cue)
        P.EMU.env['EMU_ARGS'] = '-interpreter -debugger'
        P.EMU.start(card)
        if P.EMU.continue_game() == 0:
            return True
    return False


def flat_state(who):
    m = P.mem(f'{who}.flatSprite', f'{who}.type')
    return m.get(f'{who}.flatSprite'), m.get(f'{who}.type')


def slot_sprite(who):
    """The 9 bytes getFlatSprite keeps for the model slot of `who` (partner or slot 0's Digimon)."""
    t = P.mem(f'{who}.type')[f'{who}.type']
    kind = 3 if who == PARTNER else 0
    model = call('getEntityModelComponent', t, kind)
    ptr = call('getFlatSprite', model)
    ram = P.EMU.ram()
    return list(ram[(ptr & 0x1FFFFF):(ptr & 0x1FFFFF) + 9])


def replace_wild(t):
    """Slot 0's Digimon of Native Forest becomes species t, as the screen script would have placed it."""
    autotalk = P.mem('NPC_ENTITIES[0].autotalk').get('NPC_ENTITIES[0].autotalk', 0)
    call('scriptLoadModel', t)
    P.seq('wait 5')
    P.mset(f'MAP_DIGIMON_TABLE[0].typeId={t}')
    ok = call('scriptSetDigimon', t, 0, autotalk)
    P.seq('wait 2')
    return ok == 1 and flat_state(ENEMY)[1] == t


def fight(name, t, out, r, enemy=None, technique=False):
    P.mset('PARTNER_ENTITY.digimonEntity.stats.base.hp=9999', 'PARTNER_ENTITY.digimonEntity.stats.current.currentHP=9999',
           'PARTNER_ENTITY.digimonEntity.stats.base.mp=9999', 'PARTNER_ENTITY.digimonEntity.stats.current.currentMP=9999',
           'PARTNER_ENTITY.digimonEntity.stats.base.speed=400', 'PARTNER_PARA.condition=0', 'PARTNER_PARA.tiredness=0')
    if technique:
        P.mset(*[f'PARTNER_ENTITY.digimonEntity.stats.base.moves[{k}]={TEAR_DROP if k == 0 else 255}' for k in range(4)],
               f'PARTNER_ENTITY.learnedMoves[0]={1 << TEAR_DROP}', f'MOVE_DATA[{TEAR_DROP}].statusChance=100',
               f'MOVE_DATA[{TEAR_DROP}].accuracy=100')
    P.run(P.G + ['warp', '1', '0']); P.seq('wait 6'); P.run(P.G + ['warp', '0', '0']); P.seq('wait 8')
    if enemy is not None:
        r['enemy_placed'] = replace_wild(enemy)
    P.run(P.G + ['approach', '0'])
    for _ in range(20):                  # talk, the dialog, the fight (the interpreter is slow: press until it starts)
        P.seq('wait 1, CONFIRM 4, wait 2')
        P.mset(*[f'{k}=9999' for k in P.ENEMY_MAX + P.ENEMY_HP])
        if P.game_state() == 1:
            break
    P.seq('wait 6')
    r['in_battle'] = P.game_state() == 1
    who, fighter = (ENEMY, 1) if enemy is not None else (PARTNER, 0)
    P.run(P.E + ['shot', f'{out}/{name}-{t}-before.png'])
    if not technique:
        P.mset(f'COMBAT_DATA.fighter[{fighter}].flatTimer=-1')
    for _ in range(60 if technique else 20):
        fs, _ = flat_state(who)
        if fs is not None and fs != -1:
            break
        P.mset(*[f'{k}=9999' for k in P.ENEMY_HP])
        time.sleep(1)
    P.seq('wait 1')
    fs, typ = flat_state(who)
    r['flat_sprite'] = fs
    r['type'] = typ
    r['slot_sprite'] = slot_sprite(who) if P.EMU.has('getFlatSprite') else None     # (a disc from before the patch)
    P.run(P.E + ['shot', f'{out}/{name}-{t}-flat.png'])
    P.seq('wait 1')
    P.run(P.E + ['shot', f'{out}/{name}-{t}-flat2.png'])
    r['flat'] = fs is not None and fs != -1
    for _ in range(40):                  # end the fight
        P.mset(*[f'{k}=0' for k in P.ENEMY_HP])
        P.seq('wait 6, CONFIRM 4, wait 3, CONFIRM 4, wait 3, CONFIRM 4, wait 3')
        if P.game_state() == 0:
            break


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cue'); ap.add_argument('out')
    ap.add_argument('--partner', type=int, nargs='*', default=[])
    ap.add_argument('--enemy', type=int, nargs='*', default=[])
    ap.add_argument('--card', default='build/states/file-city.mcd')
    ap.add_argument('--technique', action='store_true', help='flatten enemies with the partner\'s Tear Drop')
    a = ap.parse_args()
    assert os.environ.get('EMU_PORT'), 'set EMU_PORT'
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    results, ok = [], True
    try:
        if not boot(a.cue, a.card):
            raise SystemExit('never reached the world')
        for kind, ids in (('enemy', a.enemy), ('partner', a.partner)):
            for t in ids:
                r = dict(kind=kind, id=t)
                if kind == 'partner':
                    P.lab_evolve(t, out)
                    r['evolved'] = P.partner_type() == t
                fight(kind, t, out, r, enemy=t if kind == 'enemy' else None, technique=a.technique and kind == 'enemy')
                r['ok'] = r['in_battle'] and r['flat'] and r.get('evolved', True) and r.get('enemy_placed', True)
                ok &= r['ok']
                results.append(r)
                print(json.dumps(r), flush=True)
    finally:
        P.run(P.E + ['stop'])
        with open(os.path.join(out, 'result.json'), 'w') as f:
            json.dump(results, f, indent=1)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
