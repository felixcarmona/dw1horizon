"""SYSTEM_W source rectangles shared by the localized texture and C crop tables.

The 11-row translated glyphs need taller cells than Spanish's 5-row header font.
The atlas slots below were checked against the original texture: x>=128,y>=110
and x=96..211,y=84..95 contain no native sprite. Keep shop headers in their old
cells. C tables are exported by the developer crop generator, not at runtime.
"""

def relocated_rect(item):
    key = item['en'], item['es']
    return {
        ('POWER', 'POTENCIA'): (128, 110, 38, 12),
        ('RANG', 'ALC.'): (166, 110, 28, 12),
        ('SPEC', 'EFECTO'): (194, 110, 34, 12),
        ('TECH. DATA', 'DATOS TÉC.'): (96, 84, 64, 12),
        ('RANG', 'ALCANCE'): (160, 84, 38, 12),
    }.get(key)


def crop_tables(source, metadata):
    """Regenerate the four C sprite tables using each source recipe's rectangles.

    Language differences stay in data, so LANGxx.BIN can restore them on every
    language switch. The English branch and non-label sprites remain intact.
    """
    import re
    for name in ('MOVES_VIEW_TECHSET_TEXT', 'STATS_VIEW_ELEMENTS',
                 'MOVES_VIEW_ELEMENT_NAMES', 'MOVES_SELECTED_LABELS'):
        begin = source.index('IconRect ' + name + '[')
        a = source.index('#if MOD_LANG_BUILD', begin)
        b = source.index('#else', a)
        first = re.split(r'#elif|#else', source[a:b])[0]
        rows = [[int(x, 16) for x in re.findall(r'0x([a-fA-F0-9]+)', line)]
                for line in first.splitlines()[1:] if '{' in line]
        variants = []
        for lang, macro in [('es', 'ES'), ('pt-br', 'PT_BR'), ('fr', 'FR'),
                            ('de', 'DE'), ('it', 'IT'), ('ja', 'JA'), ('ca', 'CA')]:
            meta = metadata['pt-br' if lang == 'pt-br' else 'es']
            rr = [r.copy() for r in rows]

            def put(i, en, es=None, shifted=False):
                m = next(x for x in meta if x['en'] == en and (es is None or x['es'] == es))
                rect = relocated_rect(m) if lang in ('fr', 'de', 'it', 'ja', 'ca') else None
                u, v, w, h = rect or [m[k] for k in ('u', 'v', 'w', 'h')]
                rr[i][2:] = [w, h, u, v + (128 if shifted else 0)]
                return w

            if name == 'STATS_VIEW_ELEMENTS':
                for i, en in [(0, 'PROFILE'), (1, 'CONDITION'), (2, 'PARAMETER'),
                              (3, 'NAME'), (4, 'DIGI'), (5, 'WEIGHT'), (6, 'AGE'),
                              (7, 'TYPE'), (8, 'SPECIAL'), (9, 'ACTIVE'),
                              (17, 'HAPPINESS'), (18, 'SPEED'), (19, 'BRAINS')]:
                    put(i, en)
            elif name == 'MOVES_VIEW_ELEMENT_NAMES':
                for i, en in enumerate(('FIRE', 'BATTLE', 'AIR', 'EARTH', 'ICE', 'MECH', 'FILTH')):
                    rr[i][0] = (-45 - put(i, en, shifted=True)) & 65535
            elif name == 'MOVES_VIEW_TECHSET_TEXT':
                for i, en, es in [(0, 'POWER', None), (1, 'RANG', 'ALC.'), (2, 'SPEC', None)]:
                    put(i, en, es)
                    if lang in ('fr', 'de', 'it', 'ja', 'ca'):
                        rr[i][0], rr[i][1] = [14, 82, 112][i], (-80) & 65535
            else:
                for i, en, es in [(0, 'TECH. DATA', None), (1, 'POWER', None),
                                  (2, 'MP', None), (3, 'RANG', 'ALCANCE'), (4, 'SPEC', None)]:
                    put(i, en, es, shifted=True)
                    if lang in ('fr', 'de', 'it', 'ja', 'ca'):
                        # Absolute coordinates: regeneration is idempotent.
                        rr[i][1] = [-6, 27, 44, 61, 78][i] & 65535
            variants.append(('#if' if not variants else '#elif') +
                            ' MOD_LANG_BUILD == MOD_LANG_' + macro + '\n' +
                            ''.join('\t{ ' + ', '.join('0x%04x' % x for x in r) + ' },\n' for r in rr))
        source = source[:a] + '\n'.join(variants) + '\n' + source[b:]
    return source


def main():
    import argparse
    import json
    import tempfile
    from pathlib import Path
    from tools.localize.build import run
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decomp', type=Path)
    parser.add_argument('--extracted', type=Path, default=Path('extracted'))
    parser.add_argument('--write', action='store_true', help='otherwise verify the generated C tables')
    a = parser.parse_args()
    metadata = {}
    for lang in ('es', 'pt-br'):
        with tempfile.TemporaryDirectory() as work:
            d = run('systemw', [['build.py']], work, str(a.extracted.resolve()), language=lang)
            metadata[lang] = json.loads(Path(d, 'rects.json').read_text())
    path = a.decomp / 'src/main/game_menu.c'
    old = path.read_text()
    new = crop_tables(old, metadata)
    if a.write:
        path.write_text(new)
    elif old != new:
        raise SystemExit('SYSTEM_W C crops differ from the localized texture metadata; rerun with --write')
    print('SYSTEM_W: all seven localized crop tables match their source rectangles')


if __name__ == '__main__':
    main()
