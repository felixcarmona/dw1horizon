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


def build(ctx):
    s = ST.Settings(ctx)
    if not s.scrn:
        return
    for lang, root, text, story_lang, zones, pack in s.langs(ctx):
        for v in s.variants(text, ctx.facts):
            d = os.path.join(root, v)
            with ST.tools(ctx.root, ctx):
                import screens
                screens.build_files(os.path.join(d, 'with-new-screens', 'MAPHEAD.SCN'), os.path.join(d, 'MAPHEAD.SCN'),
                                    os.path.join(d, 'SCRN.DAT'), [] if v.startswith('base') else s.screens, s.mh_max,
                                    pack_ascii=pack, log=ctx.log,
                                    cache_records=bool(os.environ.get('DW_BUILD_CACHE')) and not ctx.record and not ST.runner.strict())


def check(ctx):
    """The check of the Spanish MAPHEADs (the bash Spanish run made it, :316-321; the others are build-full.sh's own): each within the
    executable's MAPHEAD_SCRIPT_BUFFER."""
    ST.check_size(ctx)
