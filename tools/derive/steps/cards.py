"""Generate card metadata and CARD2 art, including all original replacements."""
import shutil

from tools import cards

NAME = 'cards'
DESCRIPTION = 'Card metadata and additional card archive'
AFTER = ()

PARTS = ('cards', 'parts')
UNITS = 16      # the cards are drawn in this many pieces, side by side where the build has the processes


def outputs(ctx):
    return [('cards/CARDTAB.BIN', 'CARD/CARDTAB.BIN'), ('cards/CARD2.ALL', 'CARD/CARD2.ALL')]


def card_units(ctx):
    """Every card takes about a third of a second to scale and reduce to its palette, and none depends on another:
    piece k draws cards k, k + UNITS, ... into its own file, and cards.build puts the entries in their places."""
    from tools.derive import runner
    count = len(cards.authored_cards())
    pieces = [list(range(k, count, UNITS)) for k in range(UNITS)]
    return [(indexes, runner.Unit(f'cards {k + 1}/{UNITS}', cards.card_tims, (indexes, ctx.path(*PARTS, f'{k}.bin')),
                                  ['tools/cards.py', 'tools/cardmaker.py', 'tools/image.py', 'tools/mediancut.py',
                                   'content/cards'],
                                  ['/'.join(PARTS) + f'/{k}.bin']))
            for k, indexes in enumerate(pieces) if indexes]


def build(ctx):
    art = ctx.env.get('CARD2_ALL')
    shutil.rmtree(ctx.path(*PARTS), ignore_errors=True)
    parts = []
    if not art:     # the step as a whole is what the build cache captures: its units run without a capture of their own
        from tools.derive import runner
        units = card_units(ctx)
        for d in runner.run_units(ctx, [u for _, u in units]):
            ctx.log(f'unit {d.unit.name}  ({d.seconds:.2f} s)')
        parts = [(indexes, u.args[1]) for indexes, u in units]
    cards.build(ctx.path('cards'), art, parts=parts)
    shutil.rmtree(ctx.path(*PARTS), ignore_errors=True)
