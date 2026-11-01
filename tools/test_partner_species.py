#!/usr/bin/env python3
"""A partner past 255 must never reach a script as its low byte: the engine's stores and the compiled species tests."""
import ast
from pathlib import Path
import re
import unittest

from tools.dws.py import lower as PL
from tools.dws.py.lower import Body

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / 'build/decomp-int/src'
# p4, the tournament registration: tournament.c compares it with the partner's low byte
STORED_SPECIES = r'writePStat\((?!4,|PSTAT_TOURNAMENT_DIGIMON)[^;]*entity\.type'


@unittest.skipUnless(ENGINE.exists(), 'needs tools/mods.sh prepare int')
class EngineStores(unittest.TestCase):
    def test_no_species_is_written_to_a_pstat_directly(self):
        found = []
        for path in ENGINE.rglob('*.c'):
            found += [f'{path.name}: {m.group(0)}' for m in re.finditer(STORED_SPECIES, path.read_text(errors='replace'))]
        self.assertEqual(found, [], 'use storePartnerSpecies: a pstat keeps one byte of the species')

    def test_no_species_is_read_from_a_pstat_directly(self):
        found = []
        for path in ENGINE.rglob('*.c'):
            text = path.read_text(errors='replace')
            found += [f'{path.name}: {m.group(0)}' for m in re.finditer(r'(DIGI_PARA|digimonPara)\(readPStat', text)]
            for m in re.finditer(r'(\w+) = readPStat\(\w+\);\s*\n[^\n]*(DIGI_PARA|digimonPara)\(\1\)', text):
                found.append(f'{path.name}: {m.group(0).strip()}')
        self.assertEqual(found, [], 'use pstatSpecies: it gives back the partner a pstat could not hold')


class CompiledTests(unittest.TestCase):
    def setUp(self):
        self.exe = PL.TARGET['exe']
        self.addCleanup(PL.TARGET.__setitem__, 'exe', self.exe)

    def pre(self, exe):
        PL.TARGET['exe'] = exe
        body = Body.__new__(Body)
        body.guard = False
        pre = []
        try: Body.atom(body, ast.parse('partner_type == 39', mode='eval').body, pre)
        except Exception: pass               # (the rest of atom needs a whole module; the store comes first)
        return pre

    def test_a_raw_species_test_stores_the_species_first_on_every_wide_engine(self):
        for exe in PL.WIDE_EXES:
            self.assertEqual(self.pre(exe), ['store_digimon_type(partner_type);'])

    def test_the_original_engine_keeps_the_scripts_of_the_disc(self):
        self.assertEqual(self.pre('original'), [])


if __name__ == '__main__':
    unittest.main()
