#!/usr/bin/env python3
"""Disassembler and assembler for the script bytecode of Digimon World (USA).

Usage:
  tools/dws/bytecode/__main__.py dis  extracted/SCN/DG.SCN      DIR/   one .scn.txt per entry + index
  tools/dws/bytecode/__main__.py dis  extracted/SCN/MAPHEAD.SCN DIR/   DIR/maphead.scn.txt
  tools/dws/bytecode/__main__.py asm  DIR/  out/DG.SCN                rebuilds the container (DIR/dg.scn.lst)
  tools/dws/bytecode/__main__.py asm  DIR/maphead.scn.txt out/MAPHEAD.SCN      a single script
  tools/dws/bytecode/__main__.py check extracted/SCN/DG.SCN [extracted/SCN/MAPHEAD.SCN]
                                                 disassembles, assembles and compares byte by byte
  tools/dws/bytecode/__main__.py libres extracted/SCN/DG.SCN extracted/SCN/MAPHEAD.SCN
                                                 triggers and pstats used by no script and not by the C code

asm options: --strip-accents (á→a, ñ→n, drops ¿¡), --font original (reject the
characters only the mod executables have: á é ñ ¿ ¡ ç... ( ) & % / …), --font-glyphs N
(the mod executable has only the first N extra glyphs: one built before the others were
added; the rest are rejected), --compact (drops the garbage
tails and shrinks entry 0, which the game never reads), --grow (lets DG.SCN be larger
than the original when nothing else fits: the disc must be built with build-disc.py
--relayout; tools/dws passes it for the mod executables; docs/mods/dws.md).
Ids above 255 select the wide opcodes 80-8B and IF forms (mod executable only, see
"Wide opcodes" in docs/mods/dws.md); --wide uses them always.

Script format (DG.SCN entry N, or MAPHEAD.SCN): u16 header size, (u16 section,
u16 offset) pairs up to a u16 0xFFFF, then bytecode. All offsets are relative
to the start of the script. The length of each opcode comes from the
interpreter (decomp/src/main/script_interp.c, script_textbox.c and
script_value.c); the reference is docs/mods/dws.md.

Directives: `.section ID LABEL`, `.tail FILE`, `.byte`, `.align`, `.script`.
"""
import argparse, csv, os, re, struct, sys, tempfile, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
def source_digest():
    """Identity of the codec, box policy and glyph data used by cached disassembly."""
    import hashlib
    from pathlib import Path
    codec = Path(__file__).resolve()
    root = Path(ROOT)
    paths = [codec, codec.parents[1] / 'text/profiles.py', root / 'tools/fontgen.py']
    paths += sorted(p for p in (root / 'tools/font').rglob('*') if p.is_file())
    digest = hashlib.sha1()
    for path in paths:
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b'\0')
            digest.update(path.read_bytes())
    return digest.hexdigest()


SECTOR = 0x800
MAP_SCRIPT_MAX = 0x4000      # MAP_SCRIPT_BUFFER: max. 8 sectors per entry (SCRIPT_STATE follows it)
MAPHEAD_MAX = 0x61A8         # MAPHEAD_SCRIPT_BUFFER; anything past this is overwritten by SCRIPT_OFFSET_TABLE


class BytecodeError(Exception):
    pass


# --------------------------------------------------------------------------
# Opcodes. Field types:
#   _ padding (byte the interpreter skips; must be 0)   u8 u16 s16 s32
#   p pstat (u8, written pN)   t trigger (u16)   l label (u16, offset within the script)
#   e entity (u8: TAMER = 0xFD, PARTNER = 0xFC, or a number)   c comparison (u8: == != >= <= > <)
#   i item (u8)  d Digimon type (u8)  m screen (u8)  v technique (u8)
#   s script (u16)  S section (u16)  M screen (u16)
#   wide ids (u16, mod executable): d16 Digimon  m16 screen  i16 item  v16 technique  k16 card
#   w wide register (u8, written wN)
# The special opcodes (10, 18, 19, 1A, 6B, 93) are handled separately.
OPS = {
    0x11: ('UNUSED_11', ''), 0x12: ('UNUSED_12', ''),
    0x13: ('JUMP_AND_LINK', '_ l'),
    0x14: ('JUMP_TO_FILE_AND_LINK', '_ s S'),
    0x15: ('JUMP_RETURN', '_'),
    0x16: ('JUMP_TO', '_ l'),
    0x17: ('JUMP_TO_FILE', '_ s S'),
    0x1B: ('SET_DIALOG_OWNER', 'e'),
    0x1C: ('SET_TRIGGER', '_ t'), 0x1D: ('UNSET_TRIGGER', '_ t'),
    0x1E: ('SET_PSTAT', '_ p u8'), 0x1F: ('ADD_TO_PSTAT', '_ p u8'), 0x20: ('REDUCE_PSTAT', '_ p u8'),
    0x21: ('STORE_MAP_ID', 'p'), 0x22: ('STORE_DIGIMON_TYPE', 'p'),
    0x23: ('SET_INVENTORY_SIZE', 'u8'), 0x24: ('STORE_RANDOM', '_ p u8'), 0x25: ('STORE_DATE', 'p'),
    0x26: ('SET_TEXTBOX_SIZE', 'e u8 u8'), 0x27: ('FADEOUT_HUD', 'u8'),
    0x28: ('GIVE_ITEM', '_ i u8'), 0x29: ('REMOVE_ITEM', '_ i u8'),
    0x2A: ('ADD_MONEY', '_ s32'), 0x2B: ('REDUCE_MONEY', '_ s32'),
    0x2C: ('COMPARE_DATE', 'p t c u8 u8 u8 u8 _'),
    0x2D: ('LEARN_MOVE', 'v'), 0x2E: ('UNUSED_2E', 'u8'),
    0x2F: ('GIVE_CARD', 'u8'), 0x30: ('TAKE_CARD', 'u8'),
    0x31: ('SET_MERIT', '_ u16'), 0x32: ('ADD_MERIT', '_ u16'), 0x33: ('REDUCE_MERIT', '_ u16'),
    0x34: ('SET_STAT', 'u8 u16'), 0x35: ('ADD_STAT', 'u8 u16'), 0x36: ('REDUCE_STAT', 'u8 u16'),
    0x37: ('ADVANCE_TO_DATE_AT', 'p'),
    0x38: ('ADD_MINUTES_TO_DATE_AT', 'p s32'), 0x39: ('ADD_MINUTES_TO_DATE_AT_2', 'p s32'),
    0x3A: ('UNUSED_3A', '_ u8 u8'), 0x3B: ('UNUSED_3B', '_ u8 u8'), 0x3C: ('UNUSED_3C', '_ u8 u8'),
    0x3D: ('UNUSED_3D', 'u8'), 0x3E: ('UNUSED_3E', 'u8'),
    0x3F: ('STORE_DIGIMON_VALUE', '_ p p'),
    0x46: ('LOAD_DIGIMON', 'd'), 0x47: ('SET_DIGIMON', 'd u8 u8'),
    0x48: ('UNLOAD_ENTITY', 'e'), 0x49: ('CALL_DIGIMON_ROUTINE', 'u8'), 0x4A: ('WAIT_FOR_ENTITY', 'e'),
    0x4B: ('WARP_TO', 'm u8 u8'),
    0x4C: ('ENTITY_LOOK_AT_ENTITY', '_ e e'),
    0x4D: ('ENTITY_SET_ROTATION', 'e s16'),
    0x4E: ('ENTITY_WALK_TO', 'e s16 s16 u8 u8'),
    0x4F: ('MOVE_CAMERA_TO', 'u8 s16 s16'),
    0x50: ('MOVE_CAMERA_TO_ENTITY', '_ e u8'),
    0x51: ('ENTITY_WALK_TO_ENTITY', 'e u8 e'),
    0x52: ('ENTITY_WALK_TO_WITH_CAMERA', 'e s16 s16 u8 u8'),
    0x53: ('ENTITY_WALK_TO_ENTITY_WITH_CAMERA', 'e u8 e'),
    0x54: ('RESET_ENTITY_ORIGIN', 'e'),
    0x55: ('SET_TEXTBOX_ORIGIN', '_ s16 s16 s16'),
    0x56: ('PLAY_ANIMATION', '_ e u8'),
    0x57: ('SET_OBJ_VISIBILITY', '_ u8 u8'),
    0x58: ('TELEPORT', 'p'),
    0x5A: ('PLAY_SOUND', '_ u8 u8'),
    0x5B: ('UNUSED_5B', 'u8'), 0x5C: ('UNUSED_5C', 'u8'),
    0x5D: ('SET_BGM', 'u8'), 0x5E: ('STOP_BGM', 'u8'), 0x5F: ('UNUSED_5F', 'u8'),
    0x64: ('CALL_ROUTINE', 'u8'), 0x65: ('REMOVE_CONDITION', 'u8'), 0x66: ('START_BATTLE', 'u8'),
    0x67: ('DELAY', '_ u16'), 0x68: ('SET_TEXTBOX_MODE', '_ u8 u8'),
    0x69: ('DEAL_DAMAGE', 'p'), 0x6A: ('SET_AUTOTALK', '_ e u8'),
    0x6C: ('ENTITY_MOVE_TO', 'e s16 s16 u8 u8'),
    0x6D: ('ENTITY_MOVE_TO_ENTITY', 'e e u8'),
    0x6E: ('ENTITY_MOVE_TO_WITH_CAMERA', 'e s16 s16 u8 u8'),
    0x6F: ('ENTITY_MOVE_TO_ENTITY_WITH_CAMERA', 'e e u8'),
    0x70: ('ROTATE_3D_OBJECT', 'u8 u8 u8'),
    0x71: ('MOVE_OBJECT_TO', 'u8 u8 u8 u8 _ s16 s16'),   # slot, object, speed, steps (s8), _, x, z
    0x72: ('ENTITY_MOVE_TO_AXIS', 'e s16 u8 u8'),
    0x73: ('ENTITY_MOVE_TO_AXIS_WITH_CAMERA', 'e s16 u8 u8'),
    0x74: ('SPAWN_ITEM', 'i s16 s16'),
    0x75: ('SPAWN_CHEST', 'i s16 s16 s16 s16 t'),
    0x76: ('SPAWN_BOULDER', 'u8'), 0x77: ('MOVE_BOULDER', 'u8 s16 s16'), 0x78: ('DESPAWN_BOULDER', 'u8'),
    0x79: ('UNLOAD_DIGIMON', 'd'),
    0x7A: ('COPY_PSTAT', '_ p p'),
    0x7B: ('SECTION_ON_EXIT', 'u8'),
    0x7C: ('SET_RECT_IMPASSABLE', 'u8 s16 s16 u8 u8'),
    0x7D: ('SPAWN_SPRITE_AT_LOCATION', 'u8 s16 s16 s16 s16'),
    0x7E: ('SPAWN_SPRITE_AT_ENTITY', 'e u8 u8'),
    # Wide opcodes 0x80-0x93 (patch series). Only the GCC/mod executable runs
    # them: the original executable treats 0x80-0xFA as "end of script".
    0x80: ('LOAD_DIGIMON16', '_ d16'), 0x81: ('SET_DIGIMON16', '_ d16 u8 u8'),
    0x82: ('UNLOAD_DIGIMON16', '_ d16'), 0x83: ('WARP_TO16', '_ m16 u8 u8'),
    0x84: ('GIVE_ITEM16', '_ i16 u8 _'), 0x85: ('REMOVE_ITEM16', '_ i16 u8 _'),
    0x86: ('SPAWN_ITEM16', '_ i16 s16 s16'), 0x87: ('SPAWN_CHEST16', '_ i16 s16 s16 s16 s16 t'),
    0x88: ('LEARN_MOVE16', '_ v16'), 0x89: ('GIVE_CARD16', '_ k16'), 0x8A: ('TAKE_CARD16', '_ k16'),
    0x8B: ('SET_BGM16', '_ u16'),
    0x8C: ('SET_WREG', 'w u16'), 0x8D: ('STORE_DIGIMON_TYPE_W', 'w'), 0x8E: ('STORE_MAP_ID_W', 'w'),
    0x8F: ('TELEPORT_W', 'w'), 0x90: ('COPY_W', '_ w w'),
    0x91: ('ADD_W', 'w u16'), 0x92: ('SUB_W', 'w u16'),
    # Story variables, story-state engine only (docs/mods/story-state-engine.md): V = u16 variable index
    # (v12 = story variable 12, s3 = scene variable 3 = index 0x8003). Even lengths, like the rest.
    0x94: ('SET_V', '_ V s32'), 0x95: ('ADD_V', '_ V s32'), 0x96: ('SUB_V', '_ V s32'),
    0x97: ('COPY_V', '_ V V'), 0x98: ('V_FROM_PSTAT', 'p V'), 0x99: ('PSTAT_FROM_V', 'p V'),
    0x9A: ('ADD_VV', '_ V V'), 0x9B: ('SUB_VV', '_ V V'),
    0x9C: ('MUL_V', '_ V s32'), 0x9D: ('DIV_V', '_ V s32'), 0x9E: ('MOD_V', '_ V s32'),
    # Stable daily pickup ID; available on mod targets with ground_pickup_max.
    0x9F: ('SPAWN_ITEM_DAILY', '_ i16 s16 s16 u16 m16'),
    0xFB: ('SET_SCRIPT', '_ s M'),
    0xFC: ('UNUSED_FC', ''), 0xFD: ('UNUSED_FD', ''),
    0xFE: ('END_SECTION', '_'), 0xFF: ('END_SCRIPT', '_'),
}
SPECIAL = {0x10: 'SET_SELECTION', 0x18: 'SWITCH', 0x19: 'IF', 0x1A: 'SHOW_TEXTBOX', 0x6B: 'DATA',
           0x93: 'SWITCH_W'}
# 8-bit opcode -> its wide variant: `asm` uses the wide one when the id (the first
# argument) does not fit in a byte, or always with --wide
WIDE = {0x46: 0x80, 0x47: 0x81, 0x79: 0x82, 0x4B: 0x83, 0x28: 0x84, 0x29: 0x85, 0x74: 0x86,
        0x75: 0x87, 0x2D: 0x88, 0x2F: 0x89, 0x30: 0x8A, 0x5D: 0x8B}
BYNAME = {n: (op, f) for op, (n, f) in OPS.items()}
BYNAME.update({n: (op, None) for op, n in SPECIAL.items()})
BYNAME['END_SELECTION'] = (0x12, None)
ALIASES = {'TEXT': 'SHOW_TEXTBOX', 'SELECT': 'SET_SELECTION', 'SPEAKER': 'SET_DIALOG_OWNER',
           'GOTO': 'JUMP_TO', 'CALL': 'JUMP_AND_LINK', 'RETURN': 'JUMP_RETURN', 'END': 'END_SECTION'}
FSIZE = {'_': 1, 'u8': 1, 'p': 1, 'e': 1, 'c': 1, 'i': 1, 'd': 1, 'm': 1, 'v': 1, 'w': 1,
         'u16': 2, 's16': 2, 't': 2, 'l': 2, 's': 2, 'S': 2, 'M': 2, 's32': 4,
         'd16': 2, 'm16': 2, 'i16': 2, 'v16': 2, 'k16': 2, 'V': 2}
CMP = ['==', '!=', '>=', '<=', '>', '<']
TYPENAME = {'p': 'pstat', 't': 'trigger', 'l': 'label', 'e': 'entity', 'c': 'comparison', 'i': 'item',
            'd': 'digimon', 'm': 'screen', 'v': 'technique', 's': 'script', 'S': 'section', 'M': 'screen',
            'w': 'wide register', 'd16': 'digimon', 'm16': 'screen', 'i16': 'item', 'v16': 'technique',
            'k16': 'card', 'V': 'story variable'}
ENT = {0xFD: 'TAMER', 0xFC: 'PARTNER'}

# --------------------------------------------------------------------------
# Text. The original USA font only has these 79 glyphs (CHAR_TO_GLYPH_TABLE, font.c:1167,
# with their pixel width from GLYPH_DATA); any other code draws the last one. The four buttons are
# what GLYPH_DATA draws, not the Shift-JIS meaning of the code: 819B ○ and 81A0 □ as in Shift-JIS,
# but 81A2 (Shift-JIS △) draws × and 817E (Shift-JIS ×) draws △ (the US font redrew them; the US
# executable's own strings, decomp/text/*.yaml, keep the Shift-JIS labels: tools/localize/executable/bank.py).
_GLYPHS = ([0x8260 + i for i in range(26)] + [0x8281 + i for i in range(26)] +
           [0x824F + i for i in range(10)] +
           [0x8140, 0x8142, 0x8148, 0x8149, 0x8176, 0x8175, 0x8143, 0x815F, 0x8146, 0x8147,
            0x817B, 0x817C, 0x8181, 0x819B, 0x81A0, 0x81A2, 0x817E])
_GLYPH_CHARS = ([chr(0x41 + i) for i in range(26)] + [chr(0x61 + i) for i in range(26)] +
                [chr(0x30 + i) for i in range(10)] + list(' .?!"\',\\:;+-=') + list('○□×△'))
_WIDTHS = [12] * 26 + [8, 8, 8, 8, 8, 6, 8, 8, 4, 6, 8, 4, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8] + \
          [8] * 10 + [4, 5, 8, 5, 8, 5, 5, 8, 5, 5, 12, 12, 12, 12, 12, 12, 12]
CHAR2SJIS = dict(zip(_GLYPH_CHARS, _GLYPHS))
SJIS2CHAR = dict(zip(_GLYPHS, _GLYPH_CHARS))
CHARWIDTH = dict(zip(_GLYPH_CHARS, _WIDTHS))
# The mod executable adds glyphs at F040+ (á é ñ ¿ ¡ ç · « » ( ) & % / … [ ] # * ~ @ – — ♪,
# tools/font/extra.txt, docs/mods/font.md). They are always decoded; `asm --font original`
# rejects them (the original executable would draw them all as the last glyph), and
# `--font-glyphs N` the ones past the first N (an executable built before they were added).
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import fontgen
EXTRA_CHAR2SJIS = {}
for _ch, (_code, _w) in fontgen.extra_map().items():
    EXTRA_CHAR2SJIS[_ch] = _code; SJIS2CHAR[_code] = _ch; CHARWIDTH[_ch] = _w
# control codes (script_textbox.c:1051-1194): name, takes a free argument
CTRL = {0x01: ('color', True), 0x04: ('pstat', True), 0x05: ('player', False), 0x06: ('partner', False),
        0x07: ('digimon', True), 0x08: ('move', True), 0x09: ('item', True), 0x0A: ('money', False),
        0x0B: ('merit', False), 0x0C: ('tab', True), 0x0E: ('tab11', True), 0x0F: ('half', True),
        0x10: ('shopvar', False), 0x11: ('bgm', True), 0x12: ('cup', True), 0x13: ('cupswon', False),
        0x14: ('wins', False), 0x15: ('losses', False)}
for _c in range(0x16, 0x1D):
    CTRL[_c] = ('pos%02x' % _c, True)
CTRLNAME = {n: (c, a) for c, (n, a) in CTRL.items()}
# One-byte text (patch 0145, `asm --pack-ascii`): a letter, digit, space or . , : ; ? ! ' " + - = may be stored as its ASCII byte instead
# of its two-byte glyph code. The set is the one a packed row holds (fontgen.PACKED, script_textbox.c PACKED_CODES). The original's text
# has no unit starting in 0x20..0x7e, so reading both forms leaves every disc's scripts as they were.
PACK_BYTE2CODE = {ord(c): CHAR2SJIS[c] for c in fontgen.PACKED}
PACK_CODE2BYTE = {v: k for k, v in PACK_BYTE2CODE.items()}
READ_PACKED = True      # False reads every unit as two bytes: the text of another disc (tools/dws/text/extract.py), whose units may start in 0x20..0x7e


def pack_units(ln):
    """A line of two-byte units (03 takes 4) with every packable glyph code as its ASCII byte."""
    out = bytearray(); p = 0
    while p < len(ln):
        c = ln[p]
        if c == 0x03:
            out += ln[p:p + 4]; p += 4; continue
        code = (c << 8) | (ln[p + 1] if p + 1 < len(ln) else 0)
        if code in PACK_CODE2BYTE:
            out.append(PACK_CODE2BYTE[code])
        else:
            out += ln[p:p + 2]
        p += 2
    return bytes(out)
LINE_PX = 252          # renderString copies 252 px per row
DRAW_LIMIT = 244       # drawGlyph skips glyphs that start at x >= 244 (TEXT_DRAW_LIMIT); the
                       # original text's last glyphs start at most at 240
from ..text.profiles import BINARY_ROW_UNITS
LINE_UNITS = BINARY_ROW_UNITS        # 64-byte rows in TEXTBOX_LINES_BUFFER (the original reaches 32)
ACCENTS = str.maketrans('áéíóúüïÁÉÍÓÚÜÏñÑçÇàèìòùÀÈÌÒÙ·«»', 'aeiouuiAEIOUUInNcCaeiouAEIOU.""')


def decode_text(b, p):
    """Reads a text the way showTextbox does: 2-byte units (03 takes 4) up to 0D 00 + 00 00.
    Returns (lines, end). Raises BytecodeError if it cannot be represented losslessly."""
    lines, cur = [], []
    while True:
        if p + 2 > len(b):
            raise BytecodeError('unterminated text')
        c, a = b[p], b[p + 1]
        if c == 0x0D:
            if a != 0:
                raise BytecodeError('line break 0D %02x' % a)
            p += 2; lines.append(''.join(cur)); cur = []
            if p + 2 > len(b):
                raise BytecodeError('unterminated text')
            if b[p] == 0:
                if b[p + 1] != 0:
                    raise BytecodeError('terminator 00 %02x' % b[p + 1])
                return lines, p + 2
            continue
        if c == 0x03:
            cur.append('{raw %s}' % b[p:p + 4].hex(' ')); p += 4; continue
        if c in CTRL:
            name, arg = CTRL[c]
            if arg:
                cur.append('{%s %d}' % (name, a))
            elif a == 0:
                cur.append('{%s}' % name)
            else:
                cur.append('{raw %02x %02x}' % (c, a))
            p += 2; continue
        if READ_PACKED and c in PACK_BYTE2CODE:
            ch = chr(c)
            cur.append({'"': '\\"', '\\': '\\\\', '{': '\\{'}.get(ch, ch))
            p += 1; continue
        code = (c << 8) | a
        if code in SJIS2CHAR:
            ch = SJIS2CHAR[code]
            cur.append({'"': '\\"', '\\': '\\\\', '{': '\\{'}.get(ch, ch))
        elif c >= 0x81:
            cur.append('{sjis %04x}' % code)
        else:
            cur.append('{raw %02x %02x}' % (c, a))
        p += 2


def text_units(s, where, opts, warn):
    """Converts a string (without quotes) into a list of byte lines."""
    lines, cur, i = [], bytearray(), 0
    s = unicodedata.normalize('NFC', s)
    if opts.get('strip_accents'):
        s2 = s.translate(ACCENTS).replace('¿', '').replace('¡', '')
        if s2 != s:
            warn(f'{where}: accents stripped: "{s2}"')
        s = s2
    while i < len(s):
        ch = s[i]
        if ch == '\\':
            if i + 1 >= len(s):
                raise BytecodeError(f'{where}: "\\" at the end of the string')
            ch = s[i + 1]; i += 2
            if ch not in CHAR2SJIS and ch != '{':
                raise BytecodeError(f'{where}: unknown escape \\{ch}')
            if ch == '{':
                raise BytecodeError(f'{where}: the font has no "{{"')
            cur += struct.pack('>H', CHAR2SJIS[ch]); continue
        if ch == '{':
            j = s.find('}', i)
            if j < 0:
                raise BytecodeError(f'{where}: missing "}}"')
            tok = s[i + 1:j].split(); i = j + 1
            if not tok:
                raise BytecodeError(f'{where}: empty escape {{}}')
            k = tok[0].lower()
            if k == 'br':
                lines.append(bytes(cur)); cur = bytearray(); continue
            if k == 'raw':
                cur += bytes(int(x, 16) for x in tok[1:]); continue
            if k == 'sjis':
                cur += struct.pack('>H', int(tok[1], 16)); continue
            if k in CTRLNAME:
                c, hasarg = CTRLNAME[k]
                if hasarg:
                    if len(tok) != 2:
                        raise BytecodeError(f'{where}: {{{k} N}} needs a number')
                    v = parse_int(tok[1].lstrip('pP'), where)
                else:
                    if len(tok) != 1:
                        raise BytecodeError(f'{where}: {{{k}}} takes no argument')
                    v = 0
                cur += bytes([c, v & 0xFF]); continue
            raise BytecodeError(f'{where}: unknown escape {{{tok[0]}}}')
        if ch in CHAR2SJIS:
            cur += struct.pack('>H', CHAR2SJIS[ch]); i += 1; continue
        if ch in EXTRA_CHAR2SJIS:
            if opts.get('font') == 'original':
                raise BytecodeError(f'{where}: character {ch!r} only exists in the mod executable\'s font '
                               '(docs/mods/font.md): drop --font original or use --strip-accents')
            n = opts.get('font_glyphs')
            if n is not None and fontgen.code_to_index(EXTRA_CHAR2SJIS[ch]) >= n:
                raise BytecodeError(f'{where}: character {ch!r} is extra glyph {EXTRA_CHAR2SJIS[ch]:04X} and the target executable has '
                               f'the first {n} (--font-glyphs {n}): it was built before {ch!r} was added; rebuild it (docs/mods/font.md)')
            cur += struct.pack('>H', EXTRA_CHAR2SJIS[ch]); i += 1; continue
        hint = ' (to add a glyph: tools/font/extra.txt, docs/mods/font.md)'
        raise BytecodeError(f'{where}: character {ch!r} has no glyph in the font{hint}')
    lines.append(bytes(cur))
    return lines


def line_metrics(line, space=fontgen.SPACE_WIDTH):
    """(units, pixels, start of the last glyph) of an already encoded line, the way
    drawString2 advances: each glyph by its width, and a space (81 40) by `space` px
    (mod executable: fontgen.SPACE_WIDTH). space=None is the original executable, which
    only clears 12 px and keeps the previous glyph's advance. Variable names count as 0;
    the codes showTextbox copies into the row as they are (colour 01, 02, tab 0C, 0E, 0F,
    03 xx xx xx) take their units of the 32 there though they draw nothing."""
    units = px = 0; p = 0; prev = 12; last = 0
    while p < len(line):
        c = line[p]
        if c == 0x03:
            units += 2; p += 4; continue
        if c in (0x01, 0x02, 0x0C, 0x0E, 0x0F):
            units += 1; p += 2; continue
        code = (c << 8) | (line[p + 1] if p + 1 < len(line) else 0)
        if code == 0x8140:
            units += 1; px += prev if space is None else space
        elif code in SJIS2CHAR or c >= 0x80:
            prev = CHARWIDTH[SJIS2CHAR[code]] if code in SJIS2CHAR else 12
            units += 1; last = px; px += prev
        p += 2
    return units, px, last


def line_metrics_pixel(line, font):
    """(bytes in a packed row, pixels, start of the last glyph) of an encoded line for a font placed to the pixel (a, b):
    showTextbox writes a letter, digit, space or . , : ; ? ! ' " + - = as one byte; drawString2 moves by each glyph's
    advance (fontgen.metrics) and font b's kerning."""
    adv = fontgen.metrics(font); kern = fontgen.kern(font)
    n = px = 0; p = 0; last = 0; prev = None
    while p < len(line):
        c = line[p]
        if c == 0x03:
            n += 4; p += 4; continue                  # drawn as nothing, the pen stays: a pair still kerns
        if c in (0x01, 0x02, 0x0C, 0x0E, 0x0F):
            n += 2; p += 2; prev = prev if c in (0x01, 0x02) else None; continue
        code = (c << 8) | (line[p + 1] if p + 1 < len(line) else 0)
        ch = SJIS2CHAR.get(code)
        n += 1 if ch in fontgen.PACKED else 2
        px += kern.get((prev, ch), 0); prev = ch      # font b's kerning (drawGlyph: a glyph right after the previous)
        last = px; px += adv.get(ch, 12) if ch else 12
        p += 2
    return n, px, last


def encode_text(strings, where, opts, warn, check=True):
    out = bytearray(); lines = []
    for s in strings:
        lines += text_units(s, where, opts, warn)
    ctx = opts.get('_ctx') or {}
    maxpx = ctx.get('px', LINE_PX); maxrows = ctx.get('rows', 99)   # no warning without a known speaker
    for ln in lines:
        if check and opts.get('font_name') in ('a', 'b') and ctx.get('unpacked'):
            _, px, last = line_metrics_pixel(ln, opts['font_name'])
            u = line_metrics(ln)[0]
            if u > LINE_UNITS - 1 or px > maxpx or last >= DRAW_LIMIT:
                warn(f'{where}: line of {u} characters / {px} px in a box other than the dialogue box (box 1-3, whose '
                     f'rows are not packed: {LINE_UNITS - 1} characters and {maxpx} px with every font): it will be cut')
        elif check and opts.get('font_name') in ('a', 'b'):
            b, px, last = line_metrics_pixel(ln, opts['font_name'])
            if b > fontgen.ROW_BYTES + 1 or px > maxpx or last >= DRAW_LIMIT:
                warn(f'{where}: line of {b} bytes / {px} px (max. {fontgen.ROW_BYTES} bytes, {maxpx} px, '
                     f'last letter starting before {DRAW_LIMIT} px): it will be cut')
        elif check:
            u, px, last = line_metrics(ln, None if opts.get('font') == 'original' else fontgen.SPACE_WIDTH)
            if u > LINE_UNITS or px > maxpx or last >= DRAW_LIMIT:
                warn(f'{where}: line of {u} characters / {px} px (max. {LINE_UNITS} characters, {maxpx} px, '
                     f'last letter starting before {DRAW_LIMIT} px): it will be cut')
        out += (pack_units(ln) if opts.get('pack_ascii') else ln) + b'\x0d\x00'
    if check and len(lines) > maxrows:
        warn(f'{where}: {len(lines)} lines in a box that fits {maxrows} '
             '(3 with a speaker, 4 with SET_DIALOG_OWNER 255, or the rows of SET_TEXTBOX_SIZE): '
             'split the text into several consecutive SHOW_TEXTBOX')
    out = bytes(out + b'\x00\x00')
    if len(out) % 2:
        out = _even_text(out)
    return out


def _even_text(b):
    """A packed text of odd length would leave the next instruction at an odd offset (its 16-bit fields are read with lhu): the last
    one-byte unit goes back to two."""
    p = 0; last = None
    while p < len(b):
        c = b[p]
        if c == 0x0D:
            p += 2
            if b[p] == 0:
                break
            continue
        if c == 0x03:
            p += 4; continue
        if c in PACK_BYTE2CODE:
            last = p; p += 1; continue
        p += 2
    code = PACK_BYTE2CODE[b[last]]
    return b[:last] + struct.pack('>H', code) + b[last + 1:]


from ..text.profiles import UNPACKED_ENTRIES, UNPACKED_SCRIPTS, unpacked_entry, BINARY_ROW_UNITS


def update_text_ctx(ins, opts):
    """Remembers how many rows and pixels fit in the next box (for warnings only)."""
    ctx = opts.setdefault('_ctx', {})
    name = ALIASES.get(ins.name, ins.name)
    try:
        if name == 'SET_DIALOG_OWNER':
            ctx.clear(); ctx['rows'] = 4 if ins.args and ins.args[0].strip() in ('255', '0xff', '0xFF') else 3
        elif name == 'SET_TEXTBOX_SIZE' and len(ins.args) == 3:
            ctx['rows'] = int(ins.args[2], 0); ctx['px'] = int(ins.args[1], 0) * 12 + 8   # box: cols*12+10 px; the original reaches +7
    except ValueError:
        pass


def quote(s):
    return '"' + s + '"'


# --------------------------------------------------------------------------
# Names for the comments (docs/data/*.csv, if present)
def _species_names():
    """{id: name} of the species (content/species, tools/species.py); empty without it."""
    try:
        import species
        out = {t: r['name'] for t, r in species.all_rows().items()}
        # an id of the disc without a file (a species the game does not have) keeps its disc name, so the story that still
        # names it compiles and tools/missing_refs.py finds it; the species itself is empty in the tables. The disc's names
        # are docs/data/species.csv (species.disc_names): a missing file stops here, it is not an empty list
        for t, name in species.disc_names().items():
            if t not in out and name: out[t] = name
        return out
    except (ImportError, SystemExit):
        return {}


def _load_names(fname, col='name'):
    path = os.path.join(ROOT, 'docs', 'data', fname)
    out = {}
    try:
        with open(path, newline='') as f:
            for r in csv.DictReader(f):
                out[int(r['id'])] = r[col]
    except (OSError, KeyError, ValueError):
        pass
    return out


NAMES = None


def names():
    global NAMES
    if NAMES is None:
        NAMES = {'i': _load_names('items.csv'), 'd': _species_names(),
                 'm': _load_names('map_files.csv', 'map_name'), 'v': _load_names('techs.csv')}
        NAMES['M'] = NAMES['m']
    return NAMES


# --------------------------------------------------------------------------
# Script header
def parse_header(e):
    if len(e) < 4:
        raise BytecodeError('empty script')
    hdr = struct.unpack_from('<H', e, 0)[0]
    p = 2; secs = []
    while True:
        if p + 2 > len(e):
            raise BytecodeError('section table without 0xFFFF')
        sid = struct.unpack_from('<H', e, p)[0]
        if sid == 0xFFFF:
            break
        secs.append((sid, struct.unpack_from('<H', e, p + 2)[0])); p += 4
    if hdr != p + 2:
        raise BytecodeError(f'header: size {hdr:#x} ≠ end of table {p + 2:#x}')
    return hdr, secs


def u16(b, p):
    return struct.unpack_from('<H', b, p)[0]


def instr_length(b, p):
    """Length of the instruction at p (as the interpreter consumes it) and its jump targets."""
    op = b[p]; tg = []
    if op == 0x10:
        n = b[p + 1]
        tg = [u16(b, p + 2 + 2 * k) for k in range(n)]
        q = p + 2 + 2 * n + 2
        _, q = decode_text_len(b, q)
        return q - p, tg
    if op == 0x1A:
        _, q = decode_text_len(b, p + 2)
        return q - p, tg
    if op in (0x18, 0x93):
        n = u16(b, p + 2)
        return 4 + 2 * n, [u16(b, p + 4 + 2 * k) for k in range(n)]
    if op == 0x19:
        q = p + 2
        while True:
            cop = b[q]; q += 2
            if cop == 0x19:
                return q - p, tg
            k = cop & 0x38
            if k in (0x10, 0x18):
                tg.append(u16(b, q))
            q += IF_ARGLEN(cop)
    if op == 0x6B:
        q = p + 2
        while b[q] != 0xFF:
            q += 1
        return q + 1 - p, tg
    if op in OPS:
        n = 1
        for f in OPS[op][1].split():
            if f == 'l':
                tg.append(u16(b, p + n))
            n += FSIZE[f]
        return n, tg
    return None, tg


def IF_ARGLEN(cop):
    k = cop & 0x38
    if k in (0x00, 0x08, 0x10, 0x18):
        return 2
    if k == 0x20:          # 26 item16 and 27 wreg: mod executable only
        return {0: 4, 1: 4, 2: 2, 3: 2, 4: 4, 5: 6, 6: 6, 7: 4}[cop & 7]
    if k == 0x28:          # 28 move16, 29 card16: mod executable only; 2A, 2B story variables: story-state only
        return {0: 4, 1: 6, 2: 8, 3: 6}.get(cop & 7, 0)
    return 0


def decode_text_len(b, p):
    """End of a text, following showTextbox exactly (without validating the content)."""
    while True:
        c = b[p]
        if c == 0x03:
            p += 4; continue
        if c == 0x0D:
            p += 2
            if b[p] == 0:
                return None, p + 2
            continue
        p += 1 if READ_PACKED and c in PACK_BYTE2CODE else 2


def sweep(e):
    """Linear sweep from the end of the header up to the END_SCRIPT (FF 00) after which
    there are no more sections or targets. Returns (header, sections, [(offset, len)], end)."""
    hdr, secs = parse_header(e)
    p = hdr; ins = []; targets = set()
    smax = max([o for _, o in secs] + [hdr])
    while True:
        if p >= len(e):
            if p == len(e) and smax < p and all(t < p for t in targets):
                return hdr, secs, ins, p, targets
            raise BytecodeError(f'the code runs past the end of the script at {p:#x}')
        try:
            n, tg = instr_length(e, p)
        except IndexError:
            n = None
        if n is None:
            raise BytecodeError(f'unknown opcode {e[p]:#04x} at {p:#x}')
        # after SET_SELECTION, "12 00" is the end of the selection (DIALOGUE_SELECTION.endPointer)
        ins.append((p, n)); targets.update(tg)
        if e[p] == 0x10 and e[p + n:p + n + 2] == b'\x12\x00':
            ins.append((p + n, 2)); n += 2
        p += n
        if e[p - 2:p] == b'\xff\x00' and ins[-1][1] == 2 and e[ins[-1][0]] == 0xFF:
            if smax < p and all(t < p for t in targets):
                return hdr, secs, ins, p, targets


# --------------------------------------------------------------------------
# Disassembly of one instruction
def fmt_field(f, v, labels, comments):
    if f == 'p':
        return 'p%d' % v
    if f == 'w':
        return 'w%d' % v
    if f == 'V':
        return ('s%d' % (v & 0x7FFF)) if v & 0x8000 else ('v%d' % v)
    if f == 'l':
        return labels[v]
    if f == 'e':
        return ENT.get(v, str(v))
    if f == 'c':
        return CMP[v] if v < len(CMP) else None
    if f in ('i', 'd', 'm', 'v', 'M', 'i16', 'd16', 'm16', 'v16'):
        nm = names()[f[0]].get(v)
        if nm:
            comments.append(nm)
    return str(v)


def read_field(b, q, f):
    if FSIZE[f] == 2 and f != 's16':
        return u16(b, q)
    if f == 's16':
        return struct.unpack_from('<h', b, q)[0]
    if f == 's32':
        return struct.unpack_from('<i', b, q)[0]
    return b[q]


def dis_instr(b, p, n, labels, prev_op=None):
    """Returns (text lines, comments) for the instruction b[p:p+n]."""
    op = b[p]; com = []
    if op == 0x12 and n == 2 and prev_op == 0x10:
        return ['END_SELECTION'], com
    if op == 0x10:
        cnt = b[p + 1]
        tg = [labels[u16(b, p + 2 + 2 * k)] for k in range(cnt)]
        q = p + 2 + 2 * cnt
        if b[q:q + 2] != b'\x1a\x00':
            raise BytecodeError('selection without 1A 00')
        lines, end = decode_text(b, q + 2)
        return ['SET_SELECTION ' + ', '.join(tg)] + ['    ' + quote(s) for s in lines], com
    if op == 0x1A:
        if b[p + 1]:
            raise BytecodeError('padding')
        lines, end = decode_text(b, p + 2)
        return ['SHOW_TEXTBOX'] + ['    ' + quote(s) for s in lines], com
    if op in (0x18, 0x93):
        cnt = u16(b, p + 2)
        reg = ('p%d' if op == 0x18 else 'w%d') % b[p + 1]
        return [SPECIAL[op] + ' ' + ', '.join([reg] + [labels[u16(b, p + 4 + 2 * k)] for k in range(cnt)])], com
    if op == 0x19:
        if b[p + 1]:
            raise BytecodeError('padding')
        cl = []; q = p + 2
        while True:
            cop, pad = b[q], b[q + 1]
            if pad:
                raise BytecodeError('padding')
            q += 2
            if cop == 0x19:
                break
            cl.append(dis_if_clause(b, q, cop, labels)); q += IF_ARGLEN(cop)
        return ['IF ' + ', '.join(cl)], com
    if op == 0x6B:
        if b[p + 1]:
            raise BytecodeError('padding')
        return ['DATA ' + ', '.join(str(x) for x in b[p + 2:p + n - 1])], com
    name, fmt = OPS[op]
    args = []; q = p + 1
    for f in fmt.split():
        v = read_field(b, q, f); q += FSIZE[f]
        if f == '_':
            if v:
                raise BytecodeError('padding')
            continue
        s = fmt_field(f, v, labels, com)
        if s is None:
            raise BytecodeError('field')
        args.append(s)
    return [name + (' ' + ', '.join(args) if args else '')], com


def dis_if_clause(b, q, cop, labels):
    comb = cop & 0xC0; k = cop & 0x38; sub = cop & 7
    pre = {0: '', 0x40: 'or ', 0x80: 'and '}.get(comb)
    if pre is None:
        raise BytecodeError('IF: combination %#x' % cop)
    if k == 0x00:
        if sub > 1:
            raise BytecodeError('IF trigger')
        return pre + ('not ' if sub else '') + 'trigger %d' % u16(b, q)
    if k == 0x08:
        if sub > 5:
            raise BytecodeError('IF pstat')
        return pre + 'p%d %s %d' % (b[q], CMP[sub], b[q + 1])
    if k in (0x10, 0x18):
        if comb or sub:
            raise BytecodeError('IF jump')
        return ('then ' if k == 0x10 else 'else ') + labels[u16(b, q)]
    if k == 0x20:
        if sub in (0, 1, 4):
            what = {0: 'stat', 1: 'card', 4: 'item'}[sub]
            if b[q + 1] > 5:
                raise BytecodeError('IF cmp')
            v = u16(b, q + 2)
            if sub == 0 and b[q] == 9:
                v = struct.unpack_from('<h', b, q + 2)[0]
            return pre + '%s %d %s %d' % (what, b[q], CMP[b[q + 1]], v)
        if sub in (2, 3):
            if b[q + 1] > 1:
                raise BytecodeError('IF negate')
            return pre + ('not ' if b[q + 1] else '') + ('move' if sub == 2 else 'cond') + ' %d' % b[q]
        if sub == 5:
            if b[q] or b[q + 1] > 5:
                raise BytecodeError('IF money')
            return pre + 'money %s %d' % (CMP[b[q + 1]], struct.unpack_from('<i', b, q + 2)[0])
        if sub == 6:
            if b[q + 2] > 5 or b[q + 3]:
                raise BytecodeError('IF item16')
            return pre + 'item16 %d %s %d' % (u16(b, q), CMP[b[q + 2]], u16(b, q + 4))
        if sub == 7:
            if b[q + 1] > 5:
                raise BytecodeError('IF wreg')
            return pre + 'w%d %s %d' % (b[q], CMP[b[q + 1]], u16(b, q + 2))
    if k == 0x28 and sub == 0:
        if b[q + 2] > 1 or b[q + 3]:
            raise BytecodeError('IF move16')
        return pre + ('not ' if b[q + 2] else '') + 'move16 %d' % u16(b, q)
    if k == 0x28 and sub == 1:
        if b[q + 2] > 5 or b[q + 3]:
            raise BytecodeError('IF card16')
        return pre + 'card16 %d %s %d' % (u16(b, q), CMP[b[q + 2]], u16(b, q + 4))
    if k == 0x28 and sub in (2, 3):         # story-state engine: story variable conditions
        if b[q + 2] > 5 or b[q + 3]:
            raise BytecodeError('IF story variable')
        if sub == 2:
            return pre + '%s %s %d' % (fmt_field('V', u16(b, q), None, None), CMP[b[q + 2]],
                                       struct.unpack_from('<i', b, q + 4)[0])
        return pre + '%s %s %s' % (fmt_field('V', u16(b, q), None, None), CMP[b[q + 2]],
                                   fmt_field('V', u16(b, q + 4), None, None))
    raise BytecodeError('IF: condition %#x' % cop)


# --------------------------------------------------------------------------
# Assembly
def parse_int(s, where):
    try:
        return int(s.strip(), 0)
    except ValueError:
        raise BytecodeError(f'{where}: invalid number: {s!r}')


def split_args(s):
    s = s.strip()
    return [a.strip() for a in s.split(',')] if s else []


class Instr:
    def __init__(self, name, args, strings, where):
        self.name, self.args, self.strings, self.where = name, args, strings, where


def instr_size(ins, opts, warn):
    """Size of an instruction (does not depend on the labels)."""
    return len(encode_instr(ins, None, 0, opts, warn, sizing=True))


def get_label(labels, name, where, sizing):
    if sizing:
        return 0
    if name not in labels:
        raise BytecodeError(f'{where}: label {name!r} not defined')
    return labels[name]


def story_var_index(a, where):
    """v12 -> 12 (a story variable), s3 -> 0x8003 (a scene variable), a plain number as it is."""
    a = a.strip()
    if a[:1] in 'vV' and a[1:].isdigit():
        v = int(a[1:])
        if v > 0x7FFF: raise BytecodeError(f'{where}: story variable {a!r}: v0..v32767')
        return v
    if a[:1] in 'sS' and a[1:].isdigit():
        v = int(a[1:])
        if v > 0x7FFF: raise BytecodeError(f'{where}: scene variable {a!r}: s0..s32767')
        return 0x8000 | v
    return parse_int(a, where)


def enc_field(f, a, labels, where, sizing):
    if f == 'l':
        return struct.pack('<H', get_label(labels, a, where, sizing))
    if f == 'p':
        v = parse_int(a[1:] if a[:1] in 'pP' else a, where)
    elif f == 'w':
        v = parse_int(a[1:] if a[:1] in 'wW' else a, where)
        if not 0 <= v < 64:
            raise BytecodeError(f'{where}: wide register {a!r}: w0..w63')
    elif f == 'V':
        v = story_var_index(a, where)
    elif f == 'e':
        v = {'TAMER': 0xFD, 'PARTNER': 0xFC}.get(a.upper())
        if v is None:
            v = parse_int(a, where)
    elif f == 'c':
        if a not in CMP:
            raise BytecodeError(f'{where}: comparison {a!r} (use == != >= <= > <)')
        v = CMP.index(a)
    else:
        v = parse_int(a, where)
    size = FSIZE[f]
    if f in ('s16',):
        if not -0x8000 <= v <= 0x7FFF:
            raise BytecodeError(f'{where}: {v} does not fit in s16')
        return struct.pack('<h', v)
    if f == 's32':
        if not -0x80000000 <= v <= 0x7FFFFFFF:
            raise BytecodeError(f'{where}: {v} does not fit in s32')
        return struct.pack('<i', v)
    if size == 2:
        if not 0 <= v <= 0xFFFF:
            raise BytecodeError(f'{where}: {v} does not fit in u16')
        return struct.pack('<H', v)
    if not 0 <= v <= 0xFF:
        raise BytecodeError(f'{where}: {v} does not fit in a byte')
    return bytes([v])


def enc_if_clause(c, labels, where, sizing, wide=False):
    t = c.split()
    if not t:
        raise BytecodeError(f'{where}: empty condition in IF')
    comb = 0
    if t[0].lower() in ('and', 'or'):
        comb = 0x80 if t[0].lower() == 'and' else 0x40; t = t[1:]
    neg = 0
    if t and t[0].lower() == 'not':
        neg = 1; t = t[1:]
    if not t:
        raise BytecodeError(f'{where}: incomplete condition: {c!r}')
    k = t[0].lower()
    if k in ('then', 'else'):
        if comb or neg or len(t) != 2:
            raise BytecodeError(f'{where}: {c!r}: then/else stand alone with a label')
        return bytes([0x10 if k == 'then' else 0x18, 0]) + struct.pack('<H', get_label(labels, t[1], where, sizing))
    if k == 'trigger':
        if len(t) != 2:
            raise BytecodeError(f'{where}: {c!r}: trigger N')
        return bytes([comb | neg, 0]) + enc_field('t', t[1], labels, where, sizing)
    if k[:1] in 'vs' and k[1:].isdigit():
        # story-state engine: vN OP value (0x2A, signed 32 bit) or vN OP vM / sM (0x2B)
        if neg or len(t) != 3 or t[1] not in CMP:
            raise BytecodeError(f'{where}: {c!r}: vN OP value (or vN OP vM)')
        v1 = story_var_index(k, where)
        r = t[2].lower()
        if r[:1] in 'vs' and r[1:].isdigit():
            return (bytes([comb | 0x2B, 0]) + struct.pack('<H', v1) + bytes([CMP.index(t[1]), 0]) +
                    struct.pack('<H', story_var_index(r, where)))
        v = parse_int(t[2], where)
        if not -0x80000000 <= v <= 0x7FFFFFFF:
            raise BytecodeError(f'{where}: {c!r}: value does not fit in s32')
        return (bytes([comb | 0x2A, 0]) + struct.pack('<H', v1) + bytes([CMP.index(t[1]), 0]) +
                struct.pack('<i', v))
    if k[:1] == 'w' and k[1:].isdigit():
        if neg or len(t) != 3 or t[1] not in CMP:
            raise BytecodeError(f'{where}: {c!r}: wN OP value')
        wr, v = int(k[1:]), parse_int(t[2], where)
        if wr > 63 or not 0 <= v <= 0xFFFF:
            raise BytecodeError(f'{where}: {c!r}: register w0..w63 and value 0..65535')
        return bytes([comb | 0x27, 0, wr, CMP.index(t[1])]) + struct.pack('<H', v)
    if k in ('item', 'card', 'move'):
        # the 8-bit forms take the id in a byte: use the wide form when it does not fit
        idv = parse_int(t[1], where) if len(t) > 1 else 0
        if wide or idv > 0xFF:
            k += '16'
    if k in ('item16', 'card16'):
        if neg or len(t) != 4 or t[2] not in CMP:
            raise BytecodeError(f'{where}: {c!r}: {k} N OP value')
        idv, v = parse_int(t[1], where), parse_int(t[3], where)
        if not 0 <= idv <= 0xFFFF or not 0 <= v <= 0xFFFF:
            raise BytecodeError(f'{where}: {c!r}: id and value 0..65535')
        return (bytes([comb | (0x26 if k == 'item16' else 0x29), 0]) + struct.pack('<H', idv) +
                bytes([CMP.index(t[2]), 0]) + struct.pack('<H', v))
    if k == 'move16':
        if len(t) != 2:
            raise BytecodeError(f'{where}: {c!r}: [not] move16 N')
        idv = parse_int(t[1], where)
        if not 0 <= idv <= 0xFFFF:
            raise BytecodeError(f'{where}: {c!r}: technique 0..65535')
        return bytes([comb | 0x28, 0]) + struct.pack('<H', idv) + bytes([neg, 0])
    if k[:1] == 'p' and k[1:].isdigit():
        if neg or len(t) != 3 or t[1] not in CMP:
            raise BytecodeError(f'{where}: {c!r}: pN OP value')
        ps, v = int(k[1:]), parse_int(t[2], where)
        if ps > 255 or not 0 <= v <= 255:
            raise BytecodeError(f'{where}: {c!r}: pstat 0..255 and value 0..255')
        return bytes([comb | 0x08 | CMP.index(t[1]), 0, ps, v])
    if k in ('stat', 'card', 'item'):
        if neg or len(t) != 4 or t[2] not in CMP:
            raise BytecodeError(f'{where}: {c!r}: {k} N OP value')
        sub = {'stat': 0, 'card': 1, 'item': 4}[k]
        v = parse_int(t[3], where)
        return bytes([comb | 0x20 | sub, 0, parse_int(t[1], where), CMP.index(t[2])]) + struct.pack('<H', v & 0xFFFF)
    if k in ('move', 'cond'):
        if len(t) != 2:
            raise BytecodeError(f'{where}: {c!r}: [not] {k} N')
        return bytes([comb | 0x20 | (2 if k == 'move' else 3), 0, parse_int(t[1], where), neg])
    if k == 'money':
        if neg or len(t) != 3 or t[1] not in CMP:
            raise BytecodeError(f'{where}: {c!r}: money OP value')
        return bytes([comb | 0x25, 0, 0, CMP.index(t[1])]) + struct.pack('<i', parse_int(t[2], where))
    raise BytecodeError(f'{where}: unknown IF condition: {c!r}')


def encode_instr(ins, labels, addr, opts, warn, sizing=False):
    name, where = ins.name, ins.where
    if name == '.byte':
        return bytes(int(x, 16) for x in ins.args)
    if name == '.align':
        return b'\x11' if addr % 2 else b''
    name = ALIASES.get(name, name)
    if name not in BYNAME:
        raise BytecodeError(f'{where}: unknown instruction {ins.name!r}')
    op, fmt = BYNAME[name]
    a = ins.args
    if name not in ('SHOW_TEXTBOX', 'SET_SELECTION') and ins.strings:
        raise BytecodeError(f'{where}: {name} takes no text')
    if name == 'END_SELECTION':
        return b'\x12\x00'
    if op == 0x1A:
        if a:
            raise BytecodeError(f'{where}: SHOW_TEXTBOX takes no arguments (the text goes in quotes below it)')
        if not ins.strings:
            raise BytecodeError(f'{where}: SHOW_TEXTBOX without text')
        return b'\x1a\x00' + encode_text(ins.strings, where, opts, warn, check=not sizing)
    if op == 0x10:
        if not a or not ins.strings:
            raise BytecodeError(f'{where}: SET_SELECTION needs labels and options')
        out = bytes([0x10, len(a)]) + b''.join(enc_field('l', x, labels, where, sizing) for x in a)
        return out + b'\x1a\x00' + encode_text(ins.strings, where, opts, warn, check=not sizing)
    if op in (0x18, 0x93):
        if len(a) < 2:
            raise BytecodeError(f'{where}: {name} {"pN" if op == 0x18 else "wN"}, label, ...')
        return (bytes([op]) + enc_field('p' if op == 0x18 else 'w', a[0], labels, where, sizing) +
                struct.pack('<H', len(a) - 1) + b''.join(enc_field('l', x, labels, where, sizing) for x in a[1:]))
    if op == 0x19:
        if not a:
            raise BytecodeError(f'{where}: IF without conditions')
        return b'\x19\x00' + b''.join(enc_if_clause(c, labels, where, sizing, opts.get('wide'))
                                      for c in a) + b'\x19\x00'
    if op == 0x6B:
        vals = [parse_int(x, where) for x in a]
        if any(not 0 <= v < 0xFF for v in vals):
            raise BytecodeError(f'{where}: DATA: values 0..254 (255 is the terminator)')
        return b'\x6b\x00' + bytes(vals) + b'\xff'
    if op in WIDE and a:
        try:
            idv = parse_int(a[0], where)
        except BytecodeError:
            idv = 0
        if opts.get('wide') or idv > 0xFF:
            op = WIDE[op]; name, fmt = OPS[op]
    fl = [f for f in fmt.split() if f != '_']
    if len(a) != len(fl):
        raise BytecodeError(f'{where}: {name} takes {len(fl)} arguments '
                       f'({", ".join(TYPENAME.get(f, f) for f in fl) or "none"}), not {len(a)}')
    out = bytearray([op]); it = iter(a)
    for f in fmt.split():
        out += b'\x00' if f == '_' else enc_field(f, next(it), labels, where, sizing)
    return bytes(out)


def strip_comment(line):
    out = []; inq = False; i = 0
    while i < len(line):
        ch = line[i]
        if inq and ch == '\\' and i + 1 < len(line):
            out.append(line[i:i + 2]); i += 2; continue
        if ch == '"':
            inq = not inq
        elif ch == ';' and not inq:
            break
        out.append(ch); i += 1
    return ''.join(out).rstrip()


def parse_string_literal(s, where):
    s = s.strip()
    if len(s) < 2 or s[0] != '"' or s[-1] != '"':
        raise BytecodeError(f'{where}: badly quoted string: {s}')
    body = s[1:-1]
    # unescaped quotes inside
    i = 0
    while i < len(body):
        if body[i] == '\\':
            i += 2; continue
        if body[i] == '"':
            raise BytecodeError(f'{where}: unescaped quote (use \\")')
        i += 1
    return body


def parse_script_text(text, fname):
    """Returns (sections, items, meta) where items = [('label', name) | ('ins', Instr)]."""
    items = []; secs = []; meta = {}
    for no, raw in enumerate(text.splitlines(), 1):
        where = f'{fname}:{no}'
        if raw.lstrip().startswith(';@src '):     # a source-map mark (tools/dws --srcmap): the next instruction comes from this line
            meta.setdefault('src', []).append((len(items), raw.strip()[6:].strip())); continue
        line = strip_comment(raw)
        st = line.strip()
        if not st:
            continue
        if st.startswith('"'):
            if not items or items[-1][0] != 'ins' or items[-1][1].name not in (
                    'SHOW_TEXTBOX', 'SET_SELECTION', 'TEXT', 'SELECT'):
                raise BytecodeError(f'{where}: stray string (it must go below SHOW_TEXTBOX or SET_SELECTION)')
            items[-1][1].strings.append(parse_string_literal(st, where)); continue
        m = re.match(r'^([A-Za-z_][\w.]*):\s*(.*)$', st)
        if m and not st.startswith('.'):
            items.append(('label', m.group(1), where)); st = m.group(2).strip()
            if not st:
                continue
        if st.startswith('.'):
            parts = st.split(None, 1); d = parts[0].lower(); rest = parts[1] if len(parts) > 1 else ''
            if d == '.section':
                t = rest.split()
                if len(t) != 2:
                    raise BytecodeError(f'{where}: .section ID LABEL')
                secs.append((parse_int(t[0], where), t[1], where))
            elif d == '.script':
                meta['script'] = rest.strip()
            elif d == '.tail':
                meta['tail'] = rest.strip()
            elif d == '.byte':
                items.append(('ins', Instr('.byte', rest.split(), [], where)))
            elif d == '.align':
                items.append(('ins', Instr('.align', [], [], where)))
            else:
                raise BytecodeError(f'{where}: unknown directive {d}')
            continue
        m = re.match(r'^([A-Za-z_]\w*)\s*(.*)$', st)
        if not m:
            raise BytecodeError(f'{where}: cannot parse: {st}')
        nm, rest = m.group(1).upper(), m.group(2)
        strings = []
        if '"' in rest:
            k = rest.index('"')
            strings.append(parse_string_literal(rest[k:], where)); rest = rest[:k]
        items.append(('ins', Instr(nm, split_args(rest), strings, where)))
    return secs, items, meta


def assemble_script(text, fname, opts=None, warn=None):
    """Assembles the text of a script. Returns (bytes, meta)."""
    opts = opts or {}
    warns = []
    warn = warn or warns.append
    secs, items, meta = parse_script_text(text, fname)
    if not secs and not opts.get('empty_ok', True):
        raise BytecodeError(f'{fname}: there is no .section')
    # no section at all: a script the story does not have (an empty table; patch 0112 runs nothing for any section)
    hdr = 2 + 4 * len(secs) + 2
    labels = {}; addr = hdr; layout = []; item_addr = []
    for it in items:
        item_addr.append(addr)
        if it[0] == 'label':
            if it[1] in labels:
                raise BytecodeError(f'{it[2]}: label {it[1]!r} defined twice')
            labels[it[1]] = addr
        else:
            n = instr_size(it[1], opts, lambda w: None) if it[1].name != '.align' else (addr % 2)
            layout.append((addr, it[1])); addr += n
    if addr > 0xFFFF:
        raise BytecodeError(f'{fname}: the script takes {addr:#x} bytes; offsets are u16')
    item_addr.append(addr)
    if meta.get('src'):
        meta['srcmap'] = [(item_addr[i], where) for i, where in meta.pop('src')]
    out = bytearray(struct.pack('<H', hdr))
    for sid, lab, where in secs:
        if lab not in labels:
            raise BytecodeError(f'{where}: label {lab!r} not defined')
        out += struct.pack('<HH', sid, labels[lab])
    out += b'\xff\xff'
    opts = dict(opts); opts['_ctx'] = {}; label_addrs = set(labels.values())
    m = re.match(r'script_(\d+)', os.path.basename(fname))
    script_no = int(m.group(1)) if m else None
    sec_at = {labels[lab]: sid for sid, lab, _ in secs}
    sec = None; table = []; collecting = False; entry = None
    for a, ins in layout:
        assert len(out) == a
        if a in sec_at:            # a section starts: a run of JUMP_TOs first is a table of entries (MAPHEAD's, the cups')
            sec, table, collecting, entry = sec_at[a], [], True, None
        if collecting and ALIASES.get(ins.name, ins.name) == 'JUMP_TO' and ins.args and ins.args[-1] in labels:
            table.append(labels[ins.args[-1]])
        else:
            collecting = False
            if a in table: entry = table.index(a)
        if a in label_addrs:
            opts['_ctx'] = {}      # can be reached from elsewhere: speaker unknown
        update_text_ctx(ins, opts)
        opts['_ctx']['unpacked'] = unpacked_entry(script_no, sec, entry)
        b = encode_instr(ins, labels, a, opts, warn)
        check_alignment(b, a, ins, warn)
        out += b
    if not opts.get('quiet'):
        for w in warns:
            print('warning:', w, file=sys.stderr)
    return bytes(out), meta


def needs_even(op):
    """Instructions with 16/32-bit fields (all at an even offset from the opcode)."""
    return op in (0x10, 0x18, 0x19, 0x93) or (op in OPS and any(FSIZE[f] >= 2 for f in OPS[op][1].split()))


def check_alignment(b, a, ins, warn):
    """The interpreter reads u16s with lhu: at an odd address the console hangs."""
    if ins.name in ('.byte', '.align') or not b:
        return
    if a % 2 and needs_even(b[0]):
        raise BytecodeError(f'{ins.where}: {ins.name} starts at an odd offset ({a:#x}) and has 16-bit fields '
                       '(the interpreter reads them with lhu); put .align before it')


# --------------------------------------------------------------------------
# Disassembly of a whole script
def disassemble_script(e, title, extra_header=(), tailname=None):
    """Returns (text, end of the useful content, statistics). A script is read with one-byte letters (patch 0145) and with two-byte units only,
    and the reading that leaves fewer instructions as `.byte` wins (two-byte units on a tie): a disc's text, a fan translation's included, may
    have units that start in 0x20..0x7e."""
    global READ_PACKED
    was, best, err = READ_PACKED, None, None
    try:
        for mode in ((False, True) if was else (False,)):
            READ_PACKED = mode
            try:
                r = _disassemble_script(e, title, extra_header, tailname)
            except (BytecodeError, IndexError, KeyError) as ex:
                err = err or ex; continue
            if best is None or r[2]['raw'] < best[2]['raw']:
                best = r
    finally:
        READ_PACKED = was
    if best is None:
        raise err
    return best


def _disassemble_script(e, title, extra_header=(), tailname=None):
    hdr, secs, ins, end, targets = sweep(e)
    # labels
    labels = {}; extra = {}; seclab = []; used = set()
    for i, (sid, off) in enumerate(secs):
        nm = 'sec%d' % sid
        if nm in used:
            # id repeated in the table: getScriptSection takes the first; this one is never used
            nm = 'sec%d_dup%d' % (sid, i)
        if nm not in used:
            used.add(nm)
            if off not in labels:
                labels[off] = nm
            else:
                extra.setdefault(off, []).append(nm)
        seclab.append((sid, nm))
    k = 0
    for t in sorted(targets):
        if t not in labels:
            k += 1; labels[t] = 'L%d' % k
    starts = {o for o, _ in ins}
    bad = [t for t in list(targets) + [o for _, o in secs] if t not in starts]
    if bad:
        raise BytecodeError(f'{title}: targets outside an instruction: {", ".join(hex(x) for x in bad[:5])}')
    out = [f'; {title}', f'; useful content: {end} bytes (0x0000-{end:#06x}); header {hdr:#x}']
    out += ['; ' + x for x in extra_header]
    out.append('; generated by tools/dws/bytecode/__main__.py; see docs/mods/scripts.md')
    if tailname:
        out.append(f'.tail {tailname}')
    out.append('')
    for sid, nm in seclab:
        out.append(f'.section {sid} {nm}')
    stats = {'ins': 0, 'raw': 0, 'text': 0}
    prev = None
    for o, n in ins:
        if o in labels:
            out.append('')
            out.append(f'{labels[o]}:'.ljust(40) + f'; {o:#06x}')
            for x in extra.get(o, []):
                out.append(f'{x}:')
        raw = e[o:o + n]
        try:
            lines, com = dis_instr(e, o, n, labels, prev)
            # check that it gives back the same bytes
            ins_obj = Instr(lines[0].split(None, 1)[0], split_args(lines[0].split(None, 1)[1]) if ' ' in lines[0] else [],
                            [parse_string_literal(s, title) for s in lines[1:]], title)
            inv = {v: k2 for k2, v in labels.items()}
            back = encode_instr(ins_obj, inv, o, {}, lambda w: None)
            if back != raw:     # a text stored with one-byte letters (asm --pack-ascii) gives the same bytes packed
                back = encode_instr(ins_obj, inv, o, {'pack_ascii': True}, lambda w: None)
            if back != raw:
                raise BytecodeError('not reversible')
        except (BytecodeError, IndexError, KeyError) as ex:
            lines, com = ['.byte ' + raw.hex(' ')], ['not representable: %s' % ex]
            stats['raw'] += 1
        stats['ins'] += 1
        if e[o] in (0x1A, 0x10):
            stats['text'] += 1
        c = f'; {o:#06x}' + (' ' + ', '.join(com) if com else '')
        out.append(('    ' + lines[0]).ljust(40) + c)
        for s in lines[1:]:
            out.append('    ' + s)
        prev = e[o]
    out.append('')
    return '\n'.join(out), end, stats


# --------------------------------------------------------------------------
# DG.SCN container
def container_entries(d):
    """Table of u32 offsets at the start of DG.SCN: N entries + sentinel = file size."""
    offs = []; p = 0
    while p + 4 <= SECTOR:
        o = struct.unpack_from('<I', d, p)[0]
        if o % SECTOR or o < SECTOR or (offs and o < offs[-1]) or o > len(d):
            break
        offs.append(o); p += 4
        if o == len(d):
            break
    if len(offs) < 2 or offs[-1] != len(d):
        raise BytecodeError('does not look like a DG.SCN container (offset table)')
    return offs


def is_container(d):
    return len(d) >= SECTOR and struct.unpack_from('<I', d, 0)[0] == SECTOR


def screens_by_script(mh):
    """In MAPHEAD, the section of each screen does SET_SCRIPT script, screen."""
    out = {}
    try:
        hdr, secs, ins, end, _ = sweep(mh)
    except BytecodeError:
        return out
    for sid, off in secs:
        if sid > 254:
            continue
        p = off
        for _ in range(64):
            n, _t = instr_length(mh, p)
            if n is None:
                break
            if mh[p] == 0xFB:
                out.setdefault(u16(mh, p + 2), []).append(sid); break
            if mh[p] in (0xFE, 0xFF):
                break
            p += n
    return out


def cmd_dis(src, outdir):
    d = open(src, 'rb').read()
    os.makedirs(outdir, exist_ok=True)
    if not is_container(d):
        txt, end, st = disassemble_script(d, f'{os.path.basename(src)} ({len(d)} bytes)')
        name = os.path.splitext(os.path.basename(src))[0].lower() + '.scn.txt'
        if end != len(d):
            tail = name.replace('.scn.txt', '.tail.bin')
            open(os.path.join(outdir, tail), 'wb').write(d[end:])
            txt = txt.replace('; generated', f'.tail {tail}\n; generated', 1)
        open(os.path.join(outdir, name), 'w', encoding='utf-8').write(txt)
        print(f'{name}: {st["ins"]} instructions, {st["text"]} texts, {st["raw"]} not represented')
        return
    offs = container_entries(d)
    mhpath = os.path.join(os.path.dirname(src), 'MAPHEAD.SCN')
    scr = screens_by_script(open(mhpath, 'rb').read()) if os.path.exists(mhpath) else {}
    mapn = names()['m']
    open(os.path.join(outdir, 'header.bin'), 'wb').write(d[:offs[0]])
    lst = ['; index of the DG.SCN container for tools/dws/bytecode/__main__.py asm',
           f'.container {os.path.basename(src)} {len(d)}',
           '.header header.bin   ; first sector: table of u32 offsets + garbage (kept)',
           '; .entry N file sectors_of_the_original_slot']
    tot = {'ins': 0, 'text': 0, 'raw': 0}; useful = 0
    for n in range(len(offs) - 1):
        e = d[offs[n]:offs[n + 1]]
        fname = f'script_{n:03d}.scn.txt'
        tailname = f'script_{n:03d}.tail.bin'
        hdrx = [f'DG.SCN entry {n}: slot {offs[n]:#x}, {len(e) // SECTOR} sectors ({len(e)} bytes)']
        if n == 0:
            hdrx.append('copy of MAPHEAD.SCN; the game never reads it (getScript(0) uses MAPHEAD_SCRIPT_BUFFER)')
        elif n in scr:
            hdrx.append('screens that load it (SET_SCRIPT in MAPHEAD): ' +
                        ', '.join(f'{s} {mapn.get(s, "")}'.strip() for s in sorted(scr[n])))
        txt, end, st = disassemble_script(e, f'script {n}', hdrx, tailname)
        hdr_line = f'; garbage tail after the end: {len(e) - end} bytes in {tailname} (kept as is)'
        txt = txt.replace('; generated', hdr_line + '\n; generated', 1)
        open(os.path.join(outdir, fname), 'w', encoding='utf-8').write(txt)
        open(os.path.join(outdir, tailname), 'wb').write(e[end:])
        lst.append(f'.entry {n} {fname} {len(e) // SECTOR}')
        for k in tot:
            tot[k] += st[k]
        useful += end
    open(os.path.join(outdir, 'dg.scn.lst'), 'w').write('\n'.join(lst) + '\n')
    print(f'{len(offs) - 1} entries in {outdir}: {tot["ins"]} instructions, {tot["text"]} texts, '
          f'{tot["raw"]} not represented; {useful} useful bytes of {len(d)}')


def read_lst(path):
    ents = []; meta = {}
    for no, raw in enumerate(open(path, encoding='utf-8').read().splitlines(), 1):
        line = strip_comment(raw).strip()
        if not line:
            continue
        t = line.split()
        if t[0] == '.container':
            meta['name'], meta['size'] = t[1], int(t[2])
        elif t[0] in ('.header', '.cabecera'):
            meta['cabecera'] = t[1]
        elif t[0] in ('.entry', '.entrada'):
            ents.append((int(t[1]), t[2], int(t[3])))
        else:
            raise BytecodeError(f'{path}:{no}: cannot parse {line!r}')
    if [n for n, _, _ in ents] != list(range(len(ents))):
        raise BytecodeError(f'{path}: entries must go 0, 1, 2... without gaps')
    return meta, ents


def build_container(meta, blobs, opts, log=print):
    """blobs = [(content, tail, original_sectors, name)]. Returns the DG.SCN."""
    def layout(compact, shrink0):
        bodies = []
        for i, (c, tail, sec, name) in enumerate(blobs):
            slot = sec * SECTOR
            if i == 0 and shrink0:
                body = c[:SECTOR]; slot = SECTOR
            elif compact or len(c) > slot:
                slot = max(SECTOR, -(-len(c) // SECTOR) * SECTOR); body = c
            else:
                orig_len = slot - len(tail)
                body = c + (tail if len(c) <= orig_len else tail[len(c) - orig_len:])
            body = body[:slot] if i == 0 and shrink0 else body
            bodies.append(body + b'\0' * (slot - len(body)))
        return bodies
    for i, (c, tail, sec, name) in enumerate(blobs):
        if i and len(c) > MAP_SCRIPT_MAX:
            raise BytecodeError(f'{name}: {len(c)} bytes; an entry cannot exceed {MAP_SCRIPT_MAX} '
                           '(MAP_SCRIPT_BUFFER; SCRIPT_STATE follows it)')
    hdr = bytearray(open(meta['cabecera_path'], 'rb').read())
    plans = [(False, False), (False, True), (True, True)]
    if opts.get('compact'):
        plans = [(True, True)]
    for compact, shrink0 in plans:          # the first layout that fits the original size; else the most compact one grows
        bodies = layout(compact, shrink0)
        total = len(hdr) + sum(len(b) for b in bodies)
        if total <= meta['size']:
            break
    else:
        if not opts.get('grow'):
            raise BytecodeError(f'DG.SCN would take {total} bytes, more than the original ({meta["size"]}) even when compacted; '
                           'only a disc built with --relayout can carry a larger DG.SCN (an executable built from decomp: '
                           'story-build/build --exe mods|species|story-state, or tools/build-full.sh, which do it on their own; '
                           'bytecode asm --grow by hand); see docs/mods/scripts.md "If DG.SCN grows"')
        log(f'note: DG.SCN grows to {total} bytes, {total - meta["size"]} past the original {meta["size"]} '
            f'({-(-(total - meta["size"]) // SECTOR)} more sectors): the disc is relaid out (build-disc.py --relayout '
            'moves the files after it and rewrites FILE_OFFSET_TABLE; the game finds DG.SCN by name). Save states of '
            'another disc do not work on it')
        big = max(range(1, len(blobs)), key=lambda i: len(blobs[i][0]))
        log(f'note: the largest script is {blobs[big][3]}, {len(blobs[big][0])} bytes of the {MAP_SCRIPT_MAX} each one may take '
            '(MAP_SCRIPT_BUFFER; DG.SCN as a whole has no limit)')
    if (compact, shrink0) != (False, False):
        log(f'warning: had to rearrange: {"tails dropped, " if compact else ""}'
            f'{"entry 0 shrunk to 1 sector" if shrink0 else ""}')
    offs = []; p = len(hdr)
    for b in bodies:
        offs.append(p); p += len(b)
    offs.append(p)
    if 4 * len(offs) > len(hdr):
        raise BytecodeError('the offset table does not fit in the header')
    for i, o in enumerate(offs):
        struct.pack_into('<I', hdr, 4 * i, o)
    out = bytes(hdr) + b''.join(bodies)
    for i, (b, (c, tail, sec, name)) in enumerate(zip(bodies, blobs)):
        if len(b) != sec * SECTOR:
            log(f'  {name}: slot {sec} → {len(b) // SECTOR} sectors')
    if len(out) < meta['size']:
        log(f'note: DG.SCN ends up at {len(out)} bytes ({meta["size"]} the original); build-disc.py pads it')
    return out


def cmd_asm(src, dst, opts):
    if os.path.isdir(src):
        lst = os.path.join(src, 'dg.scn.lst')
        if not os.path.exists(lst):
            txts = [f for f in os.listdir(src) if f.endswith('.scn.txt')]
            if len(txts) == 1:
                return cmd_asm(os.path.join(src, txts[0]), dst, opts)
            raise BytecodeError(f'{src}: no dg.scn.lst')
        meta, ents = read_lst(lst)
        meta['cabecera_path'] = os.path.join(src, meta['cabecera'])
        blobs = []; srcmap = {}
        for n, fname, sec in ents:
            path = os.path.join(src, fname)
            c, m = assemble_script(open(path, encoding='utf-8').read(), fname, opts)
            if m.get('srcmap'): srcmap[n] = m['srcmap']
            tail = open(os.path.join(src, m['tail']), 'rb').read() if m.get('tail') else b''
            blobs.append((c, tail, sec, fname))
        out = build_container(meta, blobs, opts)
    else:
        out, m = assemble_script(open(src, encoding='utf-8').read(), os.path.basename(src), opts)
        srcmap = {'maphead' if 'maphead' in os.path.basename(src).lower() else 0: m['srcmap']} if m.get('srcmap') else {}
        if 'maphead' in os.path.basename(src).lower():
            limit = opts.get('maphead_max') or MAPHEAD_MAX     # the mod executables hold 0x8000 (patch 0091; tools/dws passes it)
            if len(out) > limit:
                raise BytecodeError(f'MAPHEAD: {len(out)} bytes; the MAPHEAD_SCRIPT_BUFFER buffer is {limit}')
            if len(out) > 24686:
                print(f'warning: MAPHEAD grows to {len(out)} bytes (same 13 sectors; '
                      'build-disc.py will warn but the LBAs do not change)', file=sys.stderr)
        if m.get('tail') and opts.get('with_tail'):
            out += open(os.path.join(os.path.dirname(src), m['tail']), 'rb').read()
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    open(dst, 'wb').write(out)
    if opts.get('srcmap'):                       # {script: [[offset in the script, "file:line"], ...]}: kept out of the game data
        import json
        json.dump({str(k): v for k, v in srcmap.items()}, open(opts['srcmap'], 'w'), indent=0)
    print(f'{dst}: {len(out)} bytes')


# --------------------------------------------------------------------------
# The commands as functions (the story build and tools/derive call them in their own process: no `python3 tools/dws/bytecode/__main__.py`)
# rule: every option has its command-line default; SCNASM_PACK_ASCII is read by the command line only (main), a caller
# passes pack_ascii itself
ASM_DEFAULTS = {'srcmap': None, 'strip_accents': False, 'font': 'mods', 'compact': False, 'font_glyphs': None,
                'font_name': 'original', 'pack_ascii': False, 'grow': False, 'with_tail': False, 'wide': False,
                'maphead_max': None}


class Done:
    """What a command did, as its process would have: code (0, or 1 on an error), out (its stdout), err (its stderr)."""
    def __init__(self, code, out, err):
        self.returncode, self.stdout, self.stderr = code, out, err


def _captured(f, *a):
    import contextlib, io
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            f(*a)
        except BytecodeError as ex:
            print(f'error: {ex}', file=sys.stderr); code = 1
    return Done(code, out.getvalue(), err.getvalue())


def asm(src, dst, opts=None, **kw):
    """`tools/dws/bytecode/__main__.py asm SRC DST [options]` in this process: opts (and kw) are the options by their names in ASM_DEFAULTS
    (pack_ascii=True is --pack-ascii). -> Done; its output is captured, not printed."""
    o = dict(ASM_DEFAULTS); o.update(opts or {}); o.update(kw)
    return _captured(cmd_asm, src, dst, o)


def dis(src, outdir):
    """`tools/dws/bytecode/__main__.py dis SRC DIR` in this process. -> Done (output captured)."""
    return _captured(cmd_dis, src, outdir)


def cmd_check(paths):
    ok = True
    for src in paths:
        d = open(src, 'rb').read()
        with tempfile.TemporaryDirectory(dir=os.environ.get('DWS_BYTECODE_TMP')) as tmp:
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()) as so:
                cmd_dis(src, tmp)
            print(so.getvalue().strip())
            raws = 0
            for f in sorted(os.listdir(tmp)):
                if f.endswith('.scn.txt'):
                    raws += sum(1 for line in open(os.path.join(tmp, f)) if line.lstrip().startswith('.byte'))
            out = os.path.join(tmp, 'out.bin')
            opts = {'quiet': True, 'with_tail': True}
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_asm(tmp, out, opts)
            r = open(out, 'rb').read()
            same = r == d
            ok &= same
            if is_container(d):
                offs = container_entries(d); offs2 = container_entries(r) if is_container(r) else []
                eq = sum(1 for i in range(len(offs) - 1) if offs2[i:i + 2] == offs[i:i + 2] and
                         r[offs[i]:offs[i + 1]] == d[offs[i]:offs[i + 1]])
                print(f'{src}: {"IDENTICAL" if same else "DIFFERENT"} byte by byte ({len(r)} bytes); '
                      f'identical entries {eq}/{len(offs) - 1}; instructions as .byte: {raws}')
            else:
                print(f'{src}: {"IDENTICAL" if same else "DIFFERENT"} byte by byte ({len(r)} bytes); '
                      f'instructions as .byte: {raws}')
    return ok


# --------------------------------------------------------------------------
# Free triggers and pstats
# The ones used by the C code (not by scripts), from grepping decomp/src
C_TRIGGERS = (set(range(0, 5)) | set(range(5, 15)) | set(range(15, 42)) | {44, 45, 46, 47, 48, 49, 50} |
              set(range(200, 313)) | set(range(364, 383)) | set(range(384, 512)) | set(range(512, 575)) |
              {350, 640} | set(range(650, 717)))
C_PSTATS = {0, 1, 2, 3, 4, 5, 6, 28, 29, 30, 31, 121, 122, 200} | set(range(243, 256))


def scan_usage(blob):
    trig, pst = set(), set()
    hdr, secs, ins, end, _ = sweep(blob)
    for o, n in ins:
        op = blob[o]
        if op in OPS:
            q = o + 1
            for f in OPS[op][1].split():
                v = read_field(blob, q, f)
                if f == 't':
                    trig.add(v)
                if f == 'p':
                    span = 4 if op in (0x25, 0x37, 0x38, 0x39, 0x2C) else 2 if op == 0x58 else 1
                    pst.update(range(v, v + span))
                q += FSIZE[f]
        elif op == 0x18:
            pst.add(blob[o + 1])
        elif op == 0x19:
            q = o + 2
            while True:
                cop = blob[q]; q += 2
                if cop == 0x19:
                    break
                if cop & 0x38 == 0:
                    trig.add(u16(blob, q))
                elif cop & 0x38 == 8:
                    pst.add(blob[q])
                q += IF_ARGLEN(cop)
        if op in (0x1A, 0x10):
            p = o + 2 if op == 0x1A else o + 4 + 2 * blob[o + 1]
            while True:
                c = blob[p]
                if c == 3:
                    p += 4; continue
                if c in (0x04, 0x07, 0x08, 0x09, 0x11, 0x12):
                    pst.add(blob[p + 1])
                if c == 0x0D and blob[p + 2] == 0:
                    break
                p += 2
    return trig, pst


def ranges(xs):
    xs = sorted(xs); out = []; i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
            j += 1
        out.append(str(xs[i]) if i == j else f'{xs[i]}-{xs[j]}'); i = j + 1
    return ', '.join(out)


def cmd_libres(dg, mh):
    d = open(dg, 'rb').read(); m = open(mh, 'rb').read()
    offs = container_entries(d)
    trig, pst = scan_usage(m)
    for n in range(1, len(offs) - 1):
        t, p = scan_usage(d[offs[n]:offs[n + 1]]); trig |= t; pst |= p
    ft = sorted(set(range(800)) - trig - C_TRIGGERS)
    fp = sorted(set(range(256)) - pst - C_PSTATS)
    print(f'triggers used by scripts: {len(trig)}; by the C code: {len(C_TRIGGERS)}')
    print(f'free triggers ({len(ft)}): {ranges(ft)}')
    print(f'free pstats ({len(fp)}): {ranges(fp)}')
    print(f'  of those, saved to the memory card (0-34): {ranges([x for x in fp if x < 35]) or "none"}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('dis', help='disassemble DG.SCN or a single script'); a.add_argument('src'); a.add_argument('outdir')
    a = sp.add_parser('asm', help='assemble a directory or a single .scn.txt'); a.add_argument('src'); a.add_argument('dst')
    a.add_argument('--srcmap', help='write the source map (the `;@src FILE:LINE` marks of tools/dws --srcmap) as JSON: script -> [[offset, "file:line"]]')
    a.add_argument('--strip-accents', dest='strip_accents', action='store_true', help='strip accents (á→a, ñ→n, drops ¿¡)')
    a.add_argument('--font', choices=('mods', 'original'), default='mods',
                   help='mods (default): á é ñ ¿ ¡ ç · « »... use the mod executable\'s extra glyphs; '
                        'original: reject them (the original executable has no glyphs for them)')
    a.add_argument('--font-name', dest='font_name', choices=('original', 'a', 'b'), default='original',
                   help='the executable\'s font (docs/mods/font.md "Fonts"): a and b measure lines with their own advances and '
                        'pack letters one byte a row (up to fontgen.ROW_BYTES bytes)')
    a.add_argument('--font-glyphs', dest='font_glyphs', type=int, default=None, metavar='N',
                   help='with --font mods: the executable has only the first N extra glyphs (tools/fontgen.py glyphs EXE_DIR); '
                        'a character past them is an error (default: all of tools/font/extra.txt)')
    a.add_argument('--pack-ascii', dest='pack_ascii', action='store_true',
                   help='store letters, digits, spaces and . , : ; ? ! \' " + - = as one byte in the texts (patch 0145; the mod executable '
                        'expands them as it reads; a text always keeps an even length). SCNASM_PACK_ASCII=1 in the environment does the same '
                        '(the story build and build-full.sh call this tool)')
    a.add_argument('--maphead-max', dest='maphead_max', type=lambda s: int(s, 0), default=None,
                   help='size limit of MAPHEAD.SCN (default 0x61A8, the original executable\'s buffer; the mod executables hold 0x8000, patch 0091)')
    a.add_argument('--compact', dest='compact', action='store_true', help='drop the garbage tails and shrink entry 0')
    a.add_argument('--grow', dest='grow', action='store_true', help='let DG.SCN grow past the original size when it does not fit (a --relayout disc)')
    a.add_argument('--with-tail', dest='with_tail', action='store_true', help='(single script) append the garbage tail')
    a.add_argument('--wide', action='store_true',
                   help='always use the wide (u16 id) opcodes 80-8B and IF forms; they need the mod executable')
    a = sp.add_parser('check', help='disassemble, assemble and compare byte by byte'); a.add_argument('src', nargs='+')
    a = sp.add_parser('libres', help='list free triggers and pstats'); a.add_argument('dg'); a.add_argument('mh')
    args = ap.parse_args()
    try:
        if args.cmd == 'dis':
            cmd_dis(args.src, args.outdir)
        elif args.cmd == 'asm':
            cmd_asm(args.src, args.dst, {'srcmap': args.srcmap, 'strip_accents': args.strip_accents, 'font': args.font, 'compact': args.compact,
                                         'font_glyphs': args.font_glyphs, 'font_name': args.font_name,
                                         'pack_ascii': args.pack_ascii or os.environ.get('SCNASM_PACK_ASCII') == '1',
                                         'grow': args.grow, 'with_tail': args.with_tail, 'wide': args.wide,
                                         'maphead_max': args.maphead_max})
        elif args.cmd == 'check':
            sys.exit(0 if cmd_check(args.src) else 1)
        elif args.cmd == 'libres':
            cmd_libres(args.dg, args.mh)
    except BytecodeError as ex:
        sys.exit(f'error: {ex}')


if __name__ == '__main__':
    main()
