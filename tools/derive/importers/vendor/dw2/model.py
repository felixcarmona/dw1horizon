"""Digimon World 2 models (AAA/4.AAA/MODEL/MODELnnn/M<id><name>.BIN) and their
animation banks (A/B/C/D/F/G/H/I/J/K<id><name>.BIN in the same folder).

Format as the game reads it (ref/DW2-PC: src/main/model.c Gfx_AttachModel,
Gfx_DrawTexModel, Gfx_AddQuadsGT4; src/main/anim.c Anim_StepModelAnim):

Model file
    u32 texture_offset          a TIM at the end of the file (see dw2.texture)
    u32 relocated               0 on disc, set by the game
    u32 B                       number of bones
    u32 vertices[B]             offsets of each bone's vertex list
    u32 normals[B]              offsets of each bone's normal list
    u32 polygons[B]             offsets of each bone's polygon block
    s32 depth[B]                depth in the hierarchy; bones are in depth-first
                                order, the parent of bone j is the last earlier
                                bone with depth[j] - 1 (depth 0: the actor)
    texture-animation parts     eye blinks and similar (not decoded here)

    list    := s16 count, s16 pad, s16 pad, count * (s16 x, s16 y, s16 z)
               normals are 4096 = 1.0
    polygons := four sections, each u32 n then n records:
                0 quads drawn with semi-transparency on (GPU code 0x3E)
                1 quads drawn opaque (0x3C)
                2 triangles, semi-transparency on (0x36)
                3 triangles, opaque (0x34)
        quad     u8 v[4], u8 n[4], (u8 u, u8 v) * 4, u16 clut, u16 tpage  (0x14)
        triangle u8 v[3], u8 n[3], (u8 u, u8 v) * 3, u16 clut, u16 tpage  (0x10)
        UVs and clut are relative to the model's texture: clut = row << 6 | x / 16
        inside the texture image; tpage only carries the blend mode bits.
        Quads are drawn (0, 1, 2) + (1, 3, 2), front faces counter-clockwise on
        screen (the game culls with NCLIP <= 0).

Animation bank
    u32 relocated
    u32 key_table[B]            per bone, an array of keys:
                                s16 m[3][3] (rotation matrix, 4096 = 1.0, row
                                major), s16 t[3]                    (0x18 bytes)
    u32 animations[10]          offsets (0 = no animation); the list ends with 1
    animation := frames of B bytes (each bone's key index), each followed by an
                 optional control byte: 0xff = stop (hold the last frame),
                 0xfe lo hi = jump to byte offset lo|hi<<8 (loop).
    The game shows one frame per two 60 Hz ticks: 30 frames per second.
"""
import os
import struct
from dataclasses import dataclass, field

from tools.derive import arraymath as np

BANK_LETTERS = "ABCDEFGHIJK"  # animation banks; Digimon have no E, field objects only E


@dataclass
class Prim:
    verts: tuple
    normals: tuple
    uvs: tuple
    clut: int
    tpage: int
    semi: bool          # drawn with semi-transparency enabled


@dataclass
class Bone:
    index: int          # 0-based, depth-first order
    parent: int         # index of the parent bone, -1 for the actor
    vertices: list
    normals: list
    prims: list


@dataclass
class Animation:
    bank: str           # file letter
    slot: int           # 0..9 inside the bank
    frames: list        # [[key index per bone]]
    loop_to: int        # frame index the animation jumps back to, None if it stops


@dataclass
class Model:
    name: str
    bones: list
    texture: bytes      # the TIM
    keys: dict = field(default_factory=dict)        # bank -> [per bone: [(m, t)]]
    animations: list = field(default_factory=list)


def read_list(d, off):
    count = struct.unpack_from("<h", d, off)[0]
    vals = struct.unpack_from(f"<{count * 3}h", d, off + 6)
    return [vals[i:i + 3] for i in range(0, len(vals), 3)]


def read_prims(d, off):
    prims = []
    for sec in range(4):
        n = struct.unpack_from("<i", d, off)[0]
        off += 4
        k = 4 if sec < 2 else 3
        size = 0x14 if k == 4 else 0x10
        for i in range(n):
            r = d[off + i * size:off + (i + 1) * size]
            uv = r[2 * k:4 * k]
            clut, tpage = struct.unpack_from("<2H", r, 4 * k)
            prims.append(Prim(tuple(r[:k]), tuple(r[k:2 * k]),
                              tuple((uv[2 * j], uv[2 * j + 1]) for j in range(k)), clut, tpage, sec % 2 == 0))
        off += n * size
    return prims


def parse_model(d, name=""):
    toff, _rel, count = struct.unpack_from("<3I", d, 0)
    t = struct.unpack_from(f"<{count * 4}i", d, 12)
    verts, norms, polys, depth = (t[i * count:(i + 1) * count] for i in range(4))
    bones, stack = [], []
    for j in range(count):
        del stack[depth[j]:]
        parent = stack[-1] if stack else -1
        assert len(stack) == depth[j], f"{name}: depth jumps at bone {j}"
        stack.append(j)
        bones.append(Bone(j, parent, read_list(d, verts[j]), read_list(d, norms[j]), read_prims(d, polys[j])))
    return Model(name, bones, d[toff:])


class KeyTable:
    """A bone's keys: (3x3 rotation*scale matrix, translation) at table + 0x18*i."""

    def __init__(self, data, offset):
        self.data, self.offset = data, offset

    def __len__(self):
        return (len(self.data) - self.offset) // 0x18

    def __getitem__(self, i):
        if not 0 <= i < len(self):
            raise IndexError(i)
        v = struct.unpack_from("<12h", self.data, self.offset + 0x18 * i)
        return np.array(v[:9], float).reshape(3, 3) / 4096, np.array(v[9:12], float)


def parse_bank(d, count, letter):
    tables = struct.unpack_from(f"<{count}I", d, 4)
    anim_offs = []
    p = 4 + 4 * count
    while True:
        o = struct.unpack_from("<I", d, p)[0]
        if o == 1 or len(anim_offs) == 10:
            break
        anim_offs.append(o)
        p += 4
    # The game indexes a bone's keys from the start of its table with no bound
    # (tables may overlap or run into each other), so keys are read on demand.
    keys = [KeyTable(d, t) for t in tables]
    anims = []
    for slot, o in enumerate(anim_offs):
        if not o:
            continue
        frames, offsets, pos, loop_to = [], {}, o, None
        while True:
            offsets[pos - o] = len(frames)
            frames.append(list(d[pos:pos + count]))
            pos += count
            c = d[pos]
            if c == 0xFF:
                break
            if c == 0xFE:
                target = d[pos + 1] | d[pos + 2] << 8
                loop_to = offsets.get(target, 0)
                break
        anims.append(Animation(letter, slot, frames, loop_to))
    return keys, anims


def load(model_path):
    """The model and every animation bank next to it."""
    d = open(model_path, "rb").read()
    folder, base = os.path.split(model_path)
    m = parse_model(d, base[:-4])
    for letter in BANK_LETTERS:
        bank = os.path.join(folder, letter + base[1:])
        if os.path.exists(bank):
            keys, anims = parse_bank(open(bank, "rb").read(), len(m.bones), letter)
            m.keys[letter] = keys
            m.animations += anims
    return m


def local_matrix(model, anim, frame_index, bone):
    rot, t = model.keys[anim.bank][bone.index][anim.frames[frame_index][bone.index]]
    m = np.eye(4)
    m[:3, :3] = rot
    m[:3, 3] = t
    return m


def world_matrices(model, anim, frame_index):
    out = []
    for b in model.bones:
        m = local_matrix(model, anim, frame_index, b)
        out.append(m if b.parent < 0 else out[b.parent] @ m)
    return out
