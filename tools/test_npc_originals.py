"""NPC twins stay disc-derived, invisible to rosters and independent of partners."""
from pathlib import Path
import re
import sys
import unittest
import tempfile
import subprocess
import shutil

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import species as S
from tools import site_digimon

PAIRS = dict(zip((119, 120, 121, 122, 123, 124, 126), range(462, 469)))


class NpcOriginalsTest(unittest.TestCase):
    def test_disc_rows_and_sources(self):
        allsp = S.load_content()
        for original, twin in PAIRS.items():
            with self.subTest(original=original):
                s = allsp[twin]
                disc = S.originals().rec[original]
                r = S.species_record(s)
                self.assertEqual(s['_npc_original'], original)
                self.assertEqual(r['bones'], disc['bones'])
                for key in ('boneCount', 'radius', 'height'):
                    self.assertEqual(r['para'][key], disc['para'][key])
                self.assertEqual(r['vball'], disc['vball'])
                self.assertFalse(r['flags'] & S.FLAG_PARTNER)
                self.assertEqual(s['techniques'], [])
                self.assertEqual(s['condition_bubble'], [0, 0, 0, 0])
                self.assertEqual(s['effects_like'], original)
                self.assertEqual(s['model']['from'], original)
                self.assertEqual(s['texture'], {'from': original})
                self.assertEqual(s['name'], allsp[original]['name'])
                source_model = S.originals().model_path(original)
                if source_model and Path(source_model).is_file():
                    self.assertEqual(S.species_model(s)[0], Path(S.originals().model_path(original)).read_bytes())
                    model = S.species_model(s)[0]
                    self.assertEqual(S.resident_model(s, r, model), (model, b''))
                if Path(S.ALLTIM).is_file():
                    import mmd
                    self.assertEqual(S.species_texture(s), mmd.alltim_entry(Path(S.ALLTIM).read_bytes(), original))

    def test_selection_and_rosters(self):
        allsp = S.load_content()
        twins = set(PAIRS.values())
        for selection in ('', 'all', '180'):
            self.assertTrue(twins <= S.parse_selection(selection)[0])
        chart = {t for tab in S.chart_tabs(allsp, allsp) for t in tab}
        self.assertTrue(twins.isdisjoint(chart))
        self.assertTrue(twins.isdisjoint(S.all_rows()))
        self.assertTrue(twins.isdisjoint(S.extra_rows()))
        guide = site_digimon.guide()
        self.assertTrue(twins.isdisjoint({s['id'] for s in guide['digimon']}))

    @unittest.skipUnless(shutil.which('cc'), 'needs a host C compiler')
    def test_engine_mapping_in_both_directions(self):
        patch = next(Path(S.ROOT).glob('mods/patches/0281-*.patch')).read_text()
        added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
        function = added[added.index('int32_t npcSpeciesType(int32_t type, int32_t reverse)\n{'):]
        function = function[:function.index('\n}') + 2]
        cases = '\n'.join(f'if (npcSpeciesType({a},0)!={b} || npcSpeciesType({b},1)!={a}) return 1;'
                          for a, b in PAIRS.items())
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'check.c'
            source.write_text('#include <stdint.h>\nint8_t GAME_STATE;\n' + function + '\nint main(void) {\n' + cases +
                              '\nfor(int i=-1;i<1024;i++) {'
                              'int t=npcSpeciesType(i,0); if(npcSpeciesType(t,0)!=t) return 2;'
                              '} GAME_STATE=1; for(int i=0;i<1024;i++) {'
                              'if(npcSpeciesType(i,0)!=i) return 3;'
                              '} return 0; }\n')
            binary = Path(tmp) / 'check'
            subprocess.run(['cc', '-Wall', '-Werror', str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_engine_table_matches_content(self):
        patch = next(Path(S.ROOT).glob('mods/patches/0281-*.patch'))
        pairs = {int(a): int(b) for a, b in re.findall(r'\{(1\d\d), (46\d)\}', patch.read_text())}
        self.assertEqual(pairs, PAIRS)
        self.assertEqual({s['_npc_original']: t for t, s in S.load_content().items()
                          if '_npc_original' in s}, pairs)


if __name__ == '__main__':
    unittest.main()
