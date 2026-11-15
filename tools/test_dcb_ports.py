"""The own effects converted from Digital Card Battle attacks (content/battle/own-effects.json entries with "dcb").

Without discs: each port is gameplay-neutral and wired to its species (it stands for the species' proven finisher,
its chunk is the species' row of content/finishers/dcb-effects.json, that row passed the fidelity check). Rows that
did not pass keep the technique's own effect and say why.

With discs (DCB_IMAGE: the USA disc; DCB_EU_IMAGE, DCB_JP_IMAGE: the others, each optional): the derive path builds
every port from the disc's extracted files to its pinned SHA-1, so every release gives the same chunks.

    DCB_IMAGE=DCB.bin [DCB_EU_IMAGE=...] [DCB_JP_IMAGE=...] python3 -m unittest tools.test_dcb_ports
"""
import hashlib
import os
import tempfile
import unittest

from tools.test_dw3_ports import ROOT, _json, proven_finisher, species_of

CHUNKS = range(251, 330)


def ports():
    """{chunk: entry} of the Card Battle ports."""
    return {int(k): e for k, e in _json('content/battle/own-effects.json').items() if isinstance(e, dict) and 'dcb' in e}


def rows():
    return {r['chunk']: r for r in _json('content/finishers/dcb-effects.json')['effects']}


class Wiring(unittest.TestCase):
    def test_each_port_is_neutral_and_wired(self):
        import sys
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        try:
            import species as SP
        finally:
            sys.path.pop(0)
        table = rows()
        for chunk, e in sorted(ports().items()):
            with self.subTest(chunk=chunk, name=e['name']):
                self.assertIn(chunk, CHUNKS)
                self.assertFalse({'area', 'hits', 'cast', 'hit', 'scale'} & set(e), 'no gameplay, no DW2 fields')
                r = table[chunk]
                self.assertEqual(r['result'], 'converted')
                s = species_of(chunk)
                self.assertIsNotNone(s, 'a species plays it')
                self.assertEqual(s['id'], r['species'])
                self.assertEqual(e['stands_for'], proven_finisher(s['id']))
                self.assertEqual(SP.id_of('techs', s['own_effect']['technique'], 'own_effect'), e['stands_for'])
                d = e['dcb']
                self.assertEqual((d['attack'], d['hit']), (r['attack_script'], r['hit_script']))
                self.assertEqual(len(d['fit']), 3)
                self.assertRegex(d['pin'], r'^[0-9a-f]{40}$')
                for rid, pin in d.get('pins', {}).items():
                    self.assertIn(rid, ('dcb-eu', 'dcb-jp'))
                    self.assertRegex(pin, r'^[0-9a-f]{40}$')

    def test_rows_that_did_not_pass_keep_the_template(self):
        ported = ports()
        for chunk, r in sorted(rows().items()):
            with self.subTest(chunk=chunk, name=r['species_name']):
                self.assertIn(chunk, CHUNKS)
                if r['result'] == 'converted':
                    self.assertIn(chunk, ported)
                else:
                    self.assertNotIn(chunk, ported)
                    self.assertTrue(r.get('why'))
                    composed = _json('content/battle/own-effects.json').get(str(chunk))
                    if r.get('fallback') == 'composed':     # the template's own look contradicted the attack's kind
                        self.assertIn('compose', composed)
                        self.assertEqual(species_of(chunk)['id'], r['species'])
                    else:
                        self.assertEqual(r.get('fallback'), 'template')
                        self.assertIsNone(composed)
                        self.assertIsNone(species_of(chunk))


IMAGES = {rid: os.environ.get(var) for rid, var in
          (('dcb', 'DCB_IMAGE'), ('dcb-eu', 'DCB_EU_IMAGE'), ('dcb-jp', 'DCB_JP_IMAGE'))}
EFE = os.path.join(ROOT, 'extracted', 'ETCHI', 'EFEDAT.EFE')


@unittest.skipUnless(any(p and os.path.isfile(p) for p in IMAGES.values()) and os.path.isfile(EFE),
                     'needs DCB_IMAGE (or DCB_EU_IMAGE, DCB_JP_IMAGE) and extracted/ETCHI/EFEDAT.EFE')
class Discs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.derive.importers.discs import extract_to
        from tools import dcbeffect
        cls.tmp = tempfile.TemporaryDirectory()
        cls.discs = {}
        for rid, image in IMAGES.items():
            if image and os.path.isfile(image):
                games = os.path.join(cls.tmp.name, rid)
                extract_to('dcb', image, games)          # checks every pinned file
                cls.discs[rid] = dcbeffect.Disc.extracted(os.path.join(games, 'dcb'))
        with open(EFE, 'rb') as f:
            cls.archive = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_release_builds_the_pinned_chunks(self):
        from tools.derive.steps import effects
        size = effects.CHUNK_SIZE
        only = {int(k) for k in os.environ.get('DCB_PORTS', '').split(',') if k}
        for rid, disc in self.discs.items():
            for chunk, e in sorted(ports().items()):
                if only and chunk not in only:
                    continue
                with self.subTest(release=rid, chunk=chunk, name=e['name']):
                    like = effects.launch_table(self.archive[e['stands_for'] * size:(e['stands_for'] + 1) * size])
                    data, _info = effects.dcb_effect(disc, str(chunk), e, like)
                    pin = e['dcb'].get('pins', {}).get(rid, e['dcb']['pin'])
                    self.assertEqual(hashlib.sha1(data).hexdigest(), pin)


if __name__ == '__main__':
    unittest.main()
