"""Source variants of the imports (World 3 USA): the edit carry, the variant records and the pin keys of the patchers.

Synthetic models and images only: no disc is read."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / 'tools'))
sys.path.insert(2, str(ROOT / 'tools/patcher'))

import mmd  # noqa: E402
from tools.models import carry  # noqa: E402
from tools.models import delta as modeldelta  # noqa: E402
import dwpatch as dw  # noqa: E402
import literal_gate  # noqa: E402
from test_desktop_patcher import image  # noqa: E402

NB = 3          # bones (entity + two objects)


def prim(verts, uvs, norms=(0, 0, 0), cba=0x7A00, tsb=5):
    """A textured Gouraud triangle (mode 0x34)."""
    return mmd.Prim.encode(dict(mode=0x34, flag=0, olen=9, uv=list(uvs), cba=cba, tsb=tsb, uvpad=[0], colors=[],
                                norms=list(norms), verts=list(verts), pad=[]))


def anim(frames, value):
    a = mmd.Anim()
    a.frame_count, a.has_scale = frames, False
    a.pose = [[0, 0, value, 0, 0, 0] for _ in range(NB - 1)]
    a.instrs = [dict(op='end')]
    return a


def model(objects, slots):
    """objects: [(prims, verts, norms)]; slots: [Anim or None] (an Anim object twice: a shared stream)."""
    m = mmd.MMD()
    m.tmd = mmd.TMD()
    for prims, verts, norms in objects:
        o = mmd.TMDObject()
        o.prims = prims
        o.vert_start, o.nvert = len(m.tmd.verts), len(verts)
        o.norm_start, o.nnorm = len(m.tmd.norms), len(norms)
        m.tmd.verts += verts
        m.tmd.norms += norms
        m.tmd.objects.append(o)
    m.anims = mmd.AnimSection()
    order = []
    for a in slots:
        if a is not None and all(a is not b for b in order):
            order.append(a)
    m.anims.anims = order
    m.anims.table = [None if a is None else next(i for i, b in enumerate(order) if b is a) for a in slots]
    return m.build()


V = [(0, 0, 0, 0), (10, 0, 0, 0), (0, 10, 0, 0), (10, 10, 0, 0)]
N = [(0, 0, 4096, 0), (0, 4096, 0, 0)]
UV = [(1, 1), (9, 1), (1, 9)]


class Carry(unittest.TestCase):
    def setUp(self):
        idle, walk, hit = anim(10, 1), anim(20, 2), anim(5, 3)
        face = prim([0, 1, 2], UV, (0, 0, 0))
        other = prim([1, 3, 2], UV, (1, 1, 1))
        # the reference import S: object 0 two faces, object 1 one face; slots idle, walk, hit
        self.S = model([([face, other], V, N), ([face], V[:3], N[:1])], [idle, walk, hit])
        # our edit T: face 0 of object 0 turned round (winding), walk replaced, slot 3 pointed at idle
        flipped = prim([2, 1, 0], list(reversed(UV)), (0, 0, 0))
        self.T = model([([flipped, other], V, N), ([face], V[:3], N[:1])], [idle, anim(20, 7), hit, idle])
        # the other release U: object 1's mesh differs; object 0 the same faces in another order with other
        # vertex and normal indices; the hit animation differs
        Vu = [V[3], V[2], V[1], V[0]]
        Nu = [N[1], N[0]]
        face_u = prim([3, 2, 1], UV, (1, 1, 1))
        other_u = prim([2, 0, 1], UV, (0, 0, 0))
        self.U = model([([other_u, face_u], Vu, Nu), ([prim([0, 1, 2], UV)], [(5, 5, 5, 0)] * 3, N[:1])],
                       [idle, walk, anim(6, 4)])

    def test_same_source_gives_the_target_back(self):
        carry.selftest(self.S, self.T, NB)

    def test_edits_land_on_the_other_release(self):
        got, report = carry.carry(self.S, self.T, self.U, NB)
        m = mmd.MMD.parse(got, NB)
        u = mmd.MMD.parse(self.U, NB)
        # object 1 (not edited): the other release's mesh
        self.assertEqual(m.tmd.obj_verts(1), u.tmd.obj_verts(1))
        # object 0: the other release's faces; the one we turned round is turned round there, on its own indices
        faces = [p.decode() for p in m.tmd.objects[0].prims]
        self.assertEqual(faces[0]['verts'], [2, 0, 1])
        self.assertEqual(faces[1]['verts'], [1, 2, 3])
        self.assertEqual(faces[1]['uv'], list(reversed(UV)))
        self.assertEqual(faces[1]['norms'], [1, 1, 1])
        # slots: walk is ours, hit the other release's, slot 3 points at the other release's idle
        slots = [m.anims.anims[k].build() if k is not None else None for k in m.anims.table]
        self.assertEqual(slots[1], anim(20, 7).build())
        self.assertEqual(slots[2], anim(6, 4).build())
        self.assertEqual(slots[3], slots[0])
        self.assertEqual(report['objects_carried'], [0])
        self.assertEqual(report['objects_other'], [1])

    def test_an_edit_where_the_releases_differ_stops(self):
        T = model([([prim([0, 1, 2], UV), prim([1, 3, 2], UV, (1, 1, 1))], V, N), ([prim([0, 1, 2], UV)], V[:3], N[:1])],
                  [anim(10, 1), anim(20, 2), anim(5, 9)])        # we edited hit, which the other release changed
        with self.assertRaises(carry.CarryError):
            carry.carry(self.S, T, self.U, NB)

    def test_a_vertex_not_found_once_stops(self):
        moved = model([([prim([0, 1, 2], UV), prim([1, 3, 2], UV, (1, 1, 1))], [V[0], V[1], V[2], (11, 11, 0, 0)], N),
                       ([prim([0, 1, 2], UV)], V[:3], N[:1])], [anim(10, 1), anim(20, 2), anim(5, 3)])
        U = model([([prim([0, 1, 2], UV)], [V[0], V[1], V[2]], N), ([prim([0, 1, 2], UV)], V[:3], N[:1])],
                  [anim(10, 1), anim(20, 2), anim(5, 3)])
        with self.assertRaises(carry.CarryError):
            carry.carry(self.S, moved, U, NB)


class Records(unittest.TestCase):
    """The committed variant: every record carried from the current reference target, every file pinned."""

    def test_native_polish_pins_its_preceding_edit(self):
        for path in (ROOT / 'content/models/authoring/native-polish').glob('*.json'):
            row = json.loads(path.read_text())
            preceding = row.get('preceding_delta')
            if not preceding:
                continue
            with self.subTest(species=row['species']):
                delta = (ROOT / preceding['delta']).read_bytes()
                self.assertEqual(hashlib.sha256(delta).hexdigest(), preceding['delta_sha256'])
                self.assertEqual(preceding['sha256'], row['source_sha256'])
                self.assertTrue(delta.startswith(modeldelta.MAGIC + b'\0'))

    def test_variant_records_follow_the_reference(self):
        rows = {str(r['id']): r for r in json.loads((ROOT / 'content/modeldelta/models.json').read_text())['models']}
        pins = json.loads((ROOT / 'tools/derive/recipes/species-pins.json').read_text())
        imports = json.loads((ROOT / 'content/models/imports/models.json').read_text())
        for path in sorted((ROOT / 'content/modeldelta/variants').glob('*.json')):
            record = json.loads(path.read_text())
            release = record['variant']
            self.assertEqual(path.stem, release)
            self.assertEqual(set(pins.get(f'imports@{release}', {})), set(record['models']))
            for sid, entry in record['models'].items():
                with self.subTest(release=release, species=sid):
                    # an edit of the reference model since: run tools/models/variants.py make again
                    self.assertEqual(entry['from']['sha256'], rows[sid]['mmd']['sha256'],
                                     f'{sid}: the reference model changed; rerun tools/models/variants.py make {release}')
                    delta = (ROOT / entry['mmd']['delta']).read_bytes()
                    self.assertEqual(hashlib.sha256(delta).hexdigest(), entry['mmd']['delta_sha256'])
                    self.assertTrue(delta.startswith(modeldelta.MAGIC + b'\0'))       # plain copy/add only
                    self.assertEqual(entry['from']['foreign_windows'], 0)
                    if imports[sid].get('field_overlay'):
                        self.assertTrue(record['reviewed_as'], 'an overlay species needs its reviewed inputs')
            for target in record['sizes']:
                self.assertIn(target, record['sources'])

    def test_release_lists_hold_checksums_and_orders_only(self):
        for path in sorted((ROOT / 'content/imports/releases').glob('dw3-*.json')):
            j = json.loads(path.read_text())
            self.assertNotIn('patches', j, path.name)
            self.assertLessEqual(set(j), {'release', 'note', 'recipes', 'own', 'bone_order'}, path.name)
            for order in j.get('bone_order', {}).values():
                self.assertEqual(sorted(order), list(range(1, len(order) + 1)))


class PinKeys(unittest.TestCase):
    def test_pin_key_and_lookup(self):
        self.assertEqual(dw.pin_key('eu'), 'eu')
        self.assertEqual(dw.pin_key('eu', 'dw3-us'), 'eu+dw3-us')
        table = {'eu': 'a', 'eu+dw3-us': 'b', 'us+dw3-us': 'c'}
        self.assertEqual(dw.pinned_for(table, 'eu+dw3-us', 'z'), 'b')
        self.assertEqual(dw.pinned_for(table, 'fr+dw3-us', 'z'), 'z')     # neither: the default
        self.assertEqual(dw.pinned_for({'fr': 'f'}, 'fr+dw3-us', 'z'), 'f')  # not changed by the variant: the base's
        self.assertEqual(dw.pinned_for(table, 'us', 'z'), 'z')
        self.assertEqual(dw.pinned_for(None, 'us+dw3-us', 'z'), 'z')

    def test_source_variant_by_boot_file(self):
        m = dict(source_variants={'dw3-us': dict(game='dw2003', boot='SLUS_014.36')})
        with tempfile.TemporaryDirectory() as td:
            us, pal = Path(td) / 'us.bin', Path(td) / 'pal.bin'
            us.write_bytes(image('SLUS_014.36'))
            pal.write_bytes(image('SLES_039.36'))
            self.assertEqual(dw.source_variant(m, [f'dcb=x', f'dw2003={us}']), 'dw3-us')
            self.assertIsNone(dw.source_variant(m, [f'dw2003={pal}']))
            self.assertIsNone(dw.source_variant({}, [f'dw2003={us}']))          # a release made before variants
            self.assertIsNone(dw.source_variant(m, [f'dw2={us}']))              # another game's slot

    def test_hole_check_takes_the_variant_checksum(self):
        holes = [dict(id=0, file='A.BIN', size=1, sha1=hashlib.sha1(b'a').hexdigest(),
                      sha1_by_base={'eu': hashlib.sha1(b'e').hexdigest(), 'eu+dw3-us': hashlib.sha1(b'v').hexdigest()}),
                 dict(id=1, file='B.BIN', size=1, sha1=hashlib.sha1(b'b').hexdigest())]
        v = dict(local=dict(builder='derive'), holes=holes)

        class Base:
            key, pin = 'eu', 'eu+dw3-us'
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'A.BIN').write_bytes(b'v')
            (Path(td) / 'B.BIN').write_bytes(b'b')
            files = {'A.BIN': str(Path(td) / 'A.BIN'), 'B.BIN': str(Path(td) / 'B.BIN')}
            with patch.object(dw, 'derive_holes', return_value=files):
                self.assertEqual(set(dw.local_holes3({}, v, Base(), td, td, None)), {0, 1})
                Base.pin = 'eu'
                with self.assertRaises(dw.PatchError):
                    dw.local_holes3({}, v, Base(), td, td, None)

    def test_a_package_without_the_variant_stops_before_building(self):
        with tempfile.TemporaryDirectory() as td:
            rel = Path(td)
            (rel / 'bundle/content/modeldelta/variants').mkdir(parents=True)
            (rel / 'bundle/content/modeldelta/variants/dw3-us.json').write_text('{}')
            (rel / 'bundle/tools').mkdir(parents=True)
            (rel / 'bundle/tools/discs.py').write_text((ROOT / 'tools/discs.py').read_text())
            us = rel / 'us.bin'
            us.write_bytes(image('SLUS_014.36'))
            self.assertEqual(dw.unrecorded_variant({}, str(rel), [f'dw2003={us}']), 'Digimon World 3 (USA)')
            m = dict(source_variants={'dw3-us': dict(game='dw2003', boot='SLUS_014.36')})
            self.assertIsNone(dw.unrecorded_variant(m, str(rel), [f'dw2003={us}']))
            (rel / 'bundle/content/modeldelta/variants/dw3-us.json').unlink()     # a package made before variants
            self.assertIsNone(dw.unrecorded_variant({}, str(rel), [f'dw2003={us}']))

    def test_a_variant_build_never_rewrites_the_reference_pins(self):
        from tools.derive.steps import species as step
        with tempfile.TemporaryDirectory() as td:
            games = Path(td) / 'source-games/dw2003/disc'
            games.mkdir(parents=True)
            (games / 'SYSTEM.CNF').write_text('BOOT = cdrom:\\SLUS_014.36;1\r\n')
            model = Path(td) / '180.MMD'
            model.write_bytes(b'not the pinned model')

            class Ctx:
                developer = True
                def path(self, *p): return str(Path(td, *p))

            class Provider:
                name = 'imports'
                def provide_models(self, ctx): return {180: (str(model), None)}
            pins = (ROOT / step.PINS).read_bytes()
            with patch.object(step.runner, 'strict', return_value=False), self.assertRaises(SystemExit) as e:
                step.pinned(Ctx(), Provider())
            self.assertIn('variants.py make dw3-us', str(e.exception))
            self.assertEqual((ROOT / step.PINS).read_bytes(), pins)

    def test_engine_plan_gives_the_variant_jobs_their_files(self):
        sys.path.insert(0, str(ROOT / 'web/enginebuild'))
        import build_engine
        pal = 'build/everything/source-games/dw2003/disc/AAA/DAT/FIGHT/MODEL/M373RENA.BIN'
        plan = dict(paths=[pal, 'a-bundle-file'],
                    files=[['content/modeldelta/variants/dw3-us.json'], ['content/modeldelta/deltas/dw3-us/354-Renamon.MMD.mdelta'],
                           ['content/modeldelta/models.json']],
                    jobs=[dict(step='imports', tree=[0], bundle=[1]), dict(step='maps', tree=[], bundle=[1])])
        build_engine.alias_source_paths(plan)
        build_engine.add_variant_inputs(plan)
        imports, maps = plan['jobs']
        self.assertIn('build/everything/source-games/dw2003/disc/AAA/DAT/MODEL/M373RENA.BIN',
                      [plan['paths'][i] for i in imports['tree']])
        self.assertEqual(sorted(plan['paths'][i] for i in imports['bundle'] if 'dw3-us' in plan['paths'][i]),
                         ['content/modeldelta/deltas/dw3-us/354-Renamon.MMD.mdelta', 'content/modeldelta/variants/dw3-us.json'])
        self.assertEqual(maps['bundle'], [1])

    def test_gate_wants_every_base_with_every_variant(self):
        m = dict(bases={'us': {}, 'eu': {}}, source_variants={'dw3-us': {}})
        self.assertTrue(literal_gate.output_keys_complete(
            {'us': 1, 'eu': 1, 'us+dw3-us': 1, 'eu+dw3-us': 1}, m))
        self.assertFalse(literal_gate.output_keys_complete({'us': 1, 'eu': 1, 'us+dw3-us': 1}, m))
        self.assertTrue(literal_gate.output_keys_complete({'us': 1, 'eu': 1}, dict(m, source_variants={})))


    def test_gate_refuses_a_source_list_that_rebuilds_another_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'bundle/content/imports/releases').mkdir(parents=True)
            lst = root / 'bundle/content/imports/releases/dw3-us.json'
            lst.write_text(json.dumps(dict(release='us', recipes={'M1': 'aa'}, own={'M1': 'bb'})))
            literal_gate.mapping_chunks(root)
            lst.write_text(json.dumps(dict(release='us', recipes={'M1': 'aa'}, patches={'M1': {'ops': []}})))
            with self.assertRaises(literal_gate.GateFailure):
                literal_gate.mapping_chunks(root)


if __name__ == '__main__':
    unittest.main()
