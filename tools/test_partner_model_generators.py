"""Built-disc profile: partner generator APIs reproduce the untouched reference models."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from tools.derive import crmath, pysum, runner
from tools.derive.steps.models import MODELS


# Untouched main 1213fd08, standard everything recipe, standard-library replay.
REFERENCE = {
    'ANLP.MMD': 'ca7025a2763e8786c9b603279f973b2f1b04ac6a',
    'ICEM-partner.MMD': 'be9c02b800de9eaf820fd8d9bf00807c37faaf59',
    'INSE-partner.MMD': '2ae7ece99d20d857105be8aae4c080b8ee1531f9',
    'JIJP.MMD': '91f3959e873a7962272bf742ce23b700465d4799',
    'JURE-partner.MMD': '306e6b341aaca91f44b6b2e55e50327b86c9e88a',
    'MUGP.MMD': '60f9890791fcd3d3309d4daabd718a2810e14119',
    'SCUD-partner.MMD': '38048e8649f7d6725706722e5646857f1fc576ea',
    'TIRS-partner.MMD': 'd0a29f7e7c70c9d290995c9c7bdb8051654929eb',
    'TONO-partner.MMD': 'b5f70e4d43e2ec24962a76854627e3b77b138101',
    'VAND-partner.MMD': '092b5bb81e1c448c826ffe1573984d3e377a3471',
    'WARU-partner.MMD': '4136a8575d4785fed6b15fdf31d718477c7911f8',
}


class PartnerGenerators(unittest.TestCase):
    def test_all_partner_outputs_match_the_reference(self):
        if not (Path(runner.ROOT) / 'extracted/CHDAT/MMD0/AGUM.MMD').is_file():
            self.skipTest('requires the extracted USA disc')
        self.assertEqual({name for name, _ in MODELS}, set(REFERENCE))
        crmath.install()
        pysum.install()
        try:
            with tempfile.TemporaryDirectory() as td:
                for name, script in MODELS:
                    with self.subTest(model=name):
                        out = Path(td) / name
                        runner.run_script(script, [out])
                        self.assertEqual(hashlib.sha1(out.read_bytes()).hexdigest(), REFERENCE[name])
        finally:
            pysum.uninstall()
            crmath.uninstall()
            crmath.clear()


if __name__ == '__main__':
    unittest.main()
