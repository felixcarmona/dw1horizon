"""The hand-made babies (470-477): native DW1 rigs and animations, our mesh and texture, plain deltas only."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mmd
import motionstorage
import species
from tools.models import babies
from tools.models import delta as modeldelta
from tools.derive.importers import Provider

ROOT = Path(__file__).resolve().parents[1]
BABY_IDS = list(range(470, 478))
CALM_CLIPS = {
    470: (0, 2, 3, 4),      # Pabumon's idle, walk, tired walk and run (field_animations/pabumon_calm.py)
    471: (0, 2, 3, 4),      # Pichimon's four field clips (field_animations/pichimon_hop.py)
    472: (0, 2, 3, 4),      # Yukimibotamon's idle, walk, tired walk and run (field_animations/yukimibotamon_calm.py)
    473: (0, 2, 3, 4),      # Nyokimon's idle, walk, tired walk and run (field_animations/nyokimon_calm.py)
    474: (0, 2, 3, 4),      # Motimon's idle, walk, tired walk and run (field_animations/baby_calm.py)
    475: (0, 2, 3, 4),      # Bukamon's idle, walk, tired walk and run (field_animations/baby_calm.py)
}


def adds(delta):
    """The literal (ADD) bytes of a plain MD3 delta."""
    pos = 5
    count, pos = modeldelta._rv(delta, pos)
    for _ in range(count + 1):
        _, pos = modeldelta._rv(delta, pos)
    body = zlib.decompress(delta[pos + 32:])
    _, pos = modeldelta._rv(body, 0)
    size, pos = modeldelta._rv(body, pos)
    return body[pos + size:]


class Registry(unittest.TestCase):
    """Without the player's extraction: what is committed agrees with itself."""

    def test_every_baby_is_registered_with_its_own_builder(self):
        registry = json.loads((ROOT / 'content/models/imports/models.json').read_text())
        records = babies.records()
        self.assertEqual(sorted(records), BABY_IDS)
        for sid, record in records.items():
            module = registry[str(sid)]['builder']
            self.assertEqual(module, 'tools.models.babies.' + record['name'].lower())
            self.assertEqual(__import__(module, fromlist=['SPECIES']).SPECIES, sid)

    def test_species_files_use_the_donor_rig_and_effects(self):
        content = species.load_content()
        records = babies.records()
        for sid in BABY_IDS:
            s, record = content[sid], records[sid]
            self.assertEqual(s['name'], record['name'])
            self.assertEqual(s['model']['skeleton'], species.originals().rec[record['donor']]['bones'])
            self.assertEqual(len(s['model']['skeleton']), record['bones'])
            self.assertEqual(s['effects_like'], record['donor'])
            self.assertEqual(s['level'], 'fresh' if sid < 474 else 'in-training')
            self.assertIn('partner', s)

    def test_fresh_babies_grow_into_their_own_in_training(self):
        rules = json.loads((ROOT / 'content/tables/evolution-rules.json').read_text())['evolutionFresh']
        pairs = {(r['from'], r['to']) for r in rules}
        self.assertLessEqual(len(rules), 8)              # MOD_EVO_FRESH has eight rows
        content = species.load_content()
        for fresh in range(470, 474):
            self.assertIn((fresh, fresh + 4), pairs)
            self.assertEqual(content[fresh]['evolution']['to'], [fresh + 4])
            self.assertEqual(content[fresh + 4]['evolution']['from'], [fresh])

    def test_canon_rookie_is_the_first_in_training_target(self):
        content = species.load_content()
        canon = {474: 111, 475: 217, 476: 221, 477: 45}    # Tentomon, Gomamon, Salamon, Biyomon
        for parent, rookie in canon.items():
            targets = content[parent]['evolution']['to']
            self.assertEqual(targets[0], rookie)
            self.assertTrue(3 <= len(targets) <= 6)
            for target in targets:
                self.assertEqual(content[target]['level'], 'rookie')
                self.assertTrue(set(content[parent]['specialties']) - {None} & set(content[target]['specialties']))

    def test_deltas_are_pinned(self):
        import hashlib
        for record in babies.records().values():
            for kind in ('mmd', 'tim'):
                data = (ROOT / record[kind]['delta']).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), record[kind]['delta_sha256'])
                self.assertEqual(data[:5], modeldelta.MAGIC + b'\0')


@unittest.skipUnless((ROOT / 'extracted/CHDAT/MMD0/KORO.MMD').exists(), 'needs the player extraction')
class Replay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = babies.records()
        cls.built = {sid: babies.build_species(sid, ROOT / 'extracted') for sid in BABY_IDS}

    def test_animation_section_is_the_donors_byte_for_byte(self):
        for sid, (model, _) in self.built.items():
            record = self.records[sid]
            donor = (ROOT / 'extracted/CHDAT' / record['donor_model']).read_bytes()
            with self.subTest(baby=record['name']):
                if sid in CALM_CLIPS:
                    continue                                 # its four field clips are ours: see the next test
                self.assertEqual(model[struct.unpack_from('<I', model, 4)[0]:],
                                 donor[struct.unpack_from('<I', donor, 4)[0]:])

    def test_pabumon_keeps_every_donor_program_but_its_four_field_clips(self):
        record = self.records[470]
        parsed = mmd.MMD.parse(self.built[470][0], record['bones'])
        donor = mmd.MMD.load(str(ROOT / 'extracted/CHDAT' / record['donor_model']), record['donor'])
        self.assertEqual(len(parsed.anims.table), len(donor.anims.table))
        for slot, (a, b) in enumerate(zip(parsed.anims.table, donor.anims.table)):
            self.assertEqual(a is None, b is None)
            if a is not None and slot not in CALM_CLIPS[470]:
                self.assertEqual(vars(parsed.anims.anims[a]), vars(donor.anims.anims[b]), slot)
        self.assertIsNotNone(parsed.anims.table[0x2E])

    def test_partner_limits_and_animation_storage(self):
        for sid, (model, texture) in self.built.items():
            record = self.records[sid]
            with self.subTest(baby=record['name']):
                self.assertLessEqual(len(model), 0x18800)
                parsed = mmd.MMD.parse(model, record['bones'])
                self.assertLessEqual(record['bones'], 34)
                donor = mmd.MMD.load(str(ROOT / 'extracted/CHDAT' / record['donor_model']), record['donor'])
                if sid not in CALM_CLIPS:
                    self.assertEqual(parsed.anims.table, donor.anims.table)   # the donor baby's slots, Bubble at 0x2E
                self.assertIsNotNone(parsed.anims.table[0x2E])
                motionstorage.require(model, record['bones'])
                tim = mmd.Tim4(texture)
                self.assertEqual((tim.w, tim.h), (256, 128))

    def test_literal_bytes_are_ours(self):
        # No 16-byte run of an ADD section with more than two distinct byte values (a flat fill of one texture colour
        # is not provenance) occurs in the donor files the delta copies from.
        for sid, record in self.records.items():
            sources = babies.donor_sources(record, ROOT / 'extracted')
            for kind, source in zip(('mmd', 'tim'), sources):
                literal = adds((ROOT / record[kind]['delta']).read_bytes())
                windows = {source[i:i + 16] for i in range(len(source) - 15)}
                runs = [literal[i:i + 16] for i in range(len(literal) - 15) if len(set(literal[i:i + 16])) > 2]
                with self.subTest(baby=record['name'], kind=kind):
                    self.assertFalse([run.hex() for run in runs if run in windows])

    def test_imports_provider_uses_the_builder_without_source_games(self):
        with tempfile.TemporaryDirectory() as work:
            for sid in (470, 477):
                self.assertEqual(Provider(Path(work) / 'no-source-games', work).model(sid), self.built[sid])


if __name__ == '__main__':
    unittest.main()
