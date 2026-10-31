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
COUNT = 35  # uint16 species ids
WEIGHTS = COUNT * 2  # 63 sparse weight bytes
CELLS = WEIGHTS + 63  # 45 cell indices
VANILLA_CELLS = CELLS + 45  # 45 more, read with NEW DIGIMON off
SIZE = VANILLA_CELLS + 45 + 1  # one padding byte
# Partner rookies that reuse another species' model: they are reached by evolution, never as a quiz result.
RECOLOURS = {
    71: 'SnowAgumon', 74: 'Dokunemon', 82: 'Psychemon', 93: 'Muchomon',
    96: 'Tsukaimon', 233: 'RedOtamamon', 256: 'VioletElecmon',
}


# These new rookies have Baby II routes but no quiz slot in the fixed 35-row table.
EVOLUTION_ONLY = {263: 'Mushroomon', 283: 'Syakomon'}

def load():
    return json.loads((ROOT / 'content/tables/new-game.json').read_text())['newGame']


def validate(data):
    starters = data['starters']
    species = [json.loads(p.read_text()) for p in (ROOT / 'content/species').glob('*.json')]
    pool = {s['id'] for s in species if s.get('level') == 'rookie' and 'partner' in s}
    vanilla = {s['id'] for s in species if s.get('vanilla')} & set(starters)
    if len(starters) != COUNT or len(set(starters)) != COUNT or set(starters) != pool - set(RECOLOURS) - set(EVOLUTION_ONLY):
        raise ValueError(f'starters must contain each of the {COUNT} selected partner rookies exactly once')
    if any(type(s) is not int or not 0 <= s <= 65535 for s in starters):
        raise ValueError('starter ids must be uint16')
    quiz = data['quiz']
    if set(quiz) != {'weights', 'cells', 'vanillaCells'}:
        raise ValueError('quiz requires weights, cells and vanillaCells only')
    weights, cells, vanilla_cells = quiz['weights'], quiz['cells'], quiz['vanillaCells']
    if len(weights) != 7 or any(len(q) != 3 for q in weights):
        raise ValueError('quiz must have seven questions with three answers each')
    for q in weights:
        for answer in q:
            if not isinstance(answer, dict) or not 1 <= len(answer) <= 3:
                raise ValueError('each answer needs one to three weighted axes')
            if any(axis not in AXES or type(w) is not int or not 1 <= w <= 15
                   for axis, w in answer.items()):
                raise ValueError('unknown axis or weight outside 1..15')
    if len(cells) != 45 or any(type(i) is not int or not 0 <= i < COUNT for i in cells):
        raise ValueError('cells must be 45 valid starter indices')
    if set(cells) != set(range(COUNT)):
        raise ValueError('each pool species must have a cell')
    if len(vanilla_cells) != 45 or any(type(i) is not int or not 0 <= i < COUNT for i in vanilla_cells):
        raise ValueError('vanillaCells must be 45 valid starter indices')
    if {starters[i] for i in vanilla_cells} != vanilla:
        raise ValueError('vanillaCells must hold every vanilla starter and nothing else')
    for table in (cells, vanilla_cells):
        if starters[table[9]] != 3 or starters[table[4]] != 17:
            raise ValueError('Agumon and Gabumon must keep their fixed cells')


def pack(data):
    validate(data)
    out = bytearray(struct.pack(f'<{COUNT}H', *data['starters']))
    for question in data['quiz']['weights']:
        for answer in question:
            row = [(AXES.index(axis) << 4) | answer[axis] for axis in AXES if axis in answer]
            out.extend(row + [0] * (3 - len(row)))
    out.extend(data['quiz']['cells'])
    out.extend(data['quiz']['vanillaCells'])
    out.extend(b'\0')
    assert len(out) == SIZE
    return bytes(out)


def unpack(raw):
    starters = list(struct.unpack_from(f'<{COUNT}H', raw))
    weights = []
    for q in range(7):
        question = []
        for a in range(3):
            question.append({AXES[b >> 4]: b & 15 for b in raw[WEIGHTS + q*9 + a*3:WEIGHTS + 3 + q*9 + a*3] if b})
        weights.append(question)
    return dict(starters=starters, quiz=dict(weights=weights, cells=list(raw[CELLS:CELLS + 45]),
                                                 vanillaCells=list(raw[VANILLA_CELLS:VANILLA_CELLS + 45])))


def result(data, answers, new_digimon=True):
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
    return data['quiz']['cells' if new_digimon else 'vanillaCells'][cell]


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
    vanilla = collections.Counter(data['starters'][result(data, path, False)]
                                  for path in itertools.product(range(3), repeat=7))
    if not all(0.09 <= n / 2187 <= 0.13 for n in vanilla.values()):
        raise ValueError(f'NEW DIGIMON off outside 9%..13%: {vanilla}')
    for name, seen, total in (('new digimon on', counts, COUNT), ('new digimon off', vanilla, 9)):
        print(f'{name}: 2187 paths; {len(seen)}/{total} starters reached; '
              f'min {min(seen.values())}/2187 ({100*min(seen.values())/2187:.4f}%); '
              f'max {max(seen.values())}/2187 ({100*max(seen.values())/2187:.4f}%)')
    return counts


if __name__ == '__main__':
    check(load())
