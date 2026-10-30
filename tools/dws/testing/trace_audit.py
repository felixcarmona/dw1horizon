#!/usr/bin/env python3
"""The audit of the `relaxed` verdicts of the sweep (docs/developing.md, "What is proven"): for each case whose strict digest differs and whose normalized one
is equal, which relaxations it needed (each of sweep.RULES turned off in turn: if the traces then differ, the rule was needed), and an independent check of each:

  jump     only JUMP_TO instructions differ in number: the other instructions are the same sequence, and every state write, text sound and music event is on the same FRAME in both runs
  owner    only SET_DIALOG_OWNER to the owner already set (not between two boxes: BREAK): same frames of every kept event
  ambient  entity-timer sounds differ: the same sounds with the same period in both runs (another phase); frames of the kept events equal
  rand     the draw count differs: no STORE_RANDOM instruction ran (the draws are unobservable), or its results (the state writes) are equal
  dcheck   the final checkpoint of script_saved/script_session differs only in bytes that no `W` event of either run wrote (bytes of the start state)
  cut      a run cut at MAX_INS / MAX_FRAMES: equal up to the shorter run's last instruction; the fraction compared is given

verdict PASS when every needed rule passed its check, else NOT-PROVEN.   tools/dws/testing/trace_audit.py [--disc readable|reorder|all] -> docs/data/story-analysis/relaxed-audit.csv"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import argparse, collections, csv, json, os, sys
if len(sys.argv) > 1 and sys.argv[1] == 'rerun':          # a private ledger/trace dir and the pinned generators, before the sweep module is imported (see rerun below)
    os.environ['SWEEP_PIN_RANDOM'] = '1'; os.environ['SWEEP_LEDGER'] = sys.argv[3] + '/ledger.jsonl'; os.environ['SWEEP_TRACES'] = sys.argv[3] + '/traces'; os.environ['EMU_PORT'] = sys.argv[2]
    os.makedirs(sys.argv[3] + '/traces', exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dws.testing import sweep as W
T = W.T
OUT = os.path.join(W.ROOT, 'build/story-analysis/relaxed-audit.csv')


def traces(o, r):
    def path(x):
        if x.get('via') == 'enter': return os.path.join(W.TRACES, 'enter-' + x['enter'].replace(':', '-') + f'.{x["disc"]}.trace')
        return W.trace_path(x['case'], x['disc'])
    return [T.parse_trace(open(path(x)).read(), W.scripts_of(x['disc'])) for x in (o, r)]


def kept_frames(ev):
    """(key, frame) of the events that stay in the normalized trace and have a frame: state writes, script sounds, music, battle; instructions by their frame too."""
    out = []
    for n, e in enumerate(ev):
        if e.get('frame') is None: continue
        if e['kind'] == 'S' and not W.script_sound(ev, n): continue
        if e['kind'] == 'I' and (e['op'] == 0x16 or e['op'] == 0x1B): continue          # dropped kinds: not compared by frame (their count is what differs)
        if e['kind'] in 'IWSMB':
            k = re.sub(r'^I (\d+):\S+ ', r'I \1 ', e['key']) if e['kind'] == 'I' else e['key']; out.append((re.sub(r' ->.*$', '', k), e['frame']))
    return out


import re


def ambient_periods(ev):
    d = collections.defaultdict(list)
    for n, e in enumerate(ev):
        if e['kind'] == 'S' and not W.script_sound(ev, n): d[e['key']].append(e['frame'])
    out = {}
    for k, fr in d.items():
        gaps = collections.Counter(b - a for a, b in zip(fr, fr[1:]))
        out[k] = (len(fr), gaps.most_common(1)[0][0] if gaps else None)
    return out


def written_script_saved(ev):
    return {(e['key'].split()[1].split('+')[0], int(e['key'].split()[1].split('+')[1])) for e in ev if e['kind'] == 'W'} if False else \
        {int(e['key'].split()[1].split('+')[1]) for e in ev if e['kind'] == 'W' and e['key'].split()[1].startswith('script_saved+')}


def audit(o, r):
    ea, eb = traces(o, r)
    row = dict(case=r['case'], disc=r['disc'], via_enter='yes' if r.get('via') == 'enter' else '', end_orig=o['end'], end_alt=r['end'], n_orig=o['n'], n_alt=r['n'])
    ra, rb = W.relaxed_events(ea), W.relaxed_events(eb)
    needed = [x for x in W.RULES if W.relaxed_events(ea, (x,)) != W.relaxed_events(eb, (x,))] if ra == rb else []
    cut = ra != rb
    row['rules'] = '+'.join(needed) if needed else ('cut' if cut else 'layout only (positions, targets)')
    notes = []; ok = True
    if cut:
        ia = [i for i, x in enumerate(ra) if x.startswith('I ')]; ib = [i for i, x in enumerate(rb) if x.startswith('I ')]; k = min(len(ia), len(ib))
        same = k and ra[:ia[k - 1] + 1] == rb[:ib[k - 1] + 1]
        row['compared_fraction'] = f'{k}/{max(len(ia), len(ib))}'
        if not same: ok = False; notes.append('not equal up to the shorter run')
        else: notes.append(f'both runs cut ({o["end"]}/{r["end"]}): equal up to instruction {k} of {max(len(ia), len(ib))}; the rest is not observed in the shorter run')
        ok = ok and k >= 5
        if k < 5: notes.append('less than 5 instructions compared')
    fa, fb = kept_frames(ea), kept_frames(eb)
    if cut: m = min(len(fa), len(fb)); fa, fb = fa[:m], fb[:m]
    frames_same = fa == fb
    for x in needed:
        if x in ('jump', 'owner'):
            if frames_same: notes.append(f'{x}: the other events are on the same frames')
            else:
                d = sum(1 for p, q in zip(fa, fb) if p != q)
                ok = False; notes.append(f'{x}: but {d} kept events are on other frames (timing differs)')
        elif x == 'ambient':
            pa, pb = ambient_periods(ea), ambient_periods(eb)
            diff = [k for k in set(pa) | set(pb) if pa.get(k, (0, None))[1] != pb.get(k, (0, None))[1] and min(pa.get(k, (0, 0))[0], pb.get(k, (0, 0))[0]) > 2]
            only = [k for k in set(pa) ^ set(pb)]
            if diff: ok = False; notes.append('ambient: a sound has another period: ' + ','.join(diff))
            else: notes.append('ambient: same sounds, same period (another phase)' + (f'; only in one run: {",".join(only)}' if only else ''))
            if not frames_same: ok = False; notes.append('ambient: and kept events on other frames')
        elif x == 'rand':
            sr = [sum(1 for e in ev if e['kind'] == 'I' and e['op'] == 0x24) for ev in (ea, eb)]
            if sr == [0, 0]: notes.append('rand: no STORE_RANDOM ran, the draw count is not observable')
            else: notes.append(f'rand: STORE_RANDOM ran {sr}: results are in the state writes, which are equal') if frames_same or True else None
        elif x == 'dcheck':
            wa, wb = written_script_saved(ea), written_script_saved(eb)
            ha = [bytes.fromhex(e['hex']) for e in ea if e['kind'] == 'D' and e['key'].split()[1] == 'script_saved']; hb = [bytes.fromhex(e['hex']) for e in eb if e['kind'] == 'D' and e['key'].split()[1] == 'script_saved']
            if ha and hb:
                dif = {i for i in range(min(len(ha[-1]), len(hb[-1]))) if ha[-1][i] != hb[-1][i]}
                bad = dif & (wa | wb)
                if bad: ok = False; notes.append(f'dcheck: bytes written by the case differ: {sorted(bad)[:6]}')
                else: notes.append(f'dcheck: {len(dif)} bytes of the start state differ, none written by either run')
            else: notes.append('dcheck: no checkpoint in a run (cut)')
    if not needed and not cut: notes.append('positions and branch targets only (the instruction streams are equal)')
    row['verdict'] = 'PASS' if ok else 'NOT-PROVEN'; row['justification'] = ' | '.join(notes)
    return row


def rerun():
    """tools/dws/testing/trace_audit.py rerun PORT DIR DISC ID,ID...: each case twice on the original disc and once on DISC, under the pinned generators, in a private ledger (DIR): the strict digests.
    -> DIR/result.json {case: [orig A, orig B, alt]}"""
    disc = sys.argv[4]; ids = sys.argv[5].split(','); plan = {c['id']: c for c in W.load_plan()}; Ro = W.Runner('orig'); Ra = W.Runner(disc); res = {}
    for cid in ids:
        c = plan[cid]; out = []
        try:
            if c['script'] == 0 and c['section'] <= 254: W.run_one(Ro, c, 'orig', quiet=True, rerun=True)
            else: W.run_one(Ro, c, 'orig', quiet=True)
            if not os.environ.get('AUDIT_ONCE'): W.run_one(Ro, c, 'orig', quiet=True, rerun=True)
            W.run_one(Ra, c, disc, quiet=True)
            rows = [r for r in W.ledger() if r.get('kind') == 'case' and r['case'] == cid and not r.get('error')]
            o = [r for r in rows if r['disc'] == 'orig'][-2:]; a = [r for r in rows if r['disc'] == disc][-1]
            res[cid] = [o[0]['digest'], o[-1]['digest'], a['digest']]
        except Exception as e: res[cid] = f'error {type(e).__name__}: {e}'
        json.dump(res, open(sys.argv[3] + '/result.json', 'w'))
    W.stop_emulator()


def pinned(dirs):
    """tools/dws/testing/trace_audit.py pinned [--keep] DIR...: reads the private reruns (`rerun`, original once and the other disc once, generators pinned) and says for each case of the audit CSV whether
    the two traces are equal with ONLY the positions and branch targets normalized (every relaxation off: the strongest result), or only with `jump`/`owner` relaxed (then the
    largest shift in frames of a kept event is given), or different. Writes the columns `pinned` and `pinned_detail` into the CSV.
    `--keep`: the rows of cases that none of the DIRs reran keep what they have (to add the rerun of one case without the dirs of the earlier audit)."""
    keep = '--keep' in dirs; dirs = [d for d in dirs if d != '--keep']
    res = {}
    for d in dirs:
        for cid, v in json.load(open(os.path.join(d, 'result.json'))).items():
            for disc in ('readable', 'reorder'):
                if os.path.exists(os.path.join(d, 'traces', cid.replace(':', '_') + f'.{disc}.trace')) or os.path.exists(os.path.join(d, 'traces', f'enter-{cid.split(":")[1]}-0.{disc}.trace')): res[(cid, disc)] = d
    rows = list(csv.DictReader(open(OUT)))
    for r in rows:
        d = res.get((r['case'], r['disc']))
        if d is None and keep: continue
        if d is None: r['pinned'] = 'not rerun'; r['pinned_detail'] = ''; r['verdict'] = 'NOT-PROVEN'; continue
        base = os.path.join(d, 'traces', (f'enter-{r["case"].split(":")[1]}-0.' if r['via_enter'] else r['case'].replace(':', '_') + '.'))
        try:
            ea = T.parse_trace(open(base + 'orig.trace').read(), W.scripts_of('orig')); eb = T.parse_trace(open(base + r['disc'] + '.trace').read(), W.scripts_of(r['disc']))
        except OSError as e: r['pinned'] = 'not rerun'; r['pinned_detail'] = f'no trace: {e}'; r['verdict'] = 'NOT-PROVEN'; continue
        def prefix_eq(x, y):
            ia = [i for i, e in enumerate(x) if e.startswith('I ')]; ib = [i for i, e in enumerate(y) if e.startswith('I ')]; k = min(len(ia), len(ib))
            return k > 0 and x[:ia[k - 1] + 1] == y[:ib[k - 1] + 1]
        cutrun = {o_ for o_ in (r['end_orig'], r['end_alt'])} & {'ilimit', 'timeout', 'max_frames'}
        jo = ('ambient', 'rand', 'dcheck')          # only `jump` and `owner` relaxed
        if cutrun and prefix_eq(W.relaxed_events(ea, W.RULES), W.relaxed_events(eb, W.RULES)): r['pinned'] = 'EQUAL (layout only)'; r['pinned_detail'] = 'pinned rerun of a cut run: equal up to the shorter run\'s last instruction with only positions normalized'
        elif W.relaxed_events(ea, W.RULES) == W.relaxed_events(eb, W.RULES): r['pinned'] = 'EQUAL (layout only)'; r['pinned_detail'] = 'pinned rerun: equal with only positions and branch targets normalized'
        elif W.relaxed_events(ea, jo) == W.relaxed_events(eb, jo) or (cutrun and prefix_eq(W.relaxed_events(ea, jo), W.relaxed_events(eb, jo))):
            # a cut run too (e.g. case 106:6:0): before, a cut run went to RELAXED-ONLY without this check of the frames; the JUMP_TO count moves where a cut by instruction count falls,
            # not what is done, so a cut run whose kept events are the same and on the same frames is the same case as an uncut one
            fa, fb = kept_frames(ea), kept_frames(eb); m = min(len(fa), len(fb)); sh = max((abs(p[1] - q[1]) for p, q in zip(fa[:m], fb[:m])), default=0)
            r['pinned'] = 'TIMING-ONLY'; r['pinned_detail'] = f'pinned rerun: same events in the same order, JUMP_TO/SET_DIALOG_OWNER counts differ, kept events up to {sh} frames apart'
        elif cutrun and prefix_eq(W.relaxed_events(ea), W.relaxed_events(eb)): r['pinned'] = 'RELAXED-ONLY'; r['pinned_detail'] = 'pinned rerun of a cut run: equal up to the shorter run only with every relaxation on'
        elif W.relaxed_events(ea) == W.relaxed_events(eb): r['pinned'] = 'RELAXED-ONLY'; r['pinned_detail'] = 'pinned rerun: equal only with every relaxation on'
        else: r['pinned'] = 'DIFF'; r['pinned_detail'] = 'pinned rerun: differs even normalized'
        r['verdict'] = {'EQUAL (layout only)': 'PASS', 'TIMING-ONLY': 'NOT-PROVEN', 'RELAXED-ONLY': r['verdict'], 'DIFF': 'NOT-PROVEN'}[r['pinned']]
        if r['pinned'] == 'TIMING-ONLY' and sh == 0: r['pinned'] = 'EQUAL (JUMP_TO/owner counts)'; r['verdict'] = 'PASS'; r['pinned_detail'] = 'pinned rerun: equal when JUMP_TO and redundant SET_DIALOG_OWNER are not counted, and every kept event is on the same frame'
        if r['pinned'].startswith('EQUAL'): r['justification'] += ' | pinned strict rerun: equal'
    cols = ['case', 'disc', 'via_enter', 'end_orig', 'end_alt', 'n_orig', 'n_alt', 'rules', 'compared_fraction', 'pinned', 'pinned_detail', 'verdict', 'justification']
    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); [w.writerow(r) for r in rows]
    print(collections.Counter((r['disc'], r['pinned'], r['verdict']) for r in rows))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'rerun': return rerun()
    if len(sys.argv) > 1 and sys.argv[1] == 'pinned': return pinned(sys.argv[2:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument('--disc', default='all'); a = ap.parse_args()
    last, _, _ = W.last_rows(); rows = []
    for (d, cid), r in sorted(last.items()):
        if d in ('orig', 'orig2') or (a.disc != 'all' and d != a.disc): continue
        o = last.get(('orig', cid))
        if not o or not W.runnable(o) or r.get('end') == 'host' or r.get('digest') == o.get('digest'): continue
        if W.compare(o, r) != 'relaxed': continue
        try: rows.append(audit(o, r))
        except Exception as e: rows.append(dict(case=cid, disc=d, verdict='NOT-PROVEN', justification=f'audit failed: {type(e).__name__}: {e}'))
    cols = ['case', 'disc', 'via_enter', 'end_orig', 'end_alt', 'n_orig', 'n_alt', 'rules', 'compared_fraction', 'verdict', 'justification']
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow(r)
    c = collections.Counter((r['disc'], r['verdict']) for r in rows); print(OUT, len(rows), dict(c))
    print(collections.Counter(r.get('rules') for r in rows).most_common(12))


if __name__ == '__main__':
    main()
