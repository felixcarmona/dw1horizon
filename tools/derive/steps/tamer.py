"""Generate the tamer's other looks (bald and the hairstyles) from the player's own tamer."""
from tools import tamer_pack

NAME = 'tamer'
DESCRIPTION = 'Tamer looks archive'
AFTER = ()


def outputs(ctx):
    return [('TAMER.DAT', 'TAMER.DAT')]


def build(ctx):
    data, report = tamer_pack.build(tamer_pack.MODEL, tamer_pack.ALLTIM)
    with open(ctx.path('TAMER.DAT'), 'wb') as f:
        f.write(data)
    for line in report:
        print(line)
