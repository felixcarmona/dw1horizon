"""Exact-tag selection and reviewed release freezing."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import articles


class ArticleSnapshots(unittest.TestCase):
    def test_exact_match_and_unknown_tag(self):
        self.assertEqual(articles.directory('v0.0.7'), articles.ROOT / 'released/v0.0.7')
        self.assertEqual(articles.directory('v99.0.0'), articles.ROOT)
        for tag in ('../v0.0.7', 'v0.0.7/extra', 'main'):
            with self.assertRaises(ValueError):
                articles.directory(tag)

    def test_freeze_validates_and_preserves_reviewed_bytes(self):
        # Temporary artifacts stay inside the worktree's ignored build directory.
        build = articles.ROOT.parents[2] / 'build'
        build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build) as tmp:
            root = Path(tmp)
            for name in (*[f'{lang}.json' for lang in articles.LANGS], 'review.json'):
                (root / name).write_bytes((articles.ROOT / name).read_bytes())
            dest = articles.freeze('v99.0.0', root)
            self.assertEqual(articles.directory('v99.0.0', root), dest)
            for file in dest.iterdir():
                self.assertEqual(file.read_bytes(), (root / file.name).read_bytes())
            with self.assertRaises(FileExistsError):
                articles.freeze('v99.0.0', root)
            (root / 'es.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'review changed: es'):
                articles.freeze('v99.0.1', root)
            self.assertFalse((root / 'released/v99.0.1').exists())
            # A partial snapshot must never select the working copy.
            (root / 'released/v99.0.2').mkdir()
            selected = articles.directory('v99.0.2', root)
            with self.assertRaises(FileNotFoundError):
                articles.validate(selected)

    def test_all_committed_catalogs_are_reviewed(self):
        for root in (articles.ROOT, articles.ROOT / 'released/v0.0.7'):
            articles.validate(root)
