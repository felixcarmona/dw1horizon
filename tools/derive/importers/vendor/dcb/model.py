"""Battle model files: F.DRV/<id>.PAK, F.DRV/BG<id>.PAK (arenas) and G.DRV/<id>.PAK.

Layout (little-endian):

    0x00 u16 0, u16 id             id = the file number (texture id for G)
    0x04 u32 records - 8           offset of the record list, minus 8
    0x08 char[16] texture name     "003.tim"
    0x18 u32 B                     bone count
    0x1c u8 parent[32]             parent of each bone, 0xff = root
    0x3c B x (i32 parent, i16 x, y, z, pad)   joint offset from the parent
    then B objects, one per bone in order: OMD0 or TMD (see mesh.py)
    records, each `i16 type, u16 id, u32 size` + data, until type < 0:
        type 1  animation `id` (0..7) (anim.py); packed (unpack.py)
                except in some G files, where it is stored unpacked
        type 2  "MSCD" script of a technique (its id is the card's attack
                id, which is how files are matched to cards), not decoded
        type 5  the texture: a TIM, packed in the arena (BG) files

The game finds records by (type, id) walking this list (0x8001bb44).
"""
import struct
from dataclasses import dataclass, field

from .unpack import unpack
from .mesh import parse_object
from .tim import parse_tim
from .vram import Vram


@dataclass
class Bone:
    index: int          # 0-based position in the skeleton
    parent: int         # -1 = root
    offset: tuple       # joint position relative to the parent
    mesh: object


@dataclass
class Model:
    name: str
    id: int
    texture_name: str
    bones: list
    records: list                    # (type, id, data)
    textures: list = field(default_factory=list)     # TIMs
    vram: object = None
    animations: dict = field(default_factory=dict)   # id -> unpacked bytes

    def record(self, typ, rid):
        for t, i, data in self.records:
            if t == typ and i == rid:
                return data
        return None


def parse_model(d, name):
    _, mid, rec = struct.unpack_from("<HHI", d, 0)
    tex_name = d[8:24].split(b"\0")[0].decode("ascii", "replace")
    nb = struct.unpack_from("<I", d, 0x18)[0]
    table = d[0x1c:0x1c + nb]
    bones, p = [], 0x3c
    for i in range(nb):
        parent, x, y, z = struct.unpack_from("<i3h", d, p)
        if (table[i] if table[i] != 0xff else -1) != parent:
            raise ValueError(f"{name}: parent tables disagree at bone {i}")
        bones.append(Bone(i, parent, (x, y, z), None))
        p += 12
    for b in bones:
        b.mesh, p = parse_object(d, p)
    if p != rec + 8:
        raise ValueError(f"{name}: meshes end at {p:#x}, records start at {rec + 8:#x}")
    records, p = [], rec + 8
    while p + 8 <= len(d):
        typ, rid, size = struct.unpack_from("<hHI", d, p)
        if typ < 0:
            break
        records.append((typ, rid, d[p + 8:p + 8 + size]))
        p += 8 + size
    m = Model(name, mid, tex_name, bones, records)
    m.vram = Vram()
    for t, _, data in records:
        if t == 5:
            tim = parse_tim(data if data[:8] == b"\x10\0\0\0\x08\0\0\0" else unpack(data))
            m.textures.append(tim)
            m.vram.upload(tim)
    for t, rid, data in records:
        if t == 1:
            m.animations[rid] = unpacked_animation(data)
    return m


def unpacked_animation(data):
    """Animations are packed, except where the record is exactly an unpacked
    one (u32 K, K keys of 772 bytes)."""
    if len(data) >= 4 and len(data) == 4 + 772 * struct.unpack_from("<I", data)[0]:
        return bytes(data)
    return unpack(data)
