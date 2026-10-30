"""Identify linker-generated PS-X header words from the build's ELF object.

Only R_MIPS_32 relocations are metadata addresses/sizes. Other nonzero header
bytes retain their conservative provenance; this does not clear game assets.
"""
from functools import lru_cache
from pathlib import Path
import struct


@lru_cache(maxsize=16)
def word_relocations(path, section):
    data = Path(path).read_bytes()
    if len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01' or struct.unpack_from('<H', data, 18)[0] != 8:
        raise ValueError('header object must be little-endian ELF32 MIPS')
    offset = struct.unpack_from('<I', data, 32)[0]
    stride, count, names_index = struct.unpack_from('<3H', data, 46)
    if stride < 40 or offset + stride * count > len(data) or names_index >= count:
        raise ValueError('invalid ELF section table')
    sections = [struct.unpack_from('<10I', data, offset + i * stride) for i in range(count)]
    strings = sections[names_index]
    names = data[strings[4]:strings[4] + strings[5]]

    def name(index):
        start = sections[index][0]
        return names[start:names.index(b'\0', start)].decode('ascii')

    out = []
    for rel in sections:
        if rel[1] != 9 or rel[7] >= count or name(rel[7]) != section:
            continue
        if rel[9] != 8 or rel[4] + rel[5] > len(data) or rel[5] % 8:
            raise ValueError('invalid ELF relocation table')
        for pos in range(rel[4], rel[4] + rel[5], 8):
            at, info = struct.unpack_from('<2I', data, pos)
            if info & 255 == 2:  # R_MIPS_32, the assembler's .word symbol
                if at + 4 > sections[rel[7]][5]:
                    raise ValueError('header relocation outside its section')
                out.append((at, at + 4))
    return tuple(out)


def generated(data, offset, ranges):
    """A header fragment containing only linked words and zero format padding."""
    return all(not value or any(a <= offset + i < b for a, b in ranges)
               for i, value in enumerate(data))
