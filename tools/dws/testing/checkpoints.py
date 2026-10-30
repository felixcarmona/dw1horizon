#!/usr/bin/env python3
"""The story checkpoints : the main route of the game from a REAL new game, replayed by inputs, one saved state per checkpoint,
original disc against a rebuilt disc between each pair of checkpoints. Docs: docs/developing.md, "The checkpoints".

  tools/dws/testing/checkpoints.py plan                      the checkpoints, what each segment does and how long it takes (from build/checkpoints/times.json)
  tools/dws/testing/checkpoints.py make                      the original disc from the title screen: a new game with no memory card, by inputs (about 6 minutes
                                          of real time); saves build/checkpoints/c1..c3 (states and screenshots) and times.json
  tools/dws/testing/checkpoints.py run [--disc D] [--from N] the traced segments (C3 -> C4 ...) on the original disc, each from the saved state of the one before:
                                          the trace (digests) and the state at its end are the checkpoint
  tools/dws/testing/checkpoints.py compare --disc readable   the same segments on another disc from the ORIGINAL's saved states, normalized comparison
                                          (sweep.relaxed_events: same rules as the sweep) plus the strict digest, one line per segment

The parts of a new game before the first frame of `gameLoop` (the title menu, the movies, the questions and the naming in screen 0) have no
instruction trace: the tracer hooks gameLoop. They are replayed by `emu.py seq` (the buttons by wall clock, `talk` presses X while a text or choice
is open) and a checkpoint there is a state saved at a RAM condition (screen, script running). From C2 on (the house, gameLoop running) a segment
is steps of the sweep's own step language run by the Lua tracer (frames, not seconds): a trace of every instruction, state write, text sound,
and the digests of the watched memory at its end.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import argparse, json, os, subprocess, sys, time

os.environ.setdefault('EMU_PORT', '38080')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
os.environ.setdefault('SWEEP_PIN_RANDOM', '1')          # STORE_RANDOM from the instruction count (story_trace.lua): the same on every disc
from dws.testing import sweep as W
T = W.T
_locate = T.Scripts.locate


def _safe_locate(self, sid, ip):
    try: return _locate(self, sid, ip)
    except KeyError: return None, ip          # an instruction of no script (id 65535: the scenes before a map script is loaded)


T.Scripts.locate = _safe_locate

CK = os.path.join(ROOT, 'build/checkpoints')
TIMES = os.path.join(CK, 'times.json')

# Checkpoints made by buttons (no instruction trace): name -> (seq text, state it ends in)
MAKE = '''wait 45, START 20, wait 6, START 20, wait 6
CROSS 10, wait 4, DOWN 8, wait 1, DOWN 8, wait 1, CROSS 10, wait 6, CROSS 10, wait 3, CROSS 10
wait 40
save {ck}/c1-jijimon-intro.state, shot {ck}/c1.png
talk CURRENT_SCREEN 1 218 900
wait 20
save {ck}/c2-house.state, shot {ck}/c2.png
talk CURRENT_SCREEN 1 0xCC 900
talk IS_SCRIPT_PAUSED 4 1 100
wait 20
save {ck}/c3-file-city.state, shot {ck}/c3.png
'''

# Traced segments (the sweep's step language, frames): id, from state, to state, doc, steps
SEGMENTS = [
    dict(id='C2-C3', start='c2-house', end='c3-file-city', doc='Jijimon in his house tells the story and sends the tamer out: the scene until the tamer is free in File City (screen 204)',
         steps=['until CURRENT_SCREEN==204 and free press CROSS 3 every 40 max 12000', 'wait 30']),
    dict(id='C3-C4', start='c3-file-city', end='c4-jijimon-talk', doc='back to Jijimon\'s house (warp to 218) and talk to him: everything he says after the first scene',
         steps=['warp 218 0', 'talk until CURRENT_SCREEN==218 and free max 3000', 'wait 60', 'approach 0', 'wait 20', 'until running press CROSS 3 every 40 max 300', 'talk until free max 3000', 'wait 30']),
    dict(id='C4-C5', start='c4-jijimon-talk', end='c5-file-city-plaza', doc='the way to the File City plaza (warp to 180) and a look round: the screen\'s setup script (script 0 section 180) and the NPCs it places',
         steps=['warp 180 0', 'talk until CURRENT_SCREEN==180 and free max 3000', 'wait 120']),
]


ROUTE = [181, 182, 205, 206, 216, 217, 236, 237, 238, 1, 168, 169, 170]          # the main-route screens of the sweep (sweep.MAIN_SCREENS) after the plaza 180


def visit_steps(screen):
    """Warp to the screen and talk to every NPC that is there (slots 0-7): walk up to it, press X until its script runs, read it to the end. A slot with nobody, or an NPC that says nothing, is skipped."""
    st = [f'warp {screen} 0', f'talk until CURRENT_SCREEN=={screen} and free max 3000', 'wait 60']
    for i in range(8): st += [f'approach? {i}', 'wait 20', 'until? running press CROSS 3 every 40 max 150', 'talk? until free max 2500', 'wait 20']
    return st + ['wait 30']


for _n, _s in enumerate(ROUTE):
    SEGMENTS.append(dict(id=f'C{6 + _n}', start=None, end=f'c{6 + _n}-screen-{_s}', screen=_s, doc=f'screen {_s}: warp there and talk to everybody', steps=visit_steps(_s), frames=60000))


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def spath(name): return os.path.join(CK, name + '.state')


def cmd_make(a):
    os.makedirs(CK, exist_ok=True); E = T.emu_mod(); t0 = time.time()
    st = E.state()
    if st and E.alive(st): E.stop()
    T.start_emulator(T.ORIG_CUE, card=False)
    open(os.path.join(CK, 'make.seq'), 'w').write(MAKE.format(ck=CK))
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py'), 'seq', os.path.join(CK, 'make.seq')], check=True, env=dict(os.environ))
    E.stop(); t = json.load(open(TIMES)) if os.path.exists(TIMES) else {}
    t['make'] = round(time.time() - t0); json.dump(t, open(TIMES, 'w'), indent=1)
    log('made c1..c3 in', t['make'], 's')


def steps_of(seg):
    st = [T.parse_step(x) for x in ['clock 9 12']] + [dict(t='trace', on=True)] + W.seed_pokes()
    st += [T.parse_step(x) for x in seg['steps']] + [dict(t='mark', name='final'), dict(t='end')]
    return [x for s in st for x in (s['steps'] if s['t'] == 'multi' else [s])]


def run_segment(R, seg, start, out, save=None):
    t0 = time.time()
    text = R.run(steps_of(seg), start, out, max_frames=seg.get('frames', 14000), idle_frames=None, max_ins=400000, save_state=save)
    ev, row = W.analyse(text, R.sc)
    row['secs'] = round(time.time() - t0); row['hang_at'] = R.hang_at; return ev, row


def rows_path(disc): return os.path.join(CK, f'rows.{disc}.json')


def chain(rows_orig):
    """The start state of each segment: the end state of the last one that ended in a state (a battle ends a segment without one: the route goes on from before it)."""
    cur = None; out = {}
    for seg in SEGMENTS:
        out[seg['id']] = cur if seg['start'] is None else seg['start']
        if seg['start'] is not None: cur = seg['end']
        r = rows_orig.get(seg['id'])
        if r is not None and r.get('state'): cur = r['state']
    return out


def cmd_run(a):
    R = W.Runner(a.disc); t = json.load(open(TIMES)) if os.path.exists(TIMES) else {}; res = json.load(open(rows_path('orig'))) if os.path.exists(rows_path('orig')) and a.first else {}
    cur = 'c5-file-city-plaza' if a.first > 3 else None
    for i, seg in enumerate(SEGMENTS):
        if i < a.first: continue
        start = seg['start'] or cur
        if i == a.first and seg['start'] is None:
            prev = [r.get('state') for r in res.values() if r.get('state')]; start = prev[-1] if prev else 'c5-file-city-plaza'
        out = os.path.join(CK, f'{seg["id"]}.{a.disc}.trace'); save = spath(seg['end']) if a.disc == 'orig' else None
        ev, row = run_segment(R, seg, spath(start), out, save=save)
        row['start'] = start; stop_reason = ''
        if row['end'] in ('end', 'steps_done'): row['state'] = seg['end']; cur = seg['end']
        elif row['end'] == 'battle': row['state'] = None; stop_reason = 'a battle starts (the run stops at START_BATTLE; the route goes on from the state before it)'
        elif row['end'] == 'hang': row['state'] = None; stop_reason = 'the game hangs (stuck in a C loop; in the original too: the last instructions are in the row of the trace)'
        else: row['state'] = None; stop_reason = f'the segment ended {row["end"]}'
        row['blocked'] = stop_reason
        log(f'{seg["id"]} on {a.disc}: {row["n"]} instructions, ends {row["end"]}, {row["frames"]} frames, {row["secs"]} s, digest {row["digest"][:10]}' + (f'  [{stop_reason}]' if stop_reason else ''))
        res[seg['id']] = row; t[seg['id'] + '.' + a.disc] = row['secs']
        json.dump(res, open(rows_path(a.disc), 'w'), indent=1); json.dump(t, open(TIMES, 'w'), indent=1)
        # a hang, a battle or a timeout blocks that screen; the route goes on from the last state
    W.stop_emulator()


def cmd_compare(a):
    R = W.Runner(a.disc); base = json.load(open(rows_path('orig'))); bad = 0; res = {}
    for seg in SEGMENTS:
        if seg['id'] not in base: break
        start = base[seg['id']].get('start') or seg['start']
        out = os.path.join(CK, f'{seg["id"]}.{a.disc}.trace')
        ev, row = run_segment(R, seg, spath(start), out)
        o = dict(base[seg['id']], disc='orig', case=seg['id'], reached=True); r = dict(row, disc=a.disc, case=seg['id'], reached=True)
        W.trace_path = lambda cid, disc: os.path.join(CK, f'{cid}.{disc}.trace')
        if o['end'] == 'hang' or row['end'] == 'hang':          # a blocked segment: both runs hang at the same place or they do not (compare() calls a hang `not reached`)
            eo = T.parse_trace(open(os.path.join(CK, f'{seg["id"]}.orig.trace')).read(), W.scripts_of('orig')); v = 'same' if o['digest'] == row['digest'] else 'relaxed' if W.relaxed_digest(eo) == W.relaxed_digest(ev) and o['end'] == row['end'] else 'DIFF'
        else: v = W.compare(o, r)
        bad += v not in ('same', 'relaxed'); row['compare'] = v; row['strict'] = 'same' if o['digest'] == row['digest'] else 'differs'
        res[seg['id']] = row; json.dump(res, open(rows_path(a.disc), 'w'), indent=1)
        log(f'{seg["id"]:6} orig {o["n"]:5} ins {o["frames"]} fr | {a.disc} {row["n"]:5} ins {row["frames"]} fr | strict {row["strict"]} | normalized {v}')
    W.stop_emulator(); sys.exit(1 if bad else 0)


def cmd_table(a):
    """build/story-analysis/checkpoints.csv from the rows of the runs."""
    import csv
    rows = {d: (json.load(open(rows_path(d))) if os.path.exists(rows_path(d)) else {}) for d in ('orig', 'readable', 'reorder', 'mut1')}
    out = os.path.join(ROOT, 'build/story-analysis/checkpoints.csv'); lines = []
    lines.append(dict(checkpoint='C1', description='title, NEW GAME with no memory card, Jijimon\'s first scene (screen 0): buttons, no trace', frames='', instructions='', orig='state saved', readable='(state of the original used)', reorder='(state of the original used)', mut1=''))
    lines.append(dict(checkpoint='C2', description='questions, name, movie, Jijimon speaks in his house (218): talk until screen 218', frames='', instructions='', orig='state saved', readable='', reorder='', mut1=''))
    for seg in SEGMENTS:
        o = rows['orig'].get(seg['id'])
        if o is None: lines.append(dict(checkpoint=seg['id'], description=seg['doc'], orig='not reached')); continue
        d = dict(checkpoint=seg['id'], description=seg['doc'], frames=o['frames'], instructions=o['n'], orig=('blocked: ' + o['blocked']) if o.get('blocked') else f'ends {o["end"]}')
        for disc in ('readable', 'reorder', 'mut1'):
            r = rows[disc].get(seg['id']); d[disc] = '' if r is None else f'strict {r["strict"]}, normalized {r["compare"]}'
        lines.append(d)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['checkpoint', 'description', 'frames', 'instructions', 'orig', 'readable', 'reorder', 'mut1']); w.writeheader(); [w.writerow(x) for x in lines]
    print(out, len(lines))


def cmd_plan(a):
    t = json.load(open(TIMES)) if os.path.exists(TIMES) else {}
    print('C1 title -> new game -> Jijimon\'s first scene (screen 0)      buttons, no trace    state c1-jijimon-intro')
    print('C2 questions, name, movie -> the house, Jijimon speaks (218)  talk (X while a box is open)   state c2-house')
    print('C3 the tamer free in File City (204)                          talk; free             state c3-file-city      [make: %s s for C1-C3]' % t.get('make', '?'))
    for s in SEGMENTS: print(f'{s["id"]:6} {s["doc"]}: orig {t.get(s["id"] + ".orig", "?")} s')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('plan').set_defaults(f=cmd_plan); sub.add_parser('make').set_defaults(f=cmd_make); sub.add_parser('table').set_defaults(f=cmd_table)
    for n, f in (('run', cmd_run), ('compare', cmd_compare)):
        p = sub.add_parser(n); p.add_argument('--disc', default='orig'); p.add_argument('--from', dest='first', type=int, default=0); p.set_defaults(f=f)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
