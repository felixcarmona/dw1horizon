"""Run the legacy save-check driver with a fake emulator and paths containing spaces."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class SavePaths(unittest.TestCase):
    def test_check_driver_keeps_disc_card_and_output_arguments_whole(self):
        with tempfile.TemporaryDirectory(prefix='save paths ') as td:
            root = Path(td)
            scripts = root / 'tools/dev/saves'
            scripts.mkdir(parents=True)
            shutil.copyfile(Path(__file__).parent / 'dev/saves/check.sh', scripts / 'check.sh')
            shutil.copyfile(Path(__file__).parent / 'dev/saves/symbols.sh', scripts / 'symbols.sh')
            emu = root / 'tools/dev/emulator.py'
            emu.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                           'with open(os.environ["ARG_LOG"],"a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n'
                           'if sys.argv[1] == "peek": print("0: 00")\n')
            emu.chmod(0o755)
            fakebin = root / 'fake bin'
            fakebin.mkdir()
            nm = fakebin / 'nm'
            nm.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                          'with open(os.environ["ARG_LOG"],"a") as f: f.write(json.dumps(["nm",*sys.argv[1:]])+"\\n")\n'
                          'for name in ("CURRENT_SCREEN","MONEY","PARTNER_ENTITY","MEMORY_CARD_ERROR","CURRENT_MENU"):\n'
                          ' print("80000000 T "+name)\n')
            nm.chmod(0o755)
            card = root / 'seed card.mcd'
            card.write_bytes(b'card fixture')
            disc, elf, out = (root / n for n in ('Digimon World.cue', 'game executable.elf', 'save output'))
            log = root / 'args.jsonl'
            run = subprocess.run(['bash', str(scripts / 'check.sh'), str(disc), str(elf), '8999', str(card), str(out)],
                                 env=dict(os.environ, ARG_LOG=str(log), PATH=str(fakebin) + os.pathsep + os.environ['PATH']),
                                 text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertIn(['start', str(disc), '--card', str(out) + '.run.mcd'], calls)
            self.assertIn(['shot', str(out) + '.png'], calls)
            self.assertEqual([c for c in calls if c[0] == 'nm'], [['nm', str(elf)]] * 6)
            self.assertEqual(calls[-1], ['stop'])
            self.assertEqual(Path(str(out) + '.run.mcd').read_bytes(), card.read_bytes())


if __name__ == '__main__':
    unittest.main()
