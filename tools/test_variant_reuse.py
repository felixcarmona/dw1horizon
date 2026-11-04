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
