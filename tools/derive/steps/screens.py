"""SCRN.DAT, the records of the screens >= 255 (tools/screens.py build; build-full.sh :293-315), when the executable's
file table has it (patch 0146).

Each MAPHEAD the story step made (its FOLDER/with-new-screens/MAPHEAD.SCN, music set) loses the new screens' sections to
SCRN.DAT: FOLDER/MAPHEAD.SCN is what stays resident. The extended story's folder and its copy paged for the original font
take the screen files of content/screens and SCREEN_CONTENT; the original story's (base, base/orig) content/screens' only,
and its SCRN.DAT stays off the disc (the extended story's serves both). The same for the Spanish folders.
"""
import os

from . import story as ST

NAME = 'screens'
DESCRIPTION = 'Screen records'
AFTER = ('story',)
FACTS = True


def outputs(ctx):
    s = ST.Settings(ctx)
    if not s.scrn:
        return []
    out = []
    for lang, root, text, *_ in s.langs(ctx):
        rel = os.path.relpath(root, ctx.out)
        for v in s.variants(text, ctx.facts):
            d = os.path.normpath(os.path.join(rel, v))
            out.append((os.path.join(d, 'MAPHEAD.SCN'), ST.disc_path(ctx, s, lang, v, 'MAPHEAD.SCN')))
            out.append((os.path.join(d, 'SCRN.DAT'), None if v.startswith('base') else ST.disc_path(ctx, s, lang, v, 'SCRN.DAT')))
    return out


def screens_unit(root, d, content, mh_max, pack, lang, glyphs, cache_records):
    """One folder's SCRN.DAT and resident MAPHEAD.SCN (a unit; in this process, a forked one or a worker) -> its log."""
    lines = []
    with ST.tools(root):
        import screens
        screens.build_files(os.path.join(d, 'with-new-screens', 'MAPHEAD.SCN'), os.path.join(d, 'MAPHEAD.SCN'),
                            os.path.join(d, 'SCRN.DAT'), content, mh_max, pack_ascii=pack, log=lines.append,
                            language=lang, font_glyphs=glyphs, cache_records=cache_records)
    return '\n'.join(lines) + '\n'


def build(ctx):
    s = ST.Settings(ctx)
    if not s.scrn:
        return
    cache = bool(os.environ.get('DW_BUILD_CACHE')) and not ctx.record and not ST.runner.strict()
    todo = [(lang, os.path.join(root, v), [] if v.startswith('base') else s.screens, pack)
            for lang, root, text, story_lang, zones, pack in s.langs(ctx) for v in s.variants(text, ctx.facts)]
    if ctx.jobs > 1 and not ST.runner.strict() and not ctx.record and not cache:     # (the record cache: one writer)
        # every folder's records come from its own MAPHEAD and go to its own two files: side by side
        units = [ST.runner.Unit(f'screens {os.path.relpath(d, ctx.out)}', screens_unit,
                                (ctx.root, d, content, s.mh_max, pack, lang, s.glyphs, cache),
                                ['tools', 'content/screens', 'content/localized', 'step:story'] + list(content),
                                [os.path.relpath(os.path.join(d, f), ctx.out) for f in ('MAPHEAD.SCN', 'SCRN.DAT')])
                 for lang, d, content, pack in todo]
        for done in ST.runner.run_units(ctx, units):
            for line in done.out.splitlines():
                ctx.log(line)
        return
    for lang, d, content, pack in todo:
        with ST.tools(ctx.root, ctx):
            import screens
            screens.build_files(os.path.join(d, 'with-new-screens', 'MAPHEAD.SCN'), os.path.join(d, 'MAPHEAD.SCN'),
                                os.path.join(d, 'SCRN.DAT'), content, s.mh_max,
                                pack_ascii=pack, log=ctx.log, language=lang, font_glyphs=s.glyphs,
                                cache_records=cache)


def check(ctx):
    """The check of the Spanish MAPHEADs (the bash Spanish run made it, :316-321; the others are build-full.sh's own): each within the
    executable's MAPHEAD_SCRIPT_BUFFER."""
    ST.check_size(ctx)
