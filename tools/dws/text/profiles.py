"""One authority for engine box identities and safe authoring limits.

The binary format accepts 32 units; compiler-authored rows reserve one unit of
headroom. Packed rows reserve two bytes for their terminator. These are distinct
contracts, not interchangeable capacities.
"""
from dataclasses import dataclass
import pathlib
import re

BINARY_ROW_UNITS = 32
COMPILER_ROW_UNITS = 31
PACKED_ROW_BYTES = 62
ROW_PIXELS = 240
LAST_ROW_PIXELS = 228
# The dialogue box is four rows on each of two pages (setupDialogueBox). showTextbox gives a speaker's name the first row,
# so a named speaker has three: a fourth lands on the other page's first row, where it is lost or replaces the name.
NAMED_PAGE_ROWS = 3
NAMELESS_PAGE_ROWS = 4
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


STATEMENT = re.compile(r'\bsay\(([\w()]+)((?:,\s*text\("[^"]+"\))+)\)|\b(?:choice|set_dialog_owner)\(([\w()]+)\)|'
                       r'\bshow_textbox\(text\("([^"]+)"\)\)|\bset_textbox_size\(|^\s*(?:on\s|section\()', re.M)


def named_keys(root):
    """The text keys of story/base shown in a box with a name row: `say(who, text("key"), ...)` by anyone but the narrator,
    and `show_textbox(text("key"))` after such a statement in the same event."""
    keys = set()
    for path in (pathlib.Path(root) / 'story/base').rglob('*.dws'):
        owner = None
        for m in STATEMENT.finditer(path.read_text(encoding='utf-8')):
            who = m[1] or m[3]
            if who or not m[4]:
                owner = who
            said = re.findall(r'text\("([^"]+)"\)', m[2]) if m[1] else [m[4]] if m[4] else []
            if owner not in (None, 'narrator', '255'):
                keys.update(said)
    return keys


def narrator_keys(root):
    """Direct narrator say() keys wrap to four rows; show_textbox() wraps to three."""
    return {key for path in (pathlib.Path(root) / 'story/base').rglob('*.dws')
            for match in STATEMENT.finditer(path.read_text(encoding='utf-8'))
            if match[1] in ('narrator', '255')
            for key in re.findall(r'text\("([^"]+)"\)', match[2])}


def tall_pages(script):
    """[(owner, rows)] of the pages of a script's assembly text with more rows than the box shows under their speaker.
    The owner is followed in text order within a section; a box of SET_TEXTBOX_SIZE has no name row."""
    tall, owner = [], None
    lines = script.split('\n')
    for i, line in enumerate(lines):
        words = line.split()
        if not words:
            continue
        if words[0] == 'SET_DIALOG_OWNER':
            owner = words[1]
        elif words[0] in ('SET_TEXTBOX_SIZE', 'END_SECTION'):
            owner = None
        elif words[0] == 'SHOW_TEXTBOX' and owner not in (None, '255'):
            rows = []
            for row in lines[i + 1:]:
                if not row.strip().startswith('"'):
                    break
                rows.append(row.strip().strip('"'))
            if len(rows) > NAMED_PAGE_ROWS:
                tall.append((owner, rows))
    return tall


def textbox_overflows(script, script_id=None):
    """Physical rows exceeding the active box in compiler output.

    Check named, narrator and explicitly sized boxes, including embedded row
    breaks. Tournament section 10 stores UI arrays using SHOW_TEXTBOX; those
    entries are data, like selection tables, rather than dialogue pages.
    """
    limit = NAMELESS_PAGE_ROWS
    lines = script.splitlines()
    sections = {label: int(number) for number, label in
                re.findall(r'^\.section\s+(\d+)\s+(\w+)', script, re.M)}
    section = None
    for i, line in enumerate(lines):
        words = line.split()
        if not words:
            continue
        if line.strip().removesuffix(':') in sections:
            section = sections[line.strip().removesuffix(':')]
        if words[0] == 'SET_DIALOG_OWNER':
            limit = NAMELESS_PAGE_ROWS if words[1].lower() in ('255', '0xff') else NAMED_PAGE_ROWS
        elif words[0] == 'SET_TEXTBOX_SIZE':
            limit = int(line.split(',')[-1], 0)
        elif words[0] == 'END_SECTION':
            limit = NAMELESS_PAGE_ROWS
        elif words[0] == 'SHOW_TEXTBOX' and not (script_id in UNPACKED_SCRIPTS and section == 10):
            rows = []
            for row in lines[i + 1:]:
                if not row.strip().startswith('"'):
                    break
                rows.extend(re.split(r'\{br\}', row.strip().strip('"'), flags=re.I))
            if len(rows) > limit:
                yield limit, rows


def header_row(row):
    """A coloured name written as a page's first row: the page of a nameless box that shows its speaker itself."""
    return re.match(r'^\{color [67]\}.*?\{color 1\}[.!?]*$', row.strip()) is not None


def merged_name_rows(names, pages):
    """The rows of `pages` (a value as it is shown) that hold one of `names` (a speaker's name rows, `header_row`, as the
    value wrote them) anywhere but as the whole first row of a page: a name run into the dialogue text, or left as a
    page's second row. -> [row...]"""
    names = {n.strip() for n in names if n.strip()}
    return [r for p in pages for i, r in enumerate(p)
            if any(n in r for n in names) and (i or r.strip() not in names)]


def maphead_page_too_tall(key, page):
    """A line of MAPHEAD's shared tables: the C code passes its owner, usually a shopkeeper's name, so only a page that
    writes its own name row may use the fourth row."""
    return re.match(r'^m\d+\.u\d+$', key) is not None and len(page) > NAMED_PAGE_ROWS and not header_row(page[0])


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
