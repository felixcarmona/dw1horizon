"""Exercise the authored reciprocal Infinity exit under every root combination."""
import ast
from itertools import product
from pathlib import Path
from types import SimpleNamespace
import unittest


class InfinityReturn(unittest.TestCase):
    def test_south_exit_keeps_walk_and_uses_north_hall_arrival(self):
        path = Path(__file__).resolve().parents[4]/'story/mods/what-the-island-forgot/arcs/infinity/metalgreymon-222.py'
        tree = ast.parse(path.read_text())
        tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
        for roots in product((False, True), repeat=3):
            with self.subTest(roots=roots):
                handlers, calls = [], []
                def on_step(step, when=True):
                    self.assertEqual(step, 0)
                    def register(fn):
                        if when: handlers.append(fn)
                        return fn
                    return register
                def screen(number):
                    self.assertEqual(number, 222)
                    return SimpleNamespace(on_step=on_step)
                env = dict(root1=roots[0], root2=roots[1], root3=roots[2], screen=screen,
                           tamer=SimpleNamespace(walk=lambda *a, **kw: calls.append(('walk', a, kw))),
                           warp=lambda *a, **kw: calls.append(('warp', a, kw)))
                exec(compile(tree, str(path), 'exec'), env)
                self.assertEqual(len(handlers), 1)
                handlers[0]()
                self.assertEqual(calls, [('walk', (-370, -4600), {'wait': False}),
                                         ('warp', (313 if all(roots) else 312,), {'entry': 1})])


if __name__ == '__main__': unittest.main()
