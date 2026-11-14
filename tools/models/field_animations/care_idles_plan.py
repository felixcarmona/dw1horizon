"""Planner of content/models/imports/care-idles.json (a developer tool, numpy): reads a species' bone roles from the
final model's field idle, makes the condition idles with care_idles.apply, measures them with tools/models/care_qa.py
and keeps the slots that pass and fit the resident buffer.

    python -m tools.models.field_animations.care_idles_plan ID FINAL.MMD MAIN.MMD [BASE.MMD] [--slots 1 18 ...]
        [--body biped] [--write]

FINAL is the provider's output before this stage (main's pinned model when nothing else changed), MAIN the model the
slots are compared against (never worse), BASE the importer's (the bone ranges a clip may use).
"""
import argparse
import glob
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools/models')]
from tools.models import battle_qa as bq  # noqa: E402
from tools.models import care_qa  # noqa: E402
from tools.models.field_animations import care_idles  # noqa: E402


def skeleton(sid):
    path = glob.glob(str(ROOT / f'content/species/{sid}-*.json'))[0]
    return json.loads(Path(path).read_text())['model']['skeleton']


def roles(data, bones, body=None):
    rig = bq.Rig.from_mmd(data, bones)
    ref = bq.reference(rig)
    c = bq.Clip(rig, *rig.frames(0))
    h = ref['h']
    parent = rig.parent

    def ancestors(b):
        out = []
        while parent[b] >= 0:
            b = parent[b]
            out.append(b)
        return out
    legs = [ch for ch in ref['chains'] if ch['kind'] == 'leg']
    keep = sorted({0} | {b for ch in legs for b in ch['bones'] + ancestors(ch['bones'][0])})
    cen = {b: c.V[b][0].mean(0) for b in rig.meshed}
    joint = {b: c.Wb[0, b, :3, 3] for b in range(rig.nb)}
    # the head: a centred meshed bone, high and to the front, not a leg
    cand = [b for b in rig.meshed if b not in keep and abs(cen[b][0]) < 0.15 * h]
    head = min(cand, key=lambda b: cen[b][1] + 0.3 * cen[b][2]) if cand else None
    lean, heads = [], []
    if head is not None:
        path = [b for b in reversed(ancestors(head)) if b not in keep] + [head]
        heads = [head]
        p = parent[head]
        if p in path and len(rig.children[p]) == 1:
            heads.insert(0, p)
        lean = [b for b in path if b not in heads]
    head_tree = set(heads)
    for b in range(rig.nb):
        if any(a in head_tree for a in ancestors(b)):
            head_tree.add(b)
    droop = {}
    for ch in ref['chains']:
        b0 = ch['bones'][0]
        if ch['kind'] == 'leg' or b0 in head_tree or b0 in lean or b0 in keep:
            continue
        tip = cen[ch['tip']]
        W = c.Wb[0, b0, :3, :3]
        d = W.T @ (tip - joint[b0])
        if np.linalg.norm(d) < 0.05 * h:
            continue
        droop[str(b0)] = [round(float(x), 1) for x in d]
    if body is None:
        span = max([abs(cen[ch['tip']][0]) for ch in ref['chains'] if ch['kind'] == 'limb'] + [0])
        body = ('legless' if not legs else 'quadruped' if len(legs) >= 4 else
                'flyer' if span > 0.55 * h and ref['floor'] - max(v[:, 1].max() for v in c.V.values()) < 0 else 'biped')
    return dict(body=body, keep=keep, lean=lean, head=heads, droop=droop, parents=list(parent))


UP = (1.0, 1.35, 1.7)    # a clip too close to the idle gets stronger
DOWN = (1.0, 0.7, 0.45)  # a clip that sinks, tears or tips gets weaker
TARGET = 0.05            # aim a little over care_qa.IDLE_DIST
SHARE_ORDER = ('tired', 'sick', 'sleepy', 'unhappy', 'hungry', 'toilet')
TOL_MAX = 16             # coarsest encoding tried (1/4096 turn), when the resident buffer would overflow


def _apply(final, bones, row, log):
    """care_idles.apply; when the resident buffer overflows, a coarser encoding, else (None, None)."""
    while True:
        try:
            return care_idles.apply(final, bones, row)
        except ValueError as e:
            if 'resident' not in str(e) or row.get('tol', 1) >= TOL_MAX:
                log(f'  {e}')
                return None, None
            row['tol'] = row.get('tol', 1) + 1


def plan(sid, final, main, base=None, slots=(1, 18), body=None, conds=None, log=print, compact=False):
    """The row for species `sid`: per condition a gain whose clip is TARGET off the field idle with no flag (stronger
    while too close, weaker while it sinks, tears or tips); a condition whose clip stays too close to another's
    shares that program (as native partners do); slots that do not fit the buffer are dropped from the end of
    SHARE_ORDER; a slot that fails at every gain is left out (it stays main's)."""
    bones = skeleton(sid)
    row = roles(final, bones, body)
    if compact:
        row['compact'] = True
    want = {str(s): (conds or care_idles.DEFAULT)[s] for s in slots}
    state = {c: dict(ladder=None, i=0) for c in set(want.values())}
    ok = {}
    while True:
        todo = sorted(c for c in state if c not in ok and state[c]['i'] is not None)
        if not todo:
            break
        row['slots'] = {s: c for s, c in want.items() if c in todo}
        row['gain'] = {c: (state[c]['ladder'] or UP)[state[c]['i']] for c in todo}
        row.pop('tol', None)
        out, _ = _apply(final, bones, row, log)
        if out is None:                                     # drop the last condition in SHARE_ORDER
            c = max(todo, key=SHARE_ORDER.index)
            log(f'  {sid} {c} dropped: the buffer')
            state[c]['i'] = None
            want = {s: x for s, x in want.items() if x != c}
            continue
        rows = care_qa.species_check(out, base, main, bones, tuple(int(s) for s in row['slots']))
        for c in todo:
            s = next(s for s, x in row['slots'].items() if x == c)
            r, st, g = rows[int(s)], state[c], row['gain'][c]
            hard = [k for k in r['keys'] if k not in ('pair', 'distinct')]
            d = r['final']['idle_dist'] if r.get('final') else 0
            log(f'  {sid} gain {g} {c}: d={d:.3f} {"; ".join(r["flags"])}')
            if not hard and d >= TARGET:
                ok[c] = g
                continue
            if not hard and d >= care_qa.IDLE_DIST:
                st['best'] = g
            st['ladder'] = st['ladder'] or (DOWN if hard else UP)
            if (st['ladder'] is UP) == bool(hard) or st['i'] + 1 >= len(st['ladder']):
                st['i'] = None                              # no further step helps: the best seen, if any
                if st.get('best'):
                    ok[c] = st['best']
            else:
                st['i'] += 1
    gain = ok
    use = {s: c for s, c in want.items() if c in ok}
    row['gain'] = {c: g for c, g in gain.items() if g != 1.0 and c in use.values()}
    for _ in range(len(use)):
        row['slots'] = dict(use)
        out, rep = _apply(final, bones, row, log)
        if out is None:
            break
        rows = care_qa.species_check(out, base, main, bones, tuple(int(s) for s in use))
        close = [(s, f) for s in use for k, f in zip(rows[int(s)]['keys'], rows[int(s)]['flags']) if k == 'pair']
        if not close:
            break
        # the condition latest in SHARE_ORDER among the close pairs plays the earlier one's program
        worst = max(close, key=lambda sf: SHARE_ORDER.index(use[sf[0]]))[0]
        other = int(next(f for s, f in close if s == worst).rsplit(' ', 1)[1])
        log(f'  {sid} slot {worst} ({use[worst]}) shares slot {other} ({use[str(other)]})')
        use[worst] = use[str(other)]
    row['slots'] = use
    row['gain'] = {c: g for c, g in row['gain'].items() if c in use.values()}
    if not row['gain']:
        del row['gain']
    if not use:
        return row, None, None, None
    out, rep = _apply(final, bones, row, log)
    if out is None:
        return row, None, None, None
    rows = care_qa.species_check(out, base, main, bones, tuple(int(s) for s in use))
    return row, out, rep, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('id', type=int)
    ap.add_argument('final')
    ap.add_argument('main')
    ap.add_argument('base', nargs='?')
    ap.add_argument('--slots', nargs='*', type=int, default=[1, 18])
    ap.add_argument('--body')
    ap.add_argument('--compact', action='store_true')
    ap.add_argument('--out')
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    rd = lambda p: open(p, 'rb').read() if p else None  # noqa: E731
    row, out, rep, rows = plan(a.id, rd(a.final), rd(a.main), rd(a.base), a.slots, a.body, compact=a.compact)
    print(json.dumps({k: v for k, v in row.items() if k != 'parents'}))
    print(rep)
    for s, r in rows.items():
        if s == 'buffer':
            print(f'buffer: resident {r["resident"]} B, fits {r["fits"]}')
        else:
            print(f'slot {s}: {r["verdict"]} d={r.get("final", {}).get("idle_dist", 0):.3f} body={r.get("final", {}).get("body_off", 0):.0f} ' + '; '.join(r['flags'] + r['notes']))
    if a.out:
        Path(a.out).write_bytes(out)
    if a.write:
        man = care_idles.rows()
        man[str(a.id)] = row
        care_idles.MANIFEST.write_text(json.dumps(man, indent=1, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
