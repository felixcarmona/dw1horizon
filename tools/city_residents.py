"""Owned City roster, checked against recruit writes in every compiled story."""
import argparse
import json
from pathlib import Path
import struct
import re

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / 'content/tables/city-residents.json'
# Geko Swamp sets Otamamon's defeat flag for Misty Trees; it never moves to File City.
STORY_SPECIES = {109}
LEVELS = {'rookie': 3, 'champion': 4, 'ultimate': 5, 'mega': 6}


def residents(content=None):
    species = {s['id']: s for p in (ROOT / 'content/species').glob('*.json')
               for s in [json.loads(p.read_text())]}
    if content is not None:
        species.update(content)
    rows = json.loads(ROSTER.read_text())
    ids = [r['id'] for r in rows]
    if len(set(ids)) != len(ids) or any(not 0 <= i < 1024 or i not in species for i in ids):
        raise ValueError('City roster: unique, defined species ids below 1024 required')
    if any(species[i]['level'] not in LEVELS for i in ids):
        raise ValueError('City roster: residents must be Rookie or higher')
    points = lambda i: 1 if i in (11, 39, 53) else LEVELS[species[i]['level']] - 2
    if sum(map(points, ids)) > 255:
        raise ValueError('City roster: prosperity exceeds its saved byte')
    return sorted(rows, key=lambda r: (LEVELS[species[r['id']]['level']], r['id']))


def city_cell(row, content=None):
    """A City roster cell on the disc: id, level << 12 and 0x8000 when hidden. The tab draws every cell in its
    level's colour each frame: 20 records past the 16-slot species cache would read the disc all the time."""
    species = {s['id']: s for p in (ROOT / 'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
    species.update(content or {})
    return row['id'] | LEVELS[species[row['id']]['level']] << 12 | (0x8000 if row['hidden'] else 0)


def compiled_recruits(path):
    # Decode instructions, never search raw bytes: dialogue and dead padding can
    # contain the same bytes. Ordinary flags 312+ have unrelated meanings;
    # high species use the reserved recruit-bit operands of patch 0304.
    from tools.dws import bytecode, basebuild
    data = Path(path).read_bytes()
    # DG entry zero is unused disc residue; getScript(0) reads MAPHEAD instead.
    offsets = bytecode.container_entries(data)[1:] if bytecode.is_container(data) else [0, len(data)]
    ids = set()
    for lo, hi in zip(offsets, offsets[1:]):
        if lo == hi:
            continue
        script = data[lo:hi]
        lines, _ = basebuild.flow_text(script, str(path))
        for line in lines:
            match = re.match(r'\s*SET_TRIGGER (\d+)\b', line)
            if match:
                flag = int(match[1])
                if 200 <= flag < 312:
                    ids.add(flag - 200)
                elif 0x8070 <= flag < 0x8400:
                    ids.add(flag - 0x8000)
    return ids


def membership_bits():
    """The executable's 112 roster bits, generated only from the owned JSON."""
    data = bytearray(14)
    for row in residents():
        if row['id'] < 112:
            data[row['id'] // 8] |= 1 << (row['id'] % 8)
    return bytes(data)


CHALLENGES = ROOT / 'content/tables/resident-challenges.json'
CHALLENGE_HEAD = 10            # mod_rules.h MOD_CHALLENGE_ROWS: then one species a row
CHALLENGE_MAX = 72             # mod_rules.h MOD_CHALLENGE_MAX
CHALLENGE_BAG_LAST = 14        # the bag's saved wide registers end before w15 (Sukamon's backup)
CHALLENGE_STATS = {'max-sheet-or-partner': 0}
CHALLENGE_STAGES = {'same-or-lower': 0, 'any': 1}
CHALLENGE_POOLS = ('original', 'new')  # by species: CHALLENGE_NEW_FIRST and above is the new pool
CHALLENGE_NEW_FIRST = 112      # Horizon's own species: the original game's are 0-111


def challenge_rows(doc=None):
    """The rows of content/tables/resident-challenges.json, checked."""
    doc = doc or json.loads(CHALLENGES.read_text())
    rows = doc['residents']
    if len(rows) > CHALLENGE_MAX:
        raise ValueError(f'resident-challenges.json: {len(rows)} residents, at most {CHALLENGE_MAX}')
    roster = {r['id'] for r in residents()}
    for r in rows:
        if r['species'] not in roster:
            raise ValueError(f"resident-challenges.json: {r['name']} ({r['species']}) is not a city resident")
        pool = 'new' if r['species'] >= CHALLENGE_NEW_FIRST else 'original'
        if r.get('pool') != pool:
            raise ValueError(f"resident-challenges.json: {r['name']} ({r['species']}): pool must be {pool!r}")
    return rows


def challenge_sheet(row, species):
    """A row's floor stats: its species' `wild` sheet, or the row's own `base` for a species with none (the game's own
    residents: most have no wild sheet). Exactly one of the two."""
    w, base = species[row['species']].get('wild'), row.get('base')
    if (w is None) == (base is None):
        raise ValueError(f"resident-challenges.json: {row['name']}: give `base` only when its species has no `wild` stats")
    w = w or base
    if any(type(w.get(k)) is not int or not 1 <= w[k] <= 9999 for k in ('hp', 'mp', 'off', 'def', 'speed', 'brain')):
        raise ValueError(f"resident-challenges.json: {row['name']}: hp, mp, off, def, speed and brain 1..9999")
    return w


def challenge_table(doc=None):
    """MOD_CHALLENGE (mod_rules.h): the rule, the save numbers of both pools, then each row's species (its pool is the
    species: CHALLENGE_NEW_FIRST and above is the new one). The floor stats are not here: they are the site NPC's own
    (challenge_site_stats), which the battle raises to the partner's when those are higher."""
    doc = doc or json.loads(CHALLENGES.read_text())
    rule, save = doc['rule'], doc['save']
    v = [-1] * (CHALLENGE_HEAD + CHALLENGE_MAX)
    if rule['stats'] not in CHALLENGE_STATS:
        raise ValueError(f"{CHALLENGES.name}: stats must be one of {sorted(CHALLENGE_STATS)}")
    if not 0 <= rule['sheetPercent'] <= 1000 or not 0 <= rule['partnerPercent'] <= 1000:
        raise ValueError(f'{CHALLENGES.name}: sheetPercent and partnerPercent must be 0..1000 (the species sheet is the minimum)')
    v[0] = rule['partnerPercent']
    v[1] = 1 if rule['noItems'] else 0
    v[2] = CHALLENGE_STAGES[rule['stages']]
    v[3] = 1 if rule['noLateStep'] else 0
    v[4], v[5] = save['armedPstat'], save['bagWreg']
    if not 0 <= v[5] or v[5] + (-(-CHALLENGE_MAX // 16)) - 1 > CHALLENGE_BAG_LAST:
        raise ValueError(f'{CHALLENGES.name}: the bag takes {-(-CHALLENGE_MAX // 16)} saved wide registers from bagWreg, '
                         f'within w0-w{CHALLENGE_BAG_LAST}')
    v[6], v[7], v[8], v[9] = save['challengerVar'], save['triedFlag'], save['newChallengerVar'], save['newTriedFlag']
    if v[6] == v[8] or v[7] == v[9]:
        raise ValueError(f'{CHALLENGES.name}: the two pools need their own challenger var and tried flag')
    for i, r in enumerate(challenge_rows(doc)):
        v[CHALLENGE_HEAD + i] = r['species']
    return struct.pack(f'<{len(v)}h', *v)


# The residents whose challenge is fought by the very NPC of their recruit fight, with that fight's own stats: those
# stats are the challenge's floor too (writing the sheet there would change the recruit fight).
CHALLENGE_RECRUIT_STATS = ('Armadillomon', 'Candlemon', 'Datamon', 'Digmon', 'Knightmon', 'Kotemon', 'Mammothmon',
                           'Mushroomon', 'Phantomon', 'Pumpkinmon', 'Starmon', 'Triceramon')
NPC_STATS = (('hp', 'hp'), ('mp', 'mp'), ('offense', 'off'), ('defense', 'def'), ('speed', 'speed'), ('brain', 'brain'))


def challenge_site_stats(row, doc=None):
    """The stats a row's site NPC must declare (the challenge's floor): its sheet x (100 + sheetPercent) / 100, at most
    9999; None for the CHALLENGE_RECRUIT_STATS rows, whose NPC keeps its recruit fight's stats."""
    if row['name'] in CHALLENGE_RECRUIT_STATS:
        return None
    doc = doc or json.loads(CHALLENGES.read_text())
    species = {s['id']: s for p in (ROOT / 'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
    w, pc = challenge_sheet(row, species), doc['rule']['sheetPercent']
    return {k: min(9999, w[j] * (100 + pc) // 100) for k, j in NPC_STATS}


def extra_header():
    """Exact-sized compiled list; no extra resident storage for the current roster."""
    ids = sorted(r['id'] for r in residents() if r['id'] >= 112)
    return ('/* Generated from content/tables/city-residents.json. */\n'
            f'#define CITY_RESIDENTS_EXTRA_COUNT {len(ids)}\n'
            'static const uint16_t CITY_RESIDENTS_EXTRA[] = {' +
            ', '.join(map(str, ids or [0])) + '};\n')


def write_extra_header(tree):
    path = Path(tree) / 'src/main/city_residents_extra.h'
    # Old patch series need no generated input.
    if path.exists():
        data = extra_header()
        if path.read_text() != data:
            path.write_text(data)


def verify(paths, original=False):
    """One pass (DG + MAPHEAD): original high flags are unrelated legacy writes."""
    expected = {r['id'] for r in residents() if not original or r['id'] < 59}
    species = {s['id']: s for p in (ROOT / 'content/species').glob('*.json')
               for s in [json.loads(p.read_text())]}
    actual = set()
    for path in paths:
        actual.update(i for i in compiled_recruits(path)
                      if i not in STORY_SPECIES and (not original or i < 59) and (i not in species or species[i]['level'] in LEVELS))
    if expected != actual:
        raise ValueError(f'City roster disagrees with {"original" if original else "extended"} compiled story: '
                         f'unreachable {sorted(expected - actual)}, unlisted {sorted(actual - expected)}')
    return len(expected)


def verify_archive(data):
    """Check the optional City block without changing the v2 species record ABI."""
    sector = struct.unpack_from('<I', data, 0x38)[0]
    if not sector:
        raise ValueError('City block missing')
    start = sector * 2048
    rows = residents()
    count = struct.unpack_from('<H', data, start)[0]
    ids = struct.unpack_from(f'<{count}H', data, start + 2)
    expected = tuple(city_cell(r) for r in rows)
    if ids != expected:
        raise ValueError('City block roster differs from owned data')
    for k, row in enumerate(rows):
        if row['id'] <= 61:
            continue
        offset = start + (1 + k // 7) * 2048 + k % 7 * 288
        icon = data[offset:offset + 288]
        if len(icon) != 288 or not any(icon[32:]) or not any(icon[2:32]):
            raise ValueError(f'City icon missing for species {row["id"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--c-extra-header', type=Path, help='update a patched compiler tree before building')
    parser.add_argument('stories', nargs='*', type=Path, help='compiled DG.SCN or MAPHEAD.SCN')
    parser.add_argument('--original', action='store_true', help='check the original story (ids below 59)')
    args = parser.parse_args()
    if args.c_extra_header:
        write_extra_header(args.c_extra_header)
        return
    if not args.stories:
        parser.error('provide compiled stories or --c-extra-header')
    groups = {}
    for path in args.stories:
        groups.setdefault(path.parent, []).append(path)
    for folder, paths in groups.items():
        if len(paths) < 2:  # a pass is DG + MAPHEAD: a lone file is a build's intermediate, not a story
            continue
        original = args.original or 'base' in folder.parts
        print(f'City roster: {verify(paths, original)} residents match {folder} ({"original" if original else "extended"})')


if __name__ == '__main__':
    main()
