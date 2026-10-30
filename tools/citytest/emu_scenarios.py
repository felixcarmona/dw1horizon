#!/usr/bin/env python3
"""Emulator scenarios for the city rules (docs/mods/city-rules.md, "Equivalence"): the original disc and the tier-2 discs run the same
three scenarios in PCSX-Redux and must give the same answers; a tier-2 disc with a modified table must give the changed ones.

    EMU_PORT=38030 tools/citytest/emu_scenarios.py DISC [DISC...]      DISC is one of: orig t2def t2orig t2mod
    tools/citytest/emu_scenarios.py compare                            compares the saved results (build/citytest/emu-*.json)

  prosperity  the game is running (CONTINUE from the card, Jijimon's house); trigger 200 + type is set for a set of species, pstat 3 and the
              tournament triggers are set, and the game's own recalculatePPandArena is called at a frame boundary; then pstat 1 and the
              triggers are read back
  topmap      the 5 triggers of getFileCityTopMap (Angemon, Monzaemon, Birdramon, Vegiemon, Palmon) in all 32 combinations; the game's own
              getFileCityTopMap is called for each and its return value read
  presence    (disc orig or t2def, own command `presence`) the game warps to screens whose MAPHEAD section places NPCs by triggers and by the clock;
              the entities that stand there are read back and compared with `dws`'s reading of the same section (tools/dws/presence.py)
  newgame     NEW GAME with no memory card: initializeDefaultSavegame and loadSavegame run in the game; money, clock, partner, inventory and
              the card shop's first stock are read from RAM (tools/dev/game_state.py dump)

The emulator runs one at a time, on EMU_PORT (default 38030 here), and is stopped after each disc.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import json, os, random, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import symbols as dwsyms  # noqa: E402
from dws import city  # noqa: E402

PORT = os.environ.setdefault('EMU_PORT', '38030')
OUT = os.path.join(ROOT, 'build', 'citytest'); os.makedirs(OUT, exist_ok=True)
DISCS = {'orig': ('Digimon World (USA).cue', 'orig'), 't2def': ('build/city-t2def.cue', 'decomp-tier2'),
         't2orig': ('build/city-t2orig.cue', 'decomp-tier2'), 't2mod': ('build/city-t2mod.cue', 'decomp-tier2'),
         'everything': ('build/everything.cue', 'decomp-int')}       # the series disc of the story mod: patch 0161 counts species 59..111 too
CARD = 'build/states/file-city.mcd'
TOP_T = [220, 214, 221, 225, 246]      # Angemon, Monzaemon, Birdramon, Vegiemon, Palmon


def emu(*a, check=True, timeout=900):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py'), *a], capture_output=True, text=True, cwd=ROOT, timeout=timeout)
    if check and r.returncode: sys.exit(f'emu.py {" ".join(a)} failed: {r.stdout}{r.stderr}')
    return r.stdout.strip()


def start(disc, card=True):
    os.environ['EMU_ARGS'] = '-interpreter -debugger'
    emu('stop', check=False)
    emu('start', os.path.join(ROOT, DISCS[disc][0]), *(['--card', os.path.join(ROOT, CARD)] if card else []))


def lua(code):
    return emu('lua', code)


def wait_control(maxs=240):
    t0 = time.time(); ok = 0
    while time.time() - t0 < maxs:
        v = emu('peek', 'IS_SCRIPT_PAUSED', '4').split()
        ok = ok + 1 if len(v) > 1 and v[1] == '01' else 0
        if ok >= 8: return
        emu('press', 'CROSS', '8'); time.sleep(1.5)
    sys.exit('no free control')


def run_ops(ops, timeout=300):
    """ops: [(symbol or address, a0, a1, record)] -> list of the recorded results"""
    build = DISCS[CURRENT][1]; A = lambda s: dwsyms.resolve(s, build)
    body = ','.join('{%d,%d,%d,%s}' % (A(f) if isinstance(f, str) else f, a0, a1, 'true' if rec else 'false') for f, a0, a1, rec in ops)
    lua('CC.run({%s})' % body)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if lua('return CC.done').strip() in ('true', '1'): break
        time.sleep(0.5)
    else:
        sys.exit('the calls did not finish')
    r = lua('return CC.result()').strip()
    return [int(x) for x in r.split(',')] if r else []


def prosperity_cases():
    rng = random.Random(3)
    sets = [('everyone 3..58', list(range(3, 0x3b))), ('nobody', []), ('Numemon Sukamon Nanimon', [11, 39, 53]),
            ('species 59..111 (not part of the rule)', [60, 70, 90, 111])]
    for k in range(4):
        sets.append((f'random {k + 1}', sorted(rng.sample(range(0, 112), rng.randint(5, 40)))))
    sets.append(('Agumon..Greymon', list(range(3, 12))))
    return sets


def scenario_prosperity():
    ops = []; plan = []
    for name, rec in prosperity_cases():
        for t in range(200, 200 + 0x70): ops.append(('unsetTrigger', t, 0, False))
        for t in (0x25, 0x26, 0x27): ops.append(('setTrigger', t, 0, False))
        for s in rec: ops.append(('setTrigger', 200 + s, 0, False))
        for p3 in (0x16, 0x17):             # below and at the arena threshold (the clean-up of triggers 37-39)
            for t in (0x25, 0x26, 0x27): ops.append(('setTrigger', t, 0, False))
            ops.append(('writePStat', 3, p3, False)); ops.append(('writePStat', 1, 255, False))
            ops.append(('recalculatePPandArena', 0, 0, False))
            ops.append(('readPStat', 1, 0, True))
            ops += [('isTriggerSet', t, 0, True) for t in (0x25, 0x26, 0x27)]
            plan.append((name, rec, p3))
    res = run_ops(ops); out = []
    for i, (name, rec, p3) in enumerate(plan): out.append({'case': f'{name}, p3={p3:#x}', 'recruited': rec, 'p1': res[4 * i], 'arena': res[4 * i + 1:4 * i + 4]})
    return out


def scenario_topmap():
    ops = []
    for m in range(32):
        for k, t in enumerate(TOP_T): ops.append(('setTrigger' if m >> k & 1 else 'unsetTrigger', t, 0, False))
        ops.append(('getFileCityTopMap', 0, 0, True))
    res = run_ops(ops)
    return [{'mask': m, 'screen': res[m]} for m in range(32)]


def scenario_newgame(disc):
    start(disc, card=False)
    emu('seq', 'wait 45, START 20, wait 6, START 20, wait 6')
    emu('seq', 'CROSS 10, wait 4, DOWN 8, wait 1, DOWN 8, wait 1, CROSS 10, wait 6, CROSS 10, wait 3, CROSS 10, wait 3')
    time.sleep(1)
    # SAVE_FILE + 0x200 is saves[0] (SaveFile header: id, icon flags, title, reserved, pocketstation, clut, 3 icon frames = 0x200), 0xF00 bytes
    base = dwsyms.resolve('SAVE_FILE', DISCS[disc][1]) + 0x200
    raw = emu('peek', hex(base), str(0xF00))
    hexs = ''.join(w for line in raw.splitlines() for w in line.split()[1:])
    blob = bytes.fromhex(hexs)
    emu('shot', os.path.join(OUT, f'newgame-{disc}.png'))
    emu('stop')
    return blob


def ram_peek(sym_or_addr, n):
    raw = emu('peek', sym_or_addr, str(n))
    return bytes.fromhex(''.join(w for line in raw.splitlines() for w in line.split()[1:]))


def gs(*a):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/game_state.py'), *a], capture_output=True, text=True, cwd=ROOT)
    return r.stdout


def scenario_presence(disc):
    """the same MAPHEAD sections in the real engine and in the reading of tools/dws/presence.py"""
    from dws import presence as PR
    global CURRENT
    CURRENT = disc
    start(disc)
    emu('seq', 'wait 45, START 20, wait 6, START 20, wait 6')
    emu('seq', 'DOWN 8, wait 1, CROSS 10, wait 5, CROSS 10, wait 5, CROSS 10, wait 4, CROSS 10, wait 12')
    wait_control()
    cases = [(205, [], 9), (205, [220], 9), (206, [], 9), (206, [214], 9), (206, [88], 9), (204, [], 9), (204, [54], 9), (204, [55], 9),
             (218, [], 9), (218, [], 23), (218, [], 3), (0, [], 9), (0, [], 23), (2, [], 9), (2, [246], 9)]
    watch = sorted({t for _, ts, _ in cases for t in ts} | {54, 55, 88, 50, 214, 220})
    res = []
    for scr, trig, hour in cases:
        for tn in watch: gs('trigger', str(tn), '1' if tn in trig else '0')
        gs('set', f'hour={hour}', 'minute=10')
        time.sleep(1)
        dump = json.loads(gs('dump'))
        bits = dump['script']['triggers']; trigs = {n for n in range(800) if bits[n // 8] >> (n % 8) & 1}
        pst = {i: v for i, v in enumerate(dump['script']['pstats'])}
        st = PR.Concrete(triggers=trigs, pstats=pst, clock=(dump['year'], dump['day'], dump['hour'], dump['minute']))
        want = {slot: sp for slot, (sp, _) in PR.run_original(scr, st)[0].items()}
        gs('warp', str(scr), '0')
        t0 = time.time()
        while time.time() - t0 < 90:
            time.sleep(2)
            cur = ram_peek('CURRENT_SCREEN', 1)[0]; paused = int.from_bytes(ram_peek('IS_SCRIPT_PAUSED', 4), 'little')
            if cur == scr and paused == 1: break
        time.sleep(3)
        ent = dwsyms.resolve('ENTITY_TABLE', DISCS[disc][1])
        tab = ram_peek(hex(ent), 4 * 18 if DISCS[disc][1] != 'orig' else 4 * 10)
        got = {}
        for k in range(2, len(tab) // 4):
            ptr = int.from_bytes(tab[4 * k:4 * k + 4], 'little')
            if 0x80000000 < ptr < 0x80200000:
                ty = int.from_bytes(ram_peek(hex(ptr), 4), 'little', signed=True)
                if ty > 0: got[k - 2] = ty
        # the game only places a Digimon whose type is in the .MAP's slot, so the engine may place fewer than the section asks for: report both
        res.append({'screen': scr, 'triggers': sorted(trig), 'hour': hour, 'engine': got, 'dws': want})
        print(f'  screen {scr} triggers {trig} hour {hour}: engine {got}  dws {want}', flush=True)
    emu('stop')
    json.dump(res, open(os.path.join(OUT, f'presence-{disc}.json'), 'w'), indent=1)
    bad = [r for r in res if r['engine'] != r['dws']]
    print(f'presence on {disc}: {len(res)} warps, {len(bad)} differ')
    return 1 if bad else 0


CURRENT = None


def run_disc(disc):
    global CURRENT
    CURRENT = disc
    res = {'disc': disc}
    blob = scenario_newgame(disc)
    open(os.path.join(OUT, f'newgame-{disc}.bin'), 'wb').write(blob)
    res['newgame'] = blob.hex()
    start(disc)
    emu('seq', 'wait 45, START 20, wait 6, START 20, wait 6')
    emu('seq', 'DOWN 8, wait 1, CROSS 10, wait 5, CROSS 10, wait 5, CROSS 10, wait 4, CROSS 10, wait 12')
    wait_control()
    gl = dwsyms.resolve('gameLoop', DISCS[disc][1])
    lua("dofile('%s')" % os.path.join(ROOT, 'tools/citytest/emu_call.lua')); lua('return CC.install(%d)' % gl)
    time.sleep(1)
    res['screen'] = emu('peek', 'CURRENT_SCREEN', '1')
    res['prosperity'] = scenario_prosperity()
    res['topmap'] = scenario_topmap()
    emu('stop')
    json.dump(res, open(os.path.join(OUT, f'emu-{disc}.json'), 'w'), indent=1)
    print(f'{disc}: {len(res["prosperity"])} prosperity cases, 32 top-map states, new game: save slot of {len(blob)} bytes -> build/citytest/emu-{disc}.json')


def expected(disc):
    from dws import citycli
    base = city.extract_original()
    if disc == 't2mod':
        spec = dict(base); spec.update(citycli.load_spec(os.path.join(ROOT, 'tools/dws/examples/expanded-city-rules.dws')))
    elif disc == 'everything':                 # patch 0161: the 3..58 row of the original rule runs to the last recruit flag (111)
        spec = dict(base); spec['prosperity'] = [dict(r, last=111) if r['last'] == 58 else r for r in base['prosperity']]
    else: spec = base
    return spec


def compare():
    res = {}
    for d in DISCS:
        p = os.path.join(OUT, f'emu-{d}.json')
        if os.path.exists(p): res[d] = json.load(open(p))
    if 'orig' not in res: sys.exit('run the original disc first')
    bad = 0
    for d, r in res.items():
        spec = expected(d)
        # against the reference evaluator (what the declaration says)
        for c in r['prosperity']:
            st = city.State(triggers={200 + s for s in c['recruited']})
            want = city.prosperity_of(spec['prosperity'], st)
            p3 = int(c['case'].split('p3=')[1], 16)
            # p3 >= 0x17: the tournament clean-up (kept in C) clears triggers 37-39; below it the game's own per-frame code may touch trigger 37
            # (cup registration), so only the equality with the original disc is asked there (below)
            arena_ok = c['arena'] == [0, 0, 0] if p3 >= 0x17 else True
            if c['p1'] != want or not arena_ok: bad += 1; print(f'{d}: {c["case"]}: p1 {c["p1"]} (expected {want}), arena {c["arena"]}')
        for c in r['topmap']:
            st = city.State(triggers={t for k, t in enumerate(TOP_T) if c['mask'] >> k & 1})
            want = city.top_map_of(spec['top_map'], st)
            if c['screen'] != want: bad += 1; print(f'{d}: top map mask {c["mask"]:05b}: {c["screen"]} (expected {want})')
    for d in res:
        if d in ('orig', 'everything'): continue      # everything differs from the original by design (species 59..111 count): judged above only
        ng = lambda x: bytes.fromhex(x['newgame'])[:0x4E1] + bytes.fromhex(x['newgame'])[0x500:]   # not 0x4E1-0x4FF: the save-version stamp and checksum of the tier-2 layout
        ngd = [i for i, (x, y) in enumerate(zip(ng(res[d]), ng(res['orig']))) if x != y]
        same = (res[d]['prosperity'] == res['orig']['prosperity'] and res[d]['topmap'] == res['orig']['topmap'] and not ngd)
        print(f'{d} vs orig: prosperity {"=" if res[d]["prosperity"] == res["orig"]["prosperity"] else "differs"}, top map {"=" if res[d]["topmap"] == res["orig"]["topmap"] else "differs"}, '
              f'new game {"= (3 809 of 3 840 bytes of the start save slot; not the version stamp and checksum)" if not ngd else f"differs in {len(ngd)} bytes"}' + ('  (expected: it is the modified table)' if d == 't2mod' else ''))
        if d != 't2mod' and not same: bad += 1
    if 't2mod' in res and res['t2mod']['prosperity'] == res['orig']['prosperity']: bad += 1; print('t2mod: the modified table changed nothing')
    print('EMULATOR EVIDENCE OK' if not bad else f'{bad} problems')
    return 1 if bad else 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['compare']: sys.exit(compare())
    if args and args[0] == 'presence': sys.exit(max(scenario_presence(d) for d in (args[1:] or ['orig'])))
    for d in args:
        if d not in DISCS: sys.exit(f'unknown disc {d}')
        run_disc(d)
