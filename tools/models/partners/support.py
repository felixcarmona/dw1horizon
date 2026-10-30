"""Helpers shared by the native partner model scripts (King of Sukamon, Icemon, Meteormon).

All of them build a partner MMD from animations that already exist in the game, replayed
tick by tick with tools/mmd.py's AnimPlayer (exactly like the engine) and re-encoded with
mmd.encode_anim, so the result plays the same motion on another mesh or at another size.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mmd  # noqa: E402

PARTNER_MODEL_BUFFER = 0x18800

# every slot the 64 partner models have (union), as in content/models/cherrymon/clips.py
PARTNER_SLOTS = ([0, 1, 2, 3, 4, 5] + list(range(7, 0x14)) + list(range(0x15, 0x1A)) + [0x1B] +
                 list(range(0x21, 0x26)) + list(range(0x28, 0x2D)))


def mmd_path(name):
    for d in range(6):
        p = os.path.join(ROOT, f'extracted/CHDAT/MMD{d}/{name}.MMD')
        if os.path.exists(p):
            return p
    raise SystemExit(f'{name}.MMD not found')


def play(anim, nb, slot, max_ticks=6000):
    """Per-tick samples (bone 0 tx..tz = root motion accumulated in bone 0's own frame),
    the loop sample and the sound/texture events as encode_anim takes them."""
    p = mmd.AnimPlayer(anim, nb, slot)
    out, root = [], [0, 0, 0]
    while len(out) < max_ticks and p.tick(stop_at_infinite_loop=True):
        root = [r + b for r, b in zip(root, p.base)]
        snap = [list(v) for v in p.pose]
        snap[0][6:9] = list(root)
        out.append(snap)
    if any(r != 0 for r in p.pose[0][3:6]):
        raise SystemExit(f'slot {slot:#x}: bone 0 rotates; root motion would need its R·S')
    events = []
    for k, kind, c in p.events:
        if kind == 'sound':
            events.append((k, 'sound', dict(bank=c['bank'], note=c['note'])))
        elif kind == 'tex':
            events.append((k, 'tex', dict(src=tuple(c['src']), size=tuple(c['size']), dst=tuple(c['dst']))))
        else:
            raise SystemExit(f'slot {slot:#x}: {kind}')
    return out, p.loop_sample(), events


def evkey(ev):
    return sorted((k, kind, sorted(c.items())) for k, kind, c in ev)


def check(new, nb, slot, target, ls, ev):
    """Plays the encoded animation again and compares it with what was asked for."""
    back, ls2, ev2 = play(new, nb, slot)
    tgt = [[list(v) for v in s] for s in target]
    if slot in (0x23, 0x24):          # the engine drops root X there: compare without it
        for s in back + tgt:
            s[0][6] = 0
    if len(back) != len(tgt) or ls2 != ls or evkey(ev2) != evkey(ev):
        raise SystemExit(f'slot {slot:#x}: re-encoded animation differs '
                         f'({len(back)}/{len(tgt)} ticks, loop {ls2}/{ls})')
    worst = 0
    for a, b in zip(back, tgt):
        for va, vb in zip(a, b):
            worst = max(worst, max(abs(x - y) for x, y in zip(va, vb)))
    return worst


class SlotSet:
    """Slot table being filled; identical encoded animations are shared."""

    def __init__(self, nslots):
        self.sec = mmd.AnimSection()
        self.sec.table = [None] * nslots
        self.encoded = {}

    def put(self, slot, anim):
        key = anim.build()
        if key not in self.encoded:
            self.encoded[key] = len(self.sec.anims)
            self.sec.anims.append(anim)
        while len(self.sec.table) <= slot:
            self.sec.table.append(None)
        self.sec.table[slot] = self.encoded[key]

    def missing(self, slots):
        return [s for s in slots if s >= len(self.sec.table) or self.sec.table[s] is None]


def write(out_path, tmd, sec, pad=False, label=''):
    out = mmd.MMD()
    out.tmd, out.anims = tmd, sec
    data = out.build()
    size = len(data)
    assert size <= PARTNER_MODEL_BUFFER, f'{size} bytes > PARTNER_MODEL_BUFFER'
    if pad:
        # testing: a fixed size keeps every later file at the same sector across rebuilds
        data += bytes(PARTNER_MODEL_BUFFER - size)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, 'wb').write(data)
    used = sum(x is not None for x in sec.table)
    print(f'{out_path}: {label}{len(sec.anims)} animations in {used} slots, {size} bytes '
          f'(PARTNER_MODEL_BUFFER {PARTNER_MODEL_BUFFER}, {PARTNER_MODEL_BUFFER - size} free)'
          f'{" padded" if pad else ""}')
    return size


def scale_mesh(tmd, k):
    for i, (x, y, z, p) in enumerate(tmd.verts):
        tmd.verts[i] = (round(x * k), round(y * k), round(z * k), p)
