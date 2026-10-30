#!/usr/bin/env python3
"""Random-number consumption audit (docs/developing.md).

The normalized comparison of the sweep (sweep.relaxed_events) does not compare the number of rand() draws. This tool measures it, on the traces the
sweep saved: for every case that ran on the original disc and on `reorder` / `readable`, the instructions that consume randomness are counted and the draws are compared.

  consumers   the opcodes whose handler reaches rand(): STORE_RANDOM (0x24, one draw), ADVANCE_TO_DATE_AT (0x37, dailyPStatTrigger), CALL_ROUTINE (0x64: ninjamon effect,
              card pack, tournament, lost-all-lives), START_BATTLE (0x66). Derived from the C call graph of decomp/ (tools/dws/randflow.py CONSUMERS).
  script      the sequence of consumer instructions that ran (opcode and operands, in order, over the common kept prefix of both runs): equal or not. When equal, the script
              asked for exactly the same draws on both discs; whatever differs in the number of draws is then not the script's.
  ambient     draws that are not the script's: the entities' AI and effects draw about once a frame, so the count moves with the frame phase and the time a box waits.
              Shown by `delta_draws` against `delta_frames` and, for the original disc against ITSELF, by `selfcheck`.

  tools/dws/testing/random_audit.py [all|static|case|self]  -> docs/data/story-analysis/rand-audit.csv: `static` (every section of the discs, no emulator), `case` (the sweep's traces), `self` (the reruns below)
  tools/dws/testing/random_audit.py rerun PORT DIR DISC IDS      two runs of the original disc and one of DISC per case, pinned generators, into a private ledger DIR (as trace_audit rerun)
  """
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import argparse, collections, csv, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if len(sys.argv) > 1 and sys.argv[1] == 'rerun':          # a private ledger and trace dir and the pinned generators, before the sweep module is imported
    if os.environ.get('DWS_RANDOM_UNPINNED'): os.environ.pop('SWEEP_PIN_RANDOM', None)          # DWS_RANDOM_UNPINNED=1: the draws of STORE_RANDOM are not pinned either (as in a sweep without --pin-random)
    else: os.environ['SWEEP_PIN_RANDOM'] = '1'
    os.environ['SWEEP_LEDGER'] = sys.argv[3] + '/ledger.jsonl'; os.environ['SWEEP_TRACES'] = sys.argv[3] + '/traces'; os.environ['EMU_PORT'] = sys.argv[2]
    os.makedirs(sys.argv[3] + '/traces', exist_ok=True)
from dws.testing import sweep as W
from dws.randflow import CONSUMERS
T = W.T
OUT = os.path.join(W.ROOT, 'docs/data/story-analysis/rand-audit.csv')
CUT = ('ilimit', 'timeout', 'max_frames')


def trace_file(row):
    if row.get('via') == 'enter': return os.path.join(W.TRACES, 'enter-' + row['enter'].replace(':', '-') + f'.{row["disc"]}.trace')
    return W.trace_path(row['case'], row['disc'])


def kept(ev):
    """The instruction events the normalized comparison keeps (no JUMP_TO, no SET_DIALOG_OWNER to the owner already set)."""
    out = []; owner = 0xFD
    for e in ev:
        if e['kind'] != 'I': continue
        if e['op'] in W.LAYOUT_ONLY: continue
        if e['op'] == 0x1B and len(e['raw']) > 1:
            same = e['raw'][1] == owner; owner = e['raw'][1]
            if same: continue
        out.append(e)
    return out


def ckey(e): return re.sub(r'^I (\d+):\S+ ', r'I \1 ', e['key']).split(' ->')[0]


def measure(ev, m=None):
    """The run's consumers and draws over its first m kept instructions (all when m is None)."""
    ks = kept(ev); ks = ks if m is None else ks[:m]
    allI = [e for e in ev if e['kind'] == 'I']
    if not ks: return None
    cons = [ckey(e) for e in ks if e['op'] in CONSUMERS]
    last = ks[-1]; first = allI[0]
    return dict(kept=len(ks), cons=cons, sr=sum(e['op'] == 0x24 for e in ks), draws=last['rand'] - first['rand'], frames=last['frame'] - first['frame'],
                jumps=sum(e['op'] == 0x16 for e in allI))


def pair(eo, ea):
    """-> row fields comparing two traces of the same case."""
    m = min(len(kept(eo)), len(kept(ea))); a = measure(eo, m); b = measure(ea, m)
    if a is None or b is None: return None
    same_len = len(kept(eo)) == len(kept(ea))
    return dict(kept=m, same_kept_len=same_len, sr_orig=a['sr'], sr_alt=b['sr'], cons_orig=len(a['cons']), cons_alt=len(b['cons']), same_consumers=a['cons'] == b['cons'],
                draws_orig=a['draws'], draws_alt=b['draws'], delta_draws=b['draws'] - a['draws'], frames_orig=a['frames'], frames_alt=b['frames'], delta_frames=b['frames'] - a['frames'],
                jumps_orig=a['jumps'], jumps_alt=b['jumps'])


def classify(r, end_o, end_a):
    if not r['same_consumers']: return 'SCRIPT', 'the consumer instructions that ran differ (see consumers)'
    if not r['same_kept_len'] and not (end_o in CUT or end_a in CUT): return 'SCRIPT', 'the kept instructions differ in number although the run was not cut'
    if r['delta_draws'] == 0: return 'EQUAL', 'same consumers, same draws'
    return 'AMBIENT', 'same consumers (the script asked for the same draws); the difference is frame-phase draws of entities and effects'


def orig_digests():
    """case -> set of the strict digests of every run of the original disc in the ledger."""
    out = collections.defaultdict(set)
    for r in W.ledger():
        if r.get('kind', 'case') == 'case' and r.get('disc') == 'orig' and not r.get('error') and r.get('digest') and r.get('end') != 'host': out[r['case']].add(r['digest'])
    return out


def orig_variants():
    """case -> (number of runs of the original disc in the ledger, number of different strict digests among them): the original against ITSELF over the sweep (a case is run again
    for a classification, and by a later campaign). The digest contains the draw counts, the sounds and the positions: one value for all runs means the original never varied."""
    runs = collections.defaultdict(list)
    for r in W.ledger():
        if r.get('kind', 'case') == 'case' and r.get('disc') == 'orig' and not r.get('error') and r.get('digest') and r.get('end') != 'host': runs[r['case']].append(r['digest'])
    return {c: (len(v), len(set(v))) for c, v in runs.items()}


def main_rows():
    last, _, _ = W.last_rows(); W.load_audit(); rows = []; ov = orig_variants(); od = orig_digests()
    for (d, cid), a in sorted(last.items()):
        if d not in ('reorder', 'readable'): continue
        o = last.get(('orig', cid))
        if not o or not W.runnable(o) or a.get('end') == 'host' or not a.get('reached') or a.get('skipped') or a.get('error'): continue
        try:
            eo = T.parse_trace(open(trace_file(o)).read(), W.scripts_of('orig')); ea = T.parse_trace(open(trace_file(a)).read(), W.scripts_of(d))
        except OSError: continue
        # the trace on disk must be the run of the row (a rerun that was killed after writing its trace leaves another one)
        if o.get('digest') and T.digest(eo) != o['digest'] and o.get('via') != 'enter': rows.append(dict(case=cid, disc=d, verdict='NO-TRACE', cause='the orig trace on disk is not the run of its ledger row')); continue
        if a.get('digest') and T.digest(ea) != a['digest'] and a.get('via') != 'enter': rows.append(dict(case=cid, disc=d, verdict='NO-TRACE', cause='the alt trace on disk is not the run of its ledger row')); continue
        r = pair(eo, ea)
        if r is None: continue
        v, why = classify(r, o.get('end'), a.get('end'))
        n, k = ov.get(cid, (0, 0)); same_as_a_run = a['digest'] in od.get(cid, ())
        rows.append(dict(level='case', case=cid, disc=d, end_orig=o.get('end'), end_alt=a.get('end'), strict=('same' if o['digest'] == a['digest'] else 'differs'), verdict=v, cause=why,
                         selfcheck=f'the original disc has {k} different strict digest(s) in {n} run(s) of this case', alt_equals_an_orig_run=same_as_a_run, **r))
    return rows


COLS = ['level', 'case', 'disc', 'end_orig', 'end_alt', 'strict', 'kept', 'same_kept_len', 'sr_orig', 'sr_alt', 'cons_orig', 'cons_alt', 'same_consumers', 'draws_orig', 'draws_alt', 'delta_draws',
        'frames_orig', 'frames_alt', 'delta_frames', 'jumps_orig', 'jumps_alt', 'verdict', 'cause', 'selfcheck', 'alt_equals_an_orig_run']


def rerun():
    """tools/dws/testing/random_audit.py rerun PORT DIR DISC ID,ID..: each case twice on the original disc and once on DISC, pinned generators, in a private ledger DIR. Each run's trace is copied
    to DIR/traces/<case>.<disc>.<k>.trace (k = A, B) because the ledger keeps only the latest trace per case and disc."""
    import shutil
    disc = sys.argv[4]; ids = sys.argv[5].split(','); plan = {c['id']: c for c in W.load_plan()}; Ro = W.Runner('orig'); Ra = W.Runner(disc); res = {}
    for cid in ids:
        c = plan[cid]
        try:
            for k in 'AB':
                if c['script'] == 0 and c['section'] <= 254: W.run_one(Ro, c, 'orig', quiet=True, rerun=True)
                else: W.run_one(Ro, c, 'orig', quiet=True)
                rows = [r for r in W.ledger() if r.get('kind') == 'case' and r['case'] == cid and r['disc'] == 'orig' and not r.get('error')]
                p = trace_file(rows[-1]); shutil.copy(p, p + f'.{k}')
            W.run_one(Ra, c, disc, quiet=True)
            res[cid] = 'ok'
        except Exception as e: res[cid] = f'error {type(e).__name__}: {e}'
        json.dump(res, open(sys.argv[3] + '/result.json', 'w'))
    W.stop_emulator()


def self_rows(dirs):
    """The reruns of `rerun` (pinned generators, one private ledger per DIR): the original disc against ITSELF (A against B: same disc, same state, nothing changed), and A against the other disc."""
    out = []
    for d in dirs:
        tr = os.path.join(d, 'traces')
        for f in sorted(os.listdir(tr)):
            m = re.match(r'(\d+_\d+_\d+)\.orig\.trace\.A$', f)
            if not m: continue
            cid = m.group(1).replace('_', ':'); base = os.path.join(tr, m.group(1)); ev = {}
            try:
                for k in 'AB': ev[k] = T.parse_trace(open(f'{base}.orig.trace.{k}').read(), W.scripts_of('orig'))
            except OSError: continue
            for disc in ('readable', 'reorder'):
                if os.path.exists(f'{base}.{disc}.trace'): ev[disc] = T.parse_trace(open(f'{base}.{disc}.trace').read(), W.scripts_of(disc))
            r = pair(ev['A'], ev['B'])
            if r is None: continue
            how = 'rerun, STORE_RANDOM not pinned' if 'unpinned' in d else 'rerun, STORE_RANDOM pinned'
            out.append(dict(case=cid, disc='orig-vs-orig', end_orig='-', end_alt='-', strict='-', level='self', selfcheck=how, **r, **dict(zip(('verdict', 'cause'), classify(r, '-', '-')))))
            for disc in ('readable', 'reorder'):
                if disc in ev and (r2 := pair(ev['A'], ev[disc])): out.append(dict(case=cid, disc=disc, end_orig='-', end_alt='-', strict='-', level='self', selfcheck=how, **r2, **dict(zip(('verdict', 'cause'), classify(r2, '-', '-')))))
    return out


def static_rows(alts=('reorder', 'readable')):
    """Per section of every script: the consumers the original has and the build has, and whether the multiset and the sequence of consumers on every path are equal."""
    from dws import randflow as R
    discs = T.load_discs(); S = {d: T.Scripts(discs[d]['dg'], discs[d]['maphead']) for d in ('orig',) + tuple(alts)}; rows = []
    for alt in alts:
        for sid in sorted(S['orig'].raw):
            a = S['orig'].raw[sid]; b = S[alt].raw.get(sid)
            if b is None: rows.append(dict(case=f'{sid}:*', disc=alt, level='section', verdict='SCRIPT', cause='script missing on the build')); continue
            try: rep = R.report(a, b)
            except R.Violation as e: rows.append(dict(case=f'{sid}:*', disc=alt, level='section', verdict='ERROR', cause=str(e))); continue
            for sec, ca, cb, same_set, same_seq, note in rep:
                v = 'EQUAL' if same_set and same_seq else ('SEQUENCE-EQUAL' if same_seq else 'SCRIPT')
                cause = {'EQUAL': 'same consumers on every path, same instructions', 'SEQUENCE-EQUAL': 'same consumers in the same order on every path; the build copies them into the arms of an if (a path still draws the same)',
                         'SCRIPT': 'a path draws other numbers: ' + note}[v]
                rows.append(dict(case=f'{sid}:{sec}', disc=alt, level='section', cons_orig=ca, cons_alt=cb, same_consumers=same_seq, verdict=v, cause=cause + (' [call stack abstracted: ' + note + ']' if note == 'approx' else '')))
    return rows


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'rerun': return rerun()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('what', nargs='?', default='all', choices=['all', 'static', 'case', 'self']); ap.add_argument('dirs', nargs='*', help='self: the private ledger dirs of `rerun`')
    a = ap.parse_args(); rows = []
    if a.what in ('all', 'static'): rows += static_rows()
    if a.what in ('all', 'case'): rows += main_rows()
    if a.what in ('all', 'self'): rows += self_rows(a.dirs or sorted(glob.glob(os.path.join(W.SW, 'random-audit-*'))))
    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore'); w.writeheader(); [w.writerow(r) for r in rows]
    print(OUT, len(rows), dict(collections.Counter((r['level'], r['disc'], r['verdict']) for r in rows)))


if __name__ == '__main__':
    main()
