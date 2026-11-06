"""HORIZON under DIGIMON WORLD on the two title images (tools/title_stamp.py; build-full.sh), and the rebirth scene's
four new eggs in the egg texture (tools/egg_art.py, patch 0334), and the field
care HUD atlas (tools/field_hud_art.py): artwork drawn into the player's own images."""
NAME = 'title'
DESCRIPTION = 'Title, egg and field HUD artwork'
AFTER = ()
FILES = ('ETCNA/TITLE256.TIM', 'ETCNA/TITLE2.TIM')
EGG_FILES = ('ETCDAT/TAMA.TIM',)
HUD_FILES = ('ETCDAT/ETCTIM.BIN',)


def outputs(ctx):
    return [(f'title/{f}', f) for f in FILES + EGG_FILES + HUD_FILES]


def build(ctx):
    ctx.run('tools/title_stamp.py', [ctx.path('title')])
    ctx.run('tools/egg_art.py', [ctx.path('title')])
    ctx.run('tools/field_hud_art.py', [ctx.path('title')])
