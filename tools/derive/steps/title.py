"""HORIZON under DIGIMON WORLD on the two title images (tools/title_stamp.py; build-full.sh)."""
NAME = 'title'
DESCRIPTION = 'Title artwork'
AFTER = ()
FILES = ('ETCNA/TITLE256.TIM', 'ETCNA/TITLE2.TIM')


def outputs(ctx):
    return [(f'title/{f}', f) for f in FILES]


def build(ctx):
    ctx.run('tools/title_stamp.py', [ctx.path('title')])
