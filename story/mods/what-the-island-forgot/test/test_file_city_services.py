"""Andromon's service must finish ordinary conversations and preserve Mamemon remodeling."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[4]
MOD = ROOT / 'story/mods/what-the-island-forgot/city/file-city-services.py'
BASE = ROOT / 'story/base/zones/file-city/s162-168-169-170/script.py'


def function(path, name, decorator=None):
    return next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)
                and n.name == name and (decorator is None or ast.unparse(n.decorator_list[0]) == decorator))


class Andromon(unittest.TestCase):
    def conversation(self, species, answer='b', bits=3000, roll=9, recruited=True):
        service = function(MOD, 'remodel')
        guard = next(k.value for k in service.decorator_list[0].keywords if k.arg == 'when')
        original = function(BASE, 'talk', 'andromon.on_talk')
        spoken, charges, evolutions = [], [], []
        env = dict(partner=NS(species=species), Species=NS(Mamemon=13, Andromon=40),
                   recruited=lambda _: recruited, bits=bits, say=spoken.append,
                   t7=NS(u0='original city greeting'),
                   text=NS(s162=NS(sec7=NS(u0='original city greeting'))),
                   t5=NS(**{f'u{i}': f'remodel {i}' for i in range(11)}, m0=NS(o0='yes', o1='no')),
                   choose=lambda **_: answer, take=lambda **kw: charges.append(kw['bits']),
                   random=NS(roll=lambda _: roll), hide_hud=lambda: None, wait=lambda _: None,
                   engine=NS(arg=NS(set=evolutions.append)),
                   raw=NS(call_digimon_routine=lambda _: None),
                   DigimonRoutine=NS(forced_evolution=1), tamer=NS(say=spoken.append))
        service.decorator_list = original.decorator_list = []
        exec(compile(ast.Module(body=[service, original], type_ignores=[]), str(MOD), 'exec'), env)
        calls = 0

        def dispatch():
            nonlocal calls
            calls += 1
            if calls > 3:
                self.fail('talk re-entered its own service hook without yielding')
            selected = eval(compile(ast.Expression(guard), str(MOD), 'eval'), env)
            return env['remodel' if selected else 'talk']()

        env['andromon'] = NS(talk=dispatch)
        dispatch()
        return spoken, charges, evolutions

    def test_other_partners_finish_the_original_greeting(self):
        for species in (3, 318):  # Agumon and Gallantmon
            with self.subTest(species=species):
                self.assertEqual(self.conversation(species), (['original city greeting'], [], []))

    def test_mamemon_can_decline_without_payment(self):
        self.assertEqual(self.conversation(13), (['remodel 0'], [], []))

    def test_insufficient_bits_do_not_charge_or_evolve(self):
        self.assertEqual(self.conversation(13, answer='a', bits=1999),
                         (['remodel 0', 'remodel 2'], [], []))

    def test_paid_outcomes_keep_the_original_price_and_species(self):
        for roll, target in ((0, 41), (1, 27), (5, 27), (6, None), (9, None)):
            with self.subTest(roll=roll):
                _, charges, evolutions = self.conversation(13, answer='a', roll=roll)
                self.assertEqual(charges, [2000])
                self.assertEqual(evolutions, [] if target is None else [target])


class VisitSchedule(unittest.TestCase):
    def test_daylight_visit_roll_and_resident_capacity(self):
        from test_story import Counter

        class Residents(Counter):
            def __gt__(self, other): return self.value > other

        visit = function(ROOT / 'story/base/maphead/hooks.py', 'L231')
        visit.decorator_list = []
        code = compile(ast.Module(body=[visit], type_ignores=[]), 'city visits', 'exec')
        ids = NS(Whamon=24, Whamon146=146, Greymon=5, Kokatorimon=50,
                 Kokatorimon168=168, Andromon=40, Andromon160=160,
                 Yuramon=43, Sukamon=39, Sukamon159=159)
        for recruited in (False, True):
            for hour in range(24):
                for roll in range(4):
                    for residents in (1, 2, 3):
                        spawned = []
                        env = dict(Species=ids, clock=NS(hour=hour), date_hour=hour,
                                   recruited=lambda species: recruited and species == ids.Andromon,
                                   greymon_challenge_ready=False, mt_infinity_entrance_found=False,
                                   city_resident_met=NS(kokatorimon=True),
                                   top_map_residents_placed=Residents(residents),
                                   random=NS(roll=lambda _: roll), load=lambda _: None,
                                   spawn=lambda species, **_: spawned.append(species))
                        exec(code, env)
                        env['L231']()
                        with self.subTest(hour=hour, roll=roll, residents=residents, recruited=recruited):
                            self.assertEqual(ids.Andromon160 in spawned,
                                             recruited and 7 <= hour < 19 and roll == 0 and residents <= 2)
