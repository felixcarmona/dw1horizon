#!/usr/bin/env python3
"""Validate and enumerate Jijimon's deterministic starter quiz (3**7 paths)."""
import collections
import itertools
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
AXES = ('battle', 'fire', 'ice', 'nature', 'air', 'vaccine', 'data', 'virus',
        'bold', 'calm', 'cunning')
GROUPS = ((0, 5), (5, 8), (8, 11))
SIZE = 196  # 43 uint16 species, 63 sparse weight bytes, 45 cell indices, 2 padding bytes


def load():
    return json.loads((ROOT / 'content/tables/new-game.json').read_text())['newGame']


def validate(data):
    starters = data['starters']
    pool = {s['id'] for p in (ROOT / 'content/species').glob('*.json')
            if (s := json.loads(p.read_text())).get('level') == 'rookie' and 'partner' in s}
    if len(starters) != 43 or len(set(starters)) != 43 or set(starters) != pool:
        raise ValueError('starters must contain each of the 43 partner rookies exactly once')
    if any(type(s) is not int or not 0 <= s <= 65535 for s in starters):
        raise ValueError('starter ids must be uint16')
    quiz = data['quiz']
    if set(quiz) != {'weights', 'cells'}:
        raise ValueError('quiz requires weights and cells only')
    weights, cells = quiz['weights'], quiz['cells']
    if len(weights) != 7 or any(len(q) != 3 for q in weights):
        raise ValueError('quiz must have seven questions with three answers each')
    for q in weights:
        for answer in q:
            if not isinstance(answer, dict) or not 1 <= len(answer) <= 3:
                raise ValueError('each answer needs one to three weighted axes')
            if any(axis not in AXES or type(w) is not int or not 1 <= w <= 15
                   for axis, w in answer.items()):
                raise ValueError('unknown axis or weight outside 1..15')
    if len(cells) != 45 or any(type(i) is not int or not 0 <= i < 43 for i in cells):
        raise ValueError('cells must be 45 valid starter indices')
    if set(cells) != set(range(43)):
        raise ValueError('each pool species must have a cell')
    if starters[cells[9]] != 3 or starters[cells[4]] != 17:
        raise ValueError('Agumon and Gabumon must keep their fixed cells')


def pack(data):
    validate(data)
    out = bytearray(struct.pack('<43H', *data['starters']))
    for question in data['quiz']['weights']:
        for answer in question:
            row = [(AXES.index(axis) << 4) | answer[axis] for axis in AXES if axis in answer]
            out.extend(row + [0] * (3 - len(row)))
    out.extend(data['quiz']['cells'])
    out.extend(b'\0\0')
    assert len(out) == SIZE
    return bytes(out)


def unpack(raw):
    starters = list(struct.unpack_from('<43H', raw))
    weights = []
    for q in range(7):
        question = []
        for a in range(3):
            question.append({AXES[b >> 4]: b & 15 for b in raw[86 + q*9 + a*3:89 + q*9 + a*3] if b})
        weights.append(question)
    return dict(starters=starters, quiz=dict(weights=weights, cells=list(raw[149:194])))


def result(data, answers):
    """Match modQuizResult: scores and last supporting question per axis, lower axis on a same-answer tie."""
    if len(answers) != 7 or any(type(a) is not int or not 0 <= a < 3 for a in answers):
        raise ValueError('expected seven answer indices in 0..2')
    scores, last = [0] * 11, [0] * 11
    for q, a in enumerate(answers):
        for axis, weight in data['quiz']['weights'][q][a].items():
            i = AXES.index(axis)
            scores[i] += weight
            last[i] = q + 1
    cell = 0
    for lo, hi in GROUPS:
        best = max(range(lo, hi), key=lambda i: (scores[i], last[i], -i))
        cell = cell * (hi - lo) + best - lo
    return data['quiz']['cells'][cell]


def check(data):
    validate(data)
    restored = unpack(pack(data))
    if restored != {k: data[k] for k in ('starters', 'quiz')}:
        raise ValueError('packed quiz does not round trip')
    counts = collections.Counter(data['starters'][result(data, path)]
                                 for path in itertools.product(range(3), repeat=7))
    for species in data['starters']:
        if not 0.005 <= counts[species] / 2187 <= 0.06:
            raise ValueError(f'species {species}: {counts[species]}/2187 outside 0.5%..6%')
    print(f'2187 paths; {len(counts)}/43 starters reached; '
          f'min {min(counts.values())}/2187 ({100*min(counts.values())/2187:.4f}%); '
          f'max {max(counts.values())}/2187 ({100*max(counts.values())/2187:.4f}%)')
    return counts


if __name__ == '__main__':
    check(load())
