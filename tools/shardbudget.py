#!/usr/bin/env python3
"""Evolution shard scratch budget (docs/mods/models.md, "Digivolution shard buffer").

The evolution scene (EVL overlay, EVL_buildShardSet) sheds the partner that evolves AWAY: one shard
set per bone 1..boneCount-1 whose objIndex != -1. Each piece writes into one bump-allocated scratch
that is never released during the sequence:
  6 * vern      the piece's vertices, transformed (EvlModelVertex, 3 x int16)
  6 * centers   one drift vector per primitive of mode 0x34/0x36 (walk +28 bytes) or 0x3C/0x3E (+36);
                any other mode stops the walk (the game does not advance its pointer)
So peak = sum over the pieces, whatever the random bone order. Slots: 30 shard sets, each alive for
32 ticks, one piece per event tick (EVENTS below).

  python3 tools/shardbudget.py [--limit BYTES] [--top N] [--json OUT]
    every original MMD (executable skeletons), the build's partner models (build/release/models) and
    every species of content/species/; --limit is the scratch size (5436 = the original
    EVL_D_80066274; patch 0079 makes it EVL_SHARD_SCRATCH_SIZE = 0x3000); "skipped" is the mean number of
    pieces a bounded build (patch 0062 rule: reserve 6 * (vern + primn)) drops over random orders.
"""
import argparse, glob, json, os, random, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mmd, species  # noqa: E402

ORIGINAL_SCRATCH = 0x153C
SLOTS = 30
LIFE = 32
VSIZE = 6
PARTNER_MODELS = {'TIRS-partner': 'TIRS', 'JURE-partner': 'JURE', 'SCUD-partner': 'SCUD', 'ICEM-partner': 'ICEM',
                  'INSE-partner': 'INSE', 'WARU-partner': 'WARU', 'VAND-partner': 'VAND', 'TONO-partner': 'TONO',
                  'MUGP': 'MUGE', 'JIJP': 'JIJI', 'ANLP': 'ANLG'}
_T = [0x00] + [0xff] * 15 + [0x01] + [0xff] * 9 + [0x02] + [0xff] * 7 + [0x03, 0xff, 0xff, 0xff, 0x04, 0xff, 0x05, 0xff,
                                                                         0x06, 0x00]
EVENTS = [0x6a] + [0x70 + i for i in range(0x9b - 0x70) if _T[i] < 0x80] + list(range(0x9b, 0x11c))


def pieces_of(data, skel):
    """[(bytes written, bytes reserved by the 0062 check, vern, primn, centers)] per shedding bone."""
    nobj = struct.unpack_from('<I', data, 16)[0]
    o0 = 20
    out = []
    for b in range(1, len(skel)):
        oi = skel[b][0]
        if oi == -1 or oi >= nobj:
            continue
        vt, vern, nt, norn, pt, primn, sc = struct.unpack_from('<IIIIIIi', data, o0 + 28 * oi)
        p, centers = o0 + pt, 0
        for _ in range(primn):
            mode = data[p + 3] if p + 4 <= len(data) else 0
            if mode in (0x34, 0x36):
                centers += 1; p += 28
            elif mode in (0x3c, 0x3e):
                centers += 1; p += 36
            else:
                break
        out.append((VSIZE * (vern + centers), VSIZE * (vern + primn), vern, primn, centers))
    return out


def slots_peak(n):
    alive, peak, fail = [], 0, 0
    for t in EVENTS[:n]:
        alive = [e for e in alive if e > t]
        if len(alive) >= SLOTS:
            fail += 1; continue
        alive.append(t + LIFE + 1)    # one tick of margin on the creation tick
        peak = max(peak, len(alive))
    return peak, fail


def skipped(pieces, limit, trials=400, seed=1):
    rnd = random.Random(seed)
    ps, tv = list(pieces), sum(p[2] for p in pieces) or 1
    sk = lost = 0
    for _ in range(trials):
        rnd.shuffle(ps)
        out = 0
        for real, res, vern, primn, c in ps:
            if out + res > limit:
                sk += 1; lost += vern
            else:
                out += real
    return sk / trials, lost / trials / tv


def models():
    e = mmd.exe()
    by_name = {os.path.splitext(os.path.basename(f))[0]: f for f in mmd.all_mmds()}
    for t in range(180):
        f = by_name.get(e.names[t])
        if f and e.bone_count[t] > 0:
            yield 'orig', t, e.name(t), f, e.skeleton[t]
    for fn, base in PARTNER_MODELS.items():
        f = os.path.join(ROOT, 'build/release/models', fn + '.MMD')
        if os.path.exists(f) and base in e.names:
            t = e.names.index(base)
            yield 'partner', t, f'{e.name(t)} ({fn})', f, e.skeleton[t]
    for t, d in sorted(species.imports().items()):
        yield 'import', t, d['name'], species.species_model(d)[1], species.species_record(d)['bones']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--limit', type=lambda s: int(s, 0), default=ORIGINAL_SCRATCH)
    ap.add_argument('--top', type=int, default=30)
    ap.add_argument('--json')
    a = ap.parse_args()
    rows = []
    for kind, t, name, f, skel in models():
        ps = pieces_of(open(f, 'rb').read(), skel)
        peak, fail = slots_peak(len(ps))
        sk, lost = skipped(ps, a.limit)
        rows.append(dict(kind=kind, type=t, name=name, bones=len(skel), pieces=len(ps), bytes=sum(p[0] for p in ps),
                         reserve=sum(p[1] for p in ps), verts=sum(p[2] for p in ps), prims=sum(p[3] for p in ps),
                         centers=sum(p[4] for p in ps), slots=peak, slot_fail=fail, skipped=sk, lost=lost))
    for kind in ('orig', 'partner', 'import'):
        rs = [r for r in rows if r['kind'] == kind]
        if rs:
            print(f'{kind}: {len(rs)} models, over {a.limit}: {sum(r["bytes"] > a.limit for r in rs)}, '
                  f'max {max(r["bytes"] for r in rs)} bytes, max {max(r["slots"] for r in rs)} of {SLOTS} slots, '
                  f'slot failures {sum(r["slot_fail"] for r in rs)}')
    rows.sort(key=lambda r: -r['bytes'])
    print(f'{"species":32s} {"kind":7s} bones pieces verts centers  bytes  limit% slots skipped')
    for r in rows[:a.top]:
        print(f'{r["type"]:3d} {r["name"]:28s} {r["kind"]:7s} {r["bones"]:5d} {r["pieces"]:6d} {r["verts"]:5d} '
              f'{r["centers"]:7d} {r["bytes"]:6d} {100 * r["bytes"] / a.limit:6.0f} {r["slots"]:5d} '
              f'{r["skipped"]:4.1f} ({100 * r["lost"]:.0f}% of vertices)')
    if a.json:
        json.dump(rows, open(a.json, 'w'), indent=0)
    return 0


if __name__ == '__main__':
    sys.exit(main())
