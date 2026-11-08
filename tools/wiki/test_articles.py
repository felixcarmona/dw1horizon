"""Exact-tag selection and reviewed release freezing."""
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

    def test_freeze_cli_dispatches_exact_tag(self):
        from unittest.mock import patch
        with patch.object(sys, 'argv', ['articles.py', 'freeze', 'v99.0.0']), \
             patch.object(articles, 'freeze', return_value=articles.ROOT / 'released/v99.0.0') as freeze, \
             patch('builtins.print'):
            articles.main()
        freeze.assert_called_once_with('v99.0.0')

    def test_released_pages_omit_unreleased_difficulty(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('snapshot_pages', Path(__file__).with_name('build.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = module.model.load('v0.0.7')
        self.assertEqual(data['facts']['chain_melon_hours'], 24)
        self.assertEqual(data['facts']['digiseabass_hours'], 6)
        self.assertEqual(data['facts']['timing']['megaHours'], 120)
        self.assertEqual(data['facts']['mojyamon'][1], (67, 70))
        for lang in articles.LANGS:
            import json
            catalog = json.loads((articles.directory('v0.0.7') / f'{lang}.json').read_text())
            pages = module.Pages(Path('unused'), data, lang, catalog)
            rendered = {}
            pages.page = lambda path, title, body, *args: rendered.__setitem__(path, title + body)
            pages.article_pages()
            self.assertNotIn('HARD', ''.join(rendered.values()))
            self.assertIn('120', rendered['guides/evolution-timing/'])
            self.assertIn('24', rendered['guides/evolution-timing/'])
            self.assertIn('6', rendered['guides/evolution-timing/'])
            self.assertEqual(pages.fact_block('difficulty'), '')
            block = pages.fact_block('file-city')
            self.assertIn('<details class="spoiler">', block)
            self.assertNotIn(' open', block)
            self.assertEqual(block.count('<tr>'), 9)
            self.assertIn(pages.names['main.ITEM_NAMES.70'], block)
        # A later disc's effects must change the article bindings.
        files = dict(data['files'])
        key = 'content/items/70-chain-melon.json'
        item = json.loads(files[key]); item['effect']['lifetime'] = 30
        files[key] = json.dumps(item).encode()
        self.assertEqual(module.model.article_facts(files)['chain_melon_hours'], 30)
        del files[key]
        with self.assertRaises(KeyError):
            module.model.article_facts(files)
