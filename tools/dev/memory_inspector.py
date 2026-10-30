#!/usr/bin/env python3
"""Typed live memory inspector for Digimon World running in the emulator.

Reads the game's RAM from the running emulator (tools/dev/emulator.py) and decodes any
global variable by name with its exact C type, taken from the DWARF debug info
of the GCC-compiled object files of the running build (decomp/ for the original, build/decomp-*/ for mods).
Addresses are resolved for whichever executable is running (original or a GCC
build, see tools/dev/symbols.py); struct layouts are the same in all of them.

Usage:
  memory_inspector.py show EXPR [EXPR ...]        decode and print (structs, arrays, pointers)
  memory_inspector.py set EXPR=VALUE [...]        write a scalar (ints, or a string for char arrays)
  memory_inspector.py watch EXPR [...] [-i 0.5]   print whenever a value changes (Ctrl-C to stop)
  memory_inspector.py type NAME                   print a variable's or type's layout (offsets, sizes)
  memory_inspector.py vars [PATTERN]              list known variables (with address for this build)
  memory_inspector.py where ADDR                  which variable/field contains a RAM address
  memory_inspector.py find VALUE [--size 1|2|4]   search RAM for a value; remembers the candidates
  memory_inspector.py narrow VALUE|changed|same|up|down   filter the remembered candidates (Cheat Engine style)
  memory_inspector.py dump EXPR [LEN]             raw hex of a variable or address

EXPR: NAME, NAME.field, NAME[3].field.sub, 0x80134EB8 (raw address, u32),
      or NAME:TYPE to reinterpret (e.g. 0x801557A8:PartnerEntity).
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, glob, os, pickle, re, struct, subprocess, sys, time

try:
    import elftools  # noqa: F401  (pyelftools lives in the project venv)
except ImportError:
    _venv = os.path.join(_DEV_ROOT, '.venv/bin/python')
    if os.path.exists(_venv) and not os.environ.get('DW_MEM_REEXEC'):
        os.environ['DW_MEM_REEXEC'] = '1'
        os.execv(_venv, [_venv] + sys.argv)

ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dwsyms

# Types come from the objects of the running build: the mods branch widens some
# variables (docs/reference/ids.md), so the original game is decoded with the types of
# the unmodified decompilation.
OBJ_DIRS = {'orig': 'decomp', 'gcc': 'decomp', 'mods': 'build/decomp-mods'}
OBJ_SUB = 'build/us/psx/gcc/src/**/*.c.o'
CACHE = os.path.join(ROOT, 'build/mem-types-{}.pickle')


def obj_glob():
    try:
        b = build()
    except SystemExit:                       # no emulator running: the mods build's types
        b = 'mods'
    d = OBJ_DIRS.get(b, f'build/{b}')
    if not glob.glob(os.path.join(ROOT, d, OBJ_SUB), recursive=True):
        d = 'build/decomp-mods'
    return os.path.join(ROOT, d, OBJ_SUB), os.path.basename(d)
FIND_STATE = os.path.join(ROOT, 'build/mem-find.pickle')
EMU = os.path.join(ROOT, 'tools/dev/emulator.py')
RAM_BASE = 0x80000000


# ------------------------------------------------------------------ type index
def build_index():
    from elftools.elf.elffile import ELFFile
    pattern, tag = obj_glob()
    cache = CACHE.format(tag)
    objs = sorted(glob.glob(pattern, recursive=True))
    key = [(o, os.path.getmtime(o)) for o in objs]
    if os.path.exists(cache):
        try:
            c = pickle.load(open(cache, 'rb'))
            if c['key'] == key: return c['vars'], c['types']
        except Exception:
            pass
    vars_, types = {}, {}

    def conv(die, depth=0):
        if die is None: return {'k': 'void', 'size': 0}
        tag = die.tag; a = die.attributes
        name = a['DW_AT_name'].value.decode() if 'DW_AT_name' in a else None
        size = a['DW_AT_byte_size'].value if 'DW_AT_byte_size' in a else None
        tgt = die.get_DIE_from_attribute('DW_AT_type') if 'DW_AT_type' in a else None
        if tag == 'DW_TAG_base_type':
            enc = a['DW_AT_encoding'].value
            return {'k': 'base', 'name': name, 'size': size, 'signed': enc in (5, 6, 0xd), 'float': enc == 4,
                    'char': name == 'char'}   # only plain `char` arrays are text; uint8_t/int8_t are numbers
        if tag in ('DW_TAG_typedef', 'DW_TAG_const_type', 'DW_TAG_volatile_type'):
            t = conv(tgt, depth)
            if tag == 'DW_TAG_typedef' and name and t.get('k') in ('struct', 'union') and not t.get('name'):
                t = dict(t, name=name)
            if tag == 'DW_TAG_typedef' and name: types.setdefault(name, t)
            return t
        if tag == 'DW_TAG_pointer_type':
            tn = None
            if tgt is not None:
                d = tgt
                while d is not None and d.tag in ('DW_TAG_typedef', 'DW_TAG_const_type', 'DW_TAG_volatile_type') and 'DW_AT_name' not in d.attributes:
                    d = d.get_DIE_from_attribute('DW_AT_type') if 'DW_AT_type' in d.attributes else None
                if d is not None and 'DW_AT_name' in d.attributes: tn = d.attributes['DW_AT_name'].value.decode()
            return {'k': 'ptr', 'size': 4, 'to': tn}
        if tag in ('DW_TAG_structure_type', 'DW_TAG_union_type'):
            if depth > 12: return {'k': 'struct', 'name': name, 'size': size or 0, 'members': []}
            mem = []
            for ch in die.iter_children():
                if ch.tag != 'DW_TAG_member': continue
                ca = ch.attributes
                off = ca['DW_AT_data_member_location'].value if 'DW_AT_data_member_location' in ca else 0
                if isinstance(off, list): off = off[-1] if off else 0
                mt = conv(ch.get_DIE_from_attribute('DW_AT_type'), depth + 1)
                if 'DW_AT_bit_size' in ca: mt = dict(mt, bits=ca['DW_AT_bit_size'].value,
                                                     bitoff=ca.get('DW_AT_data_bit_offset').value if 'DW_AT_data_bit_offset' in ca else None)
                mem.append((ca['DW_AT_name'].value.decode() if 'DW_AT_name' in ca else f'_anon{len(mem)}', off, mt))
            t = {'k': 'struct' if tag == 'DW_TAG_structure_type' else 'union', 'name': name, 'size': size or 0, 'members': mem}
            if name: types.setdefault(name, t)
            return t
        if tag == 'DW_TAG_array_type':
            et = conv(tgt, depth); dims = []
            for ch in die.iter_children():
                if ch.tag == 'DW_TAG_subrange_type':
                    ca = ch.attributes
                    if 'DW_AT_upper_bound' in ca and isinstance(ca['DW_AT_upper_bound'].value, int):
                        dims.append(ca['DW_AT_upper_bound'].value + 1)
                    elif 'DW_AT_count' in ca: dims.append(ca['DW_AT_count'].value)
                    else: dims.append(0)
            for n in reversed(dims or [0]):
                et = {'k': 'array', 'n': n, 'elem': et, 'size': n * et.get('size', 0)}
            return et
        if tag == 'DW_TAG_enumeration_type':
            vals = {ch.attributes['DW_AT_const_value'].value: ch.attributes['DW_AT_name'].value.decode()
                    for ch in die.iter_children() if ch.tag == 'DW_TAG_enumerator'}
            return {'k': 'enum', 'name': name, 'size': size or 4, 'vals': vals}
        if tag == 'DW_TAG_subroutine_type': return {'k': 'func', 'size': 4}
        return {'k': 'void', 'size': size or 0}

    for o in objs:
        f = ELFFile(open(o, 'rb'))
        if not f.has_dwarf_info(): continue
        for cu in f.get_dwarf_info().iter_CUs():
            for die in cu.iter_DIEs():
                if die.tag != 'DW_TAG_variable' or 'DW_AT_name' not in die.attributes: continue
                if die.get_parent() is not None and die.get_parent().tag != 'DW_TAG_compile_unit': continue
                name = die.attributes['DW_AT_name'].value.decode()
                if 'DW_AT_type' not in die.attributes: continue
                t = conv(die.get_DIE_from_attribute('DW_AT_type'))
                old = vars_.get(name)
                # prefer the definition, and arrays with a known size over `extern T x[]`
                if old is None or (t.get('size', 0) > old.get('size', 0)):
                    vars_[name] = t
    pickle.dump({'key': key, 'vars': vars_, 'types': types}, open(cache, 'wb'))
    return vars_, types


# ------------------------------------------------------------------ RAM access
_ram = None


def ram(refresh=False):
    global _ram
    if _ram is None or refresh:
        r = subprocess.run([EMU, 'ramdump'], capture_output=True)
        if r.returncode: sys.exit(r.stderr.decode().strip() or 'emulator not running (tools/dev/emulator.py start)')
        _ram = r.stdout
    return _ram


_build = None


def build():
    global _build
    if _build is None: _build = dwsyms.detect_build(ram()) or 'orig'
    return _build


def addr_of(name):
    try:
        return dwsyms.resolve(name, build())
    except KeyError:
        return None


def poke(addr, data):
    subprocess.run([EMU, 'poke', f'{addr:#x}', data.hex()], check=True, capture_output=True)


# ------------------------------------------------------------------ expressions
TOKEN = re.compile(r'\.([A-Za-z_]\w*)|\[(\d+)\]')


def resolve_expr(expr, vars_, types):
    """-> (address, type)"""
    cast = None
    if ':' in expr: expr, cast = expr.split(':', 1)
    m = re.match(r'(0x[0-9A-Fa-f]+|[A-Za-z_]\w*)', expr)
    if not m: raise SystemExit(f'bad expression: {expr}')
    head, rest = m.group(1), expr[m.end():]
    if head.startswith('0x'):
        addr = int(head, 16); t = {'k': 'base', 'name': 'u32', 'size': 4, 'signed': False}
    else:
        addr = addr_of(head)
        if addr is None: raise SystemExit(f'unknown symbol {head} for build {build()}')
        t = vars_.get(head) or {'k': 'base', 'name': 'u32?', 'size': 4, 'signed': False}
    if cast:
        if cast not in types: raise SystemExit(f'unknown type {cast}')
        t = types[cast]
    pos = 0
    for mm in TOKEN.finditer(rest):
        if mm.start() != pos: raise SystemExit(f'bad expression near {rest[pos:]}')
        pos = mm.end()
        if mm.group(1):
            if t['k'] not in ('struct', 'union'): raise SystemExit(f'.{mm.group(1)}: not a struct')
            for n, off, mt in t['members']:
                if n == mm.group(1): addr += off; t = mt; break
            else: raise SystemExit(f'no field {mm.group(1)} in {t.get("name")}: ' + ', '.join(n for n, _, _ in t['members']))
        else:
            i = int(mm.group(2))
            if t['k'] == 'array': addr += i * t['elem']['size']; t = t['elem']
            elif t['k'] == 'ptr' and t.get('to') in types:
                p = struct.unpack_from('<I', ram(), addr - RAM_BASE)[0]; t = types[t['to']]; addr = p + i * t['size']
            else: raise SystemExit(f'[{i}]: not an array')
    if pos != len(rest): raise SystemExit(f'bad expression near {rest[pos:]}')
    return addr, t


# ------------------------------------------------------------------ decoding
def scalar(t, addr):
    r = ram(); o = addr - RAM_BASE
    if not (0 <= o < len(r)): return '<out of RAM>'
    size = t.get('size', 4)
    if t['k'] == 'ptr':
        v = struct.unpack_from('<I', r, o)[0]
        return f'{v:#010x}' + (f' -> {t["to"]}' if t.get('to') else '')
    if t.get('float'):
        return struct.unpack_from('<f' if size == 4 else '<d', r, o)[0]
    fmt = {1: 'b', 2: 'h', 4: 'i', 8: 'q'}.get(size, 'i')
    if not t.get('signed'): fmt = fmt.upper()
    v = struct.unpack_from('<' + fmt, r, o)[0]
    if 'bits' in t and t.get('bitoff') is not None: v = (v >> t['bitoff']) & ((1 << t['bits']) - 1)
    if t['k'] == 'enum': return f'{v} ({t["vals"].get(v, "?")})'
    return v


def is_charray(t):
    return t['k'] == 'array' and t['elem']['k'] == 'base' and t['elem'].get('char')


def fmt(t, addr, indent=0, name='', maxarr=64):
    pad = '  ' * indent; out = []
    if t['k'] in ('struct', 'union'):
        out.append(f'{pad}{name}: {t["k"]} {t.get("name") or ""} @ {addr:#010x} (size {t["size"]:#x})')
        for n, off, mt in t['members']:
            out += fmt(mt, addr + off, indent + 1, f'+{off:#05x} {n}', maxarr)
    elif is_charray(t):
        raw = ram()[addr - RAM_BASE: addr - RAM_BASE + t['n']]
        value = raw.split(b"\\0")[0].decode("latin-1")
        out.append(f'{pad}{name} = {value!r}')
    elif t['k'] == 'array':
        el = t['elem']
        if el['k'] in ('base', 'enum', 'ptr') and t['n'] <= maxarr:
            vals = [scalar(el, addr + i * el['size']) for i in range(t['n'])]
            out.append(f'{pad}{name} = [{", ".join(str(v) for v in vals)}]')
        else:
            out.append(f'{pad}{name}: array[{t["n"]}] of {el.get("name") or el["k"]} @ {addr:#010x}'
                       + (' (showing 8)' if t['n'] > 8 else ''))
            for i in range(min(t['n'], 8)):
                out += fmt(el, addr + i * el['size'], indent + 1, f'[{i}]', maxarr)
    else:
        out.append(f'{pad}{name} = {scalar(t, addr)}')
    return out


def layout(t, indent=0, name='', base=0):
    pad = '  ' * indent; out = []
    if t['k'] in ('struct', 'union'):
        out.append(f'{pad}{name} {t["k"]} {t.get("name") or ""} size {t["size"]:#x}')
        for n, off, mt in t['members']:
            if mt['k'] in ('struct', 'union') and indent < 3: out += layout(mt, indent + 1, f'+{base + off:#05x} {n}', base + off)
            else: out.append(f'{pad}  +{base + off:#05x} {n}: {tname(mt)}')
    else:
        out.append(f'{pad}{name}: {tname(t)}')
    return out


def tname(t):
    if t['k'] == 'array': return f'{tname(t["elem"])}[{t["n"]}]'
    if t['k'] == 'ptr': return f'{t.get("to") or "void"} *'
    return f'{t.get("name") or t["k"]} ({t.get("size", 0)} B)'


# ------------------------------------------------------------------ commands
def encode(t, value):
    if is_charray(t):
        b = value.encode('latin-1')[:t['n'] - 1]; return b + b'\0'
    size = t.get('size', 4)
    if t.get('float'): return struct.pack('<f', float(value))
    v = int(value, 0)
    return v.to_bytes(size, 'little', signed=v < 0)


def where(addr, vars_):
    best = None
    for n, t in vars_.items():
        a = addr_of(n)
        if a is not None and a <= addr < a + max(t.get('size', 1), 1):
            best = (n, a, t); break
    if not best: return f'{addr:#010x}: no known variable'
    n, a, t = best; path = n; off = addr - a
    while True:
        if t['k'] in ('struct', 'union'):
            for mn, mo, mt in t['members']:
                if mo <= off < mo + max(mt.get('size', 1), 1): path += f'.{mn}'; off -= mo; t = mt; break
            else: break
        elif t['k'] == 'array' and t['elem'].get('size'):
            i = off // t['elem']['size']; path += f'[{i}]'; off -= i * t['elem']['size']; t = t['elem']
        else: break
    return f'{addr:#010x}: {path}' + (f' +{off}' if off else '') + f'  ({tname(t)})'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd'); ap.add_argument('args', nargs='*')
    ap.add_argument('-i', type=float, default=0.5); ap.add_argument('--size', type=int, default=4)
    a = ap.parse_args()
    vars_, types = build_index()
    if a.cmd == 'show':
        for e in a.args:
            addr, t = resolve_expr(e, vars_, types); print('\n'.join(fmt(t, addr, 0, e)))
    elif a.cmd == 'set':
        for kv in a.args:
            e, v = kv.split('=', 1); addr, t = resolve_expr(e, vars_, types); poke(addr, encode(t, v))
            ram(True); print('\n'.join(fmt(t, addr, 0, e)))
    elif a.cmd == 'watch':
        prev = {}
        try:
            while True:
                ram(True)
                for e in a.args:
                    addr, t = resolve_expr(e, vars_, types); cur = '\n'.join(fmt(t, addr, 0, e))
                    if prev.get(e) != cur: print(time.strftime('%H:%M:%S'), cur); prev[e] = cur
                time.sleep(a.i)
        except KeyboardInterrupt:
            pass
    elif a.cmd == 'type':
        n = a.args[0]
        t = types.get(n) or vars_.get(n)
        if t is None: sys.exit(f'unknown type or variable {n}')
        print('\n'.join(layout(t, 0, n)))
    elif a.cmd == 'vars':
        pat = re.compile(a.args[0], re.I) if a.args else None
        for n in sorted(vars_):
            if pat and not pat.search(n): continue
            ad = addr_of(n); print(f'{ad:#010x}' if ad else '   (n/a)  ', f'{n:40} {tname(vars_[n])}')
    elif a.cmd == 'where':
        print(where(int(a.args[0], 0), vars_))
    elif a.cmd == 'dump':
        addr, t = resolve_expr(a.args[0], vars_, types)
        n = int(a.args[1], 0) if len(a.args) > 1 else max(t.get('size', 16), 16)
        b = ram()[addr - RAM_BASE: addr - RAM_BASE + n]
        for i in range(0, len(b), 16): print(f'{addr + i:08x}  {b[i:i + 16].hex(" ")}')
    elif a.cmd in ('find', 'narrow'):
        r = ram(); size = a.size; fmt_ = {1: 'B', 2: 'H', 4: 'I'}[size]
        vals = lambda buf: {o: struct.unpack_from('<' + fmt_, buf, o)[0] for o in range(0, len(buf) - size + 1, size)}
        if a.cmd == 'find':
            want = int(a.args[0], 0) if a.args else None
            cand = [o for o, v in vals(r).items() if want is None or v == want]
            state = {'size': size, 'cand': cand, 'snap': r}
        else:
            state = pickle.load(open(FIND_STATE, 'rb')); size = state['size']; fmt_ = {1: 'B', 2: 'H', 4: 'I'}[size]
            g = lambda buf, o: struct.unpack_from('<' + fmt_, buf, o)[0]
            how = a.args[0]; old = state['snap']
            test = {'changed': lambda o: g(r, o) != g(old, o), 'same': lambda o: g(r, o) == g(old, o),
                    'up': lambda o: g(r, o) > g(old, o), 'down': lambda o: g(r, o) < g(old, o)}.get(how)
            if test is None: want = int(how, 0); test = lambda o: g(r, o) == want
            state['cand'] = [o for o in state['cand'] if test(o)]; state['snap'] = r
        pickle.dump(state, open(FIND_STATE, 'wb'))
        print(f'{len(state["cand"])} candidates')
        for o in state['cand'][:20]:
            print('  ' + where(RAM_BASE + o, vars_), '=', struct.unpack_from('<' + {1: 'B', 2: 'H', 4: 'I'}[state['size']], r, o)[0])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
