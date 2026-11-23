"""The curling cups' banners in every language, from the repository's own art (tools/curling_banners.py)."""
from tools import curling_banners

NAME = 'curling'
DESCRIPTION = 'Curling cup banners'
AFTER = ()


def outputs(ctx):
    return [('KARCUP.DAT', 'KARCUP.DAT')]


def build(ctx):
    with open(ctx.path('KARCUP.DAT'), 'wb') as f:
        f.write(curling_banners.pack())
