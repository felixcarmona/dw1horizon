#!/usr/bin/env python3
"""Shared padding bank for any number of runtime languages (gen_text.py).

Pick the longest encoded string per key; identity=True makes each key keep its own
array. This prevents aliases that hold for two languages but not the third.
"""
import json
import sys


def merge(banks):
    font = {}
    text = {}
    independent = any(bank.get('encoding') == 'dwzh-1' for bank in banks)
    for bank in banks:
        if bank.get('encoding') == 'dwzh-1':continue
        for char, code in bank['font'].items():
            if char in font and font[char] != code:
                raise ValueError(f'inconsistent font code for {char!r}')
            font[char] = code
    sizes = {}
    for bank in banks:
        def size(value):
            return sum(2 if c in bank['font'] else len(c.encode('cp932')) for c in value)
        for key, value in bank['text'].items():
            if not isinstance(value, str):
                raise ValueError(f'{key}: the executable padding bank expects a string')
            length = size(value)
            if key not in text or length > sizes[key]:
                text[key] = value
                sizes[key] = length
    # Share storage only when every selected language explicitly supplies the
    # same tuple of texts. Missing keys retain their own YAML-dependent identity.
    canonical = {}
    aliases = {}
    for key in sorted(text):
        if all(key in bank['text'] for bank in banks):
            signature = tuple(bank['text'][key] for bank in banks)
            aliases[key] = canonical.setdefault(signature, key)
    # Independent glyph sets can map one Unicode character to different codes.
    # gen_text needs only the encoded capacity of the padding text, never its ink.
    if independent:text = {key:'X'*sizes[key] for key in text}
    return {'font': font, 'text': text, 'identity': True, 'aliases': aliases, 'complete': sorted(aliases)}


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit('usage: padding.py OUT.json BANK.json BANK.json [BANK.json ...]')
    with open(sys.argv[1], 'w', encoding='utf-8') as f:
        json.dump(merge([json.load(open(p, encoding='utf-8')) for p in sys.argv[2:]]), f,
                  ensure_ascii=False, indent=1)
        f.write('\n')
