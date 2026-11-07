"""Only Bakemon's four spoken lines change; every recruitment path stays native."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

from tools.dws import basebuild, build, bytecode, flowcmp

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'story/base/zones/overdell-cemetery/s035-35'
DISC = ROOT / 'extracted/SCN/DG.SCN'


def script35(path):
    data = Path(path).read_bytes()
    offsets = bytecode.container_entries(data)
    return basebuild.flow_text(data[offsets[35]:offsets[36]], str(path))


def select_partner(lines, root, species, without_text=False):
    """Resolve only the added, pure species guards; retain every other branch."""
    result = ['    JUMP_TO ' + root]
    stored = species if species < 255 else 255  # storePartnerSpecies sentinel
    for line in lines:
        if line.strip() == 'STORE_DIGIMON_TYPE p103':
            continue
        if line.strip().startswith('IF p103 == '):
            args = line.strip()[3:]
            value = False
            for join, condition in flowcmp.clauses(args):
                match = re.fullmatch(r'p103 == (37|157)', condition)
                if not match:
                    raise AssertionError('unexpected partner condition: ' + condition)
                test = stored == int(match[1])
                value = value or test if join == 'or' else test
            if not value:
                result.append('    JUMP_TO ' + args.rpartition(', else ')[2])
            continue
        if without_text and flowcmp.ROW.match(line):
            continue
        result.append(line)
    return result


@unittest.skipUnless(DISC.exists(), 'needs extracted USA scripts')
class BakemonTranslation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / 'build').mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='bakemon-test-', dir=ROOT / 'build')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.compiled = {}
        for extension in ('py', 'dws'):
            output = Path(cls.temp.name) / (extension + '.SCN')
            with contextlib.redirect_stdout(io.StringIO()):
                program = build.compile_sources([str(SOURCE / ('script.' + extension))], text_source='ours')
                build.assemble(program, str(output))
            cls.compiled[extension] = script35(output)
        cls.original = script35(DISC)
        cls.words = json.loads((ROOT / 'text/ours/dialogue/overdell-cemetery.json').read_text())

    def test_all_bakemon_records_are_covered(self):
        ids = {record['id'] for path in (ROOT / 'content/species').glob('*.json')
               if (record := json.loads(path.read_text()))['name'] == 'Bakemon'}
        self.assertEqual(ids, {37, 157}, 'include new Bakemon twins in both story views and the flow cases')

    def test_every_choice_and_recruitment_effect_remains_native(self):
        old_lines, old_roots = self.original
        old = ['    JUMP_TO ' + old_roots['sec5']] + [line for line in old_lines if not flowcmp.ROW.match(line)]
        for species in (3, 37, 157, 293, 413):
            for extension, (lines, roots) in self.compiled.items():
                with self.subTest(species=species, source=extension):
                    selected = select_partner(lines, roots['sec5'], species, without_text=True)
                    comparison = flowcmp.compare(old, selected)
                    self.assertTrue(comparison['equal'], comparison)

    def test_all_four_lines_select_the_right_language_form(self):
        for species in (3, 37, 157, 293, 413):
            for extension, (lines, roots) in self.compiled.items():
                with self.subTest(species=species, source=extension):
                    _, _, reached, instructions = flowcmp.graph(select_partner(lines, roots['sec5'], species))
                    shown = {' '.join(json.loads(row) for row in instructions[i][2])
                             for i in reached if instructions[i][0] == 'SHOW_TEXTBOX'}
                    ghost = {self.words[f's035.sec5.u{n}'] for n in (0, 2, 3, 4)}
                    readable = {self.words[f's035.sec5.u{n}'] for n in (8, 9, 10, 11)}
                    expected, excluded = (readable, ghost) if species in (37, 157) else (ghost, readable)
                    self.assertTrue(expected <= shown, expected - shown)
                    self.assertFalse(excluded & shown, excluded & shown)


if __name__ == '__main__':
    unittest.main()
