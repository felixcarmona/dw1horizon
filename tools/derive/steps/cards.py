"""Generate the card metadata sector and accept the phase-B image archive."""
from tools import cards

NAME = 'cards'
DESCRIPTION = 'Card metadata and additional card archive'
AFTER = ()


def outputs(ctx):
    out = [('cards/CARDTAB.BIN', 'CARD/CARDTAB.BIN'), ('cards/CARD2.ALL', 'CARD/CARD2.ALL')]
    if cards.replaced():
        out.append(('cards/CARD.ALL', 'CARD/CARD.ALL'))
    return out


def build(ctx):
    import os
    cards.build(ctx.path('cards'), ctx.env.get('CARD2_ALL'), source=os.path.join(ctx.root, 'extracted', 'CARD', 'CARD.ALL'))
