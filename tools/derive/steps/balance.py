"""The wild Digimon of content/maps written into the .MAP files the story did not edit
(tools/balance.py build_maps; build-full.sh's `balance.py build`, whose map half needs no executable: the bash now runs
it with --no-maps after the executable for the tables only).

  balance-maps/      the extended story's: every .MAP but those the story compiler replaced (story.map_files(ctx, '')),
                     a disc file each (the bash's BAL_FILES)
  balance-maps/base  with EXTENDED STORY (ALT) the original story's: every .MAP but its own story maps; the storycopies
                     step copies from them (the bash's exe-base/maps, dws/variants.py finish)

Each folder holds the maps under their disc paths and files.txt (DEST=SRC lines, content.map_files() order).
Unchanged maps are outputs too: another base can require generation where USA
already matches content/maps. The recorded package must retain those producers.
"""
import os
import shutil

from . import story as ST

NAME = 'balance'
DESCRIPTION = 'Map gameplay data'
AFTER = ('story',)
FACTS = True
OUT = 'balance-maps'


def passes(ctx):
    """[(folder under OUT, the story pass whose maps it leaves alone)]"""
    s = ST.Settings(ctx)
    return [('', '')] + ([('base', 'base')] if s.alt else [])


def files(ctx, v=''):
    """[DEST=SRC] of one pass, in the order build_maps made them."""
    p = ctx.path(OUT, v, 'files.txt')
    return [l for l in open(p).read().split('\n') if l] if os.path.isfile(p) else []


def outputs(ctx):
    out = []
    for v, _ in passes(ctx):
        out += [(os.path.relpath(f.split('=', 1)[1], ctx.out), None if v else f.split('=', 1)[0]) for f in files(ctx, v)]
        out.append((os.path.join(OUT, v, 'files.txt'), None))
    return out


def build(ctx):
    # Retouch recipes own geometry that the final plan would otherwise replace
    # with a newly declared, USA-identical raw map. Generate gameplay data from
    # that effective input while retaining the recipe's geometry and artwork.
    for v, story in passes(ctx):
        d = ctx.path(OUT, v)
        sources = dict(f.split('=', 1) for f in ST.map_files(ctx, story))
        if os.path.isdir(os.path.join(d, 'maps')):
            shutil.rmtree(os.path.join(d, 'maps'))
        with ST.tools(ctx.root, ctx):
            import balance
            made = balance.build_maps(os.path.join(d, 'maps'), sources, map_overrides(ctx, story))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'files.txt'), 'w') as f:
            f.write(''.join(f'{rel}={dst}\n' for rel, dst in made))
        ctx.log(f'{OUT}/{v}: {len(made)} maps with the wild Digimon of content/maps')


def map_overrides(ctx, story=''):
    """Retouch geometry belongs to the extended story; base copies use the disc."""
    if story:
        return {}
    return {dest: os.path.join(ctx.root, source) for dest, source in
            (entry.split('=', 1) for entry in ctx.env.get('EXTRA_FILES', '').split())}
