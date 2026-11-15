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


def _instructions(data, base, name):
    """Script offsets (from the chunk's script head, base + 0x34) of every instruction of the start script."""
    script, end = struct.unpack_from('<2I', data, base)
    pc, stop = base + 0x34 + script, base + 0x34 + end
    if not base + 0x34 <= pc < stop <= base + CHUNK_SIZE:
        raise ValueError(f'{name}: invalid script bounds')
    while pc < stop:
        op = data[pc]
        if op >= len(SIZES) or pc + SIZES[op] > stop:
            raise ValueError(f'{name}: invalid script instruction')
        yield pc - base - 0x34
        pc += SIZES[op]


SIZES = (6, 6, 2, 10, 6, 2, 2, 10, 2, 6, 6, 6, 6, 6, 2, 2, 6, 12)
DEADLY_BOMB = 74
THROW = 0x880           # the bomb's throw, at frame 30 of the effect (script offset)
THROW_LEN = 0x84
THROW_SOURCE = bytes.fromhex(
    '01040000adda040400000000' '0acd00000000' '0c0404000000' '0c0410000000' '0e3e'
    '0c0404000000' '0acd04000000' '0acd0c000000' '0e1a' '00cd00010000' '040410000000'
    '00cd00080000' '041414000000' '00cd00000000' '040424000000' '00cd00000000' '040428000000'
    '00cd64000000' '04042c000000' '0c0410000000' '0c0424000000' '0e39' '09cd540cadda')
THROW_SPEED = 12        # ticks from the throw to the first landing (frames 31-42), so it lands on the target
LANDING = 0x982         # the first landing's 'speed z / 3' (script offset): becomes 'next phase', the hit check
LANDING_SOURCE = bytes.fromhex('00cd03000000' '04442c000000')
LANDING_HIT = bytes.fromhex('00cd01000000' '04141c000000')
THROW_UP = -38          # the original lob's upward speed, (0, 0, 100) turned 256 units up


def _words(*values):
    return struct.pack('<%dH' % len(values), *[v & 0xffff for v in values])


def aimed_throw():
    """The throw block, aimed: velocity = (target - bomb) / THROW_SPEED, upward speed THROW_UP."""
    block = THROW_SOURCE[:12]                                          # instance frame = the effect's frame
    block += _words(0x040c, 4, 0, 0xcd0a, 4, 0, 0xcd0a, 12, 0, 0x1a0e)   # position = the bomb in the hand
    block += _words(0xcd00, 256, 0, 0x0404, 0x10, 0)                     # spin x = 256, as before
    block += _words(0x040c, 0x24, 0, 0x0e0e)                             # v = target position (sub 14)
    block += _words(0x040c, 0x24, 0, 0x040c, 4, 0, 0x320e)               # v -= position (sub 50)
    block += _words(0x040c, 0x24, 0, 0xcd0a, THROW_SPEED, 0, 0x480e)     # v /= THROW_SPEED (sub 72)
    block += _words(0xcd00, THROW_UP, 0, 0x0404, 0x28, 0)                # v.y = THROW_UP
    block += THROW_SOURCE[-6:]                                         # jmp to the routine's return
    return block + _words(0xcd0f) * ((THROW_LEN - len(block)) // 2)    # unreachable returns


def aim_deadly_bomb(archive):
    """Deadly Bomb's bomb lands on the target and goes off there.

    Chunk 74 throws the bomb at frame 30 with velocity (0, 0, 100) turned by the caster's bone-0 angles (x forced to
    256, y + 2048), lets it fly and bounce (gravity 10, horizontal speed / 3 per bounce) until frame 77, and only then
    looks for a Digimon in a +-200 box around it (BTL_findHitEntity, then the box hit) until frame 700. The lob is
    fixed: it comes to rest about 1400 units out whatever the distance to the enemy, and by frame 77 the enemy has
    moved on, so it never hits. The aimed throw keeps the bomb, spin, upward speed and gravity and sets the
    horizontal speed to (target - bomb) / THROW_SPEED, so the first landing is on the target; the landing then
    starts the box check (phase 3) at once instead of the second bounce's z slowdown. Frame 77 still starts it if
    the bomb never lands, and a missed bomb waits as a mine until frame 700, as before.
    """
    data = bytearray(archive)
    base = DEADLY_BOMB * CHUNK_SIZE
    if len(data) < base + CHUNK_SIZE:
        raise ValueError('Deadly Bomb: missing effect chunk')
    offsets = set(_instructions(data, base, 'Deadly Bomb'))
    if THROW not in offsets:
        raise ValueError('Deadly Bomb: the throw is not an instruction')
    at = base + 0x34 + THROW
    if bytes(data[at:at + THROW_LEN]) != THROW_SOURCE:
        raise ValueError('Deadly Bomb: unexpected throw')
    data[at:at + THROW_LEN] = aimed_throw()
    if LANDING not in offsets:
        raise ValueError('Deadly Bomb: the landing is not an instruction')
    at = base + 0x34 + LANDING
    if bytes(data[at:at + len(LANDING_SOURCE)]) != LANDING_SOURCE:
        raise ValueError('Deadly Bomb: unexpected landing')
    data[at:at + len(LANDING_HIT)] = LANDING_HIT
    return bytes(data)


EFFECT_ID = 0x30        # the chunk's header word the loader compares with the effect id it asked for
DISC_CHUNKS = 122
OWN_EFFECTS = 'content/battle/own-effects.json'
DW2_EFFECTS = ('source-games', 'dw2', 'disc', 'AAA', '4.AAA', 'EFFECT')
DW3_SOURCE = ('source-games', 'dw2003')


def launch_table(chunk):
    """The origin table (10-byte rows to the type -1 row) the chunk's start script hands checkTechCompatibility."""
    start = struct.unpack_from('<i', chunk, 0)[0]
    pc = 0x34 + start + 12                  # after the start script's first spawn
    if struct.unpack_from('<H', chunk, pc - 12)[0] & 0xFF != 17 or struct.unpack_from('<H', chunk, pc)[0] & 0xFF != 12:
        raise ValueError('own effect: the chunk it stands for does not start with spawn, pusha table')
    at = 0x34 + struct.unpack_from('<h', chunk, pc + 2)[0]
    end = at
    while struct.unpack_from('<h', chunk, end)[0] >= 0:
        end += 10
    return bytes(chunk[at:end + 10])


def effect_objects(files):
    """[(DW2 slot, model path, anim path)] of an own effect's "cast" or "hit": ["M", "A"] (one object, slot 1) or
    [[slot, "M", "A"], ...] (every object of the DW2 technique, slot 0 above the head, 1 the launch point or mid
    height, 2 the feet)."""
    if files and isinstance(files[0], str):
        return [(1, files[0], files[1])]
    return [(int(slot), model, anim) for slot, model, anim in files]


def finisher_area_chunks(root):
    """Own chunks that play an area finisher (range 3) of content/finishers/imports.json: none while it is neutral
    (docs/mods/unique-finishers.md), since the chunk's targets are gameplay."""
    import glob, json
    with open(os.path.join(root, 'content', 'finishers', 'imports.json'), encoding='utf-8') as f:
        data = json.load(f)
    if data.get('neutral', True):
        return set()
    out = set()
    for e in data['finishers']:
        if 'buff' in e or e['move']['range'] != 3:
            continue
        for path in glob.glob(os.path.join(root, 'content', 'species', f'{e["species"]}-*.json')):
            with open(path, encoding='utf-8') as f:
                own = json.load(f).get('own_effect')
            if own and own.get('technique') == e['replaces']['name']:
                out.add(own['chunk'])
    return out


def own_effects(ctx, archive):
    """{chunk index: chunk} of the species' own effects (content/battle/own-effects.json; getSpeciesTechEffect)."""
    import json
    from tools import dw2effect, dw2efe
    with open(os.path.join(ctx.root, OWN_EFFECTS)) as f:
        spec = json.load(f)
    out = {}
    area = finisher_area_chunks(ctx.root)
    for key, e in spec.items():
        if key == 'note':
            continue
        like = bytes(archive[e['stands_for'] * CHUNK_SIZE:(e['stands_for'] + 1) * CHUNK_SIZE])
        if 'dw3' in e:
            out[int(key)], info = dw3_effect(ctx.path(*DW3_SOURCE), key, e, launch_table(like))
            ctx.log(f'own effect {key} {e["name"]}: ' + ', '.join(f'{k} {v}' for k, v in info.items()
                                                                  if k in ('chunk', 'objects', 'behaviour', 'kept')))
            continue
        lists = []
        for part in ('cast', 'hit'):
            objs = []
            for slot, *names in effect_objects(e[part]):
                paths = [ctx.path(*DW2_EFFECTS, *p.split('/')) for p in names]
                missing = [p for p in paths if not os.path.isfile(p)]
                if missing:
                    raise ValueError(f'own effect {key} {e["name"]}: source discs required: dw2 (missing '
                                     f'{missing[0]}); derive build --source-disc dw2=IMAGE')
                files = []
                for p in paths:
                    with open(p, 'rb') as f:
                        files.append(f.read())
                objs.append((slot, dw2effect.parse_effect(*files)))
            lists.append(objs)
        out[int(key)], info = dw2efe.convert_skill(lists[0], lists[1], launch_table(like), 0x100 + int(key),
                                                   e['scale'], hit_scale=e.get('hit_scale'),
                                                   area=e.get('area', False) or int(key) in area, n_hits=e.get('hits', 1))
        ctx.log(f'own effect {key} {e["name"]}: ' + ', '.join(f'{k} {v}' for k, v in info.items() if k != 'parts'))
    return out


def dw3_effect(games, key, e, origin_table):
    """(chunk, info) of an own effect converted from a DW2003 technique (tools/dw3efe.py): its "dw3" names the
    battle model, the technique's action slot and the 3D effects and sprites it spawns, read from the player's extracted
    DW2003 or Digimon World 3 disc (`games`: the build's source-games/dw2003). Gameplay stays the technique's it
    stands for: one target, one hit."""
    from tools.derive.importers import source_context
    d = e['dw3']
    disc = os.path.join(games, 'disc')
    with source_context(os.path.dirname(games)):
        from tools import dw3effect as X, dw3efe as E
        files = X.Files(disc)
        sprites = d.get('sprites', {})
        missing = [n for n in [d['model'] + '.BIN'] + [f'MEFT{n:04d}.BIN' for n in d['meft']] + X.sprite_files(sprites)
                   if n not in files.base]
        if missing:
            raise ValueError(f'own effect {key} {e["name"]}: source discs required: dw2003 (missing {missing[0]}); '
                             'derive build --source-disc dw2003=IMAGE')
        tech = X.model_scripts(files, d['model'])[d['slot']]
        return E.convert(files, X.EffectIds(d['meft'], sprites), tech, E.FIELD_SCALE, origin_table, 0x100 + int(key),
                         leave_out=[tuple(x) for x in d.get('leave_out', [])])


def append_own_effects(ctx, archive):
    data = bytearray(archive)
    if len(data) != DISC_CHUNKS * CHUNK_SIZE:
        raise ValueError(f'effect archive: {len(data):#x} bytes, expected {DISC_CHUNKS} chunks')
    for index, chunk in sorted(own_effects(ctx, archive).items()):
        if index * CHUNK_SIZE < len(data) or len(chunk) != CHUNK_SIZE:
            raise ValueError(f'own effect {index}: one chunk per index after the disc\'s, {CHUNK_SIZE:#x} bytes each')
        data += bytes(index * CHUNK_SIZE - len(data))       # indices no species plays: empty, never loaded
        chunk = bytearray(chunk)
        struct.pack_into('<i', chunk, EFFECT_ID, 0x100 + index)
        data += chunk
    return bytes(data)


def outputs(ctx):
    return [('effects/' + DISC_PATH, DISC_PATH)]


def build(ctx):
    with open(os.path.join(ctx.root, 'extracted', DISC_PATH), 'rb') as source:
        data = append_own_effects(ctx, aim_deadly_bomb(exclude_caster(source.read())))
    dest = ctx.path('effects', DISC_PATH)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'wb') as target:
        target.write(data)
