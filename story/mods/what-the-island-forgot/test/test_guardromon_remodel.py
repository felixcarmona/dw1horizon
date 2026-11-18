"""Guardromon remodels each listed species into its same-level sibling, and only those."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[4]
MOD = ROOT / 'story/mods/what-the-island-forgot/arcs/factory/remodelling.py'
SP = dict(Mamemon=13, Numemon=11, Geremon=87, MegaSeadramon=61, WaruSeadramon=112, MetalGreymonVirus=136, Agumon=3)
# partner -> (special result on roll 0, normal result on rolls 1-5)
PAIRS = {'Mamemon': (41, 27), 'Numemon': (231, 87), 'Geremon': (231, 231), 'MegaSeadramon': (112, 112),
         'WaruSeadramon': (61, 61), 'MetalGreymonVirus': (224, 224)}


def run(species, roll, bits=3000, answer='a'):
    func = next(n for n in ast.parse(MOD.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'remodel')
    func.decorator_list = []
    spoken, charges, evolutions = [], [], []
    t5 = NS(**{f'u{i}': f'u{i}' for i in range(11)}, m0=NS(o0='yes', o1='no'))
    env = dict(partner=NS(species=SP[species]), Species=NS(**SP), t5=t5, bits=bits, say=spoken.append,
               tamer=NS(arrived=lambda: None, say=spoken.append), raw=NS(entity_walk_to_entity=lambda *_: None,
               call_digimon_routine=lambda _: None), choose=lambda **_: answer, take=lambda **kw: charges.append(kw['bits']),
               random=NS(roll=lambda _: roll), hide_hud=lambda: None, wait=lambda _: None,
               engine=NS(arg=NS(set=evolutions.append)), DigimonRoutine=NS(forced_evolution=1))
    exec(compile(ast.Module(body=[func], type_ignores=[]), str(MOD), 'exec'), env)
    env['remodel']()
    return spoken, charges, evolutions


class GuardromonRemodel(unittest.TestCase):
    def test_each_pair(self):
        for name, (special, normal) in PAIRS.items():
            self.assertEqual(run(name, 0)[2], [special], name)
            self.assertEqual(run(name, 3)[2], [normal], name)
            self.assertEqual(run(name, 5)[2], [normal], name)

    def test_failure_charges_and_changes_nothing(self):
        for name in PAIRS:
            spoken, charges, evolutions = run(name, 9)
            self.assertEqual((charges, evolutions), ([2000], []), name)

    def test_declining_or_no_bits(self):
        spoken, charges, evolutions = run('Numemon', 0, answer='b')
        self.assertEqual((charges, evolutions), ([], []))
        spoken, charges, evolutions = run('Numemon', 0, bits=1999)
        self.assertEqual((charges, evolutions, spoken[-1]), ([], [], 'u2'))

    def test_other_partners_are_turned_away(self):
        spoken, charges, evolutions = run('Agumon', 0)
        self.assertEqual((charges, evolutions, spoken[-1]), ([], [], 'u1'))


if __name__ == '__main__':
    unittest.main()
