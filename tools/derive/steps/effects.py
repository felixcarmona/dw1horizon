"""Technique effect targeting, regenerated from the player's effect archive."""
import os
import struct

NAME = 'effects'
DESCRIPTION = 'Technique effect targeting'
AFTER = ()
DISC_PATH = 'ETCHI/EFEDAT.EFE'
CHUNK_SIZE = 0x5000
NIGHTMARE = 96


def exclude_caster(archive):
    """Nightmare Syndromer's random target must exclude its caster.

    EFE subopcode 75 accepts an allow-self flag: zero skips sourceEntity in
    BTL/STD/VS_selectRandomTargetEntity. Donor bones and MOVE_DATA do not
    control this choice. Walk instructions so texture/data words cannot match.
    """
    data = bytearray(archive)
    base = NIGHTMARE * CHUNK_SIZE
    if len(data) < base + CHUNK_SIZE:
        raise ValueError('Nightmare Syndromer: missing effect chunk')
    script, end = struct.unpack_from('<2I', data, base)
    pc, stop = base + 0x34 + script, base + 0x34 + end
    if not base + 0x34 <= pc < stop <= base + CHUNK_SIZE:
        raise ValueError('Nightmare Syndromer: invalid script bounds')
    sizes = (6, 6, 2, 10, 6, 2, 2, 10, 2, 6, 6, 6, 6, 6, 2, 2, 6, 12)
    previous, flags = None, []
    while pc < stop:
        word = struct.unpack_from('<H', data, pc)[0]
        op = word & 0xff
        if op >= len(sizes) or pc + sizes[op] > stop:
            raise ValueError('Nightmare Syndromer: invalid script instruction')
        if word == 0x4b0e:  # dispatch subopcode 75, selectRandomTargetEntity
            if previous is None or data[previous] != 10:
                raise ValueError('Nightmare Syndromer: target flag is not immediate')
            if struct.unpack_from('<h', data, previous + 2)[0] != 1:
                raise ValueError('Nightmare Syndromer: expected allow-self flag')
            flags.append(previous + 2)
        previous = pc
        pc += sizes[op]
    if len(flags) != 1:
        raise ValueError('Nightmare Syndromer: expected one random target selector')
    struct.pack_into('<h', data, flags[0], 0)
    return bytes(data)


def outputs(ctx):
    return [('effects/' + DISC_PATH, DISC_PATH)]


def build(ctx):
    with open(os.path.join(ctx.root, 'extracted', DISC_PATH), 'rb') as source:
        data = exclude_caster(source.read())
    dest = ctx.path('effects', DISC_PATH)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'wb') as target:
        target.write(data)
