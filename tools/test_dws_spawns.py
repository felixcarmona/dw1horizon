"""Compiler placement coverage and non-mutating author suggestions."""
import ast
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dws.checks import spawns as S


class Spawns(unittest.TestCase):
    def test_default_explicit_ranges_and_same_slot_variants(self):
        placements = [(314, 0, 10, dict(posX=1400, posZ=0), ('a.py', 1, 1), None),
                      (314, 0, 11, dict(posX=1400, posZ=0, trackingRange=1200), ('a.py', 2, 1), None),
                      (314, 1, 12, dict(posX=1300, posZ=0), ('a.py', 3, 1), None)]
        model = SimpleNamespace(warps=[dict(x=0, z=0, targetMap=1), dict(x=1400, z=0, targetMap=-1)])
        result = S.analyze(placements, lambda *_: model)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[0]['species'], [10, 11])
        self.assertEqual([r['close'] for r in result.rows], [True, False])
        self.assertIn('trackingRange', placements[1][3])

    def test_unknown_skipped_and_observational_coverage_are_explicit(self):
        placements = [(17, 0, 10, {}, None, None), (314, 0, 10, {}, None, None),
                      (315, 0, 10, dict(posX=0, posZ=0), ('new.py', 1, 1), None)]
        result = S.analyze(placements, lambda *_: SimpleNamespace(warps=[dict(x=0, z=0, targetMap=1)]),
                           enforce_sources=['old.py'])
        self.assertEqual((result.skipped, len(result.unknown), len(result.rows)), (1, 1, 1))
        self.assertTrue(result.rows[0]['close'])
        self.assertEqual(result.failed, [])

    def test_multiline_expression_and_unicode_suggestions_do_not_write_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'story.py'
            text = '# Léon\nwolf = room.npc(Species.Wolf,\n    at=(1 + 2, 4), range=200)\n'
            path.write_text(text)
            diff = S.suggestion_diffs([((str(path), 2, 1), 'at', (1500, -50))])
            self.assertIn('+    at=(1500, -50), range=200)', diff)
            self.assertEqual(path.read_text(), text)

    def test_unknown_map_check_fails_instead_of_being_silently_skipped(self):
        from tools.derive.steps import maps
        from tools.derive.runner import StepError
        with patch.object(maps, 'entries', return_value=[{'check': 'unknown'}]), \
             patch.object(maps, 'recipe', return_value={'mod': 'story/mods/MOD'}):
            with self.assertRaisesRegex(StepError, 'unknown map check'):
                maps.step_units(SimpleNamespace(), 'maps')

    def test_build_check_receives_retouch_metadata_after_outputs_exist(self):
        from tools.derive.steps import maps
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            ctx = SimpleNamespace(root=str(root), out=tmp, run=Mock(),
                                  path=lambda *parts: str(Path(tmp).joinpath(*parts)))
            entry = dict(check='story-spawns', enforce_sources=['early-game.py'])
            with patch.object(maps, 'step_outputs', return_value=[]), \
                 patch.object(maps, 'entries', return_value=[entry]), \
                 patch.object(maps, 'recipe', return_value={'mod': 'story/mods/MOD'}):
                maps.finish_step(ctx, 'retouch')
            script, args = ctx.run.call_args.args
            self.assertEqual(script, 'tools/dws.py')
            self.assertEqual(args[args.index('--maps') + 1], str(Path(tmp + '-maps') / 'retouch'))
            self.assertIn('story/mods/MOD/early-game.py', args)

    def test_suggested_keyword_after_trailing_comma_is_valid_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'story.py'
            text = 'wolf = room.npc(Species.Wolf, at=(1, 2),)\n'
            path.write_text(text)
            diff = S.suggestion_diffs([((str(path), 1, 1), 'range', 150)])
            added = ''.join(line[1:] for line in diff.splitlines(keepends=True)
                            if line.startswith('+') and not line.startswith('+++'))
            tree = ast.parse(added)
            self.assertEqual(tree.body[0].value.keywords[-1].arg, 'range')
            self.assertEqual(path.read_text(), text)


if __name__ == '__main__':
    unittest.main()
