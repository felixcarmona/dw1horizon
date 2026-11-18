"""Generate the card metadata sector and accept the phase-B image archive."""
from tools import cards

NAME = 'cards'
DESCRIPTION = 'Card metadata and additional card archive'
AFTER = ()


def outputs(ctx):
    return [('cards/CARDTAB.BIN', 'CARD/CARDTAB.BIN'), ('cards/CARD2.ALL', 'CARD/CARD2.ALL')]


def build(ctx):
    cards.build(ctx.path('cards'), ctx.env.get('CARD2_ALL'))
