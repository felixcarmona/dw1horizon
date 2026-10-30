#!/usr/bin/env python3
"""Developer: page translated banks without mixing the game's indexed text entries.

Each original page stays a separate semantic entry; overflowing entries are
reported for editorial shortening instead of silently joining unrelated pages.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from dws import backend as BE
from dws.textbank import single_page_keys, us_page_counts
def source_files():
    return sorted((ROOT / 'text/es/dialogue').glob('*.json'))


def target(source, lang):
    return ROOT / 'text' / lang / source.relative_to(ROOT / 'text/es')


def flat(value):
    return value if isinstance(value,str) else ' '.join(flat(v) for v in value)


def wrap_page(rows, source, packed=True):
    """Repeat real speaker headers; keep an inline coloured name in its sentence.

    The source is needed because a previous pass may have put an addressee on a
    row of its own. Its position in the translated rows does not make it a speaker.
    """
    text = flat(rows)
    header = re.match(r'^(\{color [67]\}.*?\{color 1\})\s*', text)
    source_rows = source if isinstance(source, list) else []
    if source_rows and isinstance(source_rows[0], list):
        source_rows = source_rows[0]
    variable_header = header and re.search(r'\{(?!color )[^{}]+\}', header[1])
    standalone = source_rows and re.fullmatch(r'\{color [67]\}.*?\{color 1\}', source_rows[0])
    if header and (not variable_header or standalone):
        return [[header[1], *p] for p in BE.wrap(text[header.end():], 3, packed=packed)]
    return BE.wrap(text, 4, packed=packed)


def repage(lang):
    BE.FONT.update(extra=True,glyphs=len(BE.EXTRA_ORDER),chars=frozenset(BE.EXTRA_ORDER),name='original')
    fixed = single_page_keys()
    counts = us_page_counts()
    report = []
    for source in source_files():
        if source.parent.name != 'dialogue':
            continue
        dest = target(source,lang)
        original = json.loads(source.read_text())
        data = json.loads(dest.read_text())
        for key,value in list(data.items()):
            if key.startswith('_'):
                continue
            if key in ('m1238.u7','m1238.u12','s000.sec1238.u7','s000.sec1238.u12'):
                data[key] = [value] if all(isinstance(v,str) for v in value) else value
                continue
            text = flat(value)
            previous = flat(original[key]) if key in original else ''
            if len(text) > max(len(previous)*2+50,200):
                report.append(dict(file=str(dest.relative_to(ROOT)),key=key,why='model expansion',source=original.get(key),text=value))
            if re.search(r'\.m\d+\.o\d+$',key):
                if not BE.fits(text,packed=BE.packed_key(key)):
                    report.append(dict(file=str(dest.relative_to(ROOT)),key=key,why='menu width',source=original.get(key),text=value))
                continue
            if isinstance(value,str):
                pages = [value]
            elif all(isinstance(v,str) for v in value):
                pages = [value]
            else:
                pages = value
            out = []
            for page in pages:
                rows = [page] if isinstance(page,str) else page
                if rows and re.fullmatch(r'\{color 6\}\{player\}\{color 1\}',rows[0]):
                    out.append(rows)
                    continue
                out.extend(wrap_page(rows, original.get(key, ''), packed=BE.packed_key(key)))
            if key in fixed and len(out) != counts[key]:
                report.append(dict(file=str(dest.relative_to(ROOT)),key=key,why='indexed pages',expected=counts[key],actual=len(out),source=original.get(key),text=out))
            else:
                data[key] = out
        dest.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n')
    path=ROOT/f'build/multilingual/review-layout-{lang}.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n')
    print(lang,len(report),'entries need review:',path)


if __name__ == '__main__':
    repage(sys.argv[1])
