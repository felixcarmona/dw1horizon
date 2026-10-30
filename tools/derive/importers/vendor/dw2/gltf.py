"""Export a Digimon World 2 model as binary glTF 2.0 (.glb): one mesh skinned
rigidly to the bone hierarchy (each part follows one bone, as in the game), the
texture as an atlas with one band per palette used, one animation per
animation slot of every bank."""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import io
import json
import struct

from tools.derive import arraymath as np

from .model import world_matrices
from .texture import image_halfwords, render

FPS = 30            # one animation frame per two 60 Hz ticks (Anim_StepModelAnim)
SCALE = 1 / 100     # PS1 units to metres (arbitrary)


class Builder:
    def __init__(self):
        self.bin = bytearray()
        self.gltf = {"asset": {"version": "2.0", "generator": "digimonworld2/dw2"},
                     "buffers": [], "bufferViews": [], "accessors": []}

    def view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            v["target"] = target
        self.bin += data
        self.gltf["bufferViews"].append(v)
        return len(self.gltf["bufferViews"]) - 1

    def accessor(self, array, kind, target=None, minmax=False, normalized=False):
        array = np.ascontiguousarray(array)
        ctype = {np.float32: 5126, np.uint8: 5121, np.uint16: 5123, np.int16: 5122}[array.dtype.type]
        a = {"bufferView": self.view(array.tobytes(), target), "componentType": ctype,
             "count": len(array), "type": kind}
        if normalized:
            a["normalized"] = True
        if minmax:
            a["min"] = array.min(axis=0).tolist() if array.ndim > 1 else [float(array.min())]
            a["max"] = array.max(axis=0).tolist() if array.ndim > 1 else [float(array.max())]
        self.gltf["accessors"].append(a)
        return len(self.gltf["accessors"]) - 1

    def glb(self):
        self.gltf["buffers"] = [{"byteLength": len(self.bin)}]
        js = json.dumps(self.gltf, separators=(",", ":")).encode()
        js += b" " * (-len(js) % 4)
        self.bin += b"\0" * (-len(self.bin) % 4)
        out = struct.pack("<3I", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(self.bin))
        out += struct.pack("<2I", len(js), 0x4E4F534A) + js
        out += struct.pack("<2I", len(self.bin), 0x004E4942) + bytes(self.bin)
        return out


from functools import lru_cache


def decompose(m):
    """A game key's rotation/scale; repeated bone keys share immutable results."""
    key = tuple(float(v) for row in m for v in row)
    q, scale = _decompose(key)
    return np.Array(list(q), (4,), np.float64), np.Array(list(scale), (3,), np.float64)


@lru_cache(maxsize=4096)
def _decompose(key):
    m = np.Array(list(key), (3, 3), np.float64)
    u, _, vt = np.linalg.svd(m)
    r = u @ vt
    if np.linalg.det(r) < 0:
        u[:, -1] = -u[:, -1]
        r = u @ vt
    s = np.einsum("ij,ij->j", r, m)  # column i of M is s_i times column i of R
    return tuple(quaternion(r)), tuple(s)


def quaternion(m):
    """xyzw quaternion of a rotation matrix (Shepperd's method: picks the largest
    component first, so rotations near 180 degrees keep their signs)."""
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        w = np.sqrt(1 + tr) * 2
        q = [(m[2, 1] - m[1, 2]) / w, (m[0, 2] - m[2, 0]) / w, (m[1, 0] - m[0, 1]) / w, w / 4]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        x = np.sqrt(1 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [x / 4, (m[0, 1] + m[1, 0]) / x, (m[0, 2] + m[2, 0]) / x, (m[2, 1] - m[1, 2]) / x]
    elif m[1, 1] > m[2, 2]:
        y = np.sqrt(1 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 1] + m[1, 0]) / y, y / 4, (m[1, 2] + m[2, 1]) / y, (m[0, 2] - m[2, 0]) / y]
    else:
        z = np.sqrt(1 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[0, 2] + m[2, 0]) / z, (m[1, 2] + m[2, 1]) / z, z / 4, (m[1, 0] - m[0, 1]) / z]
    q = np.array(q)
    return q / np.linalg.norm(q)


def rest_matrices(model):
    """Local matrices of the bind pose: the first frame of the first animation,
    or identity for models without animations (as Gfx_ResetModelBones)."""
    if not model.animations:
        return [np.eye(4) for _ in model.bones]
    a = model.animations[0]
    out = []
    for b in model.bones:
        rot, t = model.keys[a.bank][b.index][a.frames[0][b.index]]
        m = np.eye(4)
        m[:3, :3], m[:3, 3] = rot, t
        out.append(m)
    return out


def bind_worlds(model):
    """World matrices of the bind pose with the scale taken out (some keys hide a
    part with scale 0, which would make the bind matrix singular)."""
    worlds = []
    for b, m in zip(model.bones, rest_matrices(model)):
        q, _ = decompose(m[:3, :3])
        local = np.eye(4)
        local[:3, :3] = quat_matrix(q)
        local[:3, 3] = m[:3, 3]
        worlds.append(local if b.parent < 0 else worlds[b.parent] @ local)
    return worlds


def quat_matrix(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def build_geometry(model, worlds):
    """Corners [(position, normal, uv, bone)] and the CLUTs in atlas order."""
    cluts = sorted({p.clut for b in model.bones for p in b.prims})
    band = {c: i for i, c in enumerate(cluts)}
    tex_w = image_halfwords(model.texture).shape[1] * 4
    tex_h = image_halfwords(model.texture).shape[0]
    corners = {False: [], True: []}
    for bone, w in zip(model.bones, worlds):
        if not bone.vertices:
            continue
        rot = w[:3, :3]
        verts = np.array(bone.vertices, float) @ rot.T + w[:3, 3]
        normals = np.array(bone.normals, float) / 4096 @ rot.T if bone.normals else None
        for p in bone.prims:
            pos = verts[list(p.verts)]
            face = np.cross(pos[2] - pos[0], pos[1] - pos[0])
            face = face / np.linalg.norm(face) if np.linalg.norm(face) else np.array([0.0, -1.0, 0.0])
            nrm = normals[list(p.normals)] if normals is not None else np.tile(face, (len(pos), 1))
            length = np.linalg.norm(nrm, axis=1, keepdims=True)
            nrm = np.where(length > 1e-6, nrm / np.maximum(length, 1e-9), face)
            k = band[p.clut]
            uv = [((u + 0.5) / tex_w, (k * tex_h + v + 0.5) / (tex_h * len(cluts))) for u, v in p.uvs]
            # Quads are drawn (0, 1, 2) + (1, 3, 2); reversed to be
            # counter-clockwise once the Y-down space is flipped.
            for tri in ([(0, 2, 1)] if len(pos) == 3 else [(0, 2, 1), (1, 2, 3)]):
                for i in tri:
                    corners[p.semi].append((tuple(pos[i]), tuple(nrm[i]), uv[i], bone.index))
    return corners, cluts


def linear_keys(data, eps=1e-4):
    keep = [0]
    for i in range(1, len(data) - 1):
        a, b = data[keep[-1]], data[i + 1]
        span = i + 1 - keep[-1]
        ts = (np.arange(keep[-1] + 1, i + 1) - keep[-1]) / span
        if np.abs(a + (b - a) * ts[:, None] - data[keep[-1] + 1:i + 1]).max() > eps:
            keep.append(i)
    if len(data) > 1:
        keep.append(len(data) - 1)
    if len(keep) == 2 and np.abs(data[0] - data[-1]).max() <= eps:
        keep = [0]
    return np.array(keep)


def export_glb(model):
    b = Builder()
    g = b.gltf
    nb = len(model.bones)
    bind = bind_worlds(model)

    root = {"name": model.name, "rotation": [1.0, 0.0, 0.0, 0.0], "scale": [SCALE] * 3, "children": []}
    nodes = [root]
    for bone, m in zip(model.bones, rest_matrices(model)):
        q, s = decompose(m[:3, :3])
        nodes.append({"name": f"bone_{bone.index:02d}", "translation": m[:3, 3].tolist(),
                      "rotation": q.tolist(), "scale": s.tolist()})
    for bone in model.bones:
        (nodes[bone.parent + 1] if bone.parent >= 0 else root).setdefault("children", []).append(bone.index + 1)
    g["nodes"] = nodes

    corners, cluts = build_geometry(model, bind)
    atlas = np.concatenate([render(model.texture, c) for c in cluts], axis=0)
    buf = io.BytesIO()
    from tools.image import Image  # export-only; importing the matrix decoder needs just numpy
    Image.fromarray(atlas, "RGBA").save(buf, "PNG")
    g["images"] = [{"bufferView": b.view(buf.getvalue()), "mimeType": "image/png"}]
    g["samplers"] = [{"magFilter": 9728, "minFilter": 9728}]
    g["textures"] = [{"source": 0, "sampler": 0}]
    materials, prims = [], []
    for semi, cs in corners.items():
        if not cs:
            continue
        # Both kinds use alpha masking: CLUT colour 0x0000 is transparent. On
        # the PS1 the "semi-transparent" polygons only blend texels whose STP
        # bit is set; the extras keep the flag.
        materials.append({"name": "semi_transparent" if semi else "opaque", "doubleSided": False,
                          "alphaMode": "MASK", "extras": {"ps1_semi_transparency": semi},
                          "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                                   "metallicFactor": 0.0, "roughnessFactor": 1.0}})
        attrs = {
            "POSITION": b.accessor(np.array([c[0] for c in cs], np.float32), "VEC3", 34962, minmax=True),
            "NORMAL": b.accessor(np.array([c[1] for c in cs], np.float32), "VEC3", 34962),
            "TEXCOORD_0": b.accessor(np.array([c[2] for c in cs], np.float32), "VEC2", 34962),
            "JOINTS_0": b.accessor(np.array([(c[3], 0, 0, 0) for c in cs], np.uint8), "VEC4", 34962),
            "WEIGHTS_0": b.accessor(np.tile(np.array([1, 0, 0, 0], np.float32), (len(cs), 1)), "VEC4", 34962),
        }
        prims.append({"attributes": attrs, "material": len(materials) - 1, "mode": 4})
    g["materials"] = materials
    g["meshes"] = [{"name": model.name, "primitives": prims}]
    ibm = np.array([np.linalg.inv(m).T for m in bind], np.float32)
    g["skins"] = [{"joints": list(range(1, nb + 1)), "skeleton": 0,
                   "inverseBindMatrices": b.accessor(ibm.reshape(nb, 16), "MAT4")}]
    nodes.append({"name": f"{model.name}_mesh", "mesh": 0, "skin": 0})
    g["scenes"] = [{"nodes": [0, nb + 1]}]
    g["scene"] = 0

    anims = []
    for anim in model.animations:
        times_all = np.arange(len(anim.frames), dtype=np.float32) / FPS
        times = b.accessor(times_all, "SCALAR", minmax=True)
        samplers, channels = [], []
        for bone in model.bones:
            keys = model.keys[anim.bank][bone.index]
            ts, qs, ss = [], [], []
            for fr in anim.frames:
                rot, t = keys[fr[bone.index]]
                q, s = decompose(rot)
                ts.append(t)
                qs.append(q)
                ss.append(s)
            qs = np.array(qs)
            for i in range(1, len(qs)):
                if qs[i] @ qs[i - 1] < 0:
                    qs[i] = -qs[i]
            for path, data, kind in (("translation", np.array(ts, np.float32), "VEC3"),
                                     ("rotation", qs, "VEC4"),
                                     ("scale", np.array(ss, np.float32), "VEC3")):
                if path == "rotation":
                    # Every frame: the game switches whole matrices per frame.
                    inp, out, norm = times, np.round(data * 32767).astype(np.int16), True
                else:
                    keep = linear_keys(data)
                    inp = times if len(keep) == len(data) else b.accessor(times_all[keep], "SCALAR", minmax=True)
                    out, norm = data[keep], False
                samplers.append({"input": inp, "output": b.accessor(out, kind, normalized=norm),
                                 "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1, "target": {"node": bone.index + 1, "path": path}})
        name = f"{anim.bank}{anim.slot}" + ("_loop" if anim.loop_to is not None else "")
        anims.append({"name": name, "samplers": samplers, "channels": channels,
                      "extras": {"bank": anim.bank, "slot": anim.slot, "loop_to_frame": anim.loop_to}})
    if anims:
        g["animations"] = anims
    return b.glb()
