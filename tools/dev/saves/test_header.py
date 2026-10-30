#!/usr/bin/env python3
"""Old corpus headers acquire a default CHEATS flag; changing any saved option must still fail."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(_DEV_ROOT)
sys.path.insert(0, str(ROOT))
from tools.dev.saves import releases as R


class HeaderCompatibilityTests(unittest.TestCase):
    def check_copy(self, change=None, current_metadata=False):
        source = next(p for p in sorted((ROOT / 'tools/dev/saves/corpus').glob('*.json'))
                      if len(json.loads(p.read_text())['file'].get('headerOptions', '')) == 24)
        meta = json.loads(source.read_text())
        self.assertEqual(len(meta['file']['headerOptions']), 24)
        with tempfile.TemporaryDirectory() as work:
            card = Path(work) / 'card.mcd'
            js = Path(work) / 'card.json'
            shutil.copyfile(source.with_suffix('.mcd'), card)
            save = meta.get('save', R.SAVE)
            if current_metadata:
                meta['file']['headerOptions'] = R.mcd.decode_save(R.mcd.Card(card).read(save))['header_options']['bytes']
            if change is not None:
                offset, value = change
                first = R.mcd.Card(card).find(save)['blocks'][0] * R.mcd.BLOCK
                raw = bytearray(card.read_bytes())
                raw[first + offset] = value
                card.write_bytes(raw)
            # The mutation tests check the semantic comparison, independently of the file-integrity check.
            meta['sha1'] = hashlib.sha1(card.read_bytes()).hexdigest()
            js.write_text(json.dumps(meta))
            rows = []
            R.check_card(js, card, R.load_locks(), rows)
            return [(what, why) for ok, what, why in rows if not ok]

    def test_legacy_default(self):
        self.assertEqual(self.check_copy(), [])

    def test_current_default(self):
        self.assertEqual(self.check_copy(current_metadata=True), [])

    def test_changed_old_option(self):
        self.assertEqual([what for what, _ in self.check_copy((0x56, 20))], ['file headerOptions'])

    def test_changed_cheats_flag(self):
        for current in (False, True):
            with self.subTest(current_metadata=current):
                self.assertEqual([what for what, _ in self.check_copy((0x51, 0x8C), current)], ['file headerOptions'])


if __name__ == '__main__':
    unittest.main()
