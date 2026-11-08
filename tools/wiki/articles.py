"""Reviewed article catalogs and immutable, exact-tag release snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2] / 'web/wiki/articles'
LANGS = ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans')


def directory(tag, root=ROOT):
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError('Articles require an exact vMAJOR.MINOR.PATCH tag')
    released = root / 'released' / tag
    return released if released.exists() else root


def validate(root):
    review = json.loads((root / 'review.json').read_text())
    english = json.loads((root / 'en.json').read_text())
    if review['english_sha256'] != hashlib.sha256((root / 'en.json').read_bytes()).hexdigest():
        raise ValueError('English articles changed: translations need review')
    for lang in LANGS:
        source = (root / f'{lang}.json').read_bytes()
        if review['locales'][lang] != hashlib.sha256(source).hexdigest():
            raise ValueError('Article translation review changed: ' + lang)
        catalog = json.loads(source)
        if catalog.keys() != english.keys():
            raise ValueError('Article coverage differs: ' + lang)
        for ident, article in catalog.items():
            marked = article.get('spoiler_paragraphs', [])
            if marked != english[ident].get('spoiler_paragraphs', []) or any(type(i) != int or i < 0 or i >= len(article['paragraphs']) for i in marked):
                raise ValueError('Article spoiler classification differs: ' + lang + '/' + ident)
            tokens = lambda value: sorted(re.findall(r'\{\w+\}', json.dumps(value, ensure_ascii=False)))
            if tokens(article) != tokens(english[ident]):
                raise ValueError('Article variables differ: ' + lang + '/' + ident)
    return review


def freeze(tag, root=ROOT):
    directory(tag, root)  # Validate the tag before constructing paths.
    dest = root / 'released' / tag
    if dest.exists():
        raise FileExistsError('Article snapshot already exists: ' + tag)
    validate(root)
    dest.mkdir(parents=True)
    for name in (*[f'{lang}.json' for lang in LANGS], 'review.json'):
        shutil.copyfile(root / name, dest / name)
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['freeze'])
    parser.add_argument('tag')
    args = parser.parse_args()
    print(freeze(args.tag).relative_to(ROOT.parent))


if __name__ == '__main__':
    main()
