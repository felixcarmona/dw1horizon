"""Author SDK diagnostics in the player's locally generated assembly slots.

No original message text is stored here. Padding preserves every later label,
format arguments retain their types/order, and repeat application is identical.
"""
import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def author(tree):
    spec = json.loads((ROOT / 'tools/patcher/sdk-messages.json').read_text())
    changed = 0
    for sdk, entries in spec.items():
        path = Path(tree) / f'asm/us/main/data/psyq/{sdk}.rodata.s'
        if not path.exists():
            continue
        source = path.read_text()
        index = 0
        def replace(match):
            nonlocal index
            old = ast.literal_eval(match['text'])
            if not old or old == 'bu00:':
                return match[0]
            entry = entries[index]; index += 1
            new, capacity = entry['text'], entry['size']
            padding = int(match['padding'] or 0)
            if len(old.encode()) + 1 + padding != capacity:
                raise ValueError(f'{sdk}: diagnostic slot changed shape')
            formats = lambda text: re.findall(r'%(?:0\d+)?[dxs]', text)
            if formats(old) != formats(new) or len(new.encode()) + 1 > capacity:
                raise ValueError(f'{sdk}: diagnostic format/size changed')
            result = match['prefix'] + '.asciz ' + json.dumps(new)
            if capacity > len(new.encode()) + 1:
                result += '\n    .space ' + str(capacity - len(new.encode()) - 1) + ', 0'
            return result
        result = re.sub(r'(?P<prefix>^[^\n]*?)\.asciz\s+(?P<text>"(?:[^"\\]|\\.)*")'
                        r'(?:\n\s*\.space\s+(?P<padding>\d+),\s*0)?', replace, source, flags=re.M)
        if index != len(entries):
            raise ValueError(f'{sdk}: diagnostic inventory changed')
        if result != source:
            path.write_text(result); changed += 1
    # _SsInit writes this record to all 24 SPU voice register sets before
    # enabling the sequencer. Start every inactive voice muted with cleared
    # configuration; key-on/program setup supplies its actual sample, pitch,
    # envelope and volumes. Keep the 16-byte slot and every following label.
    path = Path(tree) / 'asm/us/main/data/psyq/libsnd.data.s'
    if path.is_file():
        source = path.read_text()
        pattern = r'(dlabel_section voice_on\n)(.*?)(enddlabel_section voice_on)'
        match = re.search(pattern, source, re.S)
        if not match or len(re.findall(r'\.short\s+0x[0-9A-Fa-f]+', match[2])) != 8:
            raise ValueError('voice reset register layout changed')
        body = re.sub(r'(\.short\s+)0x[0-9A-Fa-f]+', r'\g<1>0x0000', match[2])
        result = source[:match.start(2)] + body + source[match.end(2):]
        if result != source:
            path.write_text(result); changed += 1
    return changed


if __name__ == '__main__':
    author(Path(sys.argv[1]))
