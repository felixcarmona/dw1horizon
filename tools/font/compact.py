"""Build the compact Latin font from the player's USA disc and our authored glyphs.

Run after extracting the disc: python3 tools/font/compact.py ENGINE_TREE.
The generated header stays in the ignored decomp worktree; the patch series must
not carry the original game's bitmap glyphs, even in compressed form.
"""
import pathlib
import re
import sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools import fontgen
from tools.patcher import fontcopy
import struct


def parse(data, start):
    tail=data[data.index(start):];tail=tail[:tail.index('\n};')]
    result=[]
    for words,width in re.findall(r'\{\s*\{([^}]+)\}\s*,\s*([0-9 |<>]+)\s*\}',tail):
        values=[int(v,16) for v in re.findall(r'0x[0-9a-fA-F]+',words)]
        if len(values)!=11:raise ValueError('expected eleven bitmap rows')
        # The generated width is either an integer or advance | cell << 8.
        parts=width.split('|')
        advance=int(parts[0].strip())
        if len(parts)>1:
            cell,shift=parts[1].split('<<');advance |= int(cell.strip()) << int(shift.strip())
        rows=[''.join('.' if v & (0x8000>>x) else '#' for x in range(12)) for v in values]
        result.append(('?',advance,rows))
    return result


def tables(tree):
    _, original=fontgen.disc_glyphs()
    b=(tree/'src/main/font_b.h').read_text()
    groups=[[('?',width,rows) for width,rows in original],fontgen.load_extra()[:71],
            parse(b,'GlyphData GLYPH_DATA[NUM_GLYPHS]'),parse(b,'GlyphData EXTRA_GLYPH_DATA[NUM_LATIN_GLYPHS]')]
    if list(map(len,groups)) != [79,71,79,71]:raise ValueError('unexpected font table dimensions')
    return [glyph for group in groups for glyph in group]


def header(tree):
    codes, glyphs = fontgen.disc_glyphs()
    original = b''.join(struct.pack('<12H', *(fontgen.row_word(row) for row in rows), width)
                        for width, rows in glyphs)
    arrays = fontcopy.pad_tables(fontcopy.generate(original, codes, fontgen))
    lines=['/* Generated from the player font and authored glyphs; fixed regional capacities. */',
           f'#define LATIN_HUFFMAN_MAX_BITS {fontcopy.MAX_BITS}']
    for name, data in arrays.items():
        typ = 'uint8_t' if name == 'LATIN_GLYPH_BITS' else 'uint16_t'
        values = list(data) if typ == 'uint8_t' else list(struct.unpack(f'<{len(data)//2}H', data))
        lines.append(f'static const {typ} {name}[{len(values)}] = {{')
        for i in range(0,len(values),12):lines.append('\t'+', '.join(hex(v) for v in values[i:i+12])+',')
        lines.append('};')
    path=tree/'src/main/font_compact.h'
    text='\n'.join(lines)+'\n'
    if not path.exists() or path.read_text()!=text:
        path.write_text(text)


if __name__=='__main__':header(pathlib.Path(sys.argv[1]))
