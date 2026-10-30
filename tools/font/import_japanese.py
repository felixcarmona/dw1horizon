#!/usr/bin/env python3
"""Developer: import the Japanese bank's used glyphs from an OFL 10px BDF.

The committed subset is sufficient for the build; it never downloads a font.
Usage: python3 tools/font/import_japanese.py FONT.bdf
"""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT))


def import_font(path):
    import fontgen
    import unicodedata
    paths = list((ROOT / 'text/ja').rglob('*.json')) + [ROOT / 'text/ja.json']
    paths += list((ROOT / 'story/mods').glob('*/text/ja.json'))
    from tools.localize.catalog import UI
    text = ''.join(p.read_text() for p in paths if p.is_file()) + ''.join(v[3] for v in UI.values())
    # Include all kana for future small edits, and Japanese punctuation.
    text += ''.join(chr(i) for i in range(0x3041, 0x3097)) + ''.join(chr(i) for i in range(0x30A1, 0x30FB))
    text += '日本語名前決定戻る次へ保存読込状態技持物人時年日月火水木金土強速賢幸規重齢死進化便眠病疲労戦闘終了開始勝敗選択攻撃防御全力逃走自動上級中級初級幼年成熟完全究極属性空氷炎機械汚泥数値買売合計交換説明図鑑カード登録受付場所点数価格休息褒叱釣道具。、「」！？ー・～'
    # ASCII and the existing Latin table retain their byte codes.
    current = {c for c, _, _ in fontgen.load_extra(str(ROOT / 'tools/font/extra.txt'), include_japanese=False)}
    previous = [c for c, _, _ in fontgen.load_extra() if c not in current]
    wanted = {c for c in unicodedata.normalize('NFC', text) if ord(c) > 127 and c not in current and not c.isspace()}
    wanted.update(previous)
    glyphs = {}
    bdf = path.read_text()
    ascent = int(re.search(r'^FONT_ASCENT (\d+)', bdf, re.M)[1])
    for block in bdf.split('STARTCHAR ')[1:]:
        code = int(re.search(r'^ENCODING (\d+)', block, re.M)[1])
        char = chr(code)
        if char not in wanted:
            continue
        w, h, x, y = map(int, re.search(r'^BBX (-?\d+) (-?\d+) (-?\d+) (-?\d+)', block, re.M).groups())
        rows = block.split('BITMAP\n', 1)[1].split('ENDCHAR')[0].split()
        canvas = [['.'] * 12 for _ in range(11)]
        top = ascent - y - h
        for row, bits in enumerate(rows):
            value = int(bits, 16)
            for col in range(w):
                if value & (1 << ((w + 7) // 8 * 8 - col - 1)):
                    xx, yy = x + col, top + row
                    if not 0 <= xx < 12 or not 0 <= yy < 11:
                        raise ValueError(f'font glyph does not fit: {char}')
                    canvas[yy][xx] = '#'
        glyphs[char] = [''.join(row) for row in canvas]
    missing = wanted - glyphs.keys()
    if missing:
        raise ValueError(f'font has no glyphs for {"".join(sorted(missing))}')
    # Reserve the original 71 codes; sorted appended characters are deterministic.
    lines = ['; Japanese subset from Fusion Pixel 10px Mono ja, renamed Digimon World Japanese subset.',
             '; SIL OFL 1.1; attribution and source hashes: japanese-license/.', '']
    order = previous + sorted(set(glyphs) - set(previous))
    for char in order:
        lines += [f'glyph {char} 12', *glyphs[char], '']
    out = ROOT / 'tools/font/japanese.txt'
    out.write_text('\n'.join(lines))
    license_dir = ROOT / 'tools/font/japanese-license'
    license_dir.mkdir(exist_ok=True)
    shutil.copyfile(path.parent / 'OFL.txt', license_dir / 'OFL.txt')
    if (path.parent / 'LICENSES').exists():
        shutil.copytree(path.parent / 'LICENSES', license_dir / 'upstream', dirs_exist_ok=True)
    (license_dir / 'source.json').write_text(json.dumps({'source': 'https://github.com/TakWolf/fusion-pixel-font/releases/tag/2026.10.25',
                'font': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'glyphs': len(glyphs),
                'renamed_subset': 'Digimon World Japanese subset'}, indent=2) + '\n')
    print(out, len(glyphs), 'glyphs')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('bdf', type=pathlib.Path)
    import_font(p.parse_args().bdf)
