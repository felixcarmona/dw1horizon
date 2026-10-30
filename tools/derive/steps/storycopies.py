"""EXTENDED STORY's copies of the map files the mods change (tools/dws/variants.py plan and finish; build-full.sh 4b
and 5b): with a story mod and patch 0199 (ALT) every .MAP/.TFS whose extended-story file differs from the original
story's gets a copy named _AME.EXT beside it on the disc, with the original story's bytes.

Which files: dws.variants.plan compares the extended story's files (EXTRA_FILES that replace a disc file, then the
story's maps: story.map_files(ctx, '')) with the original story's (story.map_files(ctx, 'base')), each the disc's own
when a list lacks it, before the balance maps (as the bash did). Their bytes: dws.variants.finish writes each copy again
from the original story's balance maps (the balance step's base pass), which the bash could make only after the
executable; both run here, one after the other.

Writes storycopies/<_AME.EXT> and storycopies/plan.txt (the --add and COPY lines dws/variants.py plan prints; the plan
step reads the rows: the sign copies of the original story are named after them). Nothing without ALT.
"""
import os

from . import balance as BAL
from . import story as ST

NAME = 'storycopies'
DESCRIPTION = 'Original-story map copies'
AFTER = ('story', 'balance')
FACTS = True
OUT = 'storycopies'


def ext_files(ctx):
    """The extended story's files in build-disc's order (build-full.sh EXT_SRC): EXTRA_FILES that replace a disc file,
    then the story's maps."""
    ext = [f for f in ctx.env.get('EXTRA_FILES', '').split()
           if os.path.isfile(os.path.join(ctx.root, 'extracted', f.split('=', 1)[0]))]
    return ext + ST.map_files(ctx, '')


def rows(ctx):
    """[(DEST, copy name, ext file, base file)] of plan.txt's COPY lines ([] without ALT or before the step ran)."""
    p = ctx.path(OUT, 'plan.txt')
    if not ST.Settings(ctx).alt or not os.path.isfile(p):
        return []
    return [tuple(f[1:5]) for f in (l.split('\t') for l in open(p).read().split('\n') if l) if f[0] == 'COPY']


def outputs(ctx):
    out = [(os.path.join(OUT, name), f'{os.path.dirname(dest)}/{name}') for dest, name, *_ in rows(ctx)]
    return out + ([(os.path.join(OUT, 'plan.txt'), None)] if out or os.path.isfile(ctx.path(OUT, 'plan.txt')) else [])


def build(ctx):
    if not ST.Settings(ctx).alt:
        return
    d = ctx.path(OUT)
    if os.path.isdir(d):
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
    pairs = lambda specs: dict(s.split('=', 1) for s in specs)   # (the last of a DEST wins: build-disc's order)
    base = ST.map_files(ctx, 'base')
    with ST.tools(ctx.root, ctx):
        from dws import variants as SF
        made = SF.plan(d, pairs(ext_files(ctx)), pairs(base))
        n = SF.finish(d, made, pairs(base + BAL.files(ctx, 'base')))
        lines = SF.plan_lines(d, made)
    with open(os.path.join(d, 'plan.txt'), 'w') as f:
        f.write(''.join(l + '\n' for l in lines))
    ctx.log(f'{len(made)} map files differ from the original story\'s (copies in {d}); {n} rewritten from its balance maps')
