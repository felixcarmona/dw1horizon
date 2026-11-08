"""Release separation, changing facts, translations and search spoiler regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import model
import art


class WikiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=model.load('v0.0.7')

    def test_release_facts_do_not_use_main(self):
        self.assertEqual(self.data['commit'],'5861f8c8fb7ea3ffc54fba0d47d4b7582ba91baf')
        self.assertEqual(self.data['facts']['save_blocks'],2)
        self.assertIsNone(self.data['facts']['hard'])
        self.assertIsNotNone(model.load('origin/main')['facts']['hard'])

    def test_new_single_block_patch_changes_the_fact(self):
        files=dict(self.data['files'])
        files['mods/patches/series']+=b'\nwiki-save-fixture.patch\n'
        files['mods/patches/wiki-save-fixture.patch']=b'+++ b/src/main/main_menu.c\n+#define SAVE_BLOCKS 1\n+status = MemCardCreateFile(MEMORY_CARD_ID, SAVE_FILE_NAME, SAVE_BLOCKS);\n'
        self.assertEqual(model.save_blocks(files),1)
        files['mods/patches/wiki-save-fixture.patch']=b'+status = MemCardCreateFile(MEMORY_CARD_ID, SAVE_FILE_NAME, unreviewed());\n'
        with self.assertRaises((ValueError,KeyError)):model.save_blocks(files)

    def test_full_routes_and_empty_move_slots(self):
        species={s['id']:s for s in self.data['species']}
        self.assertEqual(species[3]['specialties'],['fire','battle'])
        self.assertEqual(species[3]['slots'],['fire',None,'battle'])
        self.assertEqual(len(species[3]['to']),6)
        self.assertTrue(all(3 in species[i]['parents'] for i in species[3]['to']))
        self.assertEqual(next(m['chance'] for m in species[3]['moves'] if m['id']==43),14)
        self.assertEqual(next(m['baseMP'] for m in self.data['techniques'] if m['id']==59),0)

    def test_later_single_block_article_uses_the_new_fact(self):
        spec=importlib.util.spec_from_file_location('wiki_articles',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        data=dict(self.data,facts=dict(self.data['facts'],save_blocks=1))
        articles=json.loads((model.ROOT/'web/wiki/articles/en.json').read_text())
        pages=module.Pages(Path('unused'),data,'en',articles)
        rendered={}
        pages.page=lambda path,title,body,*args:rendered.__setitem__(path,body)
        pages.article_pages()
        self.assertIn('1 free block',rendered['guides/memory-cards/'])
        self.assertNotIn('2 free blocks',rendered['guides/memory-cards/'])
        self.assertNotIn('1 free blocks',rendered['guides/memory-cards/'])

    def test_size_gates_reject_oversize_output(self):
        import tempfile
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('wiki_budget',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'wiki/en/v0.0.7').mkdir(parents=True)
            (root/'wiki/en/v0.0.7/search-index.json').write_text('[]')
            with patch.object(module,'SITE_LIMIT',1):
                with self.assertRaises(ValueError):module.budget(root)
            with patch.object(module,'INDEX_LIMIT',1):
                with self.assertRaises(ValueError):module.budget(root)
            with patch.object(module,'WIKI_LIMIT',1):
                with self.assertRaises(ValueError):module.budget(root)

    def test_quiz_tables_use_the_tagged_localized_dialogue(self):
        import html
        import re
        spec=importlib.util.spec_from_file_location('wiki_pages',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for lang in model.LANGS:
            articles=json.loads((model.ROOT/f'web/wiki/articles/{lang}.json').read_text())
            pages=module.Pages(Path('unused'),self.data,lang,articles)
            block=pages.fact_block('new-game-quiz')
            self.assertEqual(block.count('<tr>'),68)
            dialogue=json.loads(self.data['files'][f'text/{lang}.json'])
            expected=' '.join(re.sub(r'\{[^}]+\}','',x).strip() for x in dialogue['name.quiz.q1.question'][1:])
            self.assertIn(html.escape(expected),block)

    def test_local_art_coverage(self):
        for s in self.data['species']:
            svg=art.portrait(s['id'],self.data['files'])
            self.assertTrue(svg.startswith('<svg'))
            self.assertNotIn('http:',svg.replace('http://www.w3.org/2000/svg',''))

    def test_twenty_articles_and_nine_reviewed_translations(self):
        import hashlib
        root=model.ROOT/'web/wiki/articles'
        review=json.loads((root/'review.json').read_text())
        for lang in model.LANGS:
            source=(root/f'{lang}.json').read_bytes()
            self.assertEqual(review['locales'][lang],hashlib.sha256(source).hexdigest())
            articles=json.loads(source)
            self.assertEqual(len(articles),20)
            self.assertTrue(all(len(a['paragraphs'])>=3 for a in articles.values()))
            self.assertIn('{save_blocks}',articles['memory-cards']['paragraphs'][0])
        row=next(r for r in self.data['recruits'] if r['name']=='Bakemon')
        self.assertEqual(row['method'],'')
        self.assertEqual(row['when'],'')


if __name__=='__main__':unittest.main()
