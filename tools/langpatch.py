#!/usr/bin/env python3
"""The language patch of a two-language build (docs/mods/language.md).

The executable is built twice, once per language, with every string padded to the longer of its two texts
(decomp/tools/gen_text.py, TEXT_BANK_PAD): both builds lay out every symbol at the same address and differ only in the
bytes of their strings and language tables. This tool checks that (the same symbols at the same addresses, no
difference in code) and writes what the game writes into RAM to change language:

  langpatch.py exe BASE.elf BASE.EXE OTHER.elf OTHER.EXE -o LANGxx.BIN    the runs of OTHER that differ from BASE
  langpatch.py overlay BASE.BIN OTHER.BIN                                   checks an overlay pair (size; the bytes may differ)

LANGxx.BIN: "DWLP", u32 run count, then per run u32 address, u32 length, the bytes, padded to 4.
"""
import argparse
import struct
import sys


def elf_symbols(path):
    """-> {name: (address, size, kind)} of an ELF32 little-endian file's .symtab; kind 'func' / 'object' / 'other'"""
    d = open(path, 'rb').read()
    if d[:4] != b'\x7fELF':
        sys.exit(f'{path}: not an ELF file')
    shoff, = struct.unpack_from('<I', d, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x2E)
    secs = [struct.unpack_from('<IIIIIIIIII', d, shoff + i * shentsize) for i in range(shnum)]
    syms = {}
    for s in secs:
        if s[1] != 2:                       # SHT_SYMTAB
            continue
        strtab = secs[s[6]]
        for off in range(s[4], s[4] + s[5], 16):
            name, value, size, info, _, shndx = struct.unpack_from('<IIIBBH', d, off)
            if not name or shndx == 0:
                continue
            end = d.index(b'\0', strtab[4] + name)
            n = d[strtab[4] + name:end].decode('latin-1')
            kind = {2: 'func', 1: 'object'}.get(info & 0xF, 'other')
            syms[n] = (value, size, kind)
    return syms


def exe_image(path):
    """-> (load address, bytes) of a PS-X EXE"""
    d = open(path, 'rb').read()
    if d[:8] != b'PS-X EXE':
        sys.exit(f'{path}: not a PS-X EXE')
    t_addr, t_size = struct.unpack_from('<II', d, 0x18)
    return t_addr, d[0x800:0x800 + t_size]


def runs(a, b, base, gap=8):
    """-> [(address, bytes)]: the spans where b differs from a (spans closer than gap joined)"""
    out = []
    i, n = 0, len(a)
    while i < n:
        if a[i] == b[i]:
            i += 1
            continue
        j = i
        k = i
        while k < n and k - j <= gap:
            if a[k] != b[k]:
                j = k
            k += 1
        out.append((base + i, b[i:j + 1]))
        i = j + 1
    return out


def check_layout(sa, sb):
    diff = [n for n in set(sa) | set(sb) if sa.get(n, (None,))[:2] != sb.get(n, (None,))[:2]]
    if diff:
        sys.exit(f'the two builds lay out {len(diff)} symbols differently, e.g. ' + ', '.join(sorted(diff)[:8]) +
                 ' (a string the padding missed: decomp/tools/gen_text.py)')


def check_code(sa, spans):
    funcs = sorted((v, v + max(s, 1), n) for n, (v, s, k) in sa.items() if k == 'func')
    bad = []
    for addr, data in spans:
        for lo, hi, n in funcs:
            if lo < addr + len(data) and addr < hi:
                bad.append(f'{n} 0x{addr:08X}')
                break
    if bad:
        sys.exit('the two builds differ in code: ' + ', '.join(bad[:8]))


def write_patch(spans, out):
    body = bytearray(b'DWLP' + struct.pack('<I', len(spans)))
    for addr, data in spans:
        body += struct.pack('<II', addr, len(data)) + data + b'\0' * (-len(data) % 4)
    with open(out, 'wb') as f:
        f.write(body)
    return len(body)


def all_language_runs(images, base, gap=8):
    """Target spans over the UNION of all differences, for arbitrary A -> B switches.

    A byte equal in English and Spanish can still differ in Portuguese. Every target
    must write it back; pairwise patches relative to English would leave it stale.
    """
    if not images or any(len(im) != len(images[0]) for im in images):
        raise ValueError('language executable images must have the same size')
    reference = images[0]
    changed = bytearray(reference)
    for i, byte in enumerate(reference):
        if any(im[i] != byte for im in images[1:]):
            changed[i] ^= 0xFF
    spans = runs(reference, changed, base, gap)
    return [[(addr, im[addr - base:addr - base + len(data)]) for addr, data in spans] for im in images]


def multi(specs, out):
    try:
        from tools.languages import PATCHES
    except ModuleNotFoundError:
        from languages import PATCHES
    import os
    langs, symbols, images, bases = [], [], [], []
    for spec in specs:
        lang, elf, exe = spec.split(':', 2)
        if lang not in PATCHES or lang in langs:
            sys.exit(f'unknown or duplicate language: {lang}')
        langs.append(lang)
        symbols.append(elf_symbols(elf))
        base, image = exe_image(exe)
        bases.append(base)
        images.append(image)
    if len(langs) < 2 or len(set(bases)) != 1:
        sys.exit('need at least two language images with the same load address')
    for syms in symbols[1:]:
        check_layout(symbols[0], syms)
    targets = all_language_runs(images, bases[0])
    os.makedirs(out, exist_ok=True)
    for lang, spans in zip(langs, targets):
        check_code(symbols[0], spans)
        path = os.path.join(out, PATCHES[lang])
        size = write_patch(spans, path)
        print(f'{path}: {len(spans)} shared runs, {size} bytes')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('exe')
    e.add_argument('base_elf'); e.add_argument('base_exe'); e.add_argument('other_elf'); e.add_argument('other_exe')
    e.add_argument('-o', required=True)
    o = sub.add_parser('overlay')
    o.add_argument('base'); o.add_argument('other')
    m = sub.add_parser('multi')
    m.add_argument('--out', required=True)
    m.add_argument('specs', nargs='+', metavar='LANG:ELF:EXE')
    a = ap.parse_args()
    if a.cmd == 'multi':
        multi(a.specs, a.out)
        return
    if a.cmd == 'exe':
        sa, sb = elf_symbols(a.base_elf), elf_symbols(a.other_elf)
        check_layout(sa, sb)
        ba, ia = exe_image(a.base_exe)
        bb, ib = exe_image(a.other_exe)
        if ba != bb or len(ia) != len(ib):
            sys.exit('the two executables have another load address or size')
        spans = runs(ia, ib, ba)
        check_code(sa, spans)
        size = write_patch(spans, a.o)
        print(f'{a.o}: {len(spans)} runs, {sum(len(d) for _, d in spans)} bytes differ, {size} bytes')
    else:
        x, y = open(a.base, 'rb').read(), open(a.other, 'rb').read()
        if len(x) != len(y):
            sys.exit(f'{a.other}: {len(y)} bytes, {a.base} {len(x)}: the overlay pair is laid out differently')
        print(f'{a.other}: {sum(p != q for p, q in zip(x, y))} bytes differ')


if __name__ == '__main__':
    main()
