"""Battle model files: AAA/DAT/FIGHT/MODEL/M<id><name>.BIN.

The file is a table of u32 section offsets (the first offset is the table size).
Sections, located through the hierarchy section:

    0           animation table (see `parse_anim_table`) when it has that
                shape; in some files (Guilmon, Bastemon, many effects) section 0
                is a bone track or mesh like the others, the hierarchy points at
                it, and the table, if any, is a later section (`find_anim_table`)
    1..B        one track section per bone (see `parse_tracks`)
    B+1..2B     one mesh per bone (see dw3.mesh), mesh section = B + bone
    texture     u32 8, u32 0, then an RLEN-compressed TIM whose bottom rows
                hold the CLUTs (see dw3.texture)
    hierarchy   u32 texture_section, u32 B, then B * (u32 parent, u32 mesh_section,
                u32 track_section). Bones are the entries in file order; parent is
                the 1-based position of the parent entry, 0 for the model root
    events      u32 offset table, not decoded yet

Usually the order is anim, tracks, meshes, texture, hierarchy, events; a few
files (Agumon) put hierarchy and events before the meshes, and some carry extra
track+mesh pairs after them (weapons, effects) that the hierarchy doesn't list.
"""
import struct
from dataclasses import dataclass, field

from .mesh import Mesh, parse_mesh

TRACK_END = 30000


@dataclass
class Bone:
    index: int          # 1-based position in the hierarchy
    parent: int         # 0 = model root
    translation: list   # [(frame, (x, y, z))]
    rotation: list      # [(frame, (rx, ry, rz))], 4096 = 360 degrees
    scale: list         # [(frame, (sx, sy, sz))], 4096 = 1.0
    mesh: Mesh


@dataclass
class Segment:
    duration: int
    start: int
    end: int


@dataclass
class Animation:
    slot: int
    segments: list
    loop: bool


@dataclass
class Model:
    name: str
    bones: list
    animations: list
    texture: bytes          # decompressed TIM, None when the file borrows one
    sections: list = field(repr=False, default_factory=list)


def sections_of(data):
    n = struct.unpack_from("<I", data, 0)[0] // 4
    offs = list(struct.unpack_from(f"<{n}I", data, 0)) + [len(data)]
    return [data[offs[i]:offs[i + 1]] for i in range(n)]


def parse_keys(s, start, end):
    keys = []
    for p in range(start, end, 8):
        x, y, z, frame = struct.unpack_from("<3hH", s, p)
        keys.append((frame, (x, y, z)))
    return keys


def parse_tracks(s):
    """Track section: u32 offsets to translation, rotation, scale and a fourth
    track. The first three are lists of (s16 x, s16 y, s16 z, u16 frame) keys on
    a timeline shared by all animations, closed by a key at frame 30000. The
    fourth is (u16 frame, u16 value) pairs and is always 0 on this disc."""
    t, r, sc, extra = struct.unpack_from("<4I", s, 0)
    return parse_keys(s, t, r), parse_keys(s, r, sc), parse_keys(s, sc, extra)


def parse_anim_table(s):
    """Animation table (section 0, see `find_anim_table`): u32 offsets, one per animation slot (0 = slot unused). Each entry
    is u16 0, then segments of (u16 duration, u16 start, u16 end, u16 total) on
    the shared timeline; a segment with duration 0 ends the list, its start is
    0x8000 when the animation loops and 0xffff when it plays once."""
    first = struct.unpack_from("<I", s, 0)[0]
    anims = []
    for slot, off in enumerate(struct.unpack_from(f"<{first // 4}I", s, 0)):
        if not off:
            continue
        p = off + 2
        segments = []
        while True:
            duration, start, end, _total = struct.unpack_from("<4H", s, p)
            p += 8
            if duration == 0:
                break
            segments.append(Segment(duration, start, end))
        if segments:
            anims.append(Animation(slot, segments, start == 0x8000))
    return anims


def is_track_section(s):
    if len(s) < 24:
        return False
    offs = struct.unpack_from("<4I", s, 0)
    return offs[0] == 0x10 and offs[0] < offs[1] <= offs[2] < offs[3] <= len(s)


def is_anim_table(s, last):
    """Shape of an animation table on a timeline whose last key is `last`: offsets
    0 or inside the section, each entry u16 0 then segments within the timeline,
    closed by duration 0 with start 0x8000 or 0xffff."""
    if len(s) < 12:
        return False
    first = struct.unpack_from("<I", s, 0)[0]
    if not (4 <= first < len(s) and first % 4 == 0):
        return False
    offs = [o for o in struct.unpack_from(f"<{first // 4}I", s, 0) if o]
    if not offs or any(not (first <= o < len(s) - 2) for o in offs):
        return False
    segments = 0
    for o in offs:
        if struct.unpack_from("<H", s, o)[0] != 0:
            return False
        p = o + 2
        while True:
            if p + 8 > len(s):
                return False
            duration, start, end, _ = struct.unpack_from("<4H", s, p)
            p += 8
            if duration == 0:
                if start not in (0x8000, 0xFFFF):
                    return False
                break
            if not (start <= end <= last):
                return False
            segments += 1
    return segments > 0


def find_anim_table(secs, used, last):
    """The section that has the shape of an animation table, among those the
    hierarchy does not use (Guilmon M366GIRU: section 50; Bastemon M437BAST:
    section 2), or None."""
    for i, s in enumerate(secs):
        if i not in used and not is_track_section(s) and is_anim_table(s, last):
            return s
    return None


def whole_timeline(bones):
    """One animation spanning every key of every track, for files that have no
    animation table at all."""
    last = max(f for b in bones for keys in (b.translation, b.rotation, b.scale)
               for f, _ in keys if f != TRACK_END)
    return [Animation(-1, [Segment(last + 1, 0, last)], False)] if last > 0 else []


def find_hierarchy(secs):
    """The hierarchy section is recognised by its shape. Its texture section may be
    empty: those models borrow the texture of another file."""
    for i, s in enumerate(secs):
        if i == 0 or len(s) < 20:
            continue
        tex, count = struct.unpack_from("<2I", s, 0)
        if not (0 < tex < len(secs) and 0 < count < 128 and len(s) >= 8 + 12 * count):
            continue
        if secs[tex] and secs[tex][8:12] != b"RLEN":
            continue
        entries = [struct.unpack_from("<3I", s, 8 + 12 * k) for k in range(count)]
        if all(p <= count and m < len(secs) and t < len(secs) for p, m, t in entries):
            return i, tex, entries
    raise ValueError("no hierarchy section")


def parse_model(data, name=""):
    from .rlen import unrlen

    secs = sections_of(data)
    hier, tex, entries = find_hierarchy(secs)
    # Section 0 is usually the animation table, and a hierarchy entry with
    # track_section 0 has no track. Not always: in Guilmon (and many effects)
    # section 0 is a bone track that track_section 0 points at (read as "no
    # track", Guilmon's torso, arms and head stayed at the origin under its
    # legs); in Bastemon it is the mesh of bone 4 (read as a table, it gave one
    # bogus 16613-frame animation). The real table is then a later section.
    table0 = not is_track_section(secs[0]) and is_anim_table(secs[0], TRACK_END - 1)
    bones = []
    for index, (parent, mesh_sec, track_sec) in enumerate(entries, 1):
        # No track (0 when section 0 is the animation table) or an empty one:
        # the bone never moves. An empty mesh section: the bone is a bare joint.
        if (track_sec or is_track_section(secs[0])) and secs[track_sec]:
            t, r, sc = parse_tracks(secs[track_sec])
        else:
            t, r, sc = [(0, (0, 0, 0))], [(0, (0, 0, 0))], [(0, (4096, 4096, 4096))]
        mesh = parse_mesh(secs[mesh_sec]) if secs[mesh_sec] else Mesh([], [], [])
        bones.append(Bone(index, parent, t, r, sc, mesh))
    for b in bones:
        seen, p = set(), b
        while p.parent:
            assert p.parent <= len(bones) and p.index not in seen, f"{name}: bad parent chain"
            seen.add(p.index)
            p = bones[p.parent - 1]
    texture = unrlen(secs[tex], 8) if secs[tex] else None
    if table0:
        table = secs[0]
    else:
        used = {hier, tex} | {m for _, m, _ in entries} | {t for _, _, t in entries}
        last = max(f for b in bones for keys in (b.translation, b.rotation, b.scale)
                   for f, _ in keys if f != TRACK_END)
        table = find_anim_table(secs, used, last)
    anims = parse_anim_table(table) if table is not None else whole_timeline(bones)
    return Model(name, bones, anims, texture, secs)
