"""The translated textures (tools/localize/build.py; build-full.sh): the Spanish copies of the textures with
words in them (FI_INFO, SYSTEM_W, ETCTIM, BI_IN, LIFE, TITLE256, STDTIM, TAISEN_F/2, CARD.ALL, the 18 STDDAT/GRADE
banners) and the files the English game shows changed in place (CARD.ALL's card 0 in Latin letters, the GRADE banners
whose logo is Japanese art).

Writes $O/lang-tex/{en,es}/<disc path>, lang-tex/files.txt ("<lang> <disc path>", the bash after it reads it) and
lang-tex/battle-banner-es.json. An en file replaces the disc's (its disc path); an es file becomes a Spanish copy
named by the LE numbering (plan P), so it has none here. Only with LANGS naming es (build-full.sh's LANG_ON).

No Pillow (the owner's decision of 2026-10-26: the player's build, in the browser too, has none): the
tournament banners' art is the player's own banner plus our delta at the size it is used at
(content/localized/tournament/delta, tools/localize/build.py banner_art: nothing of the banner in the repository) and
quantized by tools/mediancut.py (Pillow's MEDIANCUT ported: the same bytes); the recipes write no previews in a build
(LOCALIZE_PREVIEWS=0), the only thing they used Pillow for.
"""
import os
from tools.languages import translations

NAME = 'localize'
DESCRIPTION = 'Localized textures'
AFTER = ()
FACTS = False
OUT = 'lang-tex'


def lang_on(ctx):
    """build-full.sh LANGS names es"""
    return bool(translations(ctx.env))


def outputs(ctx):
    f = ctx.path(OUT, 'files.txt')
    if not lang_on(ctx) or not os.path.isfile(f):
        return []
    out = []
    for line in open(f).read().split('\n'):
        if line:
            lang, p = line.split(' ', 1)
            out.append((f'{OUT}/{lang}/{p}', p if lang == 'en' else None))
    return out + [(f'{OUT}/files.txt', None)] + [(f'{OUT}/battle-banner-{lang}.json', None) for lang in translations(ctx.env)]


def build(ctx):
    if not lang_on(ctx):
        return
    import contextlib, io, shutil
    from tools.localize import build as L      # (not `import build`: the recipes have a build.py each)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):      # (its notes go in the step's log)
        all_lines = []
        for lang in translations(ctx.env):
            folder = ctx.path(OUT) if lang == 'es' else ctx.path(OUT + '-' + lang)
            lines = L.build(folder, os.path.join(ctx.root, 'extracted'), run_with=ctx.run,
                            scratch=ctx.path('derived'), language=lang)
            if folder != ctx.path(OUT):
                for line in lines:
                    code, path = line.split(' ', 1)
                    dest = ctx.path(OUT, code, path)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copyfile(os.path.join(folder, code, path), dest)
            if folder != ctx.path(OUT):
                shutil.copyfile(os.path.join(folder, f'battle-banner-{lang}.json'),
                                ctx.path(OUT, f'battle-banner-{lang}.json'))
            all_lines.extend(lines)
        with open(ctx.path(OUT, 'files.txt'), 'w') as f:
            f.write('\n'.join(dict.fromkeys(all_lines)) + '\n')
    for line in buf.getvalue().splitlines():
        ctx.log(line)
