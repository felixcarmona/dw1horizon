#!/usr/bin/env python3
"""Which Digimon types each technique's effect knows, and where it starts from.

Every technique chunk of ETCHI/EFEDAT.EFE (chunk i = technique i, 0x5000 bytes) holds
one or more tables of {i16 type, i16 bone, i16 x, y, z} rows ended by a negative type:
checkTechCompatibility (btl/std/vs *_effect.c) looks the attacker's original type up
there and drops the effect when it is missing (see getModTechBoneOffset /
getModDonorTechBoneOffset in efe.c for the mod-side fallbacks). The tables sit inside
the effect scripts and are found here by shape, so a table of one row can be a false
positive; real ones are usually long.

A species carried by its DIGI.DAT record (a new species, a record original) never loses an effect: without a row,
efe.c gives it the entity point of the row of the species closest to it in radius when most of the table's rows are
entity points (bone 0: punches, stings, clouds, areas), else its record's effectDefault (tools/species.py
effect_default: its own launch point, or "effect_origin_fallback").

Usage (from the repository root):
  python3 tools/efe-origins.py [TYPE ...]      rows of these types (all tables without)
  python3 tools/efe-origins.py 94 113 --min 2  only tables with at least 2 rows
  python3 tools/efe-origins.py --species 433 76  where each technique of these species starts, and why (row, donor,
                                                 entity, default; "DROPPED" = the clip plays and nothing hits)
"""
import argparse
import os
import re
import struct

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def names():
    out = {}                                   # the techniques' names (docs/data/techs.csv: id,name)
    for line in open(os.path.join(ROOT, 'docs/data/techs.csv')):
        m = re.match(r'(\d+),(.*)$', line.strip())
        if m:
            out.setdefault(int(m.group(1)), m.group(2).strip())
    return out


def tables(chunk):
    """(offset, rows) of every table of the chunk. Every 2-byte offset is tried (a table found by shape at a misaligned
    offset used to make the scan jump past the real table's first row: Giga Freeze lost 110 and 34, Blue Blaster 17,
    Pepper Breath 84); of the tables that end at one terminator the longest is kept (the others are its tails)."""
    found = {}
    for o in range(0x34, len(chunk) - 12, 2):
        rows, p = [], o
        while p + 10 <= len(chunk):
            t, b, x, y, z = struct.unpack_from('<hhhhh', chunk, p)
            if t < 0:
                break
            if not (0 < t < 180 and 0 <= b < 34 and max(abs(x), abs(y), abs(z)) < 3000):
                rows = None
                break
            rows.append((t, b, x, y, z))
            p += 10
        if rows and p + 2 <= len(chunk) and struct.unpack_from('<h', chunk, p)[0] < 0:
            if p not in found or o < found[p][0]:
                found[p] = (o, rows)
    for o, rows in sorted(found.values()):
        yield o, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('types', nargs='*', type=int)
    ap.add_argument('--min', type=int, default=1)
    ap.add_argument('--species', type=int, nargs='+')
    a = ap.parse_args()
    if a.species:
        return species_report(a.species)
    data = open(os.path.join(ROOT, 'extracted/ETCHI/EFEDAT.EFE'), 'rb').read()
    nm = names()
    want = set(a.types)
    for c in range(len(data) // 0x5000):
        chunk = data[c * 0x5000:(c + 1) * 0x5000]
        for off, rows in tables(chunk):
            if len(rows) < a.min or (want and not want & {r[0] for r in rows}):
                continue
            shown = [r for r in rows if not want or r[0] in want]
            print(f'{c:3d} {nm.get(c, "?"):24s} @{off:#06x} {len(rows):2d} rows: ' +
                  ' '.join(f'{t}:{b}({x},{y},{z})' for t, b, x, y, z in shown))


def species_report(ids):
    import sys
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import species as S
    sp = S.load_content(); O = S.originals(); techs = S.names('techs')
    for t in ids:
        s = sp[t]; et = s.get('effects_like', t); et = t if et is None or et < 0 else et
        rad = int(s['model'].get('radius', 150)); d, why = S.effect_default(s) if S.has_effect_record(s) else (None, '')
        print(f'{t} {s["name"]}: effects type {et}, radius {rad}' + (f', default {d} ({why})' if d else ', no record'))
        for m in [m for m in S.table_rows(s)['para']['moves'] if m != 0xFF]:
            how = S.technique_origin(s, m)
            if how == 'row':
                rs = S.efe_rows().get(m, {}).get(et)
                where = f'row {list(rs[0][1:])}' if rs else 'its own technique (table not found by shape)'
                eo = [e for e in s.get('effect_origins', []) if rs and e[0] == rs[0][1] and (e[1] == 'any' or tuple(e[1:4]) == rs[0][2:])]
                if eo: where += f' -> {eo[0][4:]} (effect_origins)'
            elif how == 'entity':
                main_ = max(S.efe_tables()[m], key=len)
                best = min((r for r in main_ if r[1] == 0), key=lambda r: abs(O.rec[r[0]]['para']['radius'] - rad))
                where = f'entity point {list(best[1:])} of type {best[0]} (radius {O.rec[best[0]]["para"]["radius"]})'
            elif how == 'default':
                where = f'its default {d}'
            elif how == 'donor':
                where = 'a C donor (efe.c MOD_DONOR_ENTRIES, content/tables/effect-donors.json)'
            else:
                where = 'DROPPED: the clip plays, nothing hits'
            print(f'   {m:3d} {techs.get(m, m):22s} {how or "-":8s} {where}')


if __name__ == '__main__':
    main()
