"""Split Omnimon's bent quads along the GPU diagonal so each half gets its own NCLIP.

Developer-only repair, stored in the plain delta. Vertices, normals, texture,
back faces and animation programs are retained. No runtime pass on other species.

  python3 -m tools.models.repair_omnimon_mesh SOURCE.MMD OUT.MMD
  tools/models/edit.py repin 461 OUT.MMD
  tools/models/edit.py put 461 OUT.MMD
"""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
import motionstorage
from tools.models import meshcheck


from tools.models.mesh_stability import split_quad


def repair(data, skeleton, degrees=meshcheck.WARP_DEGREES):
    model = meshcheck.Model(data, skeleton)
    bent = meshcheck.warped_quads(model, degrees)
    selected = {(r['object'], r['primitive']) for r in bent}
    result = copy.deepcopy(model.m)
    for oi, ob in enumerate(result.tmd.objects):
        ob.prims = [p for pi, prim in enumerate(ob.prims)
                    for p in (split_quad(prim) if (oi, pi) in selected else [prim])]
    count = sum(len(o.prims) for o in result.tmd.objects)
    if count > 713:
        raise ValueError(f'primitive budget: {count} > 713')
    output = result.build()
    assert result.tmd.verts == model.m.tmd.verts and result.tmd.norms == model.m.tmd.norms
    assert result.anims.build() == model.m.anims.build()
    assert not meshcheck.warped_quads(meshcheck.Model(output, skeleton), degrees)
    return output, dict(split_quads=bent, primitives=count, storage=motionstorage.require(output, len(skeleton)))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('out', type=Path)
    args = p.parse_args()
    data, proof = repair(args.source.read_bytes(), mmd.exe().skeleton[461])
    args.out.write_bytes(data)
    print(json.dumps(proof, indent=2))
