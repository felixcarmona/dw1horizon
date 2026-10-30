"""Partner animation sets for Icemon (94, ICEM.MMD) and Meteormon (113, INSE.MMD).

Icemon, Meteormon and Gotsumon (68, GOTU.MMD) are one model in three colours: the same
skeleton (DIGIMON_SKELETONS 0x8011c750, 22 bones), mesh topology and rest pose. As
NPCs each has only 18-22 slots: idle, walk, run, the battle set and its techniques.

That skeleton has exactly the hierarchy of Agumon's (and Gabumon's, SnowAgumon's,
Meramon's: hips, body, neck, head, two 3-piece arms, pelvis, two 3-piece legs, with
the same bone numbers), only the rest pose differs. So the missing slots are carried
from those partners with tools/retarget.py, bone for bone (identity map): each bone
turns in model space the way the source bone turns from its own rest, whatever the
rest orientations. Translations stay the golem's, the hips take the source's bounce
(scaled) and the root motion is scaled to the golem's size.

Texture moves: the golem's eye frames are at (8, 0) half-closed, (16, 0) closed and
(24, 0) open (destination 0, 0, 8x24 words). Agumon-like sources keep theirs at y 32:
(8, 32) narrowed, (16, 32) half, (24, 32) closed, (32, 32) open; they are mapped.
Sounds: bank 4 is the voice of whoever plays the animation (the golem's VBALL voice,
which has the same notes 53-55 the sources use); bank 1/3 are shared effects.
"""

from tools.models.partners.support import ROOT, mmd, mmd_path, play, check, SlotSet, PARTNER_SLOTS  # noqa: E402
import retarget  # noqa: E402  (tools/, available through the support module)

NB = 22
AGU_EYES = {8: 8, 16: 8, 24: 16, 32: 24, 0: 24}       # source x (words) -> golem x


def eye_event(c):
    sx, sy = c['src']
    if c['dst'] == (0, 0) and c['size'] == (8, 24):    # already the golem's layout
        return dict(c)
    return dict(src=(AGU_EYES.get(sx, 24), 0), size=(8, 24), dst=(0, 0))


def retargeted(src, src_type, slot, tgt_type, trest, hips_k=1.0, root_k=1.0, bones=None,
               weights=None, sounds=True, tex=True, bone_map=None):
    """One source slot carried onto the golem. Returns (samples, loop, events)."""
    if bone_map is None:
        bones = bones or range(1, NB)
        weights = weights or {}
        bone_map = {b: (b, weights.get(b, 1.0)) for b in bones}
    r = retarget.transfer(src, src_type, slot, tgt_type, trest, bone_map, hips=(1, 1, hips_k))
    smp = []
    for t in range(r['n']):
        pose = [list(v) for v in trest]
        for b, seq in r['rot'].items():
            pose[b][3:6] = [round(x) for x in seq[t]]
        pose[1][6:9] = [round(trest[1][6 + i] + r['hips'][t][i]) for i in range(3)]
        pose[0][6:9] = [round(x * root_k) for x in r['root'][t]]
        smp.append(pose)
    mmd.close_loop(smp, r['loop'])
    ev = []
    for k, kind, c in r['events']:
        if kind == 'sound' and sounds:
            ev.append((k, 'sound', dict(bank=c['bank'], note=c['note'])))
        elif kind == 'tex' and tex:
            ev.append((k, 'tex', eye_event(dict(src=tuple(c['src']), size=tuple(c['size']), dst=tuple(c['dst'])))))
    if not any(kind == 'tex' for _, kind, _ in ev):
        ev.insert(0, (0, 'tex', dict(src=(24, 0), size=(8, 24), dst=(0, 0))))
    return smp, r['loop'], ev


def encode(slot, smp, ls, ev, tol=1):
    new = mmd.encode_anim(smp, NB, ls, ev, tol=tol)
    worst = check(new, NB, slot, smp, ls, ev)
    assert worst <= max(tol, 2), f'slot {slot:#x}: re-encoded animation off by {worst}'
    return new


class Builder:
    def __init__(self, tgt_type, mesh_name):
        self.type = tgt_type
        self.mesh = mmd.MMD.load(mmd_path(mesh_name))
        self.trest = retarget.rest_pose(self.mesh, NB, 0)
        self.sset = SlotSet(0x2E + 16)
        self.cache = {}

    def src(self, name):
        if name not in self.cache:
            self.cache[name] = mmd.MMD.load(mmd_path(name))
        return self.cache[name]

    def own(self, slot, name=None, from_slot=None):
        """A slot of a golem model (this mesh's or Gotsumon's/the twin's: same rig), as is."""
        m = self.mesh if name is None else self.src(name)
        self.sset.put(slot, m.anims.anims[m.anims.table[slot if from_slot is None else from_slot]])

    def carry(self, slot, name, src_type, from_slot=None, tol=1, **kw):
        m = self.src(name)
        fs = slot if from_slot is None else from_slot
        smp, ls, ev = retargeted(m, src_type, fs, self.type, self.trest, **kw)
        self.sset.put(slot, encode(slot, smp, ls, ev, tol))
        return smp, ls, ev

    def missing(self, techniques):
        return self.sset.missing(PARTNER_SLOTS + [0x2E + i for i in range(techniques)])


def stretched(m, slot, factor, eye=None):
    """A looping slot of a golem model played `factor` times slower (linear in between,
    one loop of it), with the root motion per tick divided by the same factor (so the
    same stride covers the same ground); `eye` replaces the eye frame."""
    smp, ls, ev = play(m.anims.anims[m.anims.table[slot]], NB, slot)
    assert ls == 0, f'slot {slot:#x}: not a loop from 0'
    n = len(smp) - 1                      # samples 0..n-1 + the closing one
    m2 = round(n * factor)
    out = []
    for t in range(m2 + 1):
        x = t / factor
        a = min(int(x), n)
        b = min(a + 1, n)
        u = x - a
        out.append([[round(p + (q - p) * u) for p, q in zip(va, vb)] for va, vb in zip(smp[a], smp[b])])
    evs = []
    for k, kind, c in ev:
        if kind == 'tex':
            c = dict(c, src=(eye, 0)) if eye is not None else c
        evs.append((min(round(k * factor), m2 - 1), kind, c))
    return out, 0, evs


def _stretch(self, slot, from_slot, factor, eye=None):
    smp, ls, ev = stretched(self.mesh, from_slot, factor, eye)
    self.sset.put(slot, encode(slot, smp, ls, ev))


Builder.stretch = _stretch
