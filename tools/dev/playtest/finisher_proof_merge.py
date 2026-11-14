#!/usr/bin/env python3
"""Merge finisher_targets runs into docs/data/finisher-proof.json (species -> finisher id and enemy HP lost).

Usage: .venv/bin/python -m tools.dev.playtest.finisher_proof_merge DIGI.DAT RESULT_DIR...
Each RESULT_DIR holds result.json files, directly or one level down (one folder per species). Only runs that passed
(finisher played, enemy damaged, no self damage) are recorded, against the finisher id the DIGI.DAT record has.
'unproven' holds species whose finisher fails in the emulator and is not fixed yet (id -> reason), edited by hand.
tools/test_finisher_proof.py fails when a raisable species' finisher is in neither list.
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
    table = data.get('proven', {})
    for d in dirs:
        for dirpath, _, files in os.walk(d):
            if 'result.json' not in files: continue
            for run in json.load(open(os.path.join(dirpath, 'result.json'))):
                t = run.get('species')
                if t is None or not run.get('ok') or not 0 <= t < len(records): continue
                table[str(t)] = {'finisher': finisher_of(records[t]), 'enemy_damage': run['enemy_damage']}
    out = {'proven': {k: table[k] for k in sorted(table, key=int)}, 'unproven': data.get('unproven', {})}
    with open(PROOF, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(len(out['proven']), 'species recorded in', PROOF)


if __name__ == '__main__':
    main(sys.argv[1:])
