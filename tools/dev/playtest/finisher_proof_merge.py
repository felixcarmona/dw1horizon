#!/usr/bin/env python3
"""Merge finisher_targets runs into docs/data/finisher-proof.json.

Usage: .venv/bin/python -m tools.dev.playtest.finisher_proof_merge DIGI.DAT RESULT_DIR...
Each RESULT_DIR holds result.json files, directly or one level down. A species is recorded under "proven" only when
every trial of the runs given for it passed (finisher played, enemy damaged, no self damage): {finisher, trials,
enemy_damage}. A species with a miss is left alone: say why in "conditional" (it hits, but only where the enemy stands;
the reason carries the numbers) or "unproven" (it never hit), both edited by hand (id -> reason).
tools/test_finisher_proof.py fails when a raisable species' finisher is in none of the three lists.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species  # noqa: E402

PROOF = os.path.join(ROOT, 'docs', 'data', 'finisher-proof.json')


def finisher_of(record):
    return next((m for m in record['para']['moves'] if 58 <= m <= 112), None)


def main(argv):
    digi, dirs = argv[0], argv[1:]
    _, _, records = species.read_archive(digi)
    data = json.load(open(PROOF)) if os.path.exists(PROOF) else {}
    proven = data.get('proven', {})
    runs = {}
    for d in dirs:
        for dirpath, _, files in os.walk(d):
            if 'result.json' not in files: continue
            for run in json.load(open(os.path.join(dirpath, 'result.json'))):
                t = run.get('species')
                if t is not None and 0 <= t < len(records): runs.setdefault(t, []).append(run)
    for t, rs in runs.items():
        if not all(r.get('ok') for r in rs): continue
        proven[str(t)] = {'finisher': finisher_of(records[t]), 'trials': len(rs),
                          'enemy_damage': min(r['enemy_damage'] for r in rs)}
    out = {'proven': {k: proven[k] for k in sorted(proven, key=int)},
           'conditional': data.get('conditional', {}), 'unproven': data.get('unproven', {})}
    with open(PROOF, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(len(out['proven']), 'species recorded in', PROOF)


if __name__ == '__main__':
    main(sys.argv[1:])
