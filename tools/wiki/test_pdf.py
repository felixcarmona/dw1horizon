"""Unit coverage plus extraction checks on a generated site (WIKI_PDF_SITE)."""
import json
import os
import subprocess
from pathlib import Path
import unittest

import pdf


def normalized(value):
    return ''.join(c for c in value if c.isalnum()).casefold()


class PartitionTests(unittest.TestCase):
    def test_nested_disclosures_move_together(self):
        public, secret=pdf.split('<p>ordinary</p><details class="spoiler"><summary>Spoilers</summary><p>solution</p><details class="spoiler"><p>nested</p></details></details><p>end</p>')
        self.assertIn('ordinary',public); self.assertIn('end',public)
        self.assertNotIn('solution',public); self.assertNotIn('nested',public)
        self.assertIn('solution',secret); self.assertIn('nested',secret)
        self.assertNotIn('<details',secret)


@unittest.skipUnless(os.environ.get('WIKI_PDF_SITE'),'Set WIKI_PDF_SITE to check generated PDFs')
class ExtractedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec=importlib.util.spec_from_file_location('pdf_wiki_build',Path(__file__).with_name('build.py'))
        build=importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
        import model
        cls.site=Path(os.environ['WIKI_PDF_SITE'])
        cls.manifest=json.loads((cls.site/'wiki/manifest.json').read_text())
        cls.data=model.load(cls.manifest['tag'])
        cls.build=build

    def test_outline_links_release_and_budgets(self):
        pdf.validate(self.site,self.manifest)

    def test_secret_text_only_after_divider(self):
        import articles
        import model
        for lang in self.manifest['pdfs']:
            with self.subTest(lang=lang):
                strings=json.loads((self.site/f'i18n/{lang}.json').read_text())
                record=self.manifest['pdfs'][lang]
                extracted=subprocess.check_output(['pdftotext','-layout',str(self.site/record['file'].lstrip('/')),'-'],text=True)
                texts=[normalized(page) for page in extracted.split('\f') if page.strip()]
                warning=normalized(strings['wiki.pdfWarning'])
                divider=next(i for i,text in enumerate(texts) if warning in text)
                before=''.join(texts[:divider]); after=''.join(texts[divider+1:])
                self.assertNotIn(warning,before)
                # No secret content shares the dedicated warning page.
                self.assertEqual(len(texts[divider]),len(normalized(strings['wiki.pdfSpoilers']))+len(warning)+len(str(divider+1)))
                dialogue=model.bakemon_dialogue(self.data['files'],lang)
                for row in dialogue['rows']:
                    question=normalized(row['question'])
                    self.assertNotIn(question,before); self.assertIn(question,after)
                root=articles.directory(self.manifest['tag'],model.ROOT/'web/wiki/articles')
                catalog=json.loads((root/f'{lang}.json').read_text())
                for article in catalog.values():
                    for index in article.get('spoiler_paragraphs',[]):
                        # A long literal prefix avoids both ordinary shared words and release bindings.
                        prefix=normalized(article['paragraphs'][index].split('{')[0])[:100]
                        if len(prefix)>30:
                            self.assertNotIn(prefix,before); self.assertIn(prefix,after)
                for recruit in self.data['recruits']:
                    if recruit['name']=='Bakemon': continue
                    method=normalized(strings['data.recruit.method.'+str(recruit['id'])])[:100]
                    if len(method)>30:
                        self.assertNotIn(method,before)
                        self.assertIn(method,after)
                for s in self.data['species']:
                    if s['spoiler']:
                        name=normalized(model.recruits.species_name(self.data['files'],s['name'],lang))
                        # A special-route species may also be named by ordinary requirements or City records.
                        # Check its complete entry separately below, using exact destination IDs.
                        self.assertIn(name,after)
                p=self.build.Pages(self.site,self.data,lang,catalog)
                html=pdf.document(p,self.manifest['tag'])
                public,appendix=html.split('<div class="appendix">',1)
                for s in self.data['species']:
                    if s['spoiler']:
                        self.assertNotIn(f'id="species-{s["id"]}"',public)
                        self.assertIn(f'id="species-{s["id"]}"',appendix)
                for recruit in self.data['recruits']:
                    if recruit['hidden']:
                        self.assertNotIn(f'id="recruit-{recruit["id"]}"',public)
                        self.assertIn(f'id="recruit-{recruit["id"]}"',appendix)


if __name__=='__main__': unittest.main()
