"""HORIZON under DIGIMON WORLD on the two title images (tools/title_stamp.py; build-full.sh), and the rebirth scene's
four new eggs in the egg texture (tools/egg_art.py, patch 0334): artwork drawn
into the player's own images. Field UI artwork belongs to localize."""
NAME = 'title'
DESCRIPTION = 'Title and egg artwork'
AFTER = ()
FILES = ('ETCNA/TITLE256.TIM', 'ETCNA/TITLE2.TIM')
EGG_FILES = ('ETCDAT/TAMA.TIM',)


def outputs(ctx):
    return [(f'title/{f}', f) for f in FILES + EGG_FILES]


def build(ctx):
    ctx.run('tools/title_stamp.py', [ctx.path('title')])
    ctx.run('tools/egg_art.py', [ctx.path('title')])
