#!/usr/bin/env python3
"""Awaited tamer walks aim far enough inside their tile (tools/dws/checks/walk_targets.py): python3 tools/test_dws_walk_targets.py

The compiler refuses `walk/run(tamer, x, z)` followed by a wait for the tamer when (x, z) lies within half a step of a
tile edge: the engine ends such a walk only on the target's tile, and from some start points the tamer turns in place
forever (the Birdra Transport steps). Every story build runs the check: base, core, mods, arcs, new screens."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import atexit, math, os, shutil, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from dws import build as B
from dws.checks import walk_targets as W

TMP = tempfile.mkdtemp(prefix='dws-walk-')
atexit.register(shutil.rmtree, TMP, ignore_errors=True)
BAD, CENTRE = (1507, -2574), (1550, -2550)          # the Birdra Transport run before and after its fix


def errors(src, name='x.dws'):
    d = tempfile.mkdtemp(dir=TMP); p = os.path.join(d, name)
    with open(p, 'w', encoding='utf-8') as f: f.write(src)
    try:
        B.compile_sources([p])
    except B.DwsErrors as e:
        return [x.render() for x in e.errors]
    return []


def event(body):
    return 'var v;\nscript 1 { npc a = 5; on talk(a) { ' + body + ' } }'


class Tiles(unittest.TestCase):
    def test_tiles_follow_get_model_tile(self):
        # C division truncates toward 0, then x < 0 / z > 0 take one off: the tiles touching 0 are 99 units wide
        self.assertEqual(W.tile_span(0, 0), (0, 99)); self.assertEqual(W.tile_span(-1, 0), (-99, -1))
        self.assertEqual(W.tile_span(-100, 0), (-199, -100)); self.assertEqual(W.tile_span(150, 0), (100, 199))
        self.assertEqual(W.tile_span(0, 1), (-99, 0)); self.assertEqual(W.tile_span(1, 1), (1, 99))
        self.assertEqual(W.tile_span(100, 1), (100, 199)); self.assertEqual(W.tile_span(-100, 1), (-199, -100))

    def test_margin_and_centre(self):
        self.assertEqual(W.margin(*BAD), 7); self.assertEqual(W.centre(*BAD), CENTRE)
        for x in range(-1000, 1000, 7):
            for z in range(-1000, 1000, 13):
                c = W.centre(x, z)
                self.assertGreaterEqual(W.margin(*c), 49, (x, z))
                self.assertEqual((W.tile_span(c[0], 0), W.tile_span(c[1], 1)), (W.tile_span(x, 0), W.tile_span(z, 1)))

    def test_threshold_is_half_a_step(self):
        self.assertIsNone(W.too_close('run', 1526, -2550)); self.assertIsNotNone(W.too_close('run', 1525, -2550))
        self.assertIsNone(W.too_close('walk', 1511, -2550)); self.assertIsNotNone(W.too_close('walk', 1510, -2550))

    def test_the_rule_holds_in_a_model_of_the_engine(self):
        """A point as far in as the check asks always ends the walk; the Birdra point does not from its stairs."""
        def walk(sx, sz, tx, tz, step, ticks=400):
            x, z = sx, sz
            for _ in range(ticks):
                if W._tile(x, 0) == W._tile(tx, 0) and W._tile(z, 1) == W._tile(tz, 1): return True
                a = math.atan2(tz - z, tx - x)
                x, z = x + int(round(step * math.cos(a))), z + int(round(step * math.sin(a)))
            return False
        for r in (60, 130, 400):
            for k in range(72):
                a = 2 * math.pi * k / 72
                sx, sz = CENTRE[0] + round(r * math.cos(a)), CENTRE[1] + round(r * math.sin(a))
                self.assertTrue(walk(sx, sz, *CENTRE, 50), (sx, sz))
                self.assertTrue(walk(sx, sz, CENTRE[0] - 23, CENTRE[1] + 23, 50), (sx, sz))   # 26 in: the least allowed


class Compiler(unittest.TestCase):
    def test_awaited_bad_target_fails_with_a_clear_message(self):
        e = errors(event(f'run(tamer, {BAD[0]}, {BAD[1]}); await tamer;'))
        self.assertEqual(len(e), 1, e)
        self.assertIn('x.dws:2:', e[0])
        for want in (f'the tamer runs to ({BAD[0]}, {BAD[1]}) and the script waits for him', '7 units from the edge',
                     'turning him in place forever', f'its centre is ({CENTRE[0]}, {CENTRE[1]})'):
            self.assertIn(want, e[0])

    def test_centre_and_unawaited_walks_pass(self):
        self.assertEqual(errors(event(f'run(tamer, {CENTRE[0]}, {CENTRE[1]}); await tamer;')), [])
        self.assertEqual(errors(event(f'run(tamer, {BAD[0]}, {BAD[1]}); wait(30);')), [])     # an exit walk: nobody waits
        self.assertEqual(errors(event(f'walk(a, {BAD[0]}, {BAD[1]}); await a;')), [])         # NPCs: not the tamer's rule
        # a newer walk replaces the old one before the wait
        self.assertEqual(errors(event(f'walk(tamer, {BAD[0]}, {BAD[1]}); walk(tamer, {CENTRE[0]}, {CENTRE[1]}); await tamer;')), [])

    def test_every_form_of_waiting(self):
        for body in (f'walk(tamer, 1511, -2589); await tamer;', f'run(tamer, {BAD[0]}, {BAD[1]}); await narrator;',
                     f'run(tamer, {BAD[0]}, {BAD[1]}); await all;', f'par {{ run(tamer, {BAD[0]}, {BAD[1]}); }}',
                     f'run(tamer, {BAD[0]}, {BAD[1]}); wait(10); await tamer;'):
            with self.subTest(body=body):
                self.assertEqual(len(errors(event(body))), 1)

    def test_branches_join(self):
        bad, ok = f'run(tamer, {BAD[0]}, {BAD[1]});', f'run(tamer, {CENTRE[0]}, {CENTRE[1]});'
        for body in (f'if (v == 1) {{ {bad} }} else {{ {ok} }} await tamer;',
                     f'if (v == 1) {{ {ok} }} else {{ {bad} }} await tamer;',
                     f'{bad} if (v == 1) {{ wait(5); }} await tamer;',
                     f'match (v) {{ 0 => {{ {ok} }}, 1 => {{ {bad} }} }} await tamer;'):
            with self.subTest(body=body):
                self.assertEqual(len(errors(event(body))), 1)
        self.assertEqual(errors(event(f'if (v == 1) {{ {bad} wait(5); }} {ok} await tamer;')), [])   # replaced on both paths

    def test_python_view(self):
        head = 'from dw import *\nfrom dw.base.jijimons_house import house\n\n@house.on_enter()\ndef go():\n'
        for body, n in ((f'    tamer.run({BAD[0]}, {BAD[1]})\n', 1),
                        (f'    tamer.walk({BAD[0]}, {BAD[1]}, wait=False)\n    wait(500)\n    tamer.arrived()\n', 1),
                        (f'    tamer.run({BAD[0]}, {BAD[1]}, wait=False)\n', 0),
                        (f'    tamer.run({CENTRE[0]}, {CENTRE[1]})\n', 0)):
            with self.subTest(body=body):
                e = errors(head + body, 'x.py')
                self.assertEqual(len(e), n, e)
                if n: self.assertIn('x.py:6:', e[0])

    def test_lifting_the_original_is_not_checked(self):
        with W.off():
            self.assertEqual(errors(event(f'run(tamer, {BAD[0]}, {BAD[1]}); await tamer;')), [])
        self.assertEqual(len(errors(event(f'run(tamer, {BAD[0]}, {BAD[1]}); await tamer;'))), 1)


if __name__ == '__main__':
    unittest.main()
