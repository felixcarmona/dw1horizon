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
        super().__init__();self.links=[];self.ids=set();self.resources=[];self.open_spoilers=False
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if 'id' in values:self.ids.add(values['id'])
        if tag=='details' and 'spoiler' in values.get('class','').split() and 'open' in values:self.open_spoilers=True
        if tag=='a' and 'href' in values:self.links.append(values['href'])
        if tag in ('img','script') and 'src' in values:self.resources.append(values['src'])
        if tag=='link' and values.get('rel')=='stylesheet':self.resources.append(values['href'])


class Spoilers(HTMLParser):
    def __init__(self):
        super().__init__();self.details=[];self.hidden='';self.visible='';self.open_spoilers=False;self.skip=0
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag in ('script','style'):self.skip+=1
        if tag=='details':
            spoiler='spoiler' in values.get('class','').split()
            self.details.append(spoiler)
            if spoiler and 'open' in values:self.open_spoilers=True
    def handle_endtag(self,tag):
        if tag=='details':self.details.pop()
        if tag in ('script','style'):self.skip-=1
    def handle_data(self,value):
        if self.skip:return
        if any(self.details):self.hidden+=value
        else:self.visible+=value


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
        assert not parser.open_spoilers,'Generated spoiler is open: '+str(page)
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
    # Dialogue and secret route records are present only inside closed, marked disclosures.
    data=build.model.load(manifest['tag'])
    for lang in build.model.LANGS:
        base=site/'wiki'/lang
        assert not (base/manifest['tag']).exists(),'Version archives must not be generated'
        dialogue=build.model.bakemon_dialogue(data['files'],lang)
        parser=Spoilers();parser.feed((base/'guides/hidden-mechanics/index.html').read_text())
        assert not parser.open_spoilers,'Spoilers must be folded by default'
        for row in dialogue['rows']:
            assert row['question'] in parser.hidden,'Missing tagged Bakemon question in spoiler'
            assert row['answer'] in parser.hidden,'Missing tagged Bakemon answer in spoiler'
            assert row['question'] not in parser.visible,'Bakemon question outside spoiler'
        index=json.loads((base/'search-index.json').read_text())
        assert all(entry.get('spoiler') for entry in index if entry['type']=='recruit'),'Recruitment identities need spoiler classification'
        for species in data['species']:
            if species['spoiler']:
                assert all(entry.get('spoiler') for entry in index if entry['url'].split('#')[0].endswith(f'/digimon/{species["id"]}-{build.model.slug(species["name"])}/')),'Secret species needs spoiler classification'
        assert not any(row['question'] in json.dumps(index,ensure_ascii=False) for row in dialogue['rows']),'Dialogue leaked into search'
    print(f'Wiki checks passed: {len(pages)} pages; {sizes}')
    return sizes


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site',type=Path,required=True)
    check(p.parse_args().site.resolve())
