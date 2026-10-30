#!/usr/bin/env python3
"""Dumps or applies the "semantic" game state (money, time, partner,
position, inventory, triggers, pstats...) by reading/writing the emulator's
RAM through tools/dev/emulator.py (PCSX-Redux). It is the readable layer on top of
save states: a JSON that can be edited and applied again.

Usage:
  game_state.py dump [output.json]          reads RAM and writes the state as JSON (default: to the screen)
  game_state.py apply state.json             writes to RAM the fields present in the JSON
  game_state.py set FIELD=VALUE ...          shortcut: money=5000 hour=12 partner.stats.hp=999 ...
  game_state.py show [FIELD ...]             shows specific fields (or everything) as text
  game_state.py trigger N [0|1]              reads or changes a trigger (story flag)
  game_state.py pstat N [VALUE]              reads or changes a pstat (script variable; 1 = prosperity)
  game_state.py warp SCREEN [EXIT]           changes screen (ids in docs/reference/world.md)
  game_state.py move X Z                     places the player inside the screen
  game_state.py approach SLOT [DIST]         puts the player in front of NPC slot SLOT (entity 5+SLOT), facing it

Global option --syms NAME|DIR (or env DW_SYMS) names the build explicitly; otherwise the whole text
is compared with RAM, the choice is printed on stderr, and an ambiguous tie is refused.

The recipes require being in the world with control (script_paused = 1, tamer.state = 0).

Fields are defined by symbol (decomp/config/us/symbols.txt) and resolved
for the running executable: the original or the GCC build (tools/dev/symbols.py).
The structs are those in decomp/include/dw/ (params.h, entity.h, main.h,
script.h, clock.h, item.h).
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import json, os, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dwsyms

ROOT = _DEV_ROOT
EMU = os.path.join(ROOT, 'tools/dev/emulator.py')   # honors EMU_PORT from the environment

# ---- layouts (offset, struct format) ----------------------------------------
PARTNER_PARA_FIELDS = [('condition', 'I')] + [(n, 'h') for n in (
    'sleepyHour sleepyMinute wakeupHour wakeupMinute hoursAwakeDefault hoursAsleepDefault timeAwakeToday '
    'sicknessCounter missedSleepHours tirednessSleepTimer poopLevel unused1 unused2 virusBar poopingTimer '
    'tiredness subTiredness tirednessHungerTimer discipline happiness unused3 unused4 timesBeingSick '
    'sicknessTries areaEffectTimer sicknessTimer injuryTimer nextHungerHour energyLevel foodLevel '
    'starvationTimer weight refusedFavFood emptyStomachTimer remainingLifetime age trainBoostFlag '
    'trainBoostValue trainBoostTimer careMistakes battles evoTimer unused5 unused6 unused7 fishCaught '
    'unused8 unused9 unused10 upgradeHPcounter upgradeMPcounter upgradeOffCounter buggedUpgradeBrainsCounter '
    'upgradeDefenseCounter upgradeSpeedCounter upgradeBrainCounter unused11 sukaBackupHP sukaBackupMP '
    'sukaBackupOff sukaBackupDef sukaBackupSpeed sukaBackupBrain unused12').split()]
STATS_FIELDS = [('off', 'h'), ('def', 'h'), ('speed', 'h'), ('brain', 'h'), ('movesPrio', '4B'), ('moves', '4B'),
                ('hp', 'h'), ('mp', 'h'), ('currentHP', 'h'), ('currentMP', 'h'), ('unk1', 'h'),
                ('efeSubEffect', 'b'), ('isHit', 'b'), ('vabId', 'h'), ('chargeMode', 'B'), ('field7', 'B')]
CONDITION_BITS = ['sleepy', 'tired', 'hungry', 'poopy', 'unhappy', 'injured', 'sick']

# (name, RAM address, format or sublayout)
SCHEMA = {
    'main_state':      ('MAIN_STATE', 'I'),
    'game_state':      ('GAME_STATE', 'H'),
    'money':           ('MONEY', 'I'),
    'merit':           ('MERIT', 'H'),
    'hour':            ('HOUR', 'h'),
    'minute':          ('MINUTE', 'h'),
    'year':            ('YEAR', 'B'),
    'day':             ('DAY', 'h'),
    'playtime_hours':  ('PLAYTIME_HOURS', 'H'),
    'playtime_minutes': ('PLAYTIME_MINUTES', 'H'),
    'gametime_running': ('IS_GAMETIME_RUNNING', 'b'),
    'current_screen':  ('CURRENT_SCREEN', 'B'),
    'previous_screen': ('PREVIOUS_SCREEN', 'B'),
    'current_exit':    ('CURRENT_EXIT', 'B'),
    'tournaments_won': ('TOURNAMENTS_WON', 'H'),
    'tournaments_lost': ('TOURNAMENTS_LOST', 'H'),
    'partner.type':    ('PARTNER_ENTITY', 'I'),          # PARTNER_ENTITY.type (species)
    'partner.para':    ('PARTNER_PARA', PARTNER_PARA_FIELDS),
    'partner.stats':   ('PARTNER_ENTITY+0x38', STATS_FIELDS),  # PARTNER_ENTITY + 0x38
    'partner.learned_moves': ('PARTNER_ENTITY+0x58', '16B'),   # 128 bits, one per move
    'partner.name':    ('PARTNER_ENTITY+0x68', '20s'),
    'partner.lives':   ('PARTNER_ENTITY+0x7C', 'b'),
    'tamer.location':  ('TAMER_POSITION_DATA+0x78', '3i'),          # TAMER_POSITION_DATA + 0x78 (real position; write with 'move')
    'tamer.state':     ('TAMER_STATE', 'b'),           # TAMER_STATE (0 = free, 5 = changing screen)
    'script_paused':   ('IS_SCRIPT_PAUSED', 'i'),           # IS_SCRIPT_PAUSED: 1 = no script running (free control)
    'in_menu':         ('IS_IN_MENU', 'b'),           # IS_IN_MENU
    'target_map':      ('TARGET_MAP', 'B'),
    'prosperity':      ('SCRIPT_STATE+346', 'B'),           # pstat 1
    'partner.pos':     ('PARTNER_ENTITY+0x10', '3i'),
    'inventory.types': ('INVENTORY', '30B'),
    'inventory.amounts': ('INVENTORY+30', '30B'),
    'inventory.names': ('INVENTORY+60', '30B'),
    'inventory.size':  ('INVENTORY+90', 'B'),
    'script.cards':    ('SCRIPT_STATE+212', '33B'),
    'script.triggers': ('SCRIPT_STATE+245', '100B'),         # SCRIPT_STATE + 245: 800 triggers, bit n%8 of byte n/8
    'script.pstats':   ('SCRIPT_STATE+345', '256B'),
}

# Builds whose id carriers are 16-bit (docs/reference/ids.md):
# screens are int16 and the inventory types are int16 (-1 = empty).
WIDE_ID_BUILDS = {'mods'}
WIDE_SCHEMA = {
    'current_screen':  ('CURRENT_SCREEN', 'h'),
    'previous_screen': ('PREVIOUS_SCREEN', 'h'),
    'target_map':      ('TARGET_MAP', 'h'),
    'inventory.types': ('INVENTORY', '30h'),
    'inventory.amounts': ('INVENTORY+60', '30B'),
    'inventory.names': ('INVENTORY+90', '30B'),
    'inventory.size':  ('INVENTORY+120', 'B'),
}


def schema():
    """SCHEMA with the field widths of the running executable."""
    if BUILD is None: read_ram()
    return {**SCHEMA, **WIDE_SCHEMA} if dwsyms.wide_ids(BUILD) else SCHEMA


BUILD = None
SYMS_OPT = None      # --syms NAME|DIR (or the DW_SYMS environment variable)


def read_ram():
    global BUILD
    ram = subprocess.run([EMU, 'ramdump'], capture_output=True, check=True).stdout
    if BUILD is None: BUILD = dwsyms.detect_build(ram, SYMS_OPT) or 'orig'
    return ram


def A(expr):
    """Symbol address for the loaded executable."""
    if BUILD is None: read_ram()
    return dwsyms.resolve(expr, BUILD) if isinstance(expr, str) else expr


def ram_read(ram, addr, n):
    o = addr - 0x80000000; return ram[o:o + n]


def decode(ram, addr, fmt):
    addr = A(addr)
    if isinstance(fmt, list):
        out = {}; o = addr
        for name, f in fmt:
            v = struct.unpack_from('<' + f, ram, o - 0x80000000); out[name] = list(v) if len(v) > 1 else v[0]
            o += struct.calcsize('<' + f)
        return out
    v = struct.unpack_from('<' + fmt, ram, addr - 0x80000000)
    if fmt.endswith('s'): return v[0].split(b'\0')[0].decode('latin-1')
    return list(v) if len(v) > 1 else v[0]


def encode(addr, fmt, value):
    """Returns a list of (addr, bytes)."""
    addr = A(addr)
    if isinstance(fmt, list):
        out = []; o = addr
        for name, f in fmt:
            if name in value: out += encode(o, f, value[name])
            o += struct.calcsize('<' + f)
        return out
    if fmt.endswith('s'):
        n = int(fmt[:-1]); b = value.encode('latin-1')[:n].ljust(n, b'\0'); return [(addr, b)]
    vals = value if isinstance(value, list) else [value]
    return [(addr, struct.pack('<' + fmt, *vals))]


def poke(addr, data):
    subprocess.run([EMU, 'poke', f'{addr:#x}', data.hex()], check=True, capture_output=True)


def dump():
    ram = read_ram(); st = {}
    for key, (addr, fmt) in schema().items():
        d = st
        parts = key.split('.')
        for p in parts[:-1]: d = d.setdefault(p, {})
        d[parts[-1]] = decode(ram, addr, fmt)
    cond = st['partner']['para']['condition']
    st['partner']['condition_flags'] = [n for i, n in enumerate(CONDITION_BITS) if cond & (1 << i)]
    return st


def flatten(d, prefix='', full=False):
    """(dotted.key, value) pairs. With full=True it also descends into structs."""
    for k, v in d.items():
        if isinstance(v, dict) and (full or (prefix + k) not in SCHEMA): yield from flatten(v, prefix + k + '.', full)
        else: yield prefix + k, v


def apply(st):
    n = 0
    for key, value in flatten(st):
        if key not in schema(): continue
        addr, fmt = schema()[key]
        for a, b in encode(addr, fmt, value): poke(a, b); n += 1
    print(f'{n} writes')


def main():
    global SYMS_OPT
    a = sys.argv[1:]
    if '--syms' in a:
        i = a.index('--syms'); SYMS_OPT = a[i + 1]; del a[i:i + 2]
    if not a: sys.exit(__doc__)
    if a[0] == 'dump':
        st = dump(); s = json.dumps(st, indent=1)
        if len(a) > 1: open(a[1], 'w').write(s); print(a[1])
        else: print(s)
    elif a[0] == 'apply':
        apply(json.load(open(a[1])))
    elif a[0] == 'set':
        st = {}
        for kv in a[1:]:
            k, v = kv.split('=', 1); d = st; parts = k.split('.')
            for p in parts[:-1]: d = d.setdefault(p, {})
            d[parts[-1]] = v if SCHEMA.get(k, (0, ''))[1] == '20s' else json.loads(v)
        apply(st)
    elif a[0] == 'trigger':
        # trigger N [0|1]: reads or changes trigger N (800 bits from 0x801BDFCD)
        n = int(a[1], 0); addr = A('SCRIPT_STATE+245') + n // 8; bit = 1 << (n % 8)
        b = ram_read(read_ram(), addr, 1)[0]
        if len(a) > 2:
            b = (b | bit) if int(a[2]) else (b & ~bit); poke(addr, bytes([b]))
        print(f'trigger {n} = {1 if b & bit else 0}  (byte {addr:#x} = {b:#04x})')
    elif a[0] == 'pstat':
        n = int(a[1], 0); addr = A('SCRIPT_STATE+345') + n
        if len(a) > 2: poke(addr, bytes([int(a[2], 0) & 0xFF]))
        print(f'pstat {n} = {ram_read(read_ram(), addr, 1)[0]}' + ('' if n <= 34 else '  (not saved to the memory card)'))
    elif a[0] == 'warp':
        # warp SCREEN [EXIT]: changes screen like a door (docs/reference/world.md)
        screen, ex = int(a[1], 0), int(a[2], 0) if len(a) > 2 else 0
        poke(A('TAMER_SUB_STATE'), bytes([0]))     # left non-zero by a previous warp, it hangs the next one
        poke(A('TARGET_MAP'), struct.pack('<h', screen) if dwsyms.wide_ids(BUILD) else bytes([screen])); poke(A('CURRENT_EXIT'), bytes([ex])); poke(A('TAMER_STATE'), bytes([5, 0]))
        print(f'warp to screen {screen} through exit {ex}')
    elif a[0] == 'move':
        # move X Z: places the player (position, the Entity's <<15 copy and STORED_TAMER_POS)
        x, z = int(a[1], 0), int(a[2], 0)
        loc = struct.pack('<3i', x, 0, z); poke(A('TAMER_POSITION_DATA+0x78'), loc); poke(A('STORED_TAMER_POS'), loc)
        poke(A('TAMER_ENTITY+0x10'), struct.pack('<3i', x << 15, 0, z << 15)); print(f'player at x={x} z={z}')
    elif a[0] == 'approach':
        # approach SLOT [DIST]: puts the player DIST units (default 180) in front of the NPC
        # in placed-Digimon slot SLOT (entity 5+SLOT), facing it, ready to talk with CROSS
        import math
        slot, dist = int(a[1], 0), int(a[2], 0) if len(a) > 2 else 180
        ram = read_ram()
        pd = struct.unpack('<I', ram_read(ram, A('NPC_ENTITIES') + slot * 0x68 + 4, 4))[0]
        if not 0x80000000 < pd < 0x80800000: sys.exit(f'slot {slot}: no NPC')
        nx, _, nz = struct.unpack('<3i', ram_read(ram, pd + 0x78, 12))
        tx, _, tz = struct.unpack('<3i', ram_read(ram, A('TAMER_POSITION_DATA+0x78'), 12))
        d = math.hypot(tx - nx, tz - nz) or 1.0
        x, z = round(nx + (tx - nx) * dist / d), round(nz + (tz - nz) * dist / d)
        rot = round(math.atan2(nz - z, nx - x) * 4096 / (2 * math.pi)) & 0xFFF   # entityLookAtLocation: _atan(dz, dx)
        loc = struct.pack('<3i', x, 0, z); poke(A('TAMER_POSITION_DATA+0x78'), loc); poke(A('STORED_TAMER_POS'), loc)
        poke(A('TAMER_ENTITY+0x10'), struct.pack('<3i', x << 15, 0, z << 15))
        poke(A('TAMER_POSITION_DATA+0x72'), struct.pack('<h', rot))
        print(f'player at x={x} z={z} facing {rot} (NPC slot {slot} at x={nx} z={nz})')
    elif a[0] == 'show':
        st = dump(); flat = dict(flatten(st, full=True)); flat.update(dict(flatten(st)))
        for k in (a[1:] or sorted(flat)):
            print(f'{k:34} {flat.get(k)}')
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main()
