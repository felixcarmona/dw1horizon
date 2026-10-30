#!/usr/bin/env python3
"""The story route past C18 : the main story from a REAL new game, walked through the doors and the tile triggers, with the forced battles fought.
Docs: docs/developing.md, "The route (C19 on)". It continues tools/dws/testing/checkpoints.py (C1-C18: warps to the screens, kept as they were).

  tools/dws/testing/route.py plan                              the segments
  tools/dws/testing/route.py run [--disc orig] [--only ID,ID] [--redo]
                                                  the traced segments on the ORIGINAL disc, each from the saved state of the one before (build/checkpoints/r-*.state);
                                                  stops at the first segment that is blocked (hang, timeout, a check that fails)
  tools/dws/testing/route.py compare --disc readable [--port N] [--follow] [--only ID,ID]
                                                  the same segments on another disc from the ORIGINAL's saved states; `--follow` waits for segments the original
                                                  has not run yet (so the comparison can run beside the original's chain, on its own port)
  tools/dws/testing/route.py table                             docs/data/story-analysis/checkpoints.csv: the old rows stay, the rows of this route are added

How a segment is built (what the real route does that a warp does not):
  * the doors are walked: `exit E` puts the tamer on the exit tiles of the map grid (value 110+E) and the engine takes the exit, `tile V` steps on the tile of a
    section that runs when stepped on (51-79), `npc SID` walks up to the NPC whose script id is SID and `talk until` reads what it says (docs/reference/world.md);
  * the story state that the route would have made on the way (the recruits, the prosperity, the items that long walks and minigames give) is written by `pre` steps
    before the trace starts, from what the scripts' own conditions ask (`dws.py why`, docs/data/story-analysis/quest-chain.md); a recruit is `T(200+species)` and the
    prosperity that its script adds (`PROSPERITY_GAIN`);
  * a battle that a script forces is fought in the emulator (tools/dev/story_trace.lua, `S.battle`): the generators are pinned when it starts, at a fixed battle frame the enemies'
    HP is set to 0 (`win`) or the partner's (`lose`), the results screens are pressed through, and the script goes on with the result in p255.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import argparse, csv, json, os, sys, time


def _early_port():
    for i, a in enumerate(sys.argv):
        if a == '--port' and i + 1 < len(sys.argv): os.environ['EMU_PORT'] = sys.argv[i + 1]


_early_port()
os.environ.setdefault('EMU_PORT', '38020')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from dws.testing import checkpoints as C
W = C.W; T = C.T
CK = C.CK
BATTLE_AFTER = 90                  # the battle frame at which the fight is ended (win: every enemy's HP to 0; lose: the partner's HP to 0)

# ---------------------------------------------------------------------------------------------------
# state helpers: what the route has done on the way, written before the trace

# p1 (prosperity) that the recruit's script adds (scanned: SET_TRIGGER 200+species followed by ADD_TO_PSTAT p1)
PROSPERITY_GAIN = {3: 1, 4: 1, 5: 2, 6: 7, 7: 7, 8: 2, 9: 2, 10: 2, 11: 1, 12: 7, 14: 3, 17: 1, 18: 1, 19: 2, 20: 2, 21: 2, 22: 2, 23: 2, 24: 2, 25: 2, 26: 3, 27: 3, 28: 3, 31: 1, 32: 1, 33: 2,
      34: 2, 35: 2, 36: 2, 37: 2, 38: 2, 39: 1, 40: 3, 41: 3, 42: 3, 45: 1, 46: 1, 48: 2, 49: 2, 50: 2, 51: 2, 52: 2, 54: 3, 55: 3, 56: 3, 57: 1, 58: 2}


def recruit(*species, p1=None):
    """Steps that leave the state of a player that has recruited these species (the triggers 200+id the scripts read, and the prosperity they add; `p1` overrides)."""
    st = [f'trigger {200 + s} 1' for s in species]
    st.append(f'pstat 1 {p1 if p1 is not None else min(255, sum(PROSPERITY_GAIN.get(s, 0) for s in species))}')
    return st


def battle_extra(mode='win', after=BATTLE_AFTER):
    pk = [[p['a'], p['hex']] for p in W.seed_pokes()]
    return dict(battle=dict(mode=mode, after=after, finished=0x80057920 & 0x1FFFFF, game_state=T.phys('GAME_STATE'), partner=T.phys('PARTNER_ENTITY'),
                            combat_ptr=T.phys('COMBAT_DATA_PTR'), enemy_count=T.phys('ENEMY_COUNT'), entity_table=T.phys('ENTITY_TABLE'), rng=pk))


# ---------------------------------------------------------------------------------------------------
# the route

ROUTE = []


def seg(id, doc, steps, start=None, pre=(), battle=None, check=(), frames=14000, slug=None, replaces='', hang_after=30, expect=None):
    """`expect='hang'`: the segment is expected to end with the game loop stopped (the ending's movie and the title screen): that end is not a block, and no state is saved."""
    ROUTE.append(dict(id=id, doc=doc, steps=list(steps), start=start, pre=list(pre), battle=battle, check=list(check), frames=frames, slug=slug or id.lower(),
                      replaces=replaces, hang_after=hang_after, expect=expect))


def go(screen, exit_=None, wait=60):
    """Take a door and wait until the next screen is loaded and the tamer is free."""
    st = [f'exit {exit_}'] if exit_ is not None else []
    return st + [f'talk until CURRENT_SCREEN=={screen} and free max 4000', f'wait {wait}']


def talk_npc(sid, dist=180, wait=20):
    """Walk up to the NPC with script id `sid`, press X until its script runs, read it to the end."""
    return [f'npc {sid} {dist}', f'wait {wait}', 'until running press CROSS 3 every 40 max 300', 'talk until free max 4000', 'wait 30']




seg('C19', 'out of Jijimon\'s house, through File City and the Green Gym to the Native Forest; the Agumon there is fought (forced battle, script 105 section 6) and joins the city',
    ['tile 51', 'talk until CURRENT_SCREEN==204 and free max 4000', 'wait 60'] + go(112, 1) + go(109, 0) + talk_npc(6),
    start='c4-jijimon-talk', battle='win', check=[('trigger', 203, 1), ('pstat', 1, '>=', 1)], frames=9000)

seg('C20', 'the way back to the city: the Native Forest exit tile (script 105 section 51) takes the tamer to the lower File City with Agumon recruited',
    ['tile 51', 'talk until CURRENT_SCREEN==180 and free max 4000', 'wait 120'], check=[('screen', 180), ('trigger', 203, 1)])

RECRUITS_A = recruit(4, 31, 32, 45, 46, p1=6)          # Betamon, Patamon, Kunemon, Biyomon, Palmon (+ Agumon): the city has 6 residents' worth of prosperity

seg('C21', 'the first recruits are in the city (Betamon, Patamon, Kunemon, Biyomon, Palmon: triggers and prosperity 6); the lower city\'s door to the upper city (163:52) picks the layout; the rumor-monger (162:5) tells of the invisible bridge (T124)',
    ['tile 52', 'talk until CURRENT_SCREEN!=180 and free max 4000', 'wait 120'] + talk_npc(5), pre=RECRUITS_A, check=[('trigger', 124, 1), ('pstat', 1, '>=', 6)])


def tile_scene(v, cond, mx=6000):
    """Step on the tile of section V and read its scene until COND (a trigger or a pstat the scene sets). Not `free`: a section run by a tile that does not change the screen
    runs again on every frame while the tamer stands on the tile (it ends at once once its flag is set), so the tamer is never free there; the segment then walks off."""
    return [f'tile {v}', 'until running max 300', f'talk until {cond} max {mx}']


seg('C22', 'the Great Canyon Entrance (screen 36; the walk there from the city is a warp, not walked): the tile of section 36:53 by the gap, with T124 the tamer sees the invisible bridge (T103)',
    ['warp 36 0', 'talk until CURRENT_SCREEN==36 and free max 4000', 'wait 60'] + tile_scene(53, 'trigger 103') + ['wait 30'],
    check=[('trigger', 103, 1), ('screen', 36)])

seg('C23', 'back in the upper File City (screen 169, a warp): the rumor-monger (162:5) with T103 sends the tamer to the bandits (T197)',
    ['warp 169 0', 'talk until CURRENT_SCREEN==169 and free max 4000', 'wait 60'] + talk_npc(5), check=[('trigger', 197, 1)])

seg('C24', 'the bandit ambush: Great Canyon Top Area (screen 43, a warp), the tile of section 43:51 with T197: the forced battle against the three bandits (START_BATTLE with 3 foes, HP 3600/900/900), won; '
    'T198 and T155 set; the tamer walks out by exit 1 to screen 38',
    ['warp 43 0', 'talk until CURRENT_SCREEN==43 and free max 4000', 'wait 60'] + tile_scene(51, 'trigger 198 and trigger 155', 9000) + go(38, 1),
    battle='win', check=[('trigger', 198, 1), ('trigger', 155, 1), ('screen', 38)], frames=9000)

seg('C25', 'down to the Fortress Entrance on foot: the elevator of screen 38 (tile 82, "Press DOWN": with T155 it goes down, 38:82) to the Great Canyon Bottom (41), exit 0 to the Fortress Entrance (40); '
    'the Agumon at the gate (40:5) with T198 and not T199 lets the tamer in: T200, the script warps to the Ogre Fortress (45)',
    ['tile 82', 'until running press CROSS 3 every 40 max 300', 'until ACTIVE_INSTRUCTION==0x10 press CROSS 3 every 30 max 900', 'wait 30', 'press DOWN 3', 'wait 20', 'press CROSS 3',
     'talk until CURRENT_SCREEN==41 and free max 4000', 'wait 60'] + go(40, 0) + ['move -320 -1800', 'wait 5', 'npc 5 180', 'camera', 'wait 30',
     'until running press CROSS 3 every 40 max 300', 'talk until CURRENT_SCREEN==45 and free max 6000', 'wait 60'],
    check=[('trigger', 200, 1), ('screen', 45)], frames=9000)

seg('C26', 'the Ogre Fortress: through 45, 46, 47 to 48 by the doors (the wild Gabumon that charge on the way are fought and won), the tile of 48:52: Ogremon and two Agumon (forced battle, 3 foes), won: '
    'T176, T175; the elevator tile 48:51 ("go up", the first choice) takes the tamer to the Great Canyon Top Area (37)',
    ['door 1 46', 'wait 60', 'door 1 47', 'wait 60', 'door 1 48', 'wait 60'] + tile_scene(52, 'trigger 175', 9000) + ['tile 51', 'talk until CURRENT_SCREEN==37 and free max 4000', 'wait 60'],
    battle='win', check=[('trigger', 175, 1), ('trigger', 176, 1), ('screen', 37)], frames=14000)

def evolve(species):
    """Steps that evolve the partner into SPECIES the way the game does (EVOLUTION_TARGET, the partner's state 13 and the tamer's 6: the evolution scene plays; its
    two boxes are pressed through). The route's partner grows as a player's would; Jijimon's 210:51 only speaks of the story to a partner that is not a baby or a rookie."""
    return [f'poke EVOLUTION_TARGET {species:02x}00', 'poke PARTNER_SUB_STATE 00', 'poke PARTNER_STATE 0d', 'poke TAMER_SUB_STATE 00', 'poke TAMER_STATE 06',
            'wait 40', 'press CROSS 4', 'wait 3', 'press CROSS 4', 'wait 3', 'talk until free max 3000', 'wait 30']


# more recruits on the way (Whamon, Ogremon, Gabumon, Elecmon, Kokatorimon, Bakemon: none of them changes the upper city's layout): prosperity 16
RECRUITS_B = recruit(24, 34, 17, 18, 50, 37, p1=16)

seg('C27', 'Greymon: the partner has grown into Greymon (evolution, as a player\'s would) and the city has 16 of prosperity; Jijimon in his house (218, talk: 178:5 -> 210:51) with p1 >= 15 sets T87; '
    'out by his door (178:51) to the upper File City (169); the tile of 162:57 by the falls: Greymon comes down (forced battle, 1 foe), won: T205, p1+2',
    ['warp 218 0', 'talk until CURRENT_SCREEN==218 and free max 4000', 'wait 60'] + talk_npc(5) + ['tile 51', 'talk until CURRENT_SCREEN==169 and free max 4000', 'wait 60']
    + tile_scene(57, 'trigger 205', 9000) + ['wait 30'],
    pre=RECRUITS_B + evolve(5), battle='win', check=[('trigger', 205, 1), ('pstat', 1, '>=', 18), ('screen', 169)], frames=14000)

# the rest of the recruits a player has by then (none of the upper city's five layout triggers): prosperity 51 (+2 of Greymon = 53 would be over; the scripts ask >= 50)
RECRUITS_C = recruit(9, 10, 19, 22, 23, 26, 27, 28, 33, 35, 36, 38, 40, 41, p1=51)

seg('C28', 'Mt. Infinity opens: with T205 and 51 of prosperity Jijimon (210:51) says its entrance appeared (T354); out by his door to the upper city (with p1 >= 50 the layout is 175), where with T354 the tamer is walked (162:58/59) onto '
    'the tile of 162:57: Airdramon (forced battle, 1 foe), won: T88, T355, the scene of 206 (Jijimon\'s house) and back to 175; the tile of 162:56 behind the falls: Mt. Infinity (166)',
    ['warp 218 0', 'talk until CURRENT_SCREEN==218 and free max 4000', 'wait 60'] + talk_npc(5) + ['tile 51', 'talk until trigger 88 max 9000', 'talk until CURRENT_SCREEN==206 max 3000', 'talk until CURRENT_SCREEN==175 max 4000', 'wait 120',
     'tile 56', 'talk until CURRENT_SCREEN==166 and free max 4000', 'wait 60'],
    pre=RECRUITS_C, battle='win', check=[('trigger', 88, 1), ('trigger', 355, 1), ('trigger', 354, 1), ('screen', 166)], frames=14000)

# The partner that climbs Mt. Infinity: the route's Greymon left the Airdramon fight with 122 HP of 1417, and a wild pair charges at the first screen of the mountain
# (with that HP the battle is lost and the partner fades away: 212:71-73, the tamer wakes in Jijimon's house). A player there has a trained and healed partner:
# off/def/speed/brain 400, HP and MP 3000, full (PARTNER_ENTITY+0x38: the stats block).
TRAINED = ['poke PARTNER_ENTITY+56 9001900190019001', 'poke PARTNER_ENTITY+72 b80bb80bb80bb80b']
CLIMB = [(51, 167), (52, 210), (51, 212), (51, 219), (51, 247), (51, 248), (51, 249), (51, 253), (51, 254)]


def choose_second():
    """A scene that asks (SET_SELECTION, instruction 0x10): its boxes are read until the choice is open, the second answer is taken."""
    return ['until ACTIVE_INSTRUCTION==0x10 press CROSS 3 every 30 max 900', 'wait 30', 'press DOWN 3', 'wait 20', 'press CROSS 3']


seg('C29', 'the climb of Mt. Infinity: 166, 167, 210, 212, 219, 247, 248, 249, 253 to 254 through the tiles of their sections 51/52 (each warps to the next screen); the partner trained and healed; '
    'the wild Digimon that charge on the way are fought and won',
    sum(([f'doortile {v} {sc}', 'wait 30'] for v, sc in CLIMB), []) + ['wait 30'],
    pre=TRAINED, battle='win', check=[('screen', 254)], frames=20000)

seg('C30', 'Megadramon (254, the tile of 198:53): the tamer answers that he will fight (the second answer), forced battle, 1 foe, won: T254, p1+3',
    tile_scene(53, 'running', 300)[:2] + choose_second() + ['talk until trigger 254 max 9000', 'wait 30'],
    battle='win', check=[('trigger', 254, 1), ('pstat', 1, '>=', 54), ('screen', 254)], frames=12000)

seg('C31', 'MetalGreymon: the tile of 198:51 to 222; the tile of 182:53: forced battle, 1 foe, won: T326',
    ['doortile 51 222', 'wait 30'] + tile_scene(53, 'trigger 326', 9000) + ['wait 30'],
    battle='win', check=[('trigger', 326, 1), ('screen', 222)], frames=12000)

seg('C32', 'the summit: the tile of 182:52 to 225; the tile of 184:51: Machinedramon (forced battle, 1 foe), won: T50 (the game is beaten), T206, T207, T212, p1+7; the script warps to 237',
    ['tile 52', 'talk until CURRENT_SCREEN==225 and free max 4000', 'wait 60'] + tile_scene(51, 'trigger 50', 15000) + ['talk until CURRENT_SCREEN==237 max 6000', 'wait 120'],
    battle='win', check=[('trigger', 50, 1), ('trigger', 206, 1), ('trigger', 207, 1), ('trigger', 212, 1), ('screen', 237)], frames=24000)

seg('C33', 'the ending (237, 192:51, run by the warp): Jijimon\'s farewell (routine 52) and the scene of the city read with X; the script\'s routines 54 and 53 play the ending; '
    'the game loop stops there (the ending movie, then the title screen, seen on the original: no game loop for 60 s ends the segment, an expected end)',
    ['until CURRENT_SCREEN!=237 press CROSS 3 every 30 max 12000', 'until? CURRENT_SCREEN==3 press CROSS 3 every 30 max 3000'],
    frames=16000, hang_after=60, expect='hang')

# ---------------------------------------------------------------------------------------------------
# running

def rows_path(disc): return os.path.join(CK, f'rows2.{disc}.json')


def load_rows(disc):
    try: return json.load(open(rows_path(disc)))
    except (OSError, ValueError): return {}


def save_rows(disc, rows):
    tmp = rows_path(disc) + f'.part{os.getpid()}'; json.dump(rows, open(tmp, 'w'), indent=1); os.replace(tmp, rows_path(disc))


def spath(name): return os.path.join(CK, name + '.state')


def end_name(s): return f'r-{s["slug"]}'


def start_of(seg_, prev_end):
    return seg_['start'] or prev_end


def steps_of(s):
    st = [T.parse_step('clock 9 12')] + [T.parse_step(x) for x in s['pre']] + [dict(t='trace', on=True)] + W.seed_pokes()
    st += [T.parse_step(x) for x in s['steps']] + [dict(t='mark', name='final'), dict(t='end')]
    return [x for z in st for x in (z['steps'] if z['t'] == 'multi' else [z])]


def peek_state():
    """The story state of the paused emulator: triggers set, pstats, screen."""
    trig = T.peek(T.phys('SCRIPT_STATE+245'), 100); ps = T.peek(T.phys('SCRIPT_STATE+345'), 256)
    return dict(triggers=[n for n in range(800) if n // 8 < len(trig) and trig[n // 8] >> (n % 8) & 1], pstats={i: v for i, v in enumerate(ps) if v},
                screen=T.peek(T.phys('CURRENT_SCREEN'), 1)[0])


def check_ok(st, conds):
    out = []
    for c in conds:
        k = c[0]
        if k == 'trigger': ok = (c[1] in st['triggers']) == bool(c[2])
        elif k == 'pstat':
            v = st['pstats'].get(c[1], 0); op = c[2]; ok = {'==': v == c[3], '>=': v >= c[3], '<=': v <= c[3], '!=': v != c[3]}[op]
        elif k == 'screen': ok = st['screen'] == c[1]
        else: ok = False
        out.append(ok)
    return out


def run_segment(R, s, start, out, save=None):
    t0 = time.time(); extra = battle_extra(s['battle'] or 'win')
    text = R.run(steps_of(s), start, out, max_frames=s['frames'], idle_frames=None, max_ins=400000, save_state=save, stop_on_battle=False, hang_after=s['hang_after'], extra=extra)
    ev, row = W.analyse(text, R.sc)
    row['secs'] = round(time.time() - t0); row['hang_at'] = R.hang_at
    row['battles'] = [e['key'] for e in ev if e['kind'] == 'Y' and ' battle ' in e['key']]
    return ev, row


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def selected(a):
    ids = set(a.only.split(',')) if getattr(a, 'only', None) else None
    return [s for s in ROUTE if ids is None or s['id'] in ids]


def cmd_run(a):
    R = W.Runner(a.disc); rows = load_rows(a.disc); prev = None
    for s in ROUTE:
        name = end_name(s); start = start_of(s, prev)
        if getattr(a, 'only', None) and s['id'] not in a.only.split(','): prev = (rows.get(s['id']) or {}).get('state') or prev; continue
        if s['id'] in rows and rows[s['id']].get('state') and os.path.exists(spath(rows[s['id']]['state'])) and not a.redo:
            prev = rows[s['id']]['state']; continue
        out = os.path.join(CK, f'{s["id"]}.{a.disc}.trace')
        ev, row = run_segment(R, s, spath(start), out, save=spath(name) if a.disc == 'orig' else None)
        row['start'] = start; why = ''
        if row['end'] in ('end', 'steps_done'):
            st = peek_state() if C.W.emu_alive() else None
            if st is not None and s['check']:
                res = check_ok(st, s['check']); row['checks'] = res
                if not all(res): why = 'a check failed: ' + ', '.join(str(c) for c, r in zip(s['check'], res) if not r)
            row['state'] = name if not why else None
            if st: row['story'] = dict(triggers=[t for t in st['triggers']], p1=st['pstats'].get(1, 0), screen=st['screen'])
        elif row['end'] == s.get('expect'):
            row['state'] = None; row['expected_end'] = True
        else:
            row['state'] = None
            why = {'hang': 'the game hangs', 'timeout': 'the segment timed out'}.get(row['end'], 'the segment ended ' + row['end'])
        if why:
            try: os.remove(spath(name))          # a blocked segment leaves no state
            except OSError: pass
        row['blocked'] = why; row['battle'] = s['battle']
        rows[s['id']] = row; save_rows(a.disc, rows)
        log(f'{s["id"]} on {a.disc}: {row["n"]} ins, {row["frames"]} frames, ends {row["end"]}, {row["secs"]} s, digest {row["digest"][:10]}, battles {len(row["battles"])}' + (f'  BLOCKED: {why} ({row["hang_at"]})' if why else ''))
        if why: break
        prev = row['state']
    open(os.path.join(CK, 'route.done'), 'w').write(time.strftime('%F %T'))
    W.stop_emulator()


def cmd_compare(a):
    R = W.Runner(a.disc); base = load_rows('orig'); res = load_rows(a.disc); bad = 0
    W.trace_path = lambda cid, disc: os.path.join(CK, f'{cid}.{disc}.trace')
    todo = [s['id'] for s in selected(a)]
    while todo:
        progressed = False
        for sid in list(todo):
            s = next(x for x in ROUTE if x['id'] == sid)
            if sid in res and not a.redo: todo.remove(sid); continue
            o = base.get(sid)
            if o is None:
                continue
            if not o.get('start') or not os.path.exists(spath(o['start'])): continue
            if o.get('blocked') and o['end'] not in ('hang', 'timeout'): todo.remove(sid); continue
            out = os.path.join(CK, f'{sid}.{a.disc}.trace')
            ev, row = run_segment(R, s, spath(o['start']), out)
            oo = dict(o, disc='orig', case=sid, reached=True); rr = dict(row, disc=a.disc, case=sid, reached=True)
            if o['end'] in ('hang', 'timeout') or row['end'] in ('hang', 'timeout'):
                eo = W.T.parse_trace(open(os.path.join(CK, f'{sid}.orig.trace')).read(), W.scripts_of('orig'))
                v = 'same' if o['digest'] == row['digest'] else 'relaxed' if W.relaxed_digest(eo) == W.relaxed_digest(ev) and o['end'] == row['end'] else 'DIFF'
            else: v = W.compare(oo, rr)
            bad += v not in ('same', 'relaxed'); row['compare'] = v; row['strict'] = 'same' if o['digest'] == row['digest'] else 'differs'
            res[sid] = row; save_rows(a.disc, res); todo.remove(sid); progressed = True
            log(f'{sid:6} orig {o["n"]:5} ins {o["frames"]} fr | {a.disc} {row["n"]:5} ins {row["frames"]} fr | strict {row["strict"]} | normalized {v}')
        if todo and not progressed:
            if not a.follow or os.path.exists(os.path.join(CK, 'route.done')) and all(x not in base for x in todo): break
            if os.path.exists(os.path.join(CK, 'route.done')) and all((base.get(x) is None) for x in todo): break
            time.sleep(15)
    W.stop_emulator(); sys.exit(1 if bad else 0)


def cmd_plan(a):
    prev = None
    for s in ROUTE:
        print(f'{s["id"]:6} {s["doc"]}  [{len(s["steps"])} steps, battle {s["battle"] or "-"}, pre {len(s["pre"])}] start {start_of(s, prev)}')
        prev = end_name(s)


def cmd_table(a):
    path = os.path.join(ROOT, 'build/story-analysis/checkpoints.csv')
    ids = {x['id'] for x in ROUTE}; old = list(csv.DictReader(open(path, newline=''))) if os.path.exists(path) else []; keep = [r for r in old if r['checkpoint'] not in ids]
    cols = ['checkpoint', 'description', 'frames', 'instructions', 'orig', 'readable', 'reorder', 'mut1', 'battle', 'story_state']
    rows = {d: load_rows(d) for d in ('orig', 'readable', 'reorder', 'mut1')}; new = []
    for s in ROUTE:
        o = rows['orig'].get(s['id'])
        if o is None: new.append(dict(checkpoint=s['id'], description=s['doc'], orig='not reached')); continue
        d = dict(checkpoint=s['id'], description=s['doc'], frames=o['frames'], instructions=o['n'], orig=('blocked: ' + o['blocked']) if o.get('blocked') else f'ends {o["end"]}' + (' (expected: the ending movie)' if o.get('expected_end') else ''),
                 battle=(s['battle'] + (' (%d)' % len(o['battles']) if o.get('battles') else ' (none started)')) if s['battle'] else ('forced battle fought' if o.get('battles') else ''),
                 story_state=('p1=%s; triggers %s' % (o['story']['p1'], ','.join(map(str, o['story']['triggers']))) if o.get('story') else ''))
        for disc in ('readable', 'reorder', 'mut1'):
            r = rows[disc].get(s['id']); d[disc] = '' if r is None else f'strict {r["strict"]}, normalized {r["compare"]}'
        new.append(d)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in keep + new: w.writerow({k: r.get(k, '') for k in cols})
    print(path, len(keep), '+', len(new))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('plan').set_defaults(f=cmd_plan); sub.add_parser('table').set_defaults(f=cmd_table)
    p = sub.add_parser('run'); p.add_argument('--disc', default='orig'); p.add_argument('--only'); p.add_argument('--redo', action='store_true'); p.add_argument('--port'); p.set_defaults(f=cmd_run)
    p = sub.add_parser('compare'); p.add_argument('--disc', required=True); p.add_argument('--only'); p.add_argument('--follow', action='store_true'); p.add_argument('--redo', action='store_true'); p.add_argument('--port'); p.set_defaults(f=cmd_compare)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
