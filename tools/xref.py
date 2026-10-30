#!/usr/bin/env python3
"""Who references what in a linked executable: the call and address graph of a build's ELF.

The Makefile links with --emit-relocs (patch 0098), so every relocation of the link is kept in the ELF;
each one is resolved here from the linked bytes (a jal's target, a lui/addiu pair, a .word), which
does not depend on the symbol the assembler chose. Sections: `.main` (the executable's code and data),
`.sbss`, `.bss`, and the overlays (`.BTL`, `.VS`, `.MOV`, ...; overlays share addresses, so a site in an
overlay that points into the load area is taken to point into that same overlay).

  xref.py refs ELF SYMBOL...     every site that references SYMBOL (section, function, kind)
  xref.py classes ELF            the executable's symbols that its own code cannot reach (from __start),
                                 grouped by the overlays that reach them: "NONE" is dead, ".VS" means
                                 only the VS overlay calls it (a candidate to move into it)
  xref.py check ELF              the references from the executable into an overlay (they are only
                                 valid while that overlay is loaded), the references between overlays,
                                 and the executable's symbols that only an overlay reaches; the
                                 validation recipe compares this with the expected output

the menu overlay patches.
"""
import bisect, collections, struct, sys

MAIN = ('.main', '.sbss', '.bss')
EXE_LO, EXE_HI = 0x80090800, 0x80200000


class Elf:
    def __init__(self, path):
        d = self.d = open(path, 'rb').read()
        assert d[:4] == b'\x7fELF' and d[4] == 1, 'not an ELF32 file'
        shoff, = struct.unpack_from('<I', d, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x2E)
        self.sh = []
        for i in range(shnum):
            name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack_from('<10I', d, shoff + i * shentsize)
            self.sh.append(dict(name=name, type=typ, flags=flags, addr=addr, off=off, size=size, link=link, info=info, entsize=entsize))
        strtab = self.sh[shstrndx]
        for s in self.sh:
            s['name'] = self.cstr(strtab['off'] + s['name'])
        self.byname = {s['name']: i for i, s in enumerate(self.sh)}
        self.syms = []
        sym = self.sh[self.byname['.symtab']]
        names = self.sh[sym['link']]
        for k in range(sym['size'] // 16):
            nm, value, size, info, other, shndx = struct.unpack_from('<IIIBBH', d, sym['off'] + k * 16)
            self.syms.append((self.cstr(names['off'] + nm), value, size, info & 0xF, shndx))

    def cstr(self, off):
        return self.d[off:self.d.index(b'\0', off)].decode('latin-1')

    def alloc_sections(self):
        return [s for s in self.sh if s['flags'] & 2 and s['size']]


def graph(path):
    """(size, kind, edges): size[(section, symbol)], kind 'func'/'data', edges[target] = {(site, how)}."""
    e = Elf(path)
    secname = {i: s['name'] for i, s in enumerate(e.sh)}
    by_sec = collections.defaultdict(list)
    size, kind = {}, {}
    for name, value, sz, typ, shndx in e.syms:
        if typ not in (0, 1, 2) or shndx == 0 or shndx >= 0xFF00 or not name or name.startswith(('.L', '$')) \
                or name.endswith('.NON_MATCHING'):
            continue
        sec = secname[shndx]
        if not (e.sh[shndx]['flags'] & 2):
            continue
        by_sec[sec].append((value, sz, name))
        key = (sec, name)
        size[key] = max(size.get(key, 0), sz)
        kind[key] = 'func' if typ == 2 else 'data'
    for v in by_sec.values():
        v.sort()
    overlays = sorted(k for k in by_sec if k not in MAIN)
    starts = {k: [x[0] for x in v] for k, v in by_sec.items()}

    def at(sec, addr):
        v = by_sec.get(sec)
        if not v:
            return None
        i = bisect.bisect_right(starts[sec], addr) - 1
        while i >= 0 and addr - v[i][0] < 0x40000:
            a, sz, n = v[i]
            if a <= addr < a + max(sz, 1):
                return (sec, n)
            i -= 1
        return None

    def target(site_sec, addr):
        if EXE_LO <= addr < EXE_HI:
            for sec in MAIN:
                r = at(sec, addr)
                if r:
                    return r
            return None
        if site_sec not in MAIN:
            return at(site_sec, addr)
        hits = [r for r in (at(sec, addr) for sec in overlays) if r]   # from the executable: every overlay there
        return ('?overlay', '%08x ' % addr + '|'.join(f'{a[1:]}:{b}' for a, b in hits))

    edges = collections.defaultdict(set)
    for rs in e.sh:
        if rs['type'] != 9 or not rs['name'].startswith('.rel'):   # SHT_REL
            continue
        tsec = rs['name'][4:]
        if tsec not in e.byname:
            continue
        t = e.sh[e.byname[tsec]]
        if not (t['flags'] & 2) or t['type'] == 8:                  # alloc, not NOBITS
            continue
        symtab = e.sh[rs['link']]
        hi = None
        for k in range(rs['size'] // 8):
            off, info = struct.unpack_from('<II', e.d, rs['off'] + k * 8)
            typ = info & 0xFF
            w, = struct.unpack_from('<I', e.d, t['off'] + off - t['addr'])
            if typ == 2:      # R_MIPS_32
                a, how = w, 'word'
            elif typ == 4:    # R_MIPS_26
                a, how = (off & 0xF0000000) | ((w & 0x3FFFFFF) << 2), 'call'
            elif typ == 5:    # R_MIPS_HI16: paired with the LO16 relocations that follow
                hi = w & 0xFFFF
                continue
            elif typ == 6:    # R_MIPS_LO16
                if hi is None:
                    continue
                lo = w & 0xFFFF
                a, how = ((hi << 16) + (lo - 0x10000 if lo & 0x8000 else lo)) & 0xFFFFFFFF, 'addr'
            elif typ == 7:    # R_MIPS_GPREL16: the symbol's own address (small data)
                si = info >> 8
                _, a, _, _, _ = struct.unpack_from('<IIIBBH', e.d, symtab['off'] + si * 16)[0:5]
                how = 'gp'
            else:
                continue
            site = at(tsec, off) or (tsec, '?%08x' % off)
            tgt = target(tsec, a)
            if tgt and tgt != site:
                edges[tgt].add((site, how))
    return size, kind, edges


def reach(size, edges):
    """The executable's symbols reachable from __start through the executable's own code and data."""
    refs = collections.defaultdict(set)
    for t, sites in edges.items():
        for s, _ in sites:
            refs[s].add(t)
    seen = {('.main', '__start')}
    st = list(seen)
    while st:
        x = st.pop()
        for t in refs.get(x, ()):
            if t[0] in MAIN and t not in seen:
                seen.add(t)
                st.append(t)
    by = collections.defaultdict(set)
    for ov in {k[0] for k in size if k[0] not in MAIN}:
        st = [k for k in size if k[0] == ov]
        got = set()
        while st:
            x = st.pop()
            for t in refs.get(x, ()):
                if t[0] in MAIN and t not in seen and t not in got:
                    got.add(t)
                    st.append(t)
        for t in got:
            by[t].add(ov)
    return seen, by


def cmd_refs(path, names):
    size, kind, edges = graph(path)
    for n in names:
        keys = [k for k in size if k[1] == n]
        if not keys:
            print(f'{n}: no such symbol')
        for k in keys:
            print(f'{k[1]} ({k[0]}, {kind[k]}, {size[k]} bytes):')
            for (sec, fn), how in sorted(edges.get(k, ())):
                print(f'    {sec:6} {fn:40} {how}')


def classes(path):
    size, kind, edges = graph(path)
    seen, by = reach(size, edges)
    out = collections.defaultdict(list)
    for k in size:
        if k[0] in MAIN and k not in seen:
            out[','.join(sorted(by.get(k, {'NONE'})))].append((size[k], k[1], kind[k]))
    return out


def cmd_classes(path, detail):
    out = classes(path)
    for key, items in sorted(out.items(), key=lambda x: -sum(i[0] for i in x[1])):
        f = sum(s for s, _, k in items if k == 'func')
        print(f'{f:7d} bytes of code, {sum(s for s, _, k in items) - f:6d} of data   {key}')
        if detail:
            for s, n, k in sorted(items, reverse=True):
                print(f'          {s:6d} {k} {n}')


def cmd_check(path):
    size, kind, edges = graph(path)
    into, cross = [], []
    for t, sites in edges.items():
        for (sec, fn), how in sites:
            if sec in MAIN and t[0] not in MAIN:
                into.append(f'{fn} -> {t[0]} {t[1]} ({how})')
            elif sec not in MAIN and t[0] not in MAIN and t[0] != '?overlay' and sec != t[0]:
                cross.append(f'{sec} {fn} -> {t[0]} {t[1]} ({how})')
    print(f'references from the executable into an overlay: {len(into)}')
    for x in sorted(into):
        print('    ' + x)
    print(f'references between overlays: {len(cross)}')
    for x in sorted(cross):
        print('    ' + x)
    out = classes(path)
    print('code of the executable that only overlays reach (bytes, overlays):')
    for key, items in sorted(out.items(), key=lambda x: -sum(i[0] for i in x[1])):
        f = sum(s for s, _, k in items if k == 'func')
        if f:
            print(f'    {f:6d} {key}')


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == 'refs':
        cmd_refs(a[1], a[2:])
    elif len(a) >= 2 and a[0] == 'classes':
        cmd_classes(a[1], '-v' in a)
    elif len(a) == 2 and a[0] == 'check':
        cmd_check(a[1])
    else:
        print(__doc__)
        sys.exit(2)
