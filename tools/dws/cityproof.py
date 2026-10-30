"""`dws city-verify` and `dws why` (docs/mods/city-rules.md)."""
import os, random, sys
from . import city, presence as PR, build as B
from .diag import DwsError

DEFAULT = os.path.join(B.ROOT, 'story', 'base', 'city', 'city.dws')


# ------------------------------------------------------------------ city-verify
def verify(spec):
    """The declaration against the original: (1) the rules equal what `city-extract` reads from the original C, (2) every NPC rule equals the
    original MAPHEAD instructions on a grid of states. The C reader against the C original is tools/dws/testing/city_equivalence.py (it needs gcc)."""
    bad = 0
    orig = city.extract_original()
    for blk in city.BLOCKS:
        if blk not in spec:
            print(f'{blk}: not declared (the engine uses its built-in default, which is the original)'); continue
        same = city.decode(city.encode({blk: spec[blk]}))[blk] == city.decode(city.encode({blk: orig[blk]}))[blk]
        print(f'{blk}: {"same as the original" if same else "DIFFERS from the original (a modded rule)"}')
        bad += 0 if same else 0
    pres = spec.get('presence')
    if pres:
        rng = random.Random(1); tot = 0; ex = 0
        for sid, sc in sorted(pres.items()):
            n, full, mm = PR.verify_screen(sid, sc, rng); tot += n; ex += full
            if mm:
                bad += 1; st, want, got = mm
                print(f'presence: screen {sid} MISMATCH on triggers {sorted(st.triggers)} pstats {st.p} clock {st.clock} rolls {st.rolls[:3]}: original {want}, declaration {got}')
        print(f'presence: {len(pres)} screens, {tot} states compared with the original MAPHEAD instructions ({ex} screens exhaustively), '
              f'{"all equal" if not bad else str(bad) + " mismatches"}')
    return 1 if bad else 0


# ------------------------------------------------------------------ why
def state_from_args(a):
    from . import backend
    sp = backend.names()['species']
    trig = set(a.trigger)
    for r in a.recruit:
        s = int(r) if r.isdigit() else sp.get(r.lower())
        if s is None: raise DwsError(f'unknown species "{r}"')
        trig.add(200 + s)
    ps = {}
    for x in a.pstat:
        k, v = x.split('='); ps[int(k)] = int(v)
    rolls = [0] * 12
    for x in a.random:
        k, v = x.split('='); rolls[int(k) - 1] = int(v)
    return PR.Concrete(triggers=trig, pstats=ps, clock=(0, a.day, a.hour, 0), rolls=rolls)


def explain_atom(c, st):
    v = PR.holds(c, st)
    if c[0] == 'trig':
        return v, f'{PR.atom_text(c)} ({"set" if v else "not set"})'
    return v, f'{PR.atom_text(c)} ({c[1].split(":")[0]} is {PR.var_value(c[1].split(":")[0], st)})'


def explain(c, st, ind='    ', env=None, lets=None):
    """lines that say why a condition tree holds or not: every literal with its value"""
    k = c[0]
    if k in ('true', 'false'): return [ind + ('always' if k == 'true' else 'never')]
    if k in ('trig', 'cmp'):
        v, t = explain_atom(c, st); return [f'{ind}{"yes" if v else "NO "} {t}']
    if k == 'ref':
        v = env[c[1]]; out = [f'{ind}{"yes" if v else "NO "} {c[1]} = {PR.cond_text(lets[c[1]])}']
        return out
    if k == 'not' and c[1][0] in ('trig', 'cmp'):
        v = PR.holds(c, st, env); _, d = explain_atom(c[1], st)
        return [f'{ind}{"yes" if v else "NO "} {PR.cond_text(c)}   [{d[len(PR.atom_text(c[1])) + 1:].strip("()")}]']
    if k == 'not':
        v = PR.holds(c, st, env); inner = explain(c[1], st, ind + '    ', env, lets)
        return [f'{ind}{"yes" if v else "NO "} not (']+ inner + [ind + ')']
    word = 'all of' if k == 'and' else 'one of'
    v = PR.holds(c, st, env); out = [f'{ind}{"yes" if v else "NO "} {word}:']
    for x in c[1]: out += explain(x, st, ind + '    ', env, lets)
    return out


def why(a):
    spec = None
    if os.path.exists(DEFAULT):
        from . import citycli
        try: spec = citycli.load_specs([DEFAULT, os.path.join(os.path.dirname(DEFAULT), 'presence')])
        except (DwsError, OSError): spec = None
    what = a.what.lower()
    st = state_from_args(a)
    trig = set(t for t in st.triggers)
    if what in ('top_map', 'revival', 'prosperity'):
        spec = spec or city.extract_original()
        cs = city.State(triggers=trig, pstats={1: st.p.get(1, 0)})
        if what == 'prosperity':
            lv = city.State.levels(); tot = 0
            for i in range(0, 1024):
                for r in spec['prosperity']:
                    if r['first'] <= i <= r['last']:
                        if cs.recruited(i) and lv.get(i, 0) >= r['min_level']:
                            w = r['add'] + r['per_level'] * lv.get(i, 0); tot += w
                            print(f'  {city.species_text(i)} (level {lv.get(i, 0)}): +{w}')
                        break
            print(f'prosperity = {tot & 0xFF} (pstat 1 is set to this on every save and game start)')
        else:
            blk = spec[what]; scr, why_ = city.explain_top_map(blk, cs)
            print(f'{what}: screen {scr}: {why_}')
        return 0
    from dws import bytecode
    if what.isdigit(): ids = {int(what)}
    else: ids = {i for i, n in bytecode.names()['d'].items() if n.lower() == what}       # a name can be two species (Angemon is 20 and the NPC 142)
    if not ids: raise DwsError(f'"{a.what}": not an NPC species, nor one of top_map, revival, prosperity')
    if spec and spec.get('presence'): pres = spec['presence']
    else: pres, _ = PR.extract_all()
    n = 0
    for scr in sorted(pres):
        if a.screen is not None and scr != a.screen: continue
        sc = pres[scr]; env = {}; lets = dict(sc['lets'])
        for name, f in sc['lets']: env[name] = PR.holds(f, st, env)
        for slot, sid, talk, cond in sc['npcs']:
            if sid not in ids: continue
            n += 1
            here = PR.holds(cond, st, env)
            print(f'{bytecode.names()["d"].get(sid, sid)} ({sid}) on screen {scr} {PR.screen_name(scr)} (MAPHEAD section {scr}), slot {slot}{" (talks first)" if talk else ""}: '
                  f'{"PRESENT" if here else "ABSENT"}')
            print(f'  rule: when {PR.cond_text(cond)}')
            for line in explain(cond, st, env=env, lets=lets): print(line)
    if not n: print(f'{a.what}: no MAPHEAD setup section places it (it may be placed by a script, or it is not an NPC)')
    return 0
