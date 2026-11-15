#!/usr/bin/env python3
"""Digimon World 2003 / Digimon World 3 technique effects: decode, inspect and render them offline.

A technique in DW2003 is a small bytecode script stored in the caster's own battle model
(AAA/DAT/FIGHT/MODEL/M###XXXX.BIN, one script per action slot). The script plays the caster's
clips, moves the camera, waits, deals the hits and spawns two kinds of effects:
- 3D effects (MEFT####.BIN): small models in the battle-model format, with their own bone tracks
  and texture page, found through the fight overlay's MEFT table;
- sprite effects: flat animated sprites from the E###XXXX.BIN packs (E000COM* are shared, the
  others belong to one Digimon), found through the fight overlay's sprite table.
The formats are written down in docs/reference/dw3-effects.md.

Everything is read from the player's own disc image (PAL Digimon World 2003, or the USA Digimon
World 3), through the boot executable's file table; table positions are found by their shape, not
pinned. Models are parsed with the `dw3` package of $DW3_ROOT, like tools/dw3mmd.py. Nothing from
the disc is stored in the repository.

Usage (from the repository root; the disc can also be given with DW3_IMAGE):
  python3 tools/dw3effect.py --disc DW3.bin signatures            every imported species' signature
  python3 tools/dw3effect.py --disc DW3.bin script M373RENA [SLOT]  a battle model's technique scripts
  python3 tools/dw3effect.py --disc DW3.bin move "Hot Head"         one move record
  python3 tools/dw3effect.py --disc DW3.bin meft 85                 one 3D effect: bones, frames, texture
  python3 tools/dw3effect.py --disc DW3.bin render M372SGRG 11 --out sheet.png [--mp4 out.mp4]
"""
import argparse
import glob
import json
import math
import os
import re
import struct
import sys
from dataclasses import dataclass, field

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import dw2effect as D            # noqa: E402

RELEASES = {'SLES_039.36': 'pal', 'SLUS_014.36': 'us', 'SLPS_034.46': 'jp'}
SKILL_NAMES = {'pal': 'ESSKLNAM.BIN', 'us': 'USSKLNAM.BIN', 'jp': 'MSSKLNAM.BIN'}
MOVE_FMT, MOVE_SIZE = '<HHBBBBBBBBBIB', 18
MOVE_FIELDS = ('mp', 'power', 'move_type', 'unk1', 'accuracy', 'boosted_stat', 'boost', 'effective_against',
               'hit_effect', 'effect_rate', 'effect_value', 'unk4', 'freq')
ENEMY_FMT, ENEMY_SIZE = '<7H12h5HH20B', 70
PARTNER_SIZE = 88
SPRITE_SELF = 9999                 # sprite id: the spawning object's own sprite
FIGHT_FPS = 30                     # a displayed frame (Effect frames); game time runs in 1/60 s ticks
TICKS = 60                         # script waits, sprite block entries and 3D effect keyframe ticks per second
SIGNATURE_SLOT = 11                # a partner's (playable) signature technique
ENEMY_SLOTS = {'attack': 5, 'move_1': 9, 'move_2': 10}   # observed: an enemy row's moves and their script slots

# ------------------------------------------------------------------ disc


class Disc:
    """The disc image: files by name, the boot executable and its file table (file index -> name)."""

    def __init__(self, path):
        from tools.derive.importers.discs import Image
        self.image = Image(path)
        self.files = self.image.index()
        boot = [n for n in self.files if n in RELEASES]
        if not boot:
            raise SystemExit(f'{path}: not Digimon World 2003 / 3 (no known boot executable)')
        self.exe_name = boot[0]
        self.release = RELEASES[self.exe_name]
        self._cache = {}
        self.base = {}
        for name in self.files:
            self.base.setdefault(name.rsplit('/', 1)[-1], name)
        self.exe = self.read(self.exe_name)
        self.by_lba = {lba: name for name, (lba, _) in self.files.items()}
        self.table = locate_file_table(self.exe, set(self.by_lba))

    def path(self, base):
        if base not in self.base:
            raise KeyError(f'{base}: not on this disc')
        return self.base[base]

    def read(self, base):
        name = self.base.get(base, base)
        if name not in self._cache:
            self._cache[name] = self.image.read(*self.files[name])
        return self._cache[name]

    def name_of(self, index):
        """The file at the executable's file index (the ids the fight overlay's tables use)."""
        lba = struct.unpack_from('<I', self.exe, self.table + 4 * index)[0]
        name = self.by_lba.get(lba)
        return name.rsplit('/', 1)[-1] if name else None


class Files:
    """The extracted files of a source disc (a derive's source-games/dw2003/disc), read by base name, in place of
    a Disc where there is no image: no file table, so a 3D effect is read by its own name (MEFT####.BIN, the
    name the file table gives it on every release)."""

    def __init__(self, root):
        self.base = {}
        for folder, _dirs, names in sorted(os.walk(root)):
            for n in sorted(names):
                self.base.setdefault(n, os.path.join(folder, n))

    def read(self, base):
        if base not in self.base:
            raise KeyError(f'{base}: not among the extracted source files')
        with open(self.base[base], 'rb') as f:
            return f.read()

    def name_of(self, index):
        return None


class EffectIds:
    """The tables a conversion of 3D effects needs, without the fight overlay: the 3D effect ids the technique
    may spawn (each read as MEFT####.BIN) and no sprites."""

    def __init__(self, meft_ids):
        self.meft = {int(n): (0, None) for n in meft_ids}
        self.sprites = {}


def locate_file_table(exe, lbas):
    """The u32 LBA table of the executable: the longest run of words that are all file starts (or 0)."""
    n = len(exe) // 4
    words = struct.unpack_from(f'<{n}I', exe, 0)
    best, run, hits = (0, 0), 0, 0
    start = 0
    for i in range(n - 1, -1, -1):
        w = words[i]
        if w in lbas or w == 0:
            run += 1
            hits += w != 0
            if hits > best[0]:
                best = (hits, i)
        else:
            run, hits = 0, 0
    start = best[1]
    if best[0] < 500:
        raise SystemExit('dw3effect: no file table in the executable')
    return 4 * start


def decode_name(raw):
    """A lang-file string: 0x01 0x01 is a space, 0x01 0x1A a hyphen, 0x0E.. A-Z, 0x28.. a-z, 0x04.. 0-9;
    others kept as {NN} (0xE6 runs fill the unused names)."""
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if c == 1 and i + 1 < len(raw):
            out.append({1: ' ', 0x1A: '-'}.get(raw[i + 1], '{01%02X}' % raw[i + 1]))
            i += 2
            continue
        if 0x0E <= c <= 0x27:
            out.append(chr(ord('A') + c - 0x0E))
        elif 0x28 <= c <= 0x41:
            out.append(chr(ord('a') + c - 0x28))
        elif 0x04 <= c <= 0x0D:
            out.append(chr(ord('0') + c - 0x04))
        else:
            out.append('{%02X}' % c)
        i += 1
    return ''.join(out)


def lang_strings(data):
    n = struct.unpack_from('<I', data, 0)[0]
    offs = struct.unpack_from(f'<{n}I', data, 4)
    return [decode_name(data[o:data.index(b'\0', o)]) for o in offs]


# ------------------------------------------------------------------ tables


@dataclass
class Move:
    id: int
    name: str
    mp: int
    power: int
    move_type: int
    accuracy: int
    hit_effect: int
    effect_rate: int
    raw: dict


def _move_ok(exe, o):
    mp, pw, mt, _u1, acc, _bs, _bo, _ea, _he, er = struct.unpack_from('<HHBBBBBBBB', exe, o)
    return pw <= 999 and 0 < acc <= 127 and 0 < er <= 127 and 0 < mt < 16 and mp <= 999


def locate_move_table(exe, count):
    """The move table: `count` - 1 records of 18 bytes (one per skill name but the last) that all look like
    moves, with the most records of non-zero power (each residue class of 18 is walked once, from the end)."""
    runs, strong = {}, {}
    best, best_score = None, -1
    for o in range(len(exe) - MOVE_SIZE, -1, -2):
        ok = _move_ok(exe, o)
        runs[o] = runs.get(o + MOVE_SIZE, 0) + 1 if ok else 0
        strong[o] = (strong.get(o + MOVE_SIZE, 0) if ok else 0) + (ok and struct.unpack_from('<H', exe, o + 2)[0] > 0)
        if runs[o] >= count - 1:
            far = o + MOVE_SIZE * (count - 1)
            score = strong[o] - strong.get(far, 0)
            if score > best_score:
                best, best_score = o, score
    if best is None or best_score < count // 4:
        raise SystemExit('dw3effect: no move table in the executable')
    return best


class Tables:
    def __init__(self, disc):
        self.disc = disc
        self.names = lang_strings(disc.read(SKILL_NAMES[disc.release]))
        self.move_off = locate_move_table(disc.exe, len(self.names))
        self.moves = []
        for i in range(len(self.names) - 1):
            v = struct.unpack_from(MOVE_FMT, disc.exe, self.move_off + MOVE_SIZE * i)
            raw = dict(zip(MOVE_FIELDS, v))
            self.moves.append(Move(i, self.names[i], raw['mp'], raw['power'], raw['move_type'], raw['accuracy'],
                                   raw['hit_effect'], raw['effect_rate'], raw))
        self.enemies = parse_enemies(disc.read('SDIGIEDT.PRO'))
        models = {int(n[1:4]) for n in disc.base if re.fullmatch(r'M\d{3}[A-Z0-9]{4}\.BIN', n)}
        self.partner_off, self.partners = locate_partners(disc.exe, models, len(self.moves))
        fight = disc.read('FIGHTSTG.PRO')
        self.meft = locate_meft_table(fight)
        self.sprite_files, self.sprites = locate_sprite_tables(fight, disc)

    def move(self, key):
        if isinstance(key, int) or str(key).isdigit():
            return self.moves[int(key)]
        hits = [m for m in self.moves if m.name.lower().replace(' ', '') == str(key).lower().replace(' ', '')]
        if not hits:
            raise KeyError(f'no move {key!r}')
        return hits[0]

    def enemy(self, model_number):
        return [e for e in self.enemies if e['model'] == model_number]


def parse_enemies(data):
    """SDIGIEDT.PRO: one 70-byte row per enemy. `model` is the battle model number (M###), not a name index."""
    out = []
    for o in range(0, len(data) - ENEMY_SIZE + 1, ENEMY_SIZE):
        v = struct.unpack_from(ENEMY_FMT, data, o)
        if v[0] == 0 and out:
            break
        out.append({'row': len(out), 'model': v[0], 'item': v[1], 'drop_rate': v[2], 'index': v[3],
                    'attack': v[4], 'move_1': v[5], 'move_2': v[6], 'stats': v[7:19], 'type': v[24],
                    'moveset': [v[25 + 4 * k:29 + 4 * k] for k in range(5)]})
    return out


def locate_meft_table(fight):
    """{MEFT id: (sections, file index)}: 12-byte records {u32 id, u16 sections, u16 file, u16 sub, u16 file}
    with the id rising (one is listed twice) and the two file fields equal (the fight overlay's 3D effect
    table)."""
    best = {}
    for o in range(0, len(fight) - 12, 4):
        out, prev = {}, -1
        q = o
        while q + 12 <= len(fight):
            i, ns, f1, _sub, f2 = struct.unpack_from('<IHHHH', fight, q)
            if not (prev <= i < 1000 and ns < 200 and f1 == f2 and f1 > 0):
                break
            out.setdefault(i, (ns, f1))
            prev = i
            q += 12
        if len(out) > len(best):
            best = out
    if len(best) < 50:
        raise SystemExit('dw3effect: no MEFT table in FIGHTSTG.PRO')
    return best


def locate_sprite_tables(fight, disc):
    """The sprite table ({i16 id, i16 pack, i16 section, i16 file}, -1 ends it) and the sprite pack table it
    indexes (16-byte records, u16 file index at +6). Returns ({pack: file name}, {id: (pack, section)})."""
    best = None
    for o in range(0, len(fight) - 8, 2):
        q, recs = o, {}
        while q + 8 <= len(fight):
            i, e, s, f = struct.unpack_from('<4h', fight, q)
            if i == -1:
                break
            if not (0 <= i < 4000 and 0 <= e < 80 and 0 <= s < 64):
                recs = None
                break
            recs[i] = (e, s)
            q += 8
        if recs and len(recs) > 100 and 2041 in recs and (best is None or len(recs) > len(best[1])):
            best = (o, recs)
    if best is None:
        raise SystemExit('dw3effect: no sprite table in FIGHTSTG.PRO')
    o, recs = best
    packs = max(e for e, _ in recs.values()) + 1
    # the pack table ends 16 * packs bytes (plus padding) before the sprite table: find it by its file names
    for start in range(o - 16 * packs - 64, o - 16 * packs + 64, 2):
        names = {}
        for k in range(packs):
            if start + 16 * k + 8 > len(fight) or start < 0:
                break
            f = struct.unpack_from('<H', fight, start + 16 * k + 6)[0]
            n = disc.name_of(f) if f else None
            if n:
                names[k] = n
        if names.get(0, '').startswith('E000COM') and sum(n.startswith('E') for n in names.values()) > packs // 2:
            return names, recs
    raise SystemExit('dw3effect: no sprite pack table in FIGHTSTG.PRO')


# ------------------------------------------------------------------ technique scripts

OPS = {0: 'end', 1: 'flag', 2: 'motion', 3: 'sprite', 4: 'cue', 5: 'camera', 6: 'meft', 7: 'op7', 8: 'op8',
       9: 'op9', 10: 'event', 11: 'wait', 0xFF: 'end'}
HIT_EVENTS = (98, 99)              # event 98: a hit before the last, 99: the last hit


def op_len(w, i):
    """Words of the instruction at w[i] (the opcode word included), from the fight overlay's handlers."""
    op = w[i]

    def a(k):
        return w[i + k] if i + k < len(w) else 0
    if op in (0, 0xFF):
        return 1
    if op == 1:
        return 2
    if op == 2:                    # sub-op, value, [clip], [sub-op's own arguments]
        s1, n = a(1), 3
        if s1 <= 0 or 5 <= s1 <= 6 or s1 >= 10:
            n += 1
        n += {3: 4, 4: 2, 7: 1, 8: 1}.get(s1, 0)
        if s1 == 5 and a(3) == 4:
            n += 1
        return n
    if op == 3:                    # mode, id, [x, y, z]  (mode 1 = preload)
        return 3 if a(1) == 1 else 6
    if op == 4:
        return 3 if a(1) == 1 else 5
    if op == 5:                    # ticks, mode, [preset] or 14 words of keyframe
        return 17 if a(2) == 1 else 4
    if op == 6:                    # mode, id, [x, -y, -z, rx, -ry, -rz]
        return 3 if a(1) == 1 else 9
    if op in (7, 8, 9, 10):
        return 3
    if op == 11:
        return 2
    return None


def disassemble(words):
    """[(op, args...)] up to the end opcode; raises ValueError on an unknown opcode or a missing end."""
    out, i = [], 0
    while i < len(words):
        n = op_len(words, i)
        if n is None:
            raise ValueError(f'unknown opcode {words[i]} at word {i}')
        out.append(tuple(words[i:i + n]))
        if words[i] == 0xFF:
            if any(words[i + 1:]):
                raise ValueError(f'data after the end at word {i}')
            return out
        i += n
    raise ValueError('no end opcode')


def script_section(sections):
    """(section index, {slot: words}) of a battle model's technique scripts: a u32 offset table, each script
    ending in 0xFF."""
    for si, s in enumerate(sections):
        if len(s) < 8:
            continue
        first = struct.unpack_from('<I', s)[0]
        if first % 4 or not 16 <= first <= 400 or first > len(s):
            continue
        offs = struct.unpack_from(f'<{first // 4}I', s)
        if any(o and (o < first or o >= len(s) or o % 2) for o in offs):
            continue
        scripts = {}
        for k, o in enumerate(offs):
            if o:
                e = min([x for x in offs if x > o] + [len(s)])
                scripts[k] = struct.unpack_from(f'<{(e - o) // 2}h', s, o)
        if len(scripts) >= 2 and sum(0xFF in w for w in scripts.values()) >= 0.8 * len(scripts):
            return si, scripts
    return None, {}


@dataclass
class Spawn:
    tick: int              # script frame (30 Hz) it appears
    kind: str              # 'meft' or 'sprite'
    id: int
    pos: tuple             # script coordinates (caster space)
    rot: tuple = (0, 0, 0)


@dataclass
class Technique:
    model: str
    slot: int
    ops: list
    spawns: list = field(default_factory=list)
    hits: list = field(default_factory=list)       # frames of the hit events
    clips: list = field(default_factory=list)
    length: int = 0

    def summary(self):
        meft = sorted({s.id for s in self.spawns if s.kind == 'meft'})
        spr = sorted({s.id for s in self.spawns if s.kind == 'sprite'})
        return {'model': self.model, 'slot': self.slot, 'meft': meft, 'sprites': spr, 'hits': len(self.hits),
                'clips': self.clips, 'frames': self.length}


def technique(model, slot, words):
    ops = disassemble(words)
    t = Technique(model, slot, ops)
    tick = 0
    for o in ops:
        if o[0] == 11:
            tick += max(o[1], 0)
        elif o[0] == 3 and o[1] != 1 and o[2] != SPRITE_SELF:
            t.spawns.append(Spawn(tick, 'sprite', o[2], tuple(o[3:6])))
        elif o[0] == 6 and o[1] != 1:
            t.spawns.append(Spawn(tick, 'meft', o[2], (o[3], -o[4], -o[5]), (o[6], -o[7], -o[8])))
        elif o[0] == 10 and o[1] in HIT_EVENTS:
            t.hits.append(tick)
        elif o[0] == 2 and o[1] == 0 and len(o) > 3:
            t.clips.append(o[3])
    t.length = tick
    return t


def fmt_op(o):
    name = OPS.get(o[0], f'op{o[0]}')
    return f'{name} ' + ' '.join(str(x) for x in o[1:])


# ------------------------------------------------------------------ models (the dw3 package)

def _dw3():
    from tools import dw3mmd
    return dw3mmd._dw3()


def sections_of(data):
    _dw3()
    from dw3 import model as M
    return M.sections_of(data)


def parse_model(data, name=''):
    _dw3()
    from dw3 import model as M
    return M.parse_model(data, name)


def model_scripts(disc, model):
    name = model if model.endswith('.BIN') else model + '.BIN'
    if not name.startswith('M'):
        raise KeyError(name)
    si, scripts = script_section(sections_of(disc.read(name)))
    return {k: technique(name[:-4], k, w) for k, w in scripts.items()}


# ------------------------------------------------------------------ 3D effects -> dw2effect.Effect

BLEND = {0: None, 2: 1, 4: 2, 6: 3}   # render register e -> PlayStation semi-transparency mode (assumed: 2 additive)


def effect_from_model(m, texture=None):
    """A DW2003 3D effect (parsed battle-format model) as a dw2effect.Effect: one bone per model bone, the
    bones' tracks (one entry per 1/60 s tick, as the game steps them) sampled every other tick, at 30 fps, into matrices (Rz*Ry*Rx times scale), prims with
    texel UVs (material offset + UV) and their CLUT as row << 6 | x / 16 inside the effect's 256x256 page.
    A face stored twice with its winding reversed is kept once: the game culls back faces (that is why the
    effects carry both), so one of the two is drawn from any side; the offline renderers do not cull, and
    drawing both would double an additive face's light."""
    _dw3()
    from dw3 import pose as P
    tex = m.texture or texture
    if tex is None:
        raise ValueError('effect has no texture of its own')
    anim = m.animations[0] if m.animations else None
    frames_tl = (P.animation_frames(anim) if anim else [0])[::TICKS // FIGHT_FPS]
    bones = []
    for b in m.bones:
        prims, seen = [], set()
        for p in b.mesh.prims:
            if not p.uvs:
                continue
            face = (tuple(sorted(p.verts)), tuple(sorted(p.uvs)), tuple(p.material))
            if face in seen:
                continue
            seen.add(face)
            mt = p.material
            u0, v0 = mt[0] | mt[1] << 8, mt[2]
            uvs = tuple(((u0 + u) & 0xFF, (v0 + v) & 0xFF) for u, v in p.uvs)
            clut = mt[4] << 6 | mt[3] // 16      # clut x in halfwords
            prims.append(D.Prim(tuple(p.verts), uvs, clut, BLEND.get(p.state.get(0xE, 0), 1)))
        bones.append(D.Bone(b.parent - 1, [tuple(v) for v in b.mesh.vertices], prims))
    keys = [dict() for _ in m.bones]
    frames = []
    for f, tl in enumerate(frames_tl):
        row = []
        for bi, b in enumerate(m.bones):
            t, r, s = P.local_trs(b, tl)
            mm = r * s
            k = (tuple(int(round(x * 4096)) for x in mm.reshape(9)), tuple(int(round(x)) for x in t))
            k = (tuple(max(-32768, min(32767, x)) for x in k[0]), k[1])
            idx = None
            for ki, kv in keys[bi].items():
                if kv == k:
                    idx = ki
                    break
            if idx is None:
                idx = len(keys[bi])
                keys[bi][idx] = k
            row.append(idx)
        frames.append(row)
    e = D.Effect(bones, _page_tim(tex), keys, frames)
    return e


def _page_tim(tex):
    """The model's texture (a 16-bit 64x256 TIM that holds a 256x256 4bpp page with its CLUTs in the bottom
    rows) as the dw2effect convention: the same halfwords, read as a 4bpp image with the palettes inside."""
    magic, flags = struct.unpack_from('<2I', tex, 0)
    _size, _x, _y, w, h = struct.unpack_from('<I4H', tex, 8)
    body = tex[20:20 + 2 * w * h]
    return struct.pack('<II', 0x10, 0) + struct.pack('<I4H', 12 + len(body), 0, 0, w, h) + body


def load_meft(disc, tables, n):
    ns, f = tables.meft[n]
    name = disc.name_of(f) or f'MEFT{n:04d}.BIN'
    return parse_model(disc.read(name), name[:-4])


# ------------------------------------------------------------------ imported species

def imported_species(root=ROOT):
    """{species id: (name, battle model)} of the species imported from DW2003 (their JSON's _source)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(root, 'content', 'species', '*.json'))):
        j = json.load(open(f))
        m = re.search(r'dw3 (M\d{3}[A-Z0-9]{4})', json.dumps(j.get('_source', '')))
        if m:
            out[int(os.path.basename(f).split('-')[0])] = (j.get('name', ''), m.group(1))
    return out


def named(move):
    """Enemies' plain attacks have a one-letter placeholder name."""
    return len(move.name.strip()) > 1


def signature(tables, model, scripts, partner_move=None):
    """(move, script slot, how) of a model's signature: the partner's own signature move in slot 11, else the
    enemy row's strongest damaging move (power and a hit in its script), a named one before the plain attack."""
    rows = tables.enemy(int(model[1:4]))
    if partner_move is not None and SIGNATURE_SLOT in scripts:
        return partner_move, SIGNATURE_SLOT, 'partner signature, slot 11'
    best = None
    for r in rows:
        for key, slot in ENEMY_SLOTS.items():
            mv = tables.moves[r[key]] if 0 < r[key] < len(tables.moves) else None
            if mv is None or slot not in scripts or not scripts[slot].hits:
                continue
            rank = (named(mv) and mv.power > 0, mv.power)
            if best is None or rank > (named(best[0]) and best[0].power > 0, best[0].power):
                best = (mv, slot, f'enemy row {r["row"]} {key}, slot {slot}')
    if best:
        return best
    if SIGNATURE_SLOT in scripts and scripts[SIGNATURE_SLOT].hits:
        return None, SIGNATURE_SLOT, 'slot 11, no move record'
    return None, None, 'no technique script'


# ------------------------------------------------------------------ rendering

FIELD_HALF = 5376                # a fighter's row stands this far from the field's middle (z = 0)
PARTNER_SLOTS = (11, 12)         # partner techniques: the caster's row is at -z; enemy ones stand at +z


def caster_sign(tech):
    return -1 if tech.slot in PARTNER_SLOTS else 1


def _rot(rx, ry_, rz):
    """Rz * Ry * Rx of 4096-per-turn angles (dw3.pose's order)."""
    def c(a):
        return math.cos(a * math.pi / 2048), math.sin(a * math.pi / 2048)
    (cx, sx), (cy, sy), (cz, sz) = c(rx), c(ry_), c(rz)
    X_ = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    Y_ = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    Z_ = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))
    return _mul(Z_, _mul(Y_, X_))


def _mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def baked(effect, spawn, sign, delay=0):
    """The effect in the caster's frame as dw2effect has it (caster at 0, its target toward -z): the spawn's
    position and turn, and the turn from the field's frame to the caster's, put into the root bones' keys.
    `delay` hidden frames go first (the spawn's start relative to the technique's first object)."""
    flip = ((-1, 0, 0), (0, 1, 0), (0, 0, -1)) if sign < 0 else ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    R = _mul(flip, _rot(*spawn.rot))
    p = spawn.pos
    o = (flip[0][0] * p[0], p[1], flip[2][2] * p[2] - FIELD_HALF)
    keys = []
    for bone, ks in zip(effect.bones, effect.keys):
        if bone.parent >= 0:
            keys.append(dict(ks))
            continue
        out = {}
        for i, (m9, t) in ks.items():
            m = tuple(tuple(m9[3 * r + k] / 4096 for k in range(3)) for r in range(3))
            mm = _mul(R, m)
            tt = tuple(sum(R[i2][k] * t[k] for k in range(3)) + o[i2] for i2 in range(3))
            out[i] = (tuple(max(-32768, min(32767, int(round(mm[r][k] * 4096)))) for r in range(3) for k in range(3)),
                      tuple(int(round(x)) for x in tt))
        keys.append(out)
    frames = list(effect.frames)
    if delay:
        hidden = []
        for bi, ks in enumerate(keys):
            idx = len(ks)
            ks[idx] = ((0,) * 9, (0, 0, 0))
            hidden.append(idx)
        frames = [hidden] * delay + frames
    e = D.Effect(effect.bones, effect.tim, keys, frames, effect.tex_moves)
    e._image = D.tim_halfwords(e.tim)
    return e


def staged_effects(disc, tables, tech, first=None):
    """[(spawn, effect in the caster's frame)] of the technique's 3D effects, each with its start delay
    (counted from `first`, by default the first 3D effect's start)."""
    sign = caster_sign(tech)
    spawns = [s for s in tech.spawns if s.kind == 'meft' and s.id in tables.meft]
    first = min([s.tick for s in spawns], default=0) if first is None else first
    out = []
    for s in spawns:
        try:
            e = effect_from_model(load_meft(disc, tables, s.id))
        except ValueError:
            continue
        out.append((s, baked(e, s, sign, (s.tick - first) // (TICKS // FIGHT_FPS))))
    return out


# A sprite spawn's z: these two draw it in screen space (x, y screen pixels from the centre), in front of
# everything (32767) or behind it (-1); any other z is a field position, re-projected every frame.
FRONT, BACK = 32767, -1
ANCHOR_Y = -1024                      # where a screen-space sprite goes in a field: this high on a fighter
CUT_IN = (1009, 1020)                 # the shared finisher cut-in (emblem in front, white wipe behind): not carried


def sprite_anchor(spawn, sign, pixel):
    """The sprite spawn's position in the field's frame as baked() takes it (y up is negative). A screen-space
    sprite has no field position: one in front goes on the target (where the camera looks at the hit), one
    behind on the caster (where it looks while charging), its screen offset in field units."""
    x, y, z = spawn.pos
    if z in (FRONT, BACK):
        home = -sign * FIELD_HALF if z == FRONT else sign * FIELD_HALF
        return (0, ANCHOR_Y + y * pixel, home - sign * x * pixel)
    return (x, y, z)


def sprite_spawns(tables, tech):
    """The technique's sprite spawns that are carried: known ids, not the shared cut-in."""
    return [s for s in tech.spawns if s.kind == 'sprite' and s.id in tables.sprites and s.id not in CUT_IN]


def staged_sprites(disc, tables, tech, first=None, pixel=None):
    """[(spawn, effect in the caster's frame)] of the technique's sprites (dw3sprite.effect: flat quads facing
    the side camera, their right toward the target), each with its start delay counted from `first`."""
    from tools import dw3sprite as P
    sign = caster_sign(tech)
    pixel = P.PIXEL if pixel is None else pixel
    spawns = sprite_spawns(tables, tech)
    first = min([s.tick for s in spawns], default=0) if first is None else first
    out = []
    for s in spawns:
        try:
            e = P.effect(disc, tables, s.id, pixel)
        except (ValueError, KeyError, IndexError, struct.error):
            continue
        # the sprite's right is -z in the field for an enemy caster; a partner's is turned half round
        at = Spawn(s.tick, 'sprite', s.id, sprite_anchor(s, sign, pixel), (0, 2048 if sign < 0 else 0, 0))
        out.append((s, baked(e, at, sign, (s.tick - first) // (TICKS // FIGHT_FPS))))
    return out


def staged_all(disc, tables, tech, sprites=False):
    """staged_effects, and with `sprites` staged_sprites too, their delays counted from the first of them."""
    spawns = [s for s in tech.spawns if s.kind == 'meft'] + (sprite_spawns(tables, tech) if sprites else [])
    first = min([s.tick for s in spawns], default=0)
    out = staged_effects(disc, tables, tech, first)
    if sprites:
        out += staged_sprites(disc, tables, tech, first)
    return first, out


def stage(disc, tables, tech, sprites=False):
    """Placed objects (dw2effect) for the technique's 3D effects (and sprites as flat quads), at the script's
    times (60 Hz ticks, the script's own unit)."""
    first, staged = staged_all(disc, tables, tech, sprites)
    return [D.Placed(e, (0, 0, 0), False, first, 2 * len(e.frames)) for _s, e in staged]


def render_frames(objects, ticks, width=320, height=180, cam=None):
    from tools import image as img
    cam = cam or D.Camera(width, height, eye=(19000, -5000, -FIELD_HALF), look=(0, -2200, -FIELD_HALF))
    D.HOME_DISTANCE = 2 * FIELD_HALF             # the markers: this game's rows
    out = []
    for t in ticks:
        px = D.render_tick(objects, t, cam)
        out.append(img.frombytes('RGB', (width, height), bytes(c for p in px for c in p)))
    return out


def sheet(frames, cols=6):
    from tools import image as img
    w, h = frames[0].width, frames[0].height
    rows = (len(frames) + cols - 1) // cols
    s = img.new('RGB', (cols * w, rows * h), (0, 0, 0))
    for n, f in enumerate(frames):
        s.paste(f, ((n % cols) * w, (n // cols) * h))
    return s


def write_mp4(frames, path, fps=30):
    """Frames (same size) to an H.264 mp4 through ffmpeg's stdin."""
    import subprocess
    w, h = frames[0].width, frames[0].height
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}',
                          '-r', str(fps), '-i', '-', '-pix_fmt', 'yuv420p', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                          path], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit('ffmpeg failed')


# ------------------------------------------------------------------ CLI

def _disc(a):
    path = a.disc or os.environ.get('DW3_IMAGE')
    if not path:
        raise SystemExit('give the disc image with --disc or DW3_IMAGE')
    return Disc(path)


def signatures(disc, tables, root=ROOT):
    """One row per imported species: the signature move, its script and effects."""
    partner = tables.partners
    rows = []
    for sp, (name, model) in sorted(imported_species(root).items()):
        try:
            scripts = model_scripts(disc, model)
        except KeyError:
            rows.append({'species': sp, 'name': name, 'model': model, 'error': 'model not on this disc'})
            continue
        pm = partner.get(int(model[1:4]))
        mv, slot, how = signature(tables, model, scripts, tables.moves[pm] if pm is not None else None)
        r = {'species': sp, 'name': name, 'model': model, 'how': how}
        if mv is not None:
            r.update(move=mv.id, move_name=mv.name if named(mv) else None, power=mv.power, mp=mv.mp)
        if slot is not None:
            r.update(scripts[slot].summary())
        rows.append(r)
    return rows


def locate_partners(exe, models, n_moves):
    """{battle model number: signature move id} of the playable Digimon: 52 records of 88 bytes (u16 model,
    6 stats, 7 resistances, attack, 5 techniques, signature, DNA technique, then levels and growth), every
    model on the disc and every signature a distinct move."""
    span = 52 * PARTNER_SIZE
    for o in range(0, len(exe) - span + 1, 2):
        if struct.unpack_from('<H', exe, o)[0] not in models:
            continue
        recs = [struct.unpack_from('<21H', exe, o + PARTNER_SIZE * k) for k in range(52)]
        if all(r[0] in models and 0 < r[20] < n_moves for r in recs) and len({r[20] for r in recs}) == 52:
            return o, {r[0]: r[20] for r in recs}
    raise SystemExit('dw3effect: no partner table in the executable')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--disc')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('signatures')
    s = sub.add_parser('script')
    s.add_argument('model')
    s.add_argument('slot', type=int, nargs='?')
    s = sub.add_parser('move')
    s.add_argument('key')
    s = sub.add_parser('meft')
    s.add_argument('id', type=int)
    s = sub.add_parser('render')
    s.add_argument('model')
    s.add_argument('slot', type=int)
    s.add_argument('--out', required=True)
    s.add_argument('--mp4')
    s.add_argument('--step', type=int, default=12)
    a = p.parse_args(argv)
    disc = _disc(a)
    if a.cmd == 'script':
        for k, t in sorted(model_scripts(disc, a.model).items()):
            if a.slot is not None and k != a.slot:
                continue
            print(f'slot {k}: {t.summary()}')
            if a.slot is not None:
                for o in t.ops:
                    print('  ' + fmt_op(o))
        return
    tables = Tables(disc)
    if a.cmd == 'signatures':
        for r in signatures(disc, tables):
            print(json.dumps(r))
    elif a.cmd == 'move':
        print(tables.move(a.key))
    elif a.cmd == 'meft':
        m = load_meft(disc, tables, a.id)
        e = effect_from_model(m) if m.texture else None
        print(f'MEFT{a.id:04d}: {len(m.bones)} bones, {sum(len(b.mesh.prims) for b in m.bones)} prims, '
              f'{len(e.frames) if e else "?"} frames, texture {"own" if m.texture else "borrowed"}')
    elif a.cmd == 'render':
        t = model_scripts(disc, a.model)[a.slot]
        objs = stage(disc, tables, t)
        if not objs:
            raise SystemExit(f'{a.model} slot {a.slot}: no 3D effect')
        begin, end = min(o.start for o in objs), max(o.start + o.ticks for o in objs)
        frames = render_frames(objs, range(begin, end, a.step))
        sheet(frames).save(a.out)
        if a.mp4:
            write_mp4(render_frames(objs, range(begin, end, 2)), a.mp4)


if __name__ == '__main__':
    main()
