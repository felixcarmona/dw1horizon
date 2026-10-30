"""The map signs translated (tools/localize/signs.py; build-full.sh :457): our signs' cut-outs pasted into
the backgrounds the disc carries, both languages each pass.

  lang-signs       the extended story's files: EXTRA_FILES that replace a file of the disc (extracted/DEST exists),
                   then the story compiler's maps ($O/dws.log FILE: lines), each pasted into in place of the disc's
  lang-signs-base  with EXTENDED STORY (ALT: EXTRA_STORY, STORY_ALT not 0, the executable's modStoryFile) a second
                   time into the original story's maps ($O/base/dws.log FILE: lines)

Writes OUT/{en,es}/<disc path> and OUT/files.txt (the bash after it reads both). Every file becomes a copy named by the
LE numbering (plan P), so none has a disc path here. Only with LANGS naming es.

It reads the story step's maps (AFTER); the plan step names the copies.

No Pillow (standard library): the signs are masked RGB deltas at their crop's size (content/localized/signs/delta,
tools/localize/cutout.py: reconstructed from the player's crop), the mask and the paste are plain Python
(tools/localize/signs.py); a missing cut-out index stops the build.
"""
import os
import sys

from . import localize
from .. import runner

NAME = 'signs'
DESCRIPTION = 'Localized map signs'
AFTER = ('story',)
FACTS = True
PASSES = (('lang-signs', 'dws.log'), ('lang-signs-base', 'base/dws.log'))


def alt(ctx):
    """build-full.sh ALT"""
    return bool(ctx.env.get('EXTRA_STORY')) and (ctx.env.get('STORY_ALT') or '1') == '1' and \
        bool(ctx.facts and ctx.facts.get('mod_story_file'))


def story_files(ctx, v):
    """the story's maps of the English pass v ('' or 'base'): DEST=SRC (story.map_files: the story step's copies)"""
    from . import story
    return story.map_files(ctx, v)


def passes(ctx):
    """[(out folder, [DEST=SRC...])] in build-full.sh's order (:376-382)"""
    ext = [f for f in ctx.env.get('EXTRA_FILES', '').split() if os.path.isfile(os.path.join(ctx.root, 'extracted', f.split('=', 1)[0]))]
    ext += story_files(ctx, '')
    out = [(PASSES[0][0], ext)]
    if alt(ctx):
        out.append((PASSES[1][0], story_files(ctx, 'base')))
    return out


def outputs(ctx):
    if not localize.lang_on(ctx):
        return []
    out = []
    for d, _ in PASSES:
        f = ctx.path(d, 'files.txt')
        if os.path.isfile(f):
            out += [(f'{d}/{l.replace(" ", "/", 1)}', None) for l in open(f).read().split('\n') if l]
            out.append((f'{d}/files.txt', None))
    return out


def run_pass(root, out, files, languages=("en", "es")):
    """One pass (a unit; in this process or a worker): signs.signs into out -> its log line."""
    saved = sys.path[:]
    try:
        from tools.localize import signs as S    # (it puts tools/ and content/localized/signs on sys.path)
    finally:
        sys.path[:] = saved
        sys.modules.pop('jobs', None)            # (content/localized/tournament has a jobs.py too)
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):      # (its notes go in the step's log: check())
        lines = S.signs(out, os.path.join(root, 'extracted'), dict(f.split('=', 1) for f in files), languages=languages)
    notes = ''.join(l + '\n' for l in buf.getvalue().splitlines() if l.startswith('note:'))
    return f'{os.path.basename(out)}: {len(lines)} backgrounds with translated signs\n' + notes


def units(ctx):
    """The two passes (runner.Unit): each reads the disc's backgrounds, our sign edits and its story's maps."""
    if not localize.lang_on(ctx):
        return []
    return [runner.Unit(d, run_pass, (ctx.root, ctx.path(d), files, ('en',) + localize.translations(ctx.env)),
                        ['tools/localize/signs.py', 'tools/localize/cutout.py', 'content/localized/signs', 'extracted/MAP',
                         f'step:story ({dict(PASSES)[d]} FILE: lines and their maps)'], [f'{d}/files.txt'])
            for d, files in passes(ctx)]


def build(ctx):
    """The passes side by side with --jobs (runner.run_units), else one after the other here."""
    ctx.run_units(units(ctx))
