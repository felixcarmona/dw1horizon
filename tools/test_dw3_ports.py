"""The own effects converted from DW2003 techniques (content/battle/own-effects.json entries with "dw3").

Without discs: each port is gameplay-neutral and wired to its species (it stands for the species' proven finisher,
its chunk is the species' EFFECT_IDS index, its files are pinned).

With discs (DW3_IMAGE: the European disc; DW3_US_IMAGE, DW3_JP_IMAGE: the others, each optional): the derive path
builds every port from the disc's extracted files to its pinned SHA-1, so every release gives the same chunks,
and on the European disc each chunk passes tools/dw3efe.py's fidelity check against the original technique.

    DW3_IMAGE=DW2003.bin [DW3_US_IMAGE=...] [DW3_JP_IMAGE=...] python3 -m unittest tools.test_dw3_ports
"""
import glob
import hashlib
import json
import os
import struct
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS = range(196, 251)             # tools/dw3efe.py EFFECT_IDS: 196-222 3D effects, 223-250 sprite techniques


def _json(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return json.load(f)


def ports():
    """{chunk: entry} of the DW2003 ports."""
    return {int(k): e for k, e in _json('content/battle/own-effects.json').items() if isinstance(e, dict) and 'dw3' in e}


def species_of(chunk):
    for p in sorted(glob.glob(os.path.join(ROOT, 'content', 'species', '*.json'))):
        with open(p) as f:
            s = json.load(f)
        if (s.get('own_effect') or {}).get('chunk') == chunk:
            return s
    return None


def proven_finisher(species):
    proof = _json('docs/data/finisher-proof.json')
    for section in ('proven', 'conditional', 'unproven'):
        row = proof.get(section, {}).get(str(species))
        if row and row.get('finisher') is not None:
            return row['finisher']
    return None


class Wiring(unittest.TestCase):
    def test_each_port_is_neutral_and_wired(self):
        import sys
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        try:
            import species as SP
        finally:
            sys.path.pop(0)
        from tools import discs
        from tools.dw3efe import EFFECT_IDS
        for chunk, e in sorted(ports().items()):
            with self.subTest(chunk=chunk, name=e['name']):
                self.assertIn(chunk, CHUNKS)
                self.assertFalse({'area', 'hits', 'cast', 'hit', 'scale'} & set(e), 'no gameplay, no DW2 fields')
                s = species_of(chunk)
                self.assertIsNotNone(s, 'a species plays it')
                self.assertEqual(EFFECT_IDS[s['id']], chunk)
                self.assertEqual(e['stands_for'], proven_finisher(s['id']))
                self.assertEqual(SP.id_of('techs', s['own_effect']['technique'], 'own_effect'), e['stands_for'])
                d = e['dw3']
                self.assertRegex(d['model'], r'^M\d{3}[A-Z0-9]{4}$')
                self.assertRegex(d['pin'], r'^[0-9a-f]{40}$')
                for n in d['meft']:
                    self.assertIn(f'MEFT{n:04d}.BIN', discs.DW3_EFFECT_FILES)
                from tools.dw3effect import sprite_files
                for n in sprite_files(d.get('sprites', {})):
                    self.assertIn(n, discs.DW3_EFFECT_FILES)
                for rid, pin in d.get('pins', {}).items():
                    self.assertIn(rid, ('dw3-us', 'dw3-jp'))
                    self.assertRegex(pin, r'^[0-9a-f]{40}$')


class SpriteTables(unittest.TestCase):
    def test_sprites_read_without_the_fight_overlay(self):
        from tools.dw3effect import EffectIds, sprite_files
        sprites = {'2': ['E000COM1.BIN', 2, 0, 38], '2021': ['E386DINO.BIN', 2, 1, 0]}
        self.assertEqual(sprite_files(sprites), ['E000COM1.BIN', 'E386DINO.BIN', 'F000COM1.BIN'])
        t = EffectIds([97], sprites)
        self.assertEqual(set(t.meft), {97})
        p, section = t.sprites[2021]
        self.assertEqual((t.sprite_files[p], section, t.pack_sections[p]), ('E386DINO.BIN', 2, (1, 0)))


IMAGES = {rid: os.environ.get(var) for rid, var in
          (('dw2003', 'DW3_IMAGE'), ('dw3-us', 'DW3_US_IMAGE'), ('dw3-jp', 'DW3_JP_IMAGE'))}
EFE = os.path.join(ROOT, 'extracted', 'ETCHI', 'EFEDAT.EFE')


@unittest.skipUnless(any(p and os.path.isfile(p) for p in IMAGES.values()) and os.path.isfile(EFE),
                     'needs DW3_IMAGE (or DW3_US_IMAGE, DW3_JP_IMAGE) and extracted/ETCHI/EFEDAT.EFE')
class Discs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.derive.importers.discs import extract_to
        cls.tmp = tempfile.TemporaryDirectory()
        cls.games = {}
        for rid, image in IMAGES.items():
            if image and os.path.isfile(image):
                games = os.path.join(cls.tmp.name, rid)
                extract_to('dw2003', image, games)       # checks every pinned file
                cls.games[rid] = os.path.join(games, 'dw2003')
        with open(EFE, 'rb') as f:
            cls.archive = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def build(self, rid, chunk, e):
        from tools.derive.steps import effects
        size = effects.CHUNK_SIZE
        like = effects.launch_table(self.archive[e['stands_for'] * size:(e['stands_for'] + 1) * size])
        return effects.dw3_effect(self.games[rid], str(chunk), e, like,
                                  area=chunk in effects.finisher_area_chunks(ROOT))

    def test_every_release_builds_the_pinned_chunks(self):
        for rid in self.games:
            for chunk, e in sorted(ports().items()):
                with self.subTest(release=rid, chunk=chunk, name=e['name']):
                    data, _info = self.build(rid, chunk, e)
                    pin = e['dw3'].get('pins', {}).get(rid, e['dw3']['pin'])   # a release whose files differ
                    self.assertEqual(hashlib.sha1(data).hexdigest(), pin)

    @unittest.skipUnless('dw2003' in IMAGES and IMAGES['dw2003'] and os.path.isfile(IMAGES['dw2003']),
                         'the fidelity check renders the originals from the European disc (DW3_IMAGE)')
    def test_every_port_is_faithful(self):
        from tools.derive.importers import source_context
        only = {int(k) for k in os.environ.get('DW3_PORTS', '').split(',') if k}
        for chunk, e in sorted(ports().items()):
            if only and chunk not in only:
                continue
            with self.subTest(chunk=chunk, name=e['name']):
                # the conversion's fidelity, at the field scale: a "scale" only resizes the faithful conversion
                unscaled = dict(e, dw3={k: v for k, v in e['dw3'].items() if k != 'scale'})
                data, _info = self.build('dw2003', chunk, unscaled)
                with source_context(os.path.dirname(self.games['dw2003'])):
                    from tools import dw3effect as X, dw3efe as E
                    disc = X.Disc(IMAGES['dw2003'])
                    tables = X.Tables(disc)
                    tech = X.model_scripts(disc, e['dw3']['model'])[e['dw3']['slot']]
                    _frames, fid = E.compare(disc, tables, tech, data, e['name'], 480, 270)
                ok, why = E.passes(fid)
                self.assertTrue(ok, f'{why} {dict((k, v) for k, v in fid.items() if k != "rows")}')


if __name__ == '__main__':
    unittest.main()
