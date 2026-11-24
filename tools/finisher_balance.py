"""Check the unique finishers of the imported species against the DW1 finisher bands.

Reads content/finishers/imports.json and compares every entry with the native finishers of
the same level, using the battle formula (Off + P) * m / 30 (docs/reference/combat.md):
Off is the middle of the level's offense band, m the type factor averaged over every
species' specialties. A status adds its chance times a weight, an area hit counts 1.3 times.

    python3 -m tools.finisher_balance            # table and problems; exit 1 on a problem
    python3 -m tools.finisher_balance --json out.json
"""
import argparse
import glob
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'content/finishers/imports.json'
ELEMENTS = ['fire', 'battle', 'air', 'nature', 'ice', 'mech', 'filth', 'dark', 'light', 'water']
STATUS_NAMES = {0: None, 1: 'poison', 2: 'confusion', 3: 'stun', 4: 'flatten'}
STATUS_WEIGHT = {'poison': 0.15, 'confusion': 0.15, 'stun': 0.25, 'flatten': 0.25}
STATUS_CHANCE_MAX = 20
AREA_WEIGHT = 1.3          # DW1 fights are mostly one enemy, sometimes two or three
TOLERANCE = 0.10           # an entry may sit 10 % outside the natives' in-band range
BUFF_TOTAL_MAX = 70        # Full Potential gives 55 % in total
HEAL_MAX = 25
FIRST_FINISHER, LAST_FINISHER = 58, 112
LEVELS = ['rookie', 'champion', 'ultimate', 'mega']
# Range class, squared distance and iframes per kind: what the battle reads from the move.
KINDS = {
    'shot': (2, 360000), 'thrown': (2, 360000), 'rain': (2, 360000), 'breath': (2, 90000),
    'beam': (2, 640000), 'dash': (2, 160000), 'melee': (1, 0), 'area': (3, 160000), 'buff': (4, 0),
}


def load_json(path):
    return json.loads(Path(path).read_text())


def bands():
    table = load_json(ROOT / 'content/tables/species-mode-balance.json')['bands']
    out = {}
    for level in LEVELS:
        lo, hi = table[level]['finisher_power']
        if level == 'champion':
            lo = 130   # 100 is the filth-only Party time; ordinary Champions start at 130
        out[level] = dict(power=(lo, hi), offense=sum(table[level]['targets']['offense']) / 2)
    return out


def species_table():
    return {s['id']: s for s in (load_json(f) for f in glob.glob(str(ROOT / 'content/species/*.json')))}


def mean_factor(element, species):
    """Average type factor of an element over every species' three specialties (empty = 10)."""
    factors = load_json(ROOT / 'content/tables/type-factors.json')
    if isinstance(factors, dict):
        factors = factors['typeFactors']
    row = factors[ELEMENTS.index(element)]
    totals = []
    for s in species.values():
        specs = [x for x in (s.get('specialties') or []) if x][:3]
        if not specs:
            continue
        totals.append(sum(row[ELEMENTS.index(x)] for x in specs) + 10 * (3 - len(specs)))
    return sum(totals) / len(totals)


def score(power, element, status, chance, area, offense, factor):
    value = (offense + power) * factor[element] / 30
    if status:
        value *= 1 + chance / 100 * STATUS_WEIGHT[status]
    if area:
        value *= AREA_WEIGHT
    return value


def natives(species, imports, band, factor):
    """Same-level native finishers inside their band, with species mode scalars applied."""
    techniques = {t['name']: t for t in (load_json(f) for f in glob.glob(str(ROOT / 'content/techniques/*.json')))}
    out = {level: [] for level in LEVELS}
    for sid, s in species.items():
        if sid >= 180 or sid in imports or s.get('level') not in out:
            continue
        names = [t for t in (s.get('techniques') or []) if isinstance(t, str)]
        t = techniques.get(names[-1].split(' (')[0]) if names else None
        if not t or not FIRST_FINISHER <= t['id'] <= LAST_FINISHER:
            continue
        mode = s.get('finisher') or {}
        power = mode.get('power', t['power'])
        element = ELEMENTS[mode['element']] if isinstance(mode.get('element'), int) else (
            mode.get('element') or t['element'])
        if isinstance(element, int):
            element = ELEMENTS[element]
        element = element.lower()
        lo, hi = band[s['level']]['power']
        row = dict(species=s['name'], technique=t['name'], power=power, element=element,
                   in_band=lo <= power <= hi, area=t.get('range') == 3)
        row['score'] = score(power, element, None, 0, row['area'], band[s['level']]['offense'], factor)
        out[s['level']].append(row)
    return out


def native_shapes():
    """What DW1's own techniques use: (range, distance, iframes) and which ranges need a target.

    Finishers come first; the buff class (range 4) only exists among the learnable techniques.
    """
    move, target = set(), set()
    for t in (load_json(f) for f in glob.glob(str(ROOT / 'content/techniques/*.json'))):
        if t['id'] > LAST_FINISHER or (t['range'] != 4 and t['id'] < FIRST_FINISHER):
            continue
        move.add((t['range'], t['distance'], t['iframes']))
        target.add((t['range'], bool(t.get('unk3', 0) & 1)))
    move |= {(4, 0, 1)}   # buffs ignore distance and iframes
    target.add((4, False))
    return dict(move=move, target=target)


def check(data=None):
    data = data or load_json(DATA)
    species = species_table()
    band = bands()
    factor = {e: mean_factor(e, species) for e in ELEMENTS}
    entries = data['finishers']
    native = natives(species, {e['species'] for e in entries}, band, factor)
    native_names = {t['name'].lower() for t in (load_json(f) for f in glob.glob(str(ROOT / 'content/techniques/*.json')))}
    native_names |= {v.lower() for k, v in load_json(ROOT / 'text/ours/names.json').items()
                     if k.startswith('main.MOVE_NAMES.')}   # the names players see
    shapes = native_shapes()
    reference = {}
    for level in LEVELS:
        scores = [n['score'] for n in native[level] if n['in_band']]
        reference[level] = dict(min=min(scores), median=statistics.median(scores), max=max(scores), count=len(scores))
    problems, rows, seen = [], [], {}

    def bad(entry, why):
        problems.append(f"{entry['species']} {entry['species_name']}: {why}")

    for e in entries:
        s = species.get(e['species'])
        m = e['move']
        kind = e['behavior']['kind']
        level = e['level']
        if s is None:
            bad(e, 'no species file'); continue
        if s['level'] != level:
            bad(e, f"level {level} but the species is {s['level']}")
        specs = [x for x in s.get('specialties') or [] if x]
        if m['element'] not in specs:
            bad(e, f"element {m['element']} is not one of its specialties {specs}")
        if e['name'].lower() in native_names:
            bad(e, f"name {e['name']!r} is a DW1 technique name")
        if e['name'] in seen:
            bad(e, f"name {e['name']!r} already used by {seen[e['name']]}")
        seen[e['name']] = e['species_name']
        if not FIRST_FINISHER <= e['replaces']['id'] <= LAST_FINISHER:
            bad(e, f"replaces {e['replaces']['id']}, not a finisher id")
        if kind not in KINDS:
            bad(e, f'unknown kind {kind}'); continue
        rng, distance = KINDS[kind]
        if (m['range'], m['distance']) != (rng, distance):
            bad(e, f"{kind} needs range {rng} distance {distance}, has {m['range']} {m['distance']}")
        if (m['range'], m['distance'], m['iframes']) not in shapes['move']:
            bad(e, f"no DW1 technique has range {m['range']}, distance {m['distance']} and iframes {m['iframes']}")
        if ('T' in m['flags']) and (m['range'], True) not in shapes['target']:
            bad(e, f"no DW1 technique of range {m['range']} needs a target")
        if m['accuracy'] != 100 or m['mpCost'] != 40:
            bad(e, 'finishers keep accuracy 100 and the stored cost 40')
        status = STATUS_NAMES.get(m['status'], '?')
        if status == '?':
            bad(e, f"status {m['status']} unknown")
            status = None
        if bool(status) != bool(m['statusChance']) or m['statusChance'] > STATUS_CHANCE_MAX:
            bad(e, f"status chance {m['statusChance']} (1..{STATUS_CHANCE_MAX} with a status, 0 without)")
        lo, hi = band[level]['power']
        if kind == 'buff':
            buff = e.get('buff') or {}
            if m['power'] != 0:
                bad(e, 'a buff finisher has power 0')
            total = buff.get('offense', 0) + buff.get('defense', 0) + buff.get('speed', 0)
            if total > BUFF_TOTAL_MAX or buff.get('heal_percent', 0) > HEAL_MAX:
                bad(e, f'buff {total} % (max {BUFF_TOTAL_MAX}), heal {buff.get("heal_percent", 0)} % (max {HEAL_MAX})')
            if 'fallback' not in e:
                bad(e, 'a buff finisher needs a damaging fallback until the engine applies it')
            else:
                fb = e['fallback']['move']
                if not lo <= fb['power'] <= hi:
                    bad(e, f"fallback power {fb['power']} outside {lo}..{hi}")
            rows.append(dict(species=e['species_name'], level=level, name=e['name'], kind=kind, power=0,
                             element=m['element'], status=status, score=None, ratio=None))
            continue
        if not lo <= m['power'] <= hi:
            bad(e, f"power {m['power']} outside the {level} band {lo}..{hi}")
        if kind == 'area' and m['power'] != lo:
            bad(e, f"an area finisher takes the band floor {lo}, has {m['power']}")
        if status and m['power'] > (lo + hi) / 2:
            bad(e, f"power {m['power']} with a status: cap is the band middle {(lo + hi) / 2:g}")
        value = score(m['power'], m['element'], status, m['statusChance'], kind == 'area',
                      band[level]['offense'], factor)
        ref = reference[level]
        if not ref['min'] * (1 - TOLERANCE) <= value <= ref['max'] * (1 + TOLERANCE):
            bad(e, f"expected damage {value:.0f} outside the native {level} range "
                   f"{ref['min']:.0f}..{ref['max']:.0f} (+-{TOLERANCE:.0%})")
        rows.append(dict(species=e['species_name'], level=level, name=e['name'], kind=kind, power=m['power'],
                         element=m['element'], status=status, score=round(value, 1),
                         ratio=round(value / ref['median'], 2)))
    return dict(problems=problems, rows=rows, reference=reference, natives=native,
                factor={k: round(v, 2) for k, v in factor.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    result = check()
    for level in LEVELS:
        ref = result['reference'][level]
        mine = [r for r in result['rows'] if r['level'] == level and r['score']]
        print(f"{level:9} natives {ref['count']:3} expected {ref['min']:.0f}..{ref['max']:.0f} (median {ref['median']:.0f}); "
              f"imports {len(mine)} expected {min(r['score'] for r in mine):.0f}..{max(r['score'] for r in mine):.0f}")
    if args.json:
        args.json.write_text(json.dumps(result, indent=1) + '\n')
    for p in result['problems']:
        print('PROBLEM', p)
    print(f"{len(result['rows'])} finishers checked; {len(result['problems'])} problems")
    return 1 if result['problems'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
