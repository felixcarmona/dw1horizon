"""One authority for engine box identities and safe authoring limits.

The binary format accepts 32 units; compiler-authored rows reserve one unit of
headroom. Packed rows reserve two bytes for their terminator. These are distinct
contracts, not interchangeable capacities.
"""
from dataclasses import dataclass
import re

BINARY_ROW_UNITS = 32
COMPILER_ROW_UNITS = 31
PACKED_ROW_BYTES = 62
ROW_PIXELS = 240
LAST_ROW_PIXELS = 228
UNPACKED_ENTRIES = {1237: (4, 5), 1238: (15,), 1240: (0, 1)}
UNPACKED_SCRIPTS = (102, 168, 209, 213)
UNPACKED_KEYS = re.compile(r'^(?:' + '|'.join(
    rf'm{section}\.u(?:' + '|'.join(map(str, entries)) + ')'
    for section, entries in UNPACKED_ENTRIES.items()) +
    r'|s(?:' + '|'.join(map(str, UNPACKED_SCRIPTS)) + r')\.sec10\.u\d+)$')


def unpacked_entry(script, section, entry):
    if section in UNPACKED_ENTRIES:
        return entry in UNPACKED_ENTRIES[section]
    return section == 10 and script in UNPACKED_SCRIPTS


def packed_key(key):
    return not (key and UNPACKED_KEYS.match(key))


@dataclass(frozen=True)
class BoxProfile:
    name: str
    packed: bool
    row_pixels: int
    last_row_pixels: int
    author_units: int
    row_bytes: int


PACKED_DIALOGUE = BoxProfile('packed-dialogue', True, ROW_PIXELS, LAST_ROW_PIXELS,
                            COMPILER_ROW_UNITS, PACKED_ROW_BYTES)
UNPACKED_WINDOW = BoxProfile('unpacked-window', False, ROW_PIXELS, ROW_PIXELS,
                           COMPILER_ROW_UNITS, PACKED_ROW_BYTES)
