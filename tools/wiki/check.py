#!/usr/bin/env python3
"""Check the final Pages overlay: budgets, static links, provenance and spoiler exclusion."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import json
import subprocess
import sys
from urllib.parse import unquote, urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build


class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=set();self.resources=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if 'id' in values:self.ids.add(values['id'])
        if tag=='a' and 'href' in values:self.links.append(values['href'])
        if tag in ('img','script') and 'src' in values:self.resources.append(values['src'])
        if tag=='link' and values.get('rel')=='stylesheet':self.resources.append(values['href'])


def check(site):
    manifest=json.loads((site/'wiki/manifest.json').read_text())
    current=site/'engine/current.json'
    if current.exists():
        engine=json.loads(current.read_text())
        assert manifest['commit']==engine['commit'],'Wiki game snapshot differs from engine'
        assert manifest['tag'].removeprefix('v')==engine['release_version'],'Wiki release differs from engine'
    sizes=build.budget(site)
    parsed={}
    pages=list((site/'wiki').rglob('*.html'))
    for page in pages:
        parser=Links();parser.feed(page.read_text());parsed[page]=parser
        for href in parser.resources:
            assert not urlsplit(href).netloc,'External wiki resource'
    for page,parser in parsed.items():
        for href in parser.links+parser.resources:
            parts=urlsplit(href)
            if parts.scheme or parts.netloc:continue
            target=(site/unquote(parts.path).lstrip('/')) if parts.path.startswith('/') else page.parent/unquote(parts.path)
            if not parts.path:target=page
            if target.is_dir():target=target/'index.html'
            assert target.is_file(),f'Missing local wiki target: {target.relative_to(site)}'
            if parts.fragment and target in parsed:
                assert parts.fragment in parsed[target].ids,f'Missing wiki anchor: {target.relative_to(site)}#{parts.fragment}'
    # Only the approved mechanic hint may occupy the protected recruit fields.
    # Dialogue is never an export input for articles or the search model.
    for lang in build.model.LANGS:
        catalog=json.loads((site/f'i18n/{lang}.json').read_text())
        articles=json.loads((build.CONTENT/f'articles/{lang}.json').read_text())
        hint=articles['hidden-mechanics']['paragraphs'][0]
        for field in ('method','when'):
            assert catalog[f'data.recruit.{field}.37']==hint,'Protected recruit field must be mechanic-only'
    print(f'Wiki checks passed: {len(pages)} pages; {sizes}')
    return sizes


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site',type=Path,required=True)
    check(p.parse_args().site.resolve())
