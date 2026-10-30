"""Mesh sections of the battle models (AAA/DAT/FIGHT/MODEL/M*.BIN).

Layout of one mesh section (all offsets relative to the section start):

    u32 vertices_offset
    u32 normals_offset
    u32 prims_offset
    u32 unknown0, unknown1
    u32 bounds_offset            -> same list layout: centre + 8 box corners

    list := u32 count, u16 pad, count * (s16 x, s16 y, s16 z)
            normals are 1.12 fixed point (4096 == 1.0)

    prims := a byte stream; each byte is one of
        0xff          end of stream
        0x8R..0xeR    state write: register (byte >> 4) = byte & 0x0f, no record
                      follows. The stream opens with one write to each of the
                      registers 8, 9, a, b, c, d, e. Register 8 is the primitive
                      kind (0 triangles, 1 quads); the others are render state.
        0x00          a record of the current kind follows
        0x01          a 7-byte material header, then a record
        0x02          a 3-byte RGB colour (for unlit primitives), no record
    Register 9 says whether records carry UVs (1) or not (0), register c
    whether they carry normal indices (1) or not (0).
        triangle: v0 v1 v2, [n0 n1 n2], (u, v) * 3
        quad:     v0 v1 v2 v3, [n0 n1 n2 n3], (u, v) * 4
"""
import struct
from dataclasses import dataclass, field


@dataclass
class Prim:
    verts: tuple
    normals: tuple
    uvs: tuple
    material: bytes
    color: bytes
    state: dict


@dataclass
class Mesh:
    vertices: list
    normals: list
    bounds: list
    prims: list = field(default_factory=list)


def read_list(data, off):
    count = struct.unpack_from("<I", data, off)[0]
    vals = struct.unpack_from(f"<{count * 3}h", data, off + 6)
    return [vals[i:i + 3] for i in range(0, len(vals), 3)]


def parse_mesh(data):
    voff, noff, poff = struct.unpack_from("<3I", data, 0)
    boff = struct.unpack_from("<I", data, 20)[0]
    mesh = Mesh(read_list(data, voff), read_list(data, noff), read_list(data, boff))
    p = poff
    state = {}
    material = b""
    color = b"\x80\x80\x80"
    while True:
        flag = data[p]
        p += 1
        if flag == 0xFF:
            break
        if flag & 0x80:
            state[flag >> 4] = flag & 0x0F
            continue
        if flag == 0x02:
            color = data[p:p + 3]
            p += 3
            continue
        if flag & ~0x01:
            raise ValueError(f"unknown prim flag {flag:#x} at {p - 1:#x}")
        if flag & 0x01:
            material = data[p:p + 7]
            p += 7
        n = 4 if state.get(8) else 3
        lit = state.get(0xC, 1)
        textured = state.get(9, 1)
        size = (1 + lit + 2 * textured) * n
        rec = data[p:p + size]
        p += size
        normals = tuple(rec[n:2 * n]) if lit else ()
        uv = rec[(1 + lit) * n:]
        uvs = tuple((uv[2 * i], uv[2 * i + 1]) for i in range(n)) if textured else ()
        mesh.prims.append(Prim(tuple(rec[0:n]), normals, uvs, material, color, dict(state)))
    mesh.end = p
    return mesh
