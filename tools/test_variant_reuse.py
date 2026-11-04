"""tools/patcher/variantreuse.py: when make-release may reuse the USA source-variant derive for the regional bases."""
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'tools', 'patcher')]
import variantreuse as V  # noqa: E402

GRAPH = {'models': (), 'imports': (), 'record_originals': (), 'overlays': ('imports', 'record_originals'),
         'species': ('models', 'overlays', 'record_originals'), 'localize': (), 'story': (),
         'signs': ('story',), 'plan': ('models', 'species', 'localize', 'story', 'signs')}
OUTPUTS = {'models': ['m.mmd'], 'imports': ['imp'], 'record_originals': ['ro'], 'overlays': ['ovl'],
           'species': ['DIGI.DAT'], 'localize': ['loc.tim'], 'story': ['st.map'], 'signs': ['sg.map'],
           'plan': ['lang/LE000.TIM']}
DISC = {'DIGI.DAT': 'DIGI.DAT', 'ETCNA/T.TIM': 'loc.tim', 'MAP/S.MAP': 'st.map', 'ETCDAT/LE000.TIM': 'lang/LE000.TIM'}
HOLES = [dict(id=i, file=q) for i, q in enumerate(DISC)]


def manifest(outputs=OUTPUTS, files=DISC):
    return dict(files={q: dict(file=f) for q, f in files.items()},
                steps={n: dict(outputs=o) for n, o in outputs.items()})


def recorded(reads=None):
    reads = reads or {'localize': ['extracted/ETCNA/T.TIM'], 'story': ['extracted/MAP/S.MAP'],
                      'species': ['extracted/SLUS_010.32x']}
    return dict(steps={n: dict(inputs=reads.get(n, [])) for n in GRAPH})


def bases(**override):
    us = {h['id']: h['file'].encode() for h in HOLES}
    jp = {**us, **{1: b'jp title', 3: b'jp copy'}}
    b = dict(us=us, eu={**us, **{1: b'eu title'}}, jp1=jp)
    b.update(override)
    return b


class Reuse(unittest.TestCase):
    def test_reused_when_the_steps_do_not_meet(self):
        b = bases()
        made = {**b['us'], **{0: b'world 3 usa'}}
        got, why = V.reuse(HOLES, b, made, manifest(), recorded(), GRAPH, {'ETCNA/T.TIM', 'MAP/S.MAP'})
        self.assertIsNone(why)
        for key in b:
            self.assertEqual(got[key], {**b[key], **{0: b'world 3 usa'}})

    def test_nothing_changed(self):
        b = bases()
        got, why = V.reuse(HOLES, b, dict(b['us']), manifest(), recorded(), GRAPH, {'ETCNA/T.TIM'})
        self.assertEqual(got, b)

    def test_changed_file_differs_per_base(self):
        b = bases(jp1={**bases()['jp1'], **{0: b'jp digi'}})
        made = {**b['us'], **{0: b'world 3 usa'}}
        got, why = V.reuse(HOLES, b, made, manifest(), recorded(), GRAPH, set())
        self.assertIsNone(got)
        self.assertIn('DIGI.DAT', why)

    def test_regional_file_changes_on_usa(self):
        b = bases()
        made = {**b['us'], **{1: b'other title'}}
        got, why = V.reuse(HOLES, b, made, manifest(), recorded(), GRAPH, {'ETCNA/T.TIM'})
        self.assertIsNone(got)
        self.assertIn('ETCNA/T.TIM', why)

    def test_source_step_reads_the_base(self):
        b = bases()
        made = {**b['us'], **{0: b'world 3 usa'}}
        reads = {'imports': ['extracted/ETCNA/T.TIM']}
        got, why = V.reuse(HOLES, b, made, manifest(), recorded(reads), GRAPH, {'ETCNA/T.TIM'})
        self.assertIsNone(got)
        self.assertIn('imports', why)

    def test_a_dependent_of_a_source_step_reads_the_base(self):
        b = bases()
        made = {**b['us'], **{0: b'world 3 usa'}}
        reads = {'models': ['extracted/ETCNA/T.TIM']}            # species reads models: DIGI.DAT may differ per base
        got, why = V.reuse(HOLES, b, made, manifest(), recorded(reads), GRAPH, {'ETCNA/T.TIM'})
        self.assertIsNone(got)

    def test_plan_made_the_changed_file(self):
        b = bases()
        made = {**b['us'], **{3: b'other copy'}}
        b = dict(b, jp1={**b['jp1'], **{3: b['us'][3]}})       # (not regional: only plan's ownership stops it)
        got, why = V.reuse(HOLES, b, made, manifest(), recorded(), GRAPH, {'ETCNA/T.TIM'})
        self.assertIsNone(got)
        self.assertIn('plan', why)

    def test_unrecorded_steps(self):
        b = bases()
        made = {**b['us'], **{0: b'x'}}
        rec = recorded()
        del rec['steps']['species']['inputs']
        self.assertIsNone(V.reuse(HOLES, b, made, manifest(), rec, GRAPH, set())[0])
        self.assertIsNone(V.reuse(HOLES, b, made, manifest(), recorded(), GRAPH, None)[0])
        self.assertIsNone(V.reuse(HOLES, b, {0: b'x'}, manifest(), recorded(), GRAPH, set())[0])

    def test_differing_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            def put(tree, q, data):
                p = os.path.join(td, tree, 'extracted', *q.split('/'))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, 'wb') as f:
                    f.write(data)
            for tree in ('us', 'eu'):
                put(tree, 'A/SAME.BIN', b'same')
            put('us', 'A/OWN.TIM', b'usa'); put('eu', 'A/OWN.TIM', b'europe')
            roots = {'eu': os.path.join(td, 'eu')}
            self.assertEqual(V.differing_inputs(os.path.join(td, 'us'), roots, ['A/SAME.BIN', 'A/OWN.TIM']),
                             {'A/OWN.TIM'})
            self.assertIsNone(V.differing_inputs(os.path.join(td, 'us'), roots, ['A/MISSING.BIN']))


class RecordSourceVariants(unittest.TestCase):
    """dwpatch.record_source_variants' two ways: the USA run reused, or derive on every regional base."""
    def run_it(self, verdict):
        import argparse
        from unittest.mock import patch
        import dwpatch as dw
        calls = []
        holes = [dict(id=0, file='DIGI.DAT'), dict(id=1, file='ETCNA/T.TIM')]
        base_holes = {'us': {0: b'digi', 1: b'usa'}, 'eu': {0: b'digi', 1: b'europe'}}
        with tempfile.TemporaryDirectory() as td:
            def derive_holes(out, m, v, bd, work, jobs=None, source_discs=None):
                calls.append((bd.key, jobs))
                got = {}
                for h in holes:
                    data = b'w3 digi' if h['id'] == 0 else base_holes[bd.key][1]
                    got[h['file']] = os.path.join(td, f'{bd.key}-{h["id"]}')
                    with open(got[h['file']], 'wb') as f:
                        f.write(data)
                return got

            class Disc:
                def __init__(self, key, *a, **k):
                    self.key = key

            def build_disc3(p3, bd, hb, ob, expect):
                with open(ob, 'wb') as f:
                    f.write(b''.join(hb[h['id']] for h in holes))
                return f'sha-{bd.pin}-{hb[0].decode()}-{hb[1].decode()}', None

            a = argparse.Namespace(source_variant=['dw2003=W3.bin'], source_disc=['dcb=a', 'dw2=b', 'dw2003=c'],
                                   variant_jobs=7, keep_outputs=None)
            m = dict(extract=[], timings={})
            outputs = {}
            with patch.object(dw, 'variant_of_image', return_value=('dw3-us', 'SLUS_014.36')), \
                    patch.object(dw, 'derive_holes', derive_holes), patch.object(dw, 'BaseDisc', Disc), \
                    patch.object(dw, 'build_disc3', build_disc3), \
                    patch.object(dw, 'regional_derive', lambda mp, ex: True), \
                    patch.object(dw, 'say', lambda *x: None), \
                    patch.object(V, 'reuse', return_value=verdict), \
                    patch.object(V, 'differing_inputs', return_value=set()), \
                    patch.object(V, 'step_graph', return_value={}), \
                    patch.object(dw, 'derived_manifest', return_value=os.path.join(td, 'manifest.json')):
                with open(os.path.join(td, 'manifest.json'), 'w') as f:
                    f.write('{"steps": {}, "files": {}}')
                sv = dw.record_source_variants(a, m, td, td, 'everything', dict(recipe='everything'), holes,
                                               base_holes, {'us': 'us.bin', 'eu': 'eu.bin'}, {}, None, outputs)
        return sv, calls, outputs, holes

    def test_fallback_runs_every_regional_base(self):
        sv, calls, outputs, holes = self.run_it((None, 'x'))
        self.assertEqual(sv, {'dw3-us': dict(game='dw2003', boot='SLUS_014.36')})
        self.assertEqual([k for k, _ in calls], ['us', 'eu'])
        self.assertEqual(outputs['eu+dw3-us']['sha1'], 'sha-eu+dw3-us-w3 digi-europe')
        self.assertEqual(set(holes[0]['sha1_by_base']), {'us+dw3-us', 'eu+dw3-us'})
        self.assertNotIn('sha1_by_base', holes[1])

    def test_reused_runs_only_the_usa_disc(self):
        reused = {'us': {0: b'w3 digi', 1: b'usa'}, 'eu': {0: b'w3 digi', 1: b'europe'}}
        sv, calls, outputs, holes = self.run_it((reused, None))
        self.assertEqual([k for k, _ in calls], ['us'])
        self.assertEqual(outputs['eu+dw3-us']['sha1'], 'sha-eu+dw3-us-w3 digi-europe')


class TheRealSteps(unittest.TestCase):
    def test_graph_is_derives_own(self):
        from tools.derive import steps as S
        graph = V.step_graph(os.path.join(ROOT, 'tools', 'derive'))
        self.assertEqual(set(graph), set(S.ALL))
        for name in S.ALL:
            self.assertEqual(graph[name], tuple(S.load(name).AFTER), name)

    def test_source_steps_named(self):
        """A step module that opens the source discs (or calls the importers or record originals) is in SOURCE_STEPS
        or reads one that is."""
        graph = V.step_graph(os.path.join(ROOT, 'tools', 'derive'))
        covered = V.dependents(graph, V.SOURCE_STEPS)
        pattern = re.compile(r"source-games|source_variant|importers|recordoriginals|recordimports|Provider\(")
        folder = os.path.join(ROOT, 'tools', 'derive', 'steps')
        for name in sorted(os.listdir(folder)):
            if not name.endswith('.py') or name == '__init__.py':
                continue
            with open(os.path.join(folder, name), encoding='utf-8') as f:
                text = f.read()
            step = name[:-3]
            if pattern.search(text):
                self.assertIn(step, covered, f'{name} reads the source discs: add it to variantreuse.SOURCE_STEPS')


if __name__ == '__main__':
    unittest.main()
