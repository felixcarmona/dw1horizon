#!/usr/bin/env python3
"""Exact budget-shop policy search and reproducible Monte Carlo balance proof.

Prices and budgets use ten-percent steps. Profits use five-bit units. NumPy is
needed for the goal-aware dynamic program and the 200,000-shift validation.
Run: python3 tools/monochromon_shop.py --shifts 200000
"""
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
import argparse
import json
import numpy as np

SPECIES = ('Goblimon', 'Gotsumon', 'Weedmon', 'Muchomon')
RANGES = ((3, 5), (0, 3), (-1, 2), (-2, 5))
WEIGHTS = np.array((3, 3, 2, 1)) / 9
DECK = (8, 9, 3)
MULTIPLIERS = (1, 6, 20)
GOAL = 2560
MIDDLE = 1792
HALFWAY = 1280
DROP = 1
# A middle budget can produce either face; the others use broad half bands.
OVERLAP = (1, 0, 0, 0)
FACE_NOISE = (0., .25, 0., 0.)
PRICES = tuple(range(-3, 6))


def outcome(first, second, budget):
    """Sold price, or None. Rejection always reduces the budget before retry."""
    if first <= budget:
        return first
    if first - budget <= 2 and second <= budget - DROP:
        return second
    return None


def profit(price, item):
    return 0 if price is None else 5 * MULTIPLIERS[item] * (price + 3)


def face_probability(species, index):
    """Probability of the happy arrival face, conditional on the budget index."""
    lo, hi = RANGES[species]
    split = (hi - lo + 1) // 2
    if OVERLAP[species] and index == split:
        return .5
    high = float(index >= split + OVERLAP[species])
    return FACE_NOISE[species] + high * (1 - 2 * FACE_NOISE[species])


def cells(species, hint):
    lo, hi = RANGES[species]
    if not hint:
        return [(None, 1., np.arange(lo, hi + 1), np.ones(hi-lo+1)/(hi-lo+1))]
    out = []
    for face in (0, 1):
        likelihood = np.array([face_probability(species, i) if face else
                               1-face_probability(species, i) for i in range(hi-lo+1)])
        out.append((face, likelihood.sum()/(hi-lo+1), np.arange(lo, hi+1), likelihood/likelihood.sum()))
    return out


@lru_cache(None)
def actions(species, face=None):
    """All distinct profit distributions not dominated by another offer pair.

    First-order stochastic dominance is safe for every increasing goal utility;
    this prunes the exhaustive search without assuming expected-profit play.
    """
    _, _, budgets, weights = next(c for c in cells(species, face is not None) if c[0] == face)
    rows = []
    for a, b in product(PRICES, repeat=2):
        row = np.zeros(9)
        for x, w in zip(budgets, weights):
            sold = outcome(a, b, x)
            row[0 if sold is None else sold+3] += w
        if not any(np.allclose(row, r) for _, r in rows):
            rows.append(((a, b), row))
    kept = [(ab, r) for ab, r in rows if not any(
        np.all(np.cumsum(s) <= np.cumsum(r)+1e-12) and
        np.any(np.cumsum(s) < np.cumsum(r)-1e-12) for _, s in rows)]
    return sorted(kept, key=lambda ar: -np.dot(ar[1], np.arange(9)))


def fixed_probability(table, goal=GOAL, deck=DECK):
    """Exact convolution, integrating species independently for each deck card."""
    pmf = np.zeros(9)
    for s, (a, b) in enumerate(table):
        lo, hi = RANGES[s]
        for x in range(lo, hi+1):
            sold = outcome(a, b, x)
            pmf[0 if sold is None else sold+3] += WEIGHTS[s]/(hi-lo+1)
    dist = np.array([1.])
    for mult, count in zip(MULTIPLIERS, deck):
        row = np.zeros(8*mult+1)
        row[::mult] = pmf
        for _ in range(count):
            dist = np.convolve(dist, row)[:(goal+4)//5]
    return float(np.clip(1-dist.sum(), 0, 1))


def best_fixed(goal=GOAL, deck=DECK):
    """Exhaust every undominated species table, maximizing recruitment chance."""
    return max(((fixed_probability(t, goal, deck), t) for t in
                product(*[[ab for ab, _ in actions(s)] for s in range(4)])), key=lambda vt: vt[0])


@dataclass
class Optimal:
    chance: float
    choices: dict
    hint: bool
    goal: int


def optimal(hint=True, goal=GOAL, deck=DECK):
    """Bellman optimum: remaining deck, visible total, species and arrival face.

    The second offer is included in the pair: every retry gives the same public
    information (overshoot by 10 or 20), so no private information is assumed.
    """
    top = (goal+4)//5
    totals = np.arange(top+1)
    choice = {}
    @lru_cache(None)
    def value(counts):
        if sum(counts) == 0:
            return (totals >= top).astype(float)
        result = np.zeros(top+1)
        for item, count in enumerate(counts):
            if count == 0:
                continue
            nxt = list(counts); nxt[item] -= 1; nxt = tuple(nxt)
            following = value(nxt)
            shifted = np.array([following[np.minimum(totals+g*MULTIPLIERS[item], top)] for g in range(9)])
            expected = np.zeros(top+1)
            for s in range(4):
                for face, probability, _, _ in cells(s, hint):
                    candidates = actions(s, face)
                    values = np.array([row @ shifted for _, row in candidates])
                    indices = values.argmax(axis=0)
                    expected += WEIGHTS[s]*probability*values[indices, totals]
                    choice[(nxt, item, s, face)] = np.array([ab for ab, _ in candidates], dtype=np.int8)[indices]
            result += count/sum(counts)*expected
        return result
    chance = float(value(tuple(deck))[0])
    value.cache_clear()
    return Optimal(chance, choice, hint, goal)


def simulate(shifts=200000, seed=49, opt=None, table=None, goal=GOAL, deck=DECK):
    """Shuffle without replacement, then draw species, budget and face per visit."""
    rng = np.random.default_rng(seed)
    counts = np.tile(deck, (shifts, 1))
    total = np.zeros(shifts, dtype=np.int32)
    share = np.zeros(3, dtype=np.int64)
    first_offers = set()
    leaves = 0
    for _ in range(sum(deck)):
        draw = (rng.random(shifts)*counts.sum(axis=1)).astype(int)
        item = (draw[:,None] >= counts.cumsum(axis=1)).sum(axis=1)
        counts[np.arange(shifts), item] -= 1
        species = rng.choice(4, shifts, p=WEIGHTS)
        low = np.array([r[0] for r in RANGES])[species]
        width = np.array([b-a+1 for a,b in RANGES])[species]
        index = (rng.random(shifts)*width).astype(int)
        budget = low + index
        prob = np.array([face_probability(s, i) for s,i in zip(species,index)])
        face = (rng.random(shifts) < prob).astype(int)
        if opt is None:
            pairs = np.array(table, dtype=np.int8)[species]
        else:
            pairs = np.empty((shifts,2), dtype=np.int8)
            # Group only by the small discrete deck/species/face state.
            codes = np.column_stack((counts, item, species, face if opt.hint else np.zeros(shifts)))
            unique, inverse = np.unique(codes, axis=0, return_inverse=True)
            for k, row in enumerate(unique):
                mask = inverse == k
                a,b,c,it,s,f = map(int,row)
                pairs[mask] = opt.choices[((a,b,c),it,s,f if opt.hint else None)][np.minimum(total[mask]//5,(goal+4)//5)]
            first_offers.update(map(int,np.unique(pairs[total < goal,0])))
        a,b = pairs.T
        sold = np.where(a<=budget, a, np.where((a-budget<=2)&(b<=budget-DROP), b, -4))
        gain = (sold+3).clip(0)*np.array(MULTIPLIERS)[item]*5
        total += gain
        leaves += int((sold == -4).sum())
        for it in range(3):
            share[it] += gain[item==it].sum()
    return dict(shifts=shifts, seed=seed, recruit_percent=float((total>=goal).mean()*100),
                mean_profit=float(total.mean()), profit_share_percent=(share/share.sum()*100).tolist(),
                leave_percent=leaves/(shifts*sum(deck))*100, first_offers=sorted(first_offers))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--shifts', type=int, default=200000)
    p.add_argument('--seed', type=int, default=49)
    args = p.parse_args()
    fixed_chance, table = best_fixed()
    print(json.dumps(dict(best_fixed=table, exact_percent=100*fixed_chance)), flush=True)
    for name, t in [('list', [(0,0)]*4), ('simple', [(2,0)]*4), ('best_fixed', table)]:
        print(json.dumps(dict(policy=name, exact_percent=100*fixed_probability(t),
                              **simulate(args.shifts,args.seed,table=t))), flush=True)
    opt = optimal()
    print(json.dumps(dict(policy='goal_and_face', exact_percent=opt.chance*100,
                          **simulate(args.shifts,args.seed,opt=opt))), flush=True)


if __name__ == '__main__':
    main()
