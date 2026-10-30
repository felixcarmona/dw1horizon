"""Meshes of the battle models: one per bone, either OMD0 (the game's own
format, most bones) or a plain Psy-Q TMD (some bones, and every model in G.DRV).
Both are read into the same `Mesh`: vertices in the bone's local space and
primitives that index them.

OMD0 (all integers little-endian):

    "OMD0", u32 flags (0), u32 object count (always 1)
    u32 0, i16 bbox_min[4], i16 bbox_max[4], u32 0x24, u32 part count
    per part:
        u32 nv, nv x (i16 x, y, z, pad)                      vertices
        u32 group count, per group:                          lighting groups
            u8 n, u8 r, g, b, n x (i16 x, y, z, pad)         normals, 4096 = 1.0
        primitive blocks until a u32 0:
            u32 header: bits 0-7 mode, bits 8-19 n1, bits 20-31 n0
            n0 strip groups of class 0, then n1 of class 1, each:
                u16 strips, u16 length
                strips x: first primitive (3 or 4 corners), then length - 1
                steps of 1 corner (triangles) or 2 corners (quads)

`mode` is the GPU/TMD mode byte: bit 2 textured, bit 3 quad, bit 4 Gouraud,
bit 1 semi-transparent. A corner is `u16 colour_ref, u16 vertex_ref`, offsets
into the scratch buffer the renderer fills: vertex k is at 8*k, lighting entry
k at 8*nv + 4*k. A group of n normals gives n lighting entries; an empty group
gives one unlit entry of its colour. Textured primitives follow their corners
with as many texture words (`u8 u, u8 v, u16 extra`); a strip step gives its
1 or 2 corners, then their texture words.

Strips are not the usual "drop the oldest corner" kind. The renderer
(SLUS_013.28, 0x8001f94c) keeps the corners in GTE slots and each step
overwrites particular slots (STEP_SLOTS below; class 0 keeps slot 0 fixed,
a fan, class 1 rotates). The primitive drawn is the slots in order, its CLUT
taken from the texture word in slot 0 and its page from slot 1, and on odd
steps it is culled with the NCLIP sign reversed, i.e. it faces the other way.
Read like this, 99.2 % of the lit primitives face the way their own normals
say (the same share as the plain TMD meshes).

Parts exist because the scratch buffer is small (the largest part has 92
vertices); all parts of an object belong to the same bone.
"""
import struct
from dataclasses import dataclass, field


def u16(d, p): return struct.unpack_from("<H", d, p)[0]
def u32(d, p): return struct.unpack_from("<I", d, p)[0]


@dataclass
class Prim:
    verts: list               # vertex indices, 3 or 4, PS1 corner order
    normals: list | None      # normal index per corner, None if unlit
    uvs: list | None          # (u, v) per corner, None if untextured
    clut: tuple = (0, 0)      # CLUT position in VRAM (x, y)
    tpage: int = 0            # TSB
    color: tuple = (128, 128, 128)
    semi: bool = False        # semi-transparent (mode bit 1)


@dataclass
class Mesh:
    vertices: list = field(default_factory=list)
    normals: list = field(default_factory=list)
    prims: list = field(default_factory=list)
    kind: str = ""            # "OMD0" or "TMD"


def _corners(d, q, n):
    return [(u16(d, q + 4 * k), u16(d, q + 4 * k + 2)) for k in range(n)], q + 4 * n


def _texwords(d, q, n):
    return [(d[q + 4 * k], d[q + 4 * k + 1], u16(d, q + 4 * k + 2)) for k in range(n)], q + 4 * n


# Which GTE slots the corners of strip step k (k >= 1) are loaded into, as the
# renderer at 0x8001f94c does it (class 0 / class 1 groups of a block):
STEP_SLOTS = {
    (False, 0): lambda k: [2] if k % 2 else [1],
    (False, 1): lambda k: [[2, 0, 1][(k - 1) % 3]],
    (True, 0): lambda k: [2, 3] if k % 2 else [1, 3],
    (True, 1): lambda k: [2, 3] if k % 2 else [0, 1],
}
# Same triangles, other winding: (a, b, c) -> (b, a, c); a quad, drawn as
# (a, b, c) + (b, d, c), -> (a, c, b, d).
FLIP = {False: [1, 0, 2], True: [0, 2, 1, 3]}


def parse_omd(d, p):
    """Parse the OMD0 object at p; returns (Mesh, end offset)."""
    if d[p:p + 4] != b"OMD0" or u32(d, p + 8) != 1:
        raise ValueError(f"not an OMD0 object at {p:#x}")
    q = p + 32
    nparts = u32(d, q + 4)
    q += 8
    mesh = Mesh(kind="OMD0")
    for _ in range(nparts):
        nv = u32(d, q); q += 4
        vbase = len(mesh.vertices)
        mesh.vertices += [struct.unpack_from("<3h", d, q + 8 * i) for i in range(nv)]
        q += 8 * nv
        light = []                               # lighting entry -> (rgb, normal index or None)
        ngroups = u32(d, q); q += 4
        for _ in range(ngroups):
            n, rgb = d[q], tuple(d[q + 1:q + 4]); q += 4
            if n == 0:
                light.append((rgb, None))
            for i in range(n):
                light.append((rgb, len(mesh.normals)))
                mesh.normals.append(struct.unpack_from("<3h", d, q + 8 * i))
            q += 8 * n

        def make_prim(slots, order, tex, semi):
            corners = [slots[i] for i in order]
            cs = [corner(r) for r, _ in corners]
            lit = all(c[1][1] is not None for c in cs)
            prim = Prim([c[0] for c in cs], [c[1][1] for c in cs] if lit else None,
                        [(t[0], t[1]) for _, t in corners] if tex else None,
                        color=cs[0][1][0], semi=semi)
            if tex:
                # the GPU packet takes the CLUT from slot 0's texture word and
                # the texture page from slot 1's
                cba, tsb = slots[0][1][2], slots[1][1][2]
                prim.clut = ((cba & 0x3f) * 16, cba >> 6)
                prim.tpage = tsb
            return prim

        def corner(ref):
            cref, vref = ref
            if vref % 8 or vref // 8 >= nv or (cref - 8 * nv) % 4 or not 0 <= (cref - 8 * nv) // 4 < len(light):
                raise ValueError(f"corner out of range at {q:#x}")
            return vbase + vref // 8, light[(cref - 8 * nv) // 4]

        while u32(d, q):
            header = u32(d, q); q += 4
            mode = header & 0xff
            tex, quad, semi = bool(mode & 4), bool(mode & 8), bool(mode & 2)
            nc = 4 if quad else 3
            counts = (header >> 20, (header >> 8) & 0xfff)   # groups of class 0, class 1
            for cls in (0, 1):
                for _ in range(counts[cls]):
                    strips, length = u16(d, q), u16(d, q + 2); q += 4
                    for _ in range(strips):
                        refs, q = _corners(d, q, nc)
                        tw = [None] * nc
                        if tex:
                            tw, q = _texwords(d, q, nc)
                        slots = list(zip(refs, tw))
                        for step in range(length):
                            if step:
                                into = STEP_SLOTS[(quad, cls)](step)
                                new, q = _corners(d, q, len(into))
                                nt = [None] * len(into)
                                if tex:
                                    nt, q = _texwords(d, q, len(into))
                                for k, slot in enumerate(into):
                                    slots[slot] = (new[k], nt[k])
                            # The game culls with the NCLIP sign flipped on odd
                            # steps: those are emitted with the other winding.
                            order = FLIP[quad] if step % 2 else list(range(nc))
                            mesh.prims.append(make_prim(slots, order, tex, semi))
        q += 4
    return mesh, q


def parse_tmd(d, p):
    """Parse a TMD at p; returns (Mesh, end offset). The primitive layouts are the
    standard Psy-Q ones: texture words, then an RGB word if unlit or untextured,
    then normal/vertex indices (one normal per corner if Gouraud, one for the
    face if flat, none if unlit)."""
    if u32(d, p) != 0x41:
        raise ValueError(f"not a TMD at {p:#x}")
    nobj = u32(d, p + 8)
    base = p + 12
    mesh, end = Mesh(kind="TMD"), base
    for i in range(nobj):
        vt, nv, nt, nn, pt, npr, _scale = struct.unpack_from("<7I", d, base + 28 * i)
        end = max(end, base + vt + 8 * nv, base + nt + 8 * nn)
        vb, nb = len(mesh.vertices), len(mesh.normals)
        mesh.vertices += [struct.unpack_from("<3h", d, base + vt + 8 * k) for k in range(nv)]
        mesh.normals += [struct.unpack_from("<3h", d, base + nt + 8 * k) for k in range(nn)]
        q = base + pt
        for _ in range(npr):
            olen, ilen, flag, mode = d[q:q + 4]
            w = q + 4
            q = w + 4 * ilen
            nc = 4 if mode & 8 else 3
            tex, gour, semi = bool(mode & 4), bool(mode & 0x10), bool(mode & 2)
            unlit = bool(flag & 1)
            uvs = clut = tpage = None
            color = (128, 128, 128)
            if tex:
                tw = [(d[w + 4 * k], d[w + 4 * k + 1], u16(d, w + 4 * k + 2)) for k in range(nc)]
                uvs = [(t[0], t[1]) for t in tw]
                clut = ((tw[0][2] & 0x3f) * 16, tw[0][2] >> 6)
                tpage = tw[1][2]
                w += 4 * nc
            if unlit or not tex:
                color = tuple(d[w:w + 3])
                w += 4
            hw = [u16(d, x) for x in range(w, q, 2)]   # the index words
            if unlit:
                verts, normals = hw[:nc], None
            elif gour:
                normals, verts = hw[0:2 * nc:2], hw[1:2 * nc:2]
            else:
                normals, verts = [hw[0]] * nc, hw[1:1 + nc]
            mesh.prims.append(Prim([vb + v for v in verts], [nb + n for n in normals] if normals else None,
                                   uvs, clut or (0, 0), tpage or 0, color, semi))
    return mesh, end


def parse_object(d, p):
    if d[p:p + 4] == b"OMD0":
        return parse_omd(d, p)
    return parse_tmd(d, p)
