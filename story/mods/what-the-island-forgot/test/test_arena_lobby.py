#!/usr/bin/env python3
"""The Arena lobby has two screens: 208 until the ending, 223 after it (every way in tests engine.game_beaten). A resident
placed on one only vanishes from the lobby for good once the game is beaten, as Myotismon did."""
import ast
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]
LOBBY = ROOT / 'story/mods/what-the-island-forgot/city/arena-lobby.py'
# Screen 223's own NPCs, as `python3 tools/dws.py slots 223` reads them from ROOM19.MAP (spawned after the ending).
BASE_223 = {'178-greymon': (133, 1154), '131-airdramon': (1100, -1400), '179-metalgreymonvirus': (-828, -990)}
TAMER_RADIUS = 100
# 208 only, on purpose: 223 has no heap for Kotemon's 87 KB model next to Airdramon and MetalGreymon (the build's heap check).
BEFORE_THE_ENDING_ONLY = {'Kotemon'}


def radius(species):
    """A model's body radius: a file name of content/species/, or a species name (its lowest id)."""
    paths = sorted((ROOT / 'content/species').glob(species + '.json' if '-' in species else f'*-{species.lower()}.json'),
                   key=lambda p: int(p.name.split('-')[0]))
    return json.loads(paths[0].read_text())['model']['radius']


class ArenaLobby(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(LOBBY.read_text())
        screens = {}     # local name of a lobby screen -> 208 / 223
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in ('dw.base.arena_lobby_208', 'dw.base.arena_lobby_223'):
                for alias in node.names:
                    if alias.name.startswith('lobby_'):
                        screens[alias.asname or alias.name] = int(alias.name[-3:])
        cls.npcs = {}    # variable -> (screen, species, at, when)
        for node in tree.body:
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                    and node.value.func.attr == 'npc' and getattr(node.value.func.value, 'id', None) in screens):
                kw = {k.arg: k.value for k in node.value.keywords}
                cls.npcs[node.targets[0].id] = (screens[node.value.func.value.id], node.value.args[0].attr,
                                                ast.literal_eval(kw['at']), ast.dump(kw.get('when')))
        cls.talks = {}   # variable -> the screens its talk handler warps to
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                for deco in node.decorator_list:
                    if isinstance(deco, ast.Attribute) and deco.attr == 'on_talk':
                        cls.talks[deco.value.id] = {n.args[0].attr for n in ast.walk(node) if isinstance(n, ast.Call)
                                                    and getattr(n.func, 'id', None) == 'warp'}

    def residents(self, screen):
        return sorted((species, when) for s, species, at, when in self.npcs.values() if s == screen)

    def test_every_resident_stays_after_the_ending(self):
        before = [r for r in self.residents(208) if r[0] not in BEFORE_THE_ENDING_ONLY]
        self.assertIn('Myotismon', [species for species, _when in before])
        self.assertEqual(before, self.residents(223))

    def test_a_spar_comes_back_to_its_own_screen(self):
        for name, (screen, *_rest) in self.npcs.items():
            warps = self.talks.get(name, set())
            self.assertTrue(warps <= {f'arena_lobby_{screen}'}, (name, warps))

    def test_clear_of_the_postgame_cast(self):
        for name, (screen, species, (x, z), _when) in self.npcs.items():
            if screen != 223:
                continue
            for other, (ox, oz) in BASE_223.items():
                gap = math.hypot(x - ox, z - oz) - radius(species) - radius(other)
                self.assertGreater(gap, 2 * TAMER_RADIUS, (name, other))


if __name__ == '__main__':
    unittest.main()
