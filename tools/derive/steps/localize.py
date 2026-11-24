"""The translated textures (tools/localize/build.py; build-full.sh): the Spanish copies of the textures with
words in them (FI_INFO, SYSTEM_W, ETCTIM, BI_IN, LIFE, TITLE256, STDTIM, TAISEN_F/2, CARD.ALL, the 18 STDDAT/GRADE
banners) and the files the English game shows changed in place (CARD.ALL's card 0 in Latin letters, the GRADE banners
whose logo is Japanese art).

Writes $O/lang-tex/{en,es}/<disc path>, lang-tex/files.txt ("<lang> <disc path>", the bash after it reads it) and
lang-tex/battle-banner-es.json. An en file replaces the disc's (its disc path); an es file becomes a Spanish copy
named by the LE numbering (plan P), so it has none here. Only with LANGS naming es (build-full.sh's LANG_ON).

No Pillow (the player's build, in the browser too, has none): the
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
    if not os.path.isfile(f):
        return []
    out = []
    for line in open(f).read().split('\n'):
        if line:
            lang, p = line.split(' ', 1)
            out.append((f'{OUT}/{lang}/{p}', p if lang == 'en' else None))
    return out + [(f'{OUT}/files.txt', None)] + [(f'{OUT}/battle-banner-{lang}.json', None) for lang in translations(ctx.env)]


def language_folder(ctx, lang):
    return ctx.path(OUT) if lang == 'es' else ctx.path(OUT + '-' + lang)


def language_unit(folder, extracted, scratch, lang, dest):
    """One language's translated textures into folder, and their files.txt lines into dest -> the recipes' notes."""
    import contextlib, io, json
    from tools.localize import build as L
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        lines = L.build(folder, extracted, scratch=scratch, language=lang)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest + '.tmp', 'w') as f:
        json.dump(lines, f)
    os.replace(dest + '.tmp', dest)
    return buf.getvalue()


def build(ctx):
    import contextlib, io, json, shutil
    from tools.derive import runner
    from tools.localize import build as L      # (not `import build`: the recipes have a build.py each)
    from tools.care_badge import FILES, stamp
    from tools.localize.status_art import stamp as status_stamp
    from tools.localize.tech_rows_art import stamp as tech_rows_stamp
    from tools.field_hud_art import PATH as HUD_PATH, build as field_hud_art
    from tools import care_bubble_art
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):      # (its notes go in the step's log)
        all_lines = []
        # Care artwork also belongs to single-language builds, in the same two
        # native files. Their ordinary field upload installs the private CLUT.
        for path, entry in FILES:
            with open(os.path.join(ctx.root, 'extracted', path), 'rb') as f:
                data = bytearray(f.read())
            stamp(data, entry)
            status_stamp(data, entry)
            tech_rows_stamp(data, entry)
            if path == HUD_PATH:
                data = care_bubble_art.build(field_hud_art(data))
            dest = ctx.path(OUT, 'en', path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, 'wb') as f:
                f.write(data)
            all_lines.append(f'en {path}')
        path = care_bubble_art.FEEL
        with open(os.path.join(ctx.root, 'extracted', path), 'rb') as f:
            original = f.read()
        with open(ctx.path(OUT, 'en', HUD_PATH), 'rb') as f:
            data = care_bubble_art.feel(original, f.read())
        dest = ctx.path(OUT, 'en', path)
        with open(dest, 'wb') as f:
            f.write(data)
        all_lines.append(f'en {path}')
        langs = list(translations(ctx.env))
        made = {}
        if ctx.jobs > 1 and not runner.strict() and not ctx.record and len(langs) > 1:
            # a language's textures depend on no other language's and go to its own folder (Spanish: this step's):
            # they are made side by side, and gathered below in the languages' order, as one pass over them does
            parts = ctx.path('derived', 'localize-parts')
            shutil.rmtree(parts, ignore_errors=True)
            units = [runner.Unit(f'textures {lang}', language_unit,
                                 (language_folder(ctx, lang), os.path.join(ctx.root, 'extracted'), ctx.path('derived'), lang,
                                  os.path.join(parts, lang + '.json')),
                                 ['tools', 'content/localized', 'extracted'],
                                 [os.path.relpath(language_folder(ctx, lang), ctx.out)])
                     for lang in langs]
            for d in runner.run_units(ctx, units):
                print(f'unit {d.unit.name}  ({d.seconds:.2f} s)')
                if d.out:
                    print(d.out.rstrip('\n'))
                with open(d.unit.args[4]) as f:
                    made[d.unit.args[3]] = json.load(f)
            shutil.rmtree(parts, ignore_errors=True)
        for lang in langs:
            folder = language_folder(ctx, lang)
            lines = made[lang] if lang in made else L.build(folder, os.path.join(ctx.root, 'extracted'), run_with=ctx.run,
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
