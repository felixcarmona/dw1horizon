#!/usr/bin/env python3
"""Flattens species in a wild fight and photographs them: the proof of tools/flatsprite.py on a disc.

  EMU_PORT=38331 EMU_HOME=DIR DW_SYMS=EXE tools/dev/playtest/flat_sprites.py DISC.cue OUTDIR
      [--partner ID ...] [--enemy ID ...] [--card CARD.mcd] [--assets BUILD_DIR] [--technique] [--opponent ID] [--finisher]

From a fresh boot of CARD (Continue), for each case a wild fight in Native Forest (screen 0, placed Digimon slot 0):
  --partner ID   the partner made ID with the Cheats menu's Evolve (tools/dev/playtest/species_proof.py), then flattened;
  --enemy ID     slot 0's Digimon replaced by ID before the fight (the screen script's own calls: scriptLoadModel, the
                 placement's typeId, scriptSetDigimon), then flattened; the partner stays the card's. The native
                 field occupants are removed first so the imported opponent fits the original 2 MB heap.
A Digimon is flattened the way a technique flattens it (battle_main.c: status 4 sets flatTimer to -1, the fighter's next
tick starts the 65-tick squash); with --technique the enemy is flattened by the partner's own Tear Drop (status 4) with
its status chance raised to 100. Shots: NAME-ID-before.png (in the fight), NAME-ID-flat.png and NAME-ID-flat2.png
(flat, a second apart). Checks from RAM: the fight started, the Digimon is flat (`flatSprite` 0..3), its slot's frames
(`getFlatSprite`) match the built texture, and the fight returns to the world. Partners also check the slot after
evolution. Assets default to the cue stem's build folder; --assets overrides that folder.
With --opponent, flattened-partner cases use that enemy. With --finisher the opposite fighter must play its
finisher, damage the flattened fighter, advance battle frames and return to the field; a video and samples are saved.
Finisher fixtures give the replacement enemy ample MP and speed to bound its normal charge delay.
Prints one JSON line per case, writes OUTDIR/result.json; exit 1 when a check failed.
"""
from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools" / "dev" / "playtest"))
import argparse, json, os, struct, subprocess, sys, time
import species_proof as P

TEAR_DROP = 23                       # Ice, ranged, status 4 (docs/reference/combat.md)
PARTNER = 'PARTNER_ENTITY.digimonEntity.entity'
ENEMY = 'NPC_ENTITIES[0].digimonEntity.entity'


def call(name, *args):
    """Call at a frame boundary shared by the field and battle loops; return v0."""
    addr, gl = P.EMU.A(name), P.EMU.A('modTickStart')
    a = [x & 0xFFFFFFFF for x in args] + [0] * (4 - len(args))
    lua = f"""
if CF and CF.bp then CF.bp:remove() end
CF = {{ out = nil, phase = 0, saved = 0 }}
CF.bp = PCSX.addBreakpoint({gl}, 'Exec', 4, 'callfn', function()
  local r = PCSX.getRegisters()
  if CF.phase == 1 and r.GPR.n.ra == {gl} then
    CF.out = r.GPR.n.v0; r.GPR.n.ra = CF.saved
    r.GPR.n.a0 = CF.args[1]; r.GPR.n.a1 = CF.args[2]
    r.GPR.n.a2 = CF.args[3]; r.GPR.n.a3 = CF.args[4]
    CF.phase = 2; return
  end
  if CF.phase == 0 then
    CF.saved = r.GPR.n.ra
    CF.args = {{ r.GPR.n.a0, r.GPR.n.a1, r.GPR.n.a2, r.GPR.n.a3 }}
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
        P.EMU.wait(25)  # continue_game waits another 35 s; avoid interrupting the first intro load.
        if P.EMU.continue_game() == 0:
            return True
        P.EMU.stop()
    return False


def flat_state(who):
    m = P.mem(f'{who}.flatSprite', f'{who}.type')
    return m.get(f'{who}.flatSprite'), m.get(f'{who}.type')


def slot_sprite(who):
    """The 12 bytes getFlatSprite keeps for the model slot of `who` (partner or slot 0's Digimon)."""
    t = P.mem(f'{who}.type')[f'{who}.type']
    kind = 3 if who == PARTNER else 0
    model = call('getEntityModelComponent', t, kind)
    ptr = call('getFlatSprite', model)
    ram = P.EMU.ram()
    return list(ram[(ptr & 0x1FFFFF):(ptr & 0x1FFFFF) + 12])


def expected_sprite(assets, t):
    """The texture's record on disc, independently of the executable's cached slot."""
    import flatsprite
    data, _, recs = P.species.read_archive(str(assets / 'DIGI.DAT'))
    r = recs[t]
    if r['texFile'] != P.species.TEX_ARCHIVE:
        data = (assets / 'ALLTIM.TIM').read_bytes()
    tex = data[r['texSector'] * 2048:(r['texSector'] + r['texSectors']) * 2048]
    cells, row = flatsprite.sprite_of(tex)
    return [c for uv in cells for c in uv] + list(flatsprite.frame_rows(tex))


def replace_wild(t):
    """Slot 0's Digimon of Native Forest becomes species t, as the screen script would have placed it."""
    autotalk = P.mem('NPC_ENTITIES[0].autotalk').get('NPC_ENTITIES[0].autotalk', 0)
    # The field's five native entities and two models can leave too little heap
    # for another imported model on 2 MB. Remove the field occupants before
    # loading the test opponent, keeping slot 0's placement and talk script.
    ram = P.EMU.ram()
    entities = P.EMU.A('ENTITY_TABLE') & 0x1FFFFF
    models = P.EMU.A('LOADED_DIGIMON_MODELS') & 0x1FFFFF
    loaded = struct.unpack_from('<8i', ram, models)
    for slot in range(8):
        ptr = struct.unpack_from('<I', ram, entities + (slot + 2) * 4)[0]
        if ptr:
            old = struct.unpack_from('<i', ram, ptr & 0x1FFFFF)[0]
            call('removeEntity', old, slot + 2)
    for old in loaded:
        if old >= 0:
            call('scriptUnloadModel', old)
    call('scriptLoadModel', t)
    P.seq('wait 5')
    P.mset(f'MAP_DIGIMON_TABLE[0].typeId={t}')
    ok = call('scriptSetDigimon', t, 0, autotalk)
    P.seq('wait 2')
    return ok == 1 and flat_state(ENEMY)[1] == t


def finisher_slot(assets, species):
    _, _, records = P.species.read_archive(str(assets / 'DIGI.DAT'))
    moves = records[species]['para']['moves']
    return next((0x2E + i for i, move in enumerate(moves) if 58 <= move <= 112), None)


def scalar_reader(*names):
    """Resolve scalar layouts once, then sample one coherent RAM image per poll."""
    code = """
import json,sys
from tools.dev import memory_inspector as M
variables,types=M.build_index()
locations={}
for name in sys.argv[1:]:
    address,kind=M.resolve_expr(name,variables,types)
    assert kind['k'] in ('base','ptr'),(name,kind)
    locations[name]=[address&0x1fffff,kind['size'],kind.get('signed',False)]
print(json.dumps(locations))
"""
    run=subprocess.run([str(_DevPath(_DEV_ROOT)/'.venv/bin/python'),'-c',code,*names],
                       cwd=_DEV_ROOT,capture_output=True,text=True,check=True)
    locations=json.loads(run.stdout)
    def read():
        ram=P.EMU.ram()
        return {name:int.from_bytes(ram[address:address+size],'little',signed=signed)
                for name,(address,size,signed) in locations.items()}
    read.locations=locations
    return read


def finish_while_flat(assets, fighter, who, out, stem, result, *, attacker=None, entity=None, target_hp=None):
    """The opposite fighter performs its equipped finisher while the test subject stays flat."""
    attacker = (1 if fighter == 0 else 0) if attacker is None else attacker
    entity = entity or (ENEMY if attacker else PARTNER)
    species = P.mem(f'{entity}.type')[f'{entity}.type']
    fin = finisher_slot(assets, species)
    assert fin is not None, f'species {species} has no finisher'
    stats = entity.rsplit('.entity', 1)[0] + '.stats'
    target_hp = target_hp or ('PARTNER_ENTITY.digimonEntity.stats.current.currentHP' if attacker else P.ENEMY_HP[0])
    old_moves=P.mem(*[f'{stats}.base.moves[{i}]' for i in range(4)])
    P.mset(f'{stats}.base.moves[3]={fin}')
    # Let the squash's final tick set FLATTENED before lengthening the status.
    P.seq('wait 1')
    P.mset(f'COMBAT_DATA.fighter[{fighter}].flatTimer=1200')
    P.seq('wait 2')  # Exercise the flat spit's own move lookup before charging the opposite finisher.
    goal = P.mem(f'COMBAT_DATA.fighter[{attacker}].finisherGoal')[f'COMBAT_DATA.fighter[{attacker}].finisherGoal']
    P.mset(f'COMBAT_DATA.fighter[{attacker}].targetId={fighter}',
           f'COMBAT_DATA.fighter[{attacker}].finisherProgress={goal}')
    video = subprocess.Popen(P.E + ['record', str(out / (stem + '-finisher.mp4')), '50'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    hp_start = P.mem(target_hp)[target_hp]
    samples, seen, damage = [], False, 0
    charged=False
    read=scalar_reader(f'{entity}.anim.animId',f'{who}.flatSprite',target_hp,'BATTLE_FRAME_COUNT',
                       'NO_AI_FLAG','FINISHING_ENTITY','BTL_FINISHER_TIMER','COMBAT_DATA.player.currentCommand[0]',
                       f'COMBAT_DATA.fighter[{attacker}].targetId',f'COMBAT_DATA.fighter[{attacker}].queuedAnim',
                       f'COMBAT_DATA.fighter[{attacker}].flags',f'{who}.type',f'{entity}.type',
                       f'COMBAT_DATA.fighter[{fighter}].queuedAnim')
    victim_address=read.locations[f'{who}.type'][0]
    result['flat_move_lookup']=call('entityGetTechFromAnim',victim_address|0x80000000,0)
    def player_finisher():
        # Submit the target and the ordinary finisher command together, before
        # automatic targeting can pick another member of a group encounter.
        P.EMU.run('pause')
        try:
            flags=P.mem('COMBAT_DATA.fighter[0].flags')['COMBAT_DATA.fighter[0].flags']
            P.mset(f'COMBAT_DATA.fighter[0].targetId={fighter}',
                   f'COMBAT_DATA.fighter[0].flags={flags|0x400}',
                   f'COMBAT_DATA.fighter[0].finisherProgress={goal}',
                   'COMBAT_DATA.player.bufferedCommand[0]=11','COMBAT_DATA.player.currentCommand[0]=11',
                   'COMBAT_DATA.player.commandDelay[0]=0')
        finally:P.EMU.run('resume')
        P.EMU.press('SQUARE',12)
    try:
        if not attacker:player_finisher()
        end = time.monotonic() + 35
        retry_at=time.monotonic()+3
        while time.monotonic() < end:
            if not seen and time.monotonic()>=retry_at and P.mem('NO_AI_FLAG')['NO_AI_FLAG']==0:
                P.mset(f'COMBAT_DATA.fighter[{attacker}].finisherProgress={goal}')
                if not attacker:
                    player_finisher()
                retry_at=time.monotonic()+3
            m = read()
            m['wall_time']=time.time()
            samples.append(m)
            if (not attacker and not charged and m['BTL_FINISHER_TIMER']>0 and
                    (m['FINISHING_ENTITY']&0x1fffff)==read.locations[f'{entity}.type'][0]):
                P.mset('COMBAT_DATA.player.finisherChargeup[0]=80');charged=True
            playing=(m[f'{entity}.anim.animId']==fin and
                     m[f'COMBAT_DATA.fighter[{attacker}].flags']&0x20 and m['BTL_FINISHER_TIMER']==0)
            if playing:
                if not seen:
                    hp_start = samples[-2][target_hp] if len(samples)>1 else hp_start
                    P.run(P.E + ['shot', str(out / (stem + '-finisher.png'))])
                seen = True
            if seen:
                damage = max(damage, hp_start - m[target_hp])
                if damage > 0: break
            time.sleep(.1)
        result['finisher_attacker'] = species
        result['finisher_played'] = seen
        result['finisher_damage'] = damage
        result['flat_during_finisher'] = any(m[f'{entity}.anim.animId']==fin and
                    m[f'COMBAT_DATA.fighter[{attacker}].flags']&0x20 and m['BTL_FINISHER_TIMER']==0 and
                    0<=m[f'{who}.flatSprite']<=3 for m in samples)
        result['battle_frames_advanced'] = len({m['BATTLE_FRAME_COUNT'] for m in samples}) > 1
        blocked=[m for m in samples if m['NO_AI_FLAG'] and
                 (m['FINISHING_ENTITY']&0x1fffff)==victim_address and m['BTL_FINISHER_TIMER']>0]
        result['flat_spit_stall']=bool(blocked and blocked[-1]['BATTLE_FRAME_COUNT']-blocked[0]['BATTLE_FRAME_COUNT']>=120
                                     and len({m['BTL_FINISHER_TIMER'] for m in blocked})==1)
        (out / (stem + '-finisher-samples.json')).write_text(json.dumps(samples, indent=1) + '\n')
    finally:
        video.wait(timeout=60)
        P.mset(*[f'{key}={value}' for key,value in old_moves.items()])
    P.mset(f'COMBAT_DATA.fighter[{fighter}].flatTimer=65')
    P.seq('wait 7')


def fight(name, t, out, r, enemy=None, technique=False, opponent=None, finisher=False, assets=None):
    # Evolution can leave a Tamer Level Up dialog. Finish it before submitting
    # a map transition; warping while that script owns control races its return.
    if not P.EMU.in_control():
        raise RuntimeError('no field control before the encounter')
    P.EMU.gs('set', 'partner.para.age=1', 'partner.para.evoTimer=0')
    P.mset('PARTNER_ENTITY.digimonEntity.stats.base.hp=9999', 'PARTNER_ENTITY.digimonEntity.stats.current.currentHP=9999',
           'PARTNER_ENTITY.digimonEntity.stats.base.mp=9999', 'PARTNER_ENTITY.digimonEntity.stats.current.currentMP=9999',
           'PARTNER_ENTITY.digimonEntity.stats.base.speed=400', 'PARTNER_PARA.condition=0', 'PARTNER_PARA.tiredness=0')
    if technique:
        P.mset(*[f'PARTNER_ENTITY.digimonEntity.stats.base.moves[{k}]={TEAR_DROP if k == 0 else 255}' for k in range(4)],
               f'PARTNER_ENTITY.learnedMoves[0]={1 << TEAR_DROP}', f'MOVE_DATA[{TEAR_DROP}].statusChance=100',
               f'MOVE_DATA[{TEAR_DROP}].accuracy=100')
    if finisher:
        fin = finisher_slot(assets, P.partner_type())
        if fin is not None: P.mset(f'PARTNER_ENTITY.digimonEntity.stats.base.moves[3]={fin}')
    # Slot 0 exists only by day. Submit each warp while paused, then wait for
    # arrival and free control; fixed sleeps raced map loading under the interpreter.
    P.run(P.G + ['trigger', '1', '1'])
    P.mset('HOUR=12', 'IS_GAMETIME_RUNNING=0')
    for screen in (1, 0):
        if not P.EMU.warp(screen) or not P.EMU.in_control():
            raise RuntimeError(f'never reached screen {screen} with control')
    foe = enemy if enemy is not None else opponent
    if foe is not None:
        r['enemy_placed'] = replace_wild(foe)
        if finisher:
            fin = finisher_slot(assets, foe)
            if fin is not None:
                P.mset(f'NPC_ENTITIES[0].digimonEntity.stats.base.moves[3]={fin}',
                       'NPC_ENTITIES[0].digimonEntity.stats.base.speed=400',
                       'NPC_ENTITIES[0].digimonEntity.stats.base.mp=9999',
                       'NPC_ENTITIES[0].digimonEntity.stats.current.currentMP=9999')
    for _ in range(20):                  # talk, the dialog, the fight (the interpreter is slow: press until it starts)
        if P.game_state() == 1:
            break
        if P.mem('IS_SCRIPT_PAUSED')['IS_SCRIPT_PAUSED'] == 1:
            P.run(P.G + ['approach', '0'])
        P.EMU.press('CONFIRM', 12)
        P.EMU.wait(1)
        P.mset(*[f'{k}=9999' for k in P.ENEMY_MAX + P.ENEMY_HP])
        if P.game_state() == 1:
            break
    for _ in range(120):
        ready=P.mem('GAME_STATE','BATTLE_FRAME_COUNT','MOD_BATTLE_LOADING')
        if (ready['GAME_STATE']&255)==1 and ready['BATTLE_FRAME_COUNT']>=20 and ready['MOD_BATTLE_LOADING']==0:break
        P.EMU.wait(.5)
    else:raise RuntimeError('battle setup never completed')
    r['in_battle'] = P.game_state() == 1
    if not r['in_battle']:
        raise RuntimeError('the wild fight never started')
    who, fighter = (ENEMY, 1) if enemy is not None else (PARTNER, 0)
    P.run(P.E + ['shot', f'{out}/{name}-{t}-before.png'])
    if not technique:
        P.mset(f'COMBAT_DATA.fighter[{fighter}].flatTimer=-1')
    for _ in range(60 if technique else 20):
        fs, _ = flat_state(who)
        if fs is not None and 0 <= fs <= 3:
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
    r['flat'] = fs is not None and 0 <= fs <= 3 and typ == t
    if finisher:
        finish_while_flat(assets, fighter, who, _DevPath(out), f'{name}-{t}', r)
        for _ in range(30):
            if P.mem('NO_AI_FLAG')['NO_AI_FLAG']==0:break
            P.EMU.wait(.5)
        else:raise RuntimeError('AI stayed locked after the finisher')
    for _ in range(40):                  # end the fight
        P.mset(*[f'{k}=0' for k in P.ENEMY_HP])
        P.seq('wait 6, CONFIRM 4, wait 3, CONFIRM 4, wait 3, CONFIRM 4, wait 3')
        if P.game_state() == 0:
            break
    r['back_in_world'] = P.game_state() == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cue'); ap.add_argument('out')
    ap.add_argument('--partner', type=int, nargs='*', default=[])
    ap.add_argument('--enemy', type=int, nargs='*', default=[])
    ap.add_argument('--card', default='build/states/file-city.mcd')
    ap.add_argument('--technique', action='store_true', help='flatten enemies with the partner\'s Tear Drop')
    ap.add_argument('--battle-partner', type=int, help='evolve this partner before testing flattened enemies')
    ap.add_argument('--opponent', type=int, help='replace the opponent while testing a flattened partner')
    ap.add_argument('--finisher', action='store_true', help='require a finisher to play and damage the flattened fighter')
    ap.add_argument('--assets', type=_DevPath, help='build folder holding DIGI.DAT and ALLTIM.TIM (default: cue stem)')
    a = ap.parse_args()
    assert os.environ.get('EMU_PORT'), 'set EMU_PORT'
    assets = a.assets or _DevPath(a.cue).with_suffix('')
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    results, ok = [], True
    try:
        if not boot(a.cue, a.card):
            raise SystemExit('never reached the world')
        if a.battle_partner is not None:
            P.lab_evolve(a.battle_partner, out)
            assert P.partner_type() == a.battle_partner, 'battle partner evolution failed'
        for kind, ids in (('enemy', a.enemy), ('partner', a.partner)):
            for t in ids:
                r = dict(kind=kind, id=t)
                if kind == 'partner':
                    P.lab_evolve(t, out)
                    r['evolved'] = P.partner_type() == t
                    if P.EMU.has('getFlatSprite'):
                        r['evolution_slot_matches'] = slot_sprite(PARTNER) == expected_sprite(assets, t)
                fight(kind, t, out, r, enemy=t if kind == 'enemy' else None, technique=a.technique and kind == 'enemy',
                      opponent=a.opponent, finisher=a.finisher, assets=assets)
                if P.EMU.has('getFlatSprite'):
                    r['expected_sprite'] = expected_sprite(assets, t)
                    r['slot_matches'] = r['slot_sprite'] == r['expected_sprite']
                r['ok'] = (r['in_battle'] and r['flat'] and r['back_in_world']
                           and r.get('evolved', True) and r.get('enemy_placed', True)
                           and r.get('slot_matches', True) and r.get('evolution_slot_matches', True)
                           and (not a.finisher or (r.get('finisher_played') and r.get('finisher_damage', 0) > 0
                                                 and r.get('flat_during_finisher') and r.get('battle_frames_advanced'))))
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
