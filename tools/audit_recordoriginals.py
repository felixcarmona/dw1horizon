#!/usr/bin/env python3
"""Inspect plain MD3 ADD runs for exact game-data overlap (16-byte audit floor).

No decoded target data is stored in the report. ADD boundaries are preserved:
concatenating separate runs would invent matches that are not stored contiguously.
"""
import argparse
import json
from pathlib import Path
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.models import delta as D
from tools import recordoriginals as R


def literals(delta):
    if delta[:5] != b'MD3\0\0':
        raise ValueError('expected plain MD3')
    count, p = D._rv(delta, 5)
    for _ in range(count): _, p = D._rv(delta, p)
    _, p = D._rv(delta, p)
    body = zlib.decompress(delta[p + 32:])
    count, p = D._rv(body, 0)
    size, p = D._rv(body, p)
    ops, adds = body[p:p + size], body[p + size:]
    pos = used = 0
    runs = []
    for _ in range(count):
        add, pos = D._rv(ops, pos)
        _, pos = D._rv(ops, pos)
        _, pos = D._rv(ops, pos)
        if add: runs.append(adds[used:used + add])
        used += add
    if pos != len(ops) or used != len(adds):
        raise ValueError('invalid operations')
    return runs


def audit(corpus, provider=None):
    records, index = [], {}
    for row in R.records():
        for kind in ('mmd', 'tim'):
            if kind not in row: continue
            record = row[kind]
            target = R.decode(record, provider=provider)
            runs = literals((R.ROOT / record['delta']).read_bytes())
            own = R.sources(record, provider=provider)
            own_windows = {source[p:p + 16] for source in own for p in range(len(source) - 15)}
            source_matches = sum(1 for run in runs for p in range(len(run) - 15)
                                 if run[p:p + 16] in own_windows)
            rid = len(records)
            records.append(dict(id=row['id'], kind=kind, delta=record['delta'],
                                delta_bytes=(R.ROOT / record['delta']).stat().st_size,
                                target_bytes=len(target), literal_bytes=sum(map(len, runs)),
                                literal_runs=len(runs), source_match_windows=source_matches, max_game_match=0, matches=[]))
            for run in runs:
                for p in range(len(run) - 15):
                    index.setdefault(run[p:p + 16], []).append((rid, run, p))
    files = 0
    for path in sorted(corpus):
        data = path.read_bytes(); files += 1
        seen = set()
        for p in range(len(data) - 15):
            key = data[p:p + 16]
            if key not in index or key in seen: continue
            seen.add(key)
            for rid, run, q in index[key]:
                # Find all occurrences: a later one may extend farther.
                pos = data.find(key)
                while pos >= 0:
                    n = 16
                    while q + n < len(run) and pos + n < len(data) and run[q + n] == data[pos + n]: n += 1
                    rec = records[rid]
                    if n > rec['max_game_match']:
                        rec['max_game_match'] = n
                        rec['matches'] = [dict(file=str(path.relative_to(R.ROOT)) if path.is_relative_to(R.ROOT) else str(path), offset=pos, bytes=n, distinct_values=len(set(run[q:q+n])))]
                    pos = data.find(key, pos + 1)
    return dict(format='plain MD3', minimum_match_bytes=16, corpus_files=files,
                deltas=len(records), delta_bytes=sum(r['delta_bytes'] for r in records),
                target_bytes=sum(r['target_bytes'] for r in records),
                literal_bytes=sum(r['literal_bytes'] for r in records),
                source_match_windows=sum(r['source_match_windows'] for r in records), files=records)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from', dest='from_dir', type=Path, help='derive output containing source-games')
    p.add_argument('--corpus', type=Path, action='append', help='corpus folder (repeatable; default extracted/CHDAT)')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--check', action='store_true', help='fail if any ADD run retains a 16-byte game-data match')
    a = p.parse_args()
    from tools.derive.steps.species import species_tools
    from tools.derive.importers import source_context
    from tools.recordimports import Sources
    from tools.derive import crmath, pysum
    games = (a.from_dir or R.ROOT / 'build/everything') / 'source-games'
    provider = Sources(games, R.ROOT / 'build/record-audit-work')
    crmath.install(); pysum.install()
    try:
        with species_tools(), source_context(games):
            report = audit((f for base in (a.corpus or [R.ROOT / 'extracted/CHDAT'])
                            for f in base.rglob('*') if f.is_file()), provider)
    finally:
        crmath.uninstall(); crmath.clear(); pysum.uninstall()
    a.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{report["deltas"]} plain deltas, {report["delta_bytes"]} B; {report["corpus_files"]} corpus files')
    for row in report['files']:
        if row['max_game_match']: print(row['id'], row['kind'], row['max_game_match'], row['matches'])
    if a.check and any(row['max_game_match'] or row['source_match_windows'] for row in report['files']):
        raise SystemExit('record-original delta audit: game bytes must be copies from declared sources')


if __name__ == '__main__':
    main()
