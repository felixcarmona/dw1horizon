#!/usr/bin/env python3
"""Tests of the DWS compiler (tools/dws/): python3 tools/test_dws.py  (unittest; also runs under pytest).

- every DWS example in tools/dws/examples/ compiles to the golden bytes of the retired quest compiler;
- diagnostics (line numbers, hints), allocation and collisions, tiers, formatter;
- the text extractor and the lossless keyed round trip on real scripts (needs extracted/)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import atexit, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from dws import build as B, textx
from dws.diag import DwsError
from dws.fmt import format_source
from dws.alloc import Allocator

TMP = tempfile.mkdtemp(prefix='dws-test-')
atexit.register(shutil.rmtree, TMP, ignore_errors=True)
HAVE_EXTRACTED = os.path.exists(os.path.join(ROOT, 'extracted/SCN/DG.SCN'))


def original_story():
    """The original-disc fixture; the committed story also contains reviewed Horizon edits (authored.json)."""
    from dws import basebuild as BB
    if not hasattr(original_story, 'path'):
        original_story.path = tempfile.mkdtemp(prefix='.base-repro-', dir=os.path.join(ROOT, 'story'))
        atexit.register(shutil.rmtree, original_story.path, ignore_errors=True)
        BB.ensure_base(original_story.path, refresh=True, log=lambda m: None)
    return original_story.path


def pack(out, comp):
    d = {'DG': open(out, 'rb').read(), 'MAPHEAD': open(comp.maphead, 'rb').read() if comp.maphead else None}
    d.update({rel: open(p, 'rb').read() for rel, p in comp.maps.items()})
    return d


def dws_bytes(files, exe='original', **kw):
    prog = B.compile_sources(files, exe, **kw)
    out = os.path.join(tempfile.mkdtemp(prefix='d-', dir=TMP), 'DG.SCN')
    B.assemble(prog, out, exe)
    return pack(out, prog.b), prog


GOLDEN = {   # sha256 of what each example compiled to with the retired quest compiler (original executable)
    'dev-save': {
        'DG': '9cab489610c647944fa444d888b7dbb2283f337379e00b28e7e242dbbce7121a',
    },
    'font-accents': {
        'DG': '072f5429c6261e2188b1d3a2f6630073275934e6562ee33feee67947390c938a',
    },
    'forest-challenge': {   # DG pinned after the change that made a 32-character row now wraps (backend.MAX_UNITS: it ran on into the next row)
        'DG': 'f86e3ac12f38a54142e9c68f145f283725c2cda32f5493f01690ff3443fedf36',
    },
    'forest-garurumon': {
        'DG': '55aed903bfec06f31f269dd60dfd4c8bb345425c4e4a955588bc2420e7ab32f3',
        'MAPHEAD': 'dcf8c29b3b839911cb6ef68042ab958099aff5b3fc30b4dd666f88102c9a5896',
        'MAP/MAP1/MAYO01.MAP': 'c18900d5a6b8163f8e9c9d5cf6675605eb6c18036c5a1a553fcb21aaa7f57fac',
    },
    'jijimon-errand': {     # DG pinned after the change that made a 32-character row now wraps (backend.MAX_UNITS: it ran on into the next row)
        'DG': '0e17ec8f1f615c447350b8ed65ef8eebe1cef67591cec1fa91a00e4524c8f48c',
    },
    'jungle-newcomer': {
        'DG': 'e9b93ff819483db1727d2c37c0000e2cc17356038b2b598bda917bc2394f6821',
        'MAPHEAD': '6288c380c9bb7ef9fd233c30d2f445fde690b6443812c7fbc1482fea2737cb46',
        'MAP/MAP1/TROP02.MAP': 'ee387fd5095225cc5b8b22d0d0906e95c705ab901315c7fb774b8eb878d56e1b',
    },
    'new-house-story': {
        'DG': '65a21396fd948c0688c21cc23fb2eb06d93101222080fd22206376de2f05d79b',
        'MAPHEAD': 'c0714991826691245d4574fadd21865384df3712762fa951dd8d856f2e91e2d8',
    },
    'species-180': {
        'DG': '83b78b2ca7720b75b3fd26509bf3d4a77e2e2c1db969c5b951a5a4b4c8630787',
        'MAPHEAD': 'e9edad1de2d4fea3d84dae97a971a6ddc51d97146aa1ac4875da2aa9b0bb0d05',
        'MAP/MAP1/MAYO03.MAP': 'c0f5d9ebceb02fc28a4c8c3f9039c4b963589d9e461dc33d5febd81955848675',
    },
    'tokomon-sparring': {
        'DG': '6f3a8f73d7750a323d610cec7548cc1d7b32a0a9bdb6fa1d6bdee51c0d4e3635',
    },
}
EXAMPLES = os.path.join(ROOT, 'tools/dws/examples')


class Examples(unittest.TestCase):
    """Every example compiles to the bytes the retired quest compiler produced (the bank form and the literal form)."""


def make_example(name):
    def t(self):
        got, _ = dws_bytes([os.path.join(EXAMPLES, name + '.dws')])
        got = {k: v for k, v in got.items() if v is not None}
        want = GOLDEN[name]
        self.assertEqual(sorted(got), sorted(want))
        for k in want:
            self.assertEqual(hashlib.sha256(got[k]).hexdigest(), want[k], f'{name}: {k} differs')
    return t


for _n in GOLDEN:
    setattr(Examples, f'test_{_n.replace("-", "_")}', make_example(_n))


def compile_src(src, exe='original', bank=None, **kw):
    d = tempfile.mkdtemp(prefix='s-', dir=TMP); p = os.path.join(d, 'x.dws'); open(p, 'w').write(src)
    if bank is not None: json.dump(bank, open(os.path.join(d, 'x.en.json'), 'w'))
    return B.compile_sources([p], exe, **kw)


def errors_of(src, **kw):
    try:
        compile_src(src, **kw)
    except B.DwsErrors as e:
        return [x.render() for x in e.errors]
    return []


class BackendUnits(unittest.TestCase):
    """The patching back end (tools/dws/backend.py): text, font, names, section insertion."""
    def test_plain_strips_accents_on_the_original_font(self):
        from dws import backend as BE
        BE.set_font('original')
        self.assertEqual(BE.plain('¿Qué tal, señor?'), 'Que tal, senor?')
        self.assertEqual(BE.plain('Wait… so—that ♪'), 'Wait... so-that ')        # the punctuation's plain forms
        BE.FONT_GLYPHS_GIVEN = 44; BE.set_font('mods')
        self.assertEqual(BE.plain('¿Qué? Wait… (x)'), '¿Qué? Wait… (x)')
        BE.FONT_GLYPHS_GIVEN = 29; BE.set_font('mods')                       # an executable built without the extra glyphs
        self.assertEqual(BE.plain('¿Qué? Wait…'), '¿Qué? Wait...')
        BE.FONT_GLYPHS_GIVEN = None; BE.set_font('original')

    def test_wrap_pages_and_quote(self):
        from dws import backend as BE
        BE.FONT['extra'] = False
        pages = BE.wrap('word ' * 60, 3)
        self.assertGreater(len(pages), 1); self.assertTrue(all(len(p) <= 3 for p in pages))
        self.assertTrue(all(BE.text_px(l) <= BE.MAX_PX for p in pages for l in p))
        self.assertEqual(BE.quote('a "b" \\c'), '"a \\"b\\" \\\\c"')

    def test_colour_codes_take_row_units(self):
        """A colour change draws nothing but takes a 2-byte unit of the 64-byte row (showTextbox copies it): this row of
        31 letters ran on into the next one in the game ("full powerB", Toy Town). A button glyph is one unit."""
        from dws import backend as BE
        from dws import bytecode as bytecode
        row = 'go at {color 6}×{color 1} to throw at full power!'
        self.assertEqual(BE.text_units(row), 33); self.assertFalse(BE.fits(row))
        self.assertEqual(BE.text_units('Use {color 6}× {color 1}to'), 10)
        self.assertEqual(BE.text_units('{player} won'), 12)
        self.assertTrue(all(BE.text_units(r) <= BE.MAX_UNITS for p in BE.wrap('let go at {color 6}×{color 1} ' * 9, 3) for r in p))
        line = bytecode.text_units('a{color 6}×{color 1}b', 'test', {}, print)[0]
        self.assertEqual(bytecode.line_metrics(line)[0], 5)

    def test_button_glyphs_as_the_font_draws_them(self):
        """The US font draws 81A2 as × and 817E as △ (Shift-JIS says the reverse): bytecode encodes and decodes the buttons as
        drawn, the executable's bank hands gen_text the Shift-JIS label, and text/ours shows the button the US line shows."""
        from dws import bytecode as bytecode; import fontgen
        from localize.executable import bank
        self.assertEqual([bytecode.CHAR2SJIS[c] for c in '×△○□'], [0x81A2, 0x817E, 0x819B, 0x81A0])
        self.assertEqual(bytecode.SJIS2CHAR[0x81A2], '×'); self.assertEqual('Press × or △'.translate(bank.SJIS_LABELS), 'Press △ or ×')
        if os.path.exists(fontgen.EXE):
            _, glyphs = fontgen.base_font()
            x, tri = glyphs[0x81A2][1], glyphs[0x817E][1]
            self.assertEqual((x[1][0], x[1][4], x[5][4]), ('#', '.', '#'))          # corners at the top, crossing in the middle
            self.assertEqual((tri[1][0], tri[1][4], tri[9][0:9]), ('.', '#', '#########'))   # apex at the top, a base row
        us = os.path.join(ROOT, 'text/us/dialogue.json')
        if not os.path.exists(us): return
        us = json.load(open(us, encoding='utf-8')); buttons = lambda v: re.findall('[×△○□]', json.dumps(v, ensure_ascii=False))
        own = {'s176.sec7.u1': ['□', '○']}          # Punimon's tips, from the Japanese: □ all, hold ○ for tens (ALT_BUTTON)
        for p in glob.glob(os.path.join(ROOT, 'text/ours/dialogue/*.json')):
            for k, v in json.load(open(p, encoding='utf-8')).items():
                if k.startswith('_') or not buttons(v): continue
                self.assertEqual(buttons(v), own.get(k, buttons(us.get(k))), f'{os.path.basename(p)} {k}')

    def test_one_byte_script_text(self):
        """Patch 0145: `asm --pack-ascii` stores letters, digits, space and . , : ; ? ! ' " + - = as one byte in a script's text. The reader
        takes both forms, a text keeps an even length (the next instruction's 16-bit fields are read with lhu), the packed set is
        the one script_textbox.c expands (PACKED_CODES / PACKED_ASCII of patch 0100), and what is not packed stays two bytes."""
        from dws import bytecode as bytecode; import fontgen
        enc = lambda s, pack: bytecode.encode_text([s], 't', {'pack_ascii': pack, 'font': 'mods'}, lambda w: None, check=False)
        two, one = enc('Hello, world! {color 6}a\u00f1o{color 1} 42', False), enc('Hello, world! {color 6}a\u00f1o{color 1} 42', True)
        self.assertLess(len(one), len(two)); self.assertEqual(len(one) % 2, 0); self.assertEqual(len(two) % 2, 0)
        self.assertEqual(bytecode.decode_text(one + b'\0\0', 0)[0], bytecode.decode_text(two + b'\0\0', 0)[0])
        self.assertEqual(bytecode.decode_text_len(one + b'\0\0', 0)[1], len(one)); self.assertEqual(bytecode.decode_text_len(two, 0)[1], len(two))
        for t in ('a', 'ab', 'abc', 'abcd', '', '{color 6}x', 'x{raw 03 01 02 03}', '\u00f1a', '+', '"\'"'):    # parity: odd counts keep one letter in two bytes
            self.assertEqual(len(enc(t, True)) % 2, 0, t)
            self.assertEqual(bytecode.decode_text(enc(t, True), 0)[0], bytecode.decode_text(enc(t, False), 0)[0], t)
        self.assertEqual(sorted(bytecode.PACK_BYTE2CODE), sorted(ord(c) for c in fontgen.PACKED))
        self.assertEqual(bytecode.pack_units(bytes.fromhex('815f819b82f0')), bytes.fromhex('815f819b82f0'))      # backslash, a button: two bytes
        # the C side: the same twelve punctuation codes and characters, in the same order, as the code that expands them
        series = sorted(glob.glob(os.path.join(ROOT, 'mods/patches/0100-*.patch')))
        if series:
            with open(series[0], encoding='utf-8') as f: src = re.sub(r'(?m)^[+ ]', '', f.read())     # the patch's lines without their diff mark
            codes = [int(x, 16) for x in re.search(r'PACKED_CODES\[\] = \{([^}]*)\}', src).group(1).replace('\n', ' ').split(',') if x.strip()]
            chars = re.search(r'PACKED_ASCII\[\] = "((?:[^"\\]|\\.)*)"', src).group(1).replace('\\"', '"')
            self.assertEqual(len(codes), len(chars))
            for c, k in zip(chars, codes): self.assertEqual(bytecode.PACK_CODE2BYTE[k], ord(c))
            self.assertEqual(len(bytecode.PACK_BYTE2CODE), 26 + 26 + 10 + len(codes))

    def test_packed_rows_text_bytes_and_unpacked_boxes(self):
        """Fonts a and b pack box 0's rows (62 bytes: a letter, digit, space or common punctuation one byte, any other glyph
        and a colour change two, a name about sixteen); the texts shown in boxes 1-3 keep 31 two-byte units with every font
        (backend.UNPACKED_KEYS; docs/mods/font.md "Packed rows")."""
        from dws import backend as BE
        from dws import bytecode as bytecode
        old = dict(BE.FONT)
        try:
            BE.FONT.update({'name': 'b', 'extra': True})
            self.assertEqual(BE.text_bytes("I'll find it."), 13)
            self.assertEqual(BE.text_bytes('Ñu é'), 6)                         # two extra glyphs: two bytes each
            self.assertEqual(BE.text_bytes('go {color 6}×{color 1}!'), 3 + 2 + 2 + 2 + 1)
            self.assertEqual(BE.text_bytes('{player} won'), 16 + 4)
            row = 'Entry: open to all Digimon of the Rookie level'          # 46 bytes: one packed row, not a box-3 row
            self.assertTrue(BE.fits(row)); self.assertFalse(BE.fits(row, packed=False))
            self.assertFalse(BE.packed_key('s213.sec10.u4')); self.assertFalse(BE.packed_key('m1240.u0'))
            self.assertFalse(BE.packed_key('m1237.u5')); self.assertTrue(BE.packed_key('m1237.u6'))
            self.assertTrue(BE.packed_key('s213.sec9.u0')); self.assertTrue(BE.packed_key(None))
            self.assertTrue(all(BE.text_units(r) <= BE.MAX_UNITS for p in BE.wrap(row * 3, 7, packed=False) for r in p))
            self.assertTrue(any(BE.text_units(r) > BE.MAX_UNITS for p in BE.wrap(row * 3, 7) for r in p))
            self.assertEqual((bytecode.unpacked_entry(None, 1240, 0), bytecode.unpacked_entry(None, 1240, 2),
                              bytecode.unpacked_entry(213, 10, 3), bytecode.unpacked_entry(178, 10, 3)), (True, False, True, False))
        finally:
            BE.FONT.clear(); BE.FONT.update(old)

    def test_committed_font_metrics(self):
        """tools/font/original-metrics.json (what the build measures with) gives the advances the disc's bitmaps give,
        for fonts a and b (fontgen.metrics against font_glyph_map); skipped without the USA executable."""
        import fontgen
        if not os.path.exists(fontgen.EXE):
            self.skipTest('no extracted/SLUS_010.32')
        codes, base = fontgen.disc_glyphs(); m = fontgen.committed_glyphs()
        self.assertEqual(codes, m[0]); self.assertEqual([c for c, _ in base], [c for c, _ in m[1]])
        for f in ('a', 'b'):
            self.assertEqual(fontgen.metrics(f), {ch: adv for ch, (adv, _) in fontgen.font_glyph_map(f).items()})

    def test_kerning_in_every_width(self):
        """Font b's kerning (tools/font/b.txt `kern`): T, V, Y, F, P before lowercase and . , are drawn a pixel closer
        (drawGlyph); fontgen, the DWS back end and bytecode measure the same widths, a space breaks a pair."""
        import fontgen; from dws import bytecode as bytecode
        from dws import backend as BE
        k = fontgen.kern('b')
        self.assertEqual((k.get(('T', 'a')), k.get(('Y', 'o')), k.get(('r', '.')), k.get(('W', 'a')), k.get(('T', ' '))),
                         (-1, -1, -1, None, None))
        self.assertEqual(fontgen.kern('a'), {}); self.assertEqual(fontgen.kern('original'), {})
        adv = fontgen.metrics('b')
        self.assertEqual(fontgen.text_width('Tamer', 'b'), sum(adv[c] for c in 'Tamer') - 1)
        self.assertEqual(fontgen.text_width('T a', 'b'), adv['T'] + adv[' '] + adv['a'])
        old = dict(BE.FONT)
        try:
            BE.FONT.update({'name': 'b', 'extra': True})
            for t in ('Tamer Level. You can try.', 'Very far, Fafa. Pyramid'):
                line = bytecode.text_units(t, 'test', {}, print)[0]
                self.assertEqual(BE.text_px(t), fontgen.text_width(t, 'b'))
                self.assertEqual(bytecode.line_metrics_pixel(line, 'b')[1], fontgen.text_width(t, 'b'))
        finally:
            BE.FONT.clear(); BE.FONT.update(old)

    def test_exe_font_reads_the_build(self):
        """fontgen.exe_font: the linked executable decides (drawStringCells only in a font placed to the pixel; GLYPH_DATA's
        first entry tells a from b); without one, the worktree's font_sel.h, else its Makefile's FONT ?=."""
        import fontgen
        d = tempfile.mkdtemp(prefix='wt-', dir=TMP); exe = os.path.join(d, 'build', 'us', 'psx', 'gcc')
        os.makedirs(exe)
        self.assertEqual(fontgen.exe_font(exe), (None, None))
        open(os.path.join(d, 'Makefile'), 'w').write('FONT ?= b\n')
        self.assertEqual(fontgen.exe_font(exe)[0], 'b')
        open(os.path.join(d, 'Makefile'), 'w').write('CC = gcc\n')                   # before patch 0097: no FONT
        self.assertEqual(fontgen.exe_font(exe)[0], 'original')
        gen = os.path.join(d, 'build', 'us', 'psx', 'generated'); os.makedirs(gen)
        open(os.path.join(gen, 'font_sel.h'), 'w').write('#define FONT_A 1\n')
        self.assertEqual(fontgen.exe_font(exe)[0], 'a')

    def test_repage_for_font_b_and_back(self):
        """tools/dws/text/repage.py re-pages wrapped prose for font b (words unchanged; a page that ends a sentence keeps its
        break); a text paged for b built for the original font is wrapped again (textbank.fit, counted in `rewrapped`)."""
        from dws.text import repage
        from dws import backend as BE, textbank
        old = dict(BE.FONT)
        try:
            pages = [['I will find a different way. You', "can't leave the Native Forest"], ['without it.']]
            self.assertTrue(repage.is_prose(pages))
            new = repage.repage(pages, 'b')
            self.assertEqual(' '.join(r for p in new for r in p).split(), ' '.join(r for p in pages for r in p).split())
            self.assertEqual(len(new), 1); self.assertTrue(all(BE.fits(r) for p in new for r in p))
            self.assertFalse(repage.is_prose([['- Grade D -', 'A tournament mainly for']]))          # a heading: kept
            repage.set_font('original')
            tb = textbank.TextBank(source='us')
            got = tb.fit('s003.sec7.u7', new)
            self.assertIsInstance(got, str); self.assertIn('s003.sec7.u7', tb.rewrapped)       # wrapped by the compiler
            self.assertTrue(all(BE.fits(r) for p in BE.wrap(got, 3) for r in p))
            self.assertEqual(tb.fit('k', [['Short row.']]), [['Short row.']]); self.assertNotIn('k', tb.rewrapped)
        finally:
            BE.FONT.clear(); BE.FONT.update(old)

    def test_wide_opcode_only_above_255(self):
        from dws import backend as BE
        self.assertEqual(BE.op16('GIVE_ITEM', 255), 'GIVE_ITEM'); self.assertEqual(BE.op16('GIVE_ITEM', 256), 'GIVE_ITEM16')

    def test_names_resolve_items_techs_species(self):
        from dws import backend as BE
        n = BE.names()
        self.assertIn('meat', n['item'])
        self.assertIn('agumon', n['species']); self.assertTrue(n['tech'])

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/ (your own disc)')
    def test_apply_inserts_replaces_and_adds_sections(self):
        from dws import backend as BE
        b = BE.Backend(); BE.ensure_dis()
        b.scripts[178] = {'entities': {}, 'events': [(5, False, ['    DELAY 1'], {}, 'x.dws'), (7, True, ['    DELAY 2'], {}, 'x.dws'),
                                                      (90, False, ['    DELAY 3'], {}, 'x.dws')]}
        work = os.path.join(tempfile.mkdtemp(prefix='be-', dir=TMP), 'scn')
        report = BE.apply(b, work)
        self.assertTrue(any('section 5: inserted' in r for r in report)); self.assertTrue(any('section 7: replaced' in r for r in report))
        self.assertTrue(any('section 90: new' in r for r in report))
        text = open(os.path.join(work, 'script_178.scn.txt')).read()
        self.assertIn('; --- dws (x.dws)', text); self.assertIn('DELAY 3', text)


class Diagnostics(unittest.TestCase):
    def test_line_numbers_and_hint(self):
        e = errors_of('script 1 {\n  npc a = 5;\n  on talk(a) {\n    give(item("Mmeat"));\n  }\n}\n')
        self.assertEqual(len(e), 1); self.assertIn(':4:', e[0]); self.assertIn('"meat"', e[0]); self.assertIn('^', e[0])

    def test_type_error(self):
        e = errors_of('script 1 { npc a = 5; on talk(a) { give(12); } }')
        self.assertIn('expects item', e[0]); self.assertIn('item("Meat")', e[0])

    def test_syntax_error_position(self):
        with self.assertRaises(B.DwsErrors) as c: compile_src('flag a\nscript 1 { }')
        self.assertIn('x.dws:2:', c.exception.errors[0].render())

    def test_unknown_name(self):
        e = errors_of('flag gift_given;\nscript 1 { npc a = 5; on talk(a) { gift_given2 = true; } }')
        self.assertIn('unknown name', e[0]); self.assertIn('gift_given', e[0])

    def test_all_errors_reported(self):
        e = errors_of('script 1 { npc a = 5; on talk(a) { nope(); }\n on enter { zzz = 1; } }')
        self.assertEqual(len(e), 2)

    def test_after_not_original(self):
        self.assertIn('original', errors_of('script 1 { on enter after { } }')[0])

    def test_mixed_condition_grouping(self):
        e = errors_of('flag a; flag b; flag c;\nscript 1 { on enter { if (a || b && c) { return; } } }')
        self.assertIn('IF evaluates left to right', e[0])

    def test_wide_ids_need_mod_executable(self):
        src = 'script 1 { on enter { music(300); } }'
        self.assertIn('mod executable', errors_of(src)[0]); self.assertEqual(errors_of(src, exe='mods'), [])

    def test_missing_text_bank(self):
        saved = B.TextBank.load_defaults
        B.TextBank.load_defaults = lambda self, sources=(), extra=(): None      # as if text/us did not exist
        try:
            e = errors_of('script 1 { npc a = 5; on talk(a) { say(a, text("s002.sec6.u3")); } }')
        finally:
            B.TextBank.load_defaults = saved
        self.assertIn('extract the texts from your own disc', e[0])

    def test_text_key_from_bank(self):
        p = compile_src('script 1 { npc a = 5; on talk(a) { say(a, text("k.1")); } }', bank={'k.1': 'Hello there.'})
        self.assertIn('"Hello there."', '\n'.join(p.b.scripts[1]['events'][0][2]))

    def test_lint_flags(self):
        p = compile_src('flag unused; flag onlyset; script 1 { on enter { onlyset = true; } }')
        w = ' '.join(p.warn.render()); self.assertIn('"unused" is never used', w); self.assertIn('set but never read', w)

    def test_spawn_in_talk_warns(self):
        p = compile_src('script 1 { npc a = 5; on talk(a) { let x = spawn(species("Greymon"), slot: 3); } }')
        self.assertIn('hangs', ' '.join(p.warn.render()))


class Allocation(unittest.TestCase):
    def test_pin_collision(self):
        e = errors_of('flag a = 720; flag b = 720;')
        self.assertIn('collides', e[0])

    def test_pin_out_of_range(self):
        e = errors_of('flag a = 100;'); self.assertIn('alias flag', e[0])

    def test_alias_ok(self):
        self.assertEqual(errors_of('alias flag beaten = 50; script 1 { on enter { if (beaten) { return; } } }'), [])

    def test_free_order_and_pins_skipped(self):
        p = compile_src('flag a; flag b = 717; flag c;')
        self.assertEqual([p.alloc.table[k] for k in ('x.a', 'x.b', 'x.c')], [718, 717, 719])

    def test_exhaustion(self):
        self.assertIn('no free', errors_of(''.join(f'flag f{i};' for i in range(84)))[0])

    def test_vars(self):
        p = compile_src('var a; temp var t; var b = 20;')
        self.assertEqual([p.alloc.table[k] for k in ('x.a', 'x.t', 'x.b')], [7, 45, 20])

    def test_lock_file(self):
        d = tempfile.mkdtemp(dir=TMP); lock = os.path.join(d, 'story.lock')
        compile_src('flag a; flag b;', lock=lock, update_lock=True)
        p = compile_src('flag c; flag b; flag a;', lock=lock)         # names keep their numbers whatever the order
        self.assertEqual((p.alloc.table['x.a'], p.alloc.table['x.b'], p.alloc.table['x.c']), (717, 718, 719))
        self.assertIn('lock', errors_of('flag a = 730;', lock=lock)[0])


class Language(unittest.TestCase):
    def asm(self, body, head='', exe='original'):
        p = compile_src(f'{head}\nscript 1 {{ npc a = 5; on talk(a) {{ {body} }} }}', exe=exe)
        return '\n'.join(p.b.scripts[1]['events'][0][2])

    def test_function_inline_and_return(self):
        a = self.asm('hello(a, 3);', 'temp var t; fn hello(who: entity, n: int) { give_bits(n); if (t > 1) { return; } give_bits(1); }')
        self.assertIn('ADD_MONEY 3', a); self.assertIn('JUMP_TO q_fnend', a)

    def test_recursion_rejected(self):
        self.assertIn('calls itself', errors_of('fn f() { f(); } script 1 { on enter { f(); } }')[0])

    def test_while_break(self):
        a = self.asm('var_i();', 'temp var i; fn var_i() { while (i < 3) { i += 1; if (i == 2) { break; } } }')
        self.assertIn('ADD_TO_PSTAT p45, 1', a); self.assertIn('JUMP_TO q_loop', a)

    def test_cutscene_and_handles(self):
        a = self.asm('cutscene { let h = walk(a, 10, -20, camera: true); await h; camera_on(tamer); }')
        for s in ('SET_TRIGGER 44', 'ENTITY_WALK_TO_WITH_CAMERA 5, 10, -20, 0, 0', 'WAIT_FOR_ENTITY 5'):
            self.assertIn(s, a)
        self.assertNotIn('UNSET_TRIGGER 44', a); self.assertNotIn('FADEOUT_HUD', a)      # the engine clears 44 itself (scriptPauseGame)

    def test_shared_blocks_and_labels(self):
        """Code several events reach (`shared NAME { }`, `shared NAME:`), jumps to a section's entry (`secN`): the source is the
        whole script, nothing jumps into the disc's code (the review's step 1)."""
        p = compile_src('script 1 { npc a = 5;\n'
                        '  on talk(a) replace { if (trigger(5)) goto after; gosub helper; goto sec254; }\n'
                        '  section(30) replace { shared row: data(1, 2, 3); }\n'
                        '  section(31) replace { goto row; }\n'
                        '  shared after { if (trigger(6)) { give_bits(1); } }\n'
                        '  shared helper { wait(1s); jump_return(); } }')
        ev = '\n'.join(l for e in p.b.scripts[1]['events'] for l in e[2])
        for s in ('IF trigger 5, else', 'JUMP_TO sh_after', 'JUMP_AND_LINK sh_helper', 'JUMP_TO sec254', 'sh_row:', 'JUMP_TO sh_row'): self.assertIn(s, ev)
        sh = {n: '\n'.join(c) for n, c, _ in p.b.scripts[1]['shared']}
        self.assertTrue(sh['after'].startswith('sh_after:')); self.assertTrue(sh['after'].rstrip().endswith('END_SECTION'))   # falls off: ends like an event
        self.assertTrue(sh['helper'].rstrip().endswith('JUMP_RETURN'))
        self.assertIn('defined twice', errors_of('script 1 { shared x { } shared x { } }')[0])
        self.assertIn('section entry', errors_of('script 1 { on enter { sec3: return; } }')[0])
        # the section table of a script made from its sources alone (`sections`): an id is its event, `id as NAME` a shared block
        from dws import basebuild as BB
        p = compile_src('script 1 { sections 254, 30, 254 as old;\n  on enter replace { give_bits(1); }\n'
                        '  section(30) replace { goto old; }\n  shared old { give_bits(2); } }')
        t = '\n'.join(BB.generate_text('script 1', p.b.scripts[1], p.b.orders[1], p.b.gen_event))
        for s in ('.section 254 sec254\n.section 30 sec30\n.section 254 sh_old', 'sec254:', 'sec30:', 'sh_old:', 'JUMP_TO sh_old'): self.assertIn(s, t)
        p = compile_src('script 1 { sections 254, 5; on enter replace { return; } }')
        t = '\n'.join(BB.generate_text('script 1', p.b.scripts[1], p.b.orders[1], p.b.gen_event))   # a listed section whose
        self.assertIn('.section 254 sec254', t); self.assertNotIn('.section 5 ', t)                  # event was deleted: not there
        p = compile_src('script 1 { on enter { goto original(L5); } }')               # the old form: accepted, with a deprecation warning
        self.assertTrue(any('deprecated' in w for w in p.warn.render()))

    def test_original_labels_and_open_choice(self):
        a = self.asm('unless (trigger(5)) goto original(L228); gosub original(sec10); goto original(L228);')
        for s in ('IF trigger 5, else L228', 'JUMP_AND_LINK sec10', 'JUMP_TO L228'): self.assertIn(s, a)
        self.assertNotIn('u1_L228', a)                                                # the label of the original script, not one of the event
        a = self.asm('choice(open) { "Yes" => { give_bits(5); return; } "No" => { return; } }')
        self.assertIn('SET_SELECTION', a); self.assertNotIn('END_SELECTION', a)
        a = self.asm('choice(narrator, open) { "Yes" => { return; } "No" => { return; } }')
        self.assertIn('SET_DIALOG_OWNER 255', a)
        # a cancel path after SET_SELECTION without END_SELECTION: the code that follows the selection is the cancel's (7 sections of the disc)
        a = self.asm('choice(open) { "a" => { return; } "b" => { return; } cancel => { give_bits(1); } }')
        self.assertIn('SET_SELECTION', a); self.assertNotIn('END_SELECTION', a); self.assertIn('ADD_MONEY 1', a)
        self.assertIn('either a `cancel =>`', errors_of('script 1 { on enter { choice(open) { "a" or cancel => { return; } "b" => { return; } cancel => { return; } } } }')[0])

    def test_choice_keep_and_match_clamp(self):
        a = self.asm('choice(keep) { "Yes" => { return; } "No" => { return; } }')
        self.assertIn('SET_SELECTION', a); self.assertNotIn('SET_DIALOG_OWNER', a)          # the owner that is set stays
        a = self.asm('match (p34, clamp) { 0 => { give_bits(1); } 1 => { give_bits(2); } }')
        self.assertIn('SWITCH p34', a); self.assertNotIn('IF p34 <', a)                       # the original's SWITCH: no bound check
        self.assertIn('exactly 0..n-1', errors_of('script 1 { on enter { match (p34, clamp) { 0 => { return; } _ => { return; } } } }')[0])

    def test_flowcmp_original_labels_are_leaves(self):
        from dws import flowcmp
        a = ['    IF trigger 5, else L9', '    DELAY 1', '    JUMP_TO L228', 'L9:', '    END_SECTION']
        b = ['    IF trigger 5, else q1', '    DELAY 1', '    JUMP_TO L228', 'q1:', '    END_SECTION']
        c = ['    IF trigger 5, else q1', '    DELAY 1', '    JUMP_TO L229', 'q1:', '    END_SECTION']
        self.assertTrue(flowcmp.compare(a, b)['equal']); self.assertFalse(flowcmp.compare(a, c)['equal'])

    def test_say_statements_are_boxes_and_pages_of_one_say_are_chained(self):
        """Engine: SHOW_TEXTBOX followed by SHOW_TEXTBOX is ONE box (showTextbox does not finish the page); a SET_DIALOG_OWNER between them
        ends the box and sets a new one up. So every `say` statement starts with its own SET_DIALOG_OWNER (found by the verification sweep:
        163 section 6, 164 section 5)."""
        from dws import flowcmp
        a = self.asm('say(tamer, "a"); say(tamer, "b");'); b = self.asm('say(tamer, "a", "b");')
        self.assertEqual(a.count('SET_DIALOG_OWNER'), 2); self.assertEqual(b.count('SET_DIALOG_OWNER'), 1)
        sep = ['    SET_DIALOG_OWNER 6', '    SHOW_TEXTBOX', '        "a"', '    SET_DIALOG_OWNER 6', '    SHOW_TEXTBOX', '        "b"', '    END_SECTION']
        chain = ['    SET_DIALOG_OWNER 6', '    SHOW_TEXTBOX', '        "a"', '    SHOW_TEXTBOX', '        "b"', '    END_SECTION']
        self.assertFalse(flowcmp.compare(sep, chain)['equal'])                      # was "equal" (the owner is the same): not the same program
        self.assertTrue(flowcmp.compare(sep, sep + [])['equal'])
        self.assertTrue(flowcmp.compare(chain, ['    SET_DIALOG_OWNER 6'] + chain[1:3] + ['L1:'] + chain[3:])['equal'])   # a label between them is no code

    def test_battle_and_result(self):
        a = self.asm('battle(); if (won) { give_bits(5); } else if (fled) { return; }')
        self.assertIn('p255 == 1', a); self.assertIn('p255 == 0', a)

    def test_conditions(self):
        a = self.asm('if (clock.hour >= 18 && !partner.is(species("Greymon")) && bits >= 5 && has(item("Meat")) < 2) { return; }')
        for s in ('STORE_DATE p96', 'p98 >= 18', 'STORE_DIGIMON_TYPE p95', 'money >= 5', 'item 38 < 2'):
            self.assertIn(s, a)

    def test_const_and_lists(self):
        a = self.asm('give(FOOD, 1);', 'const FOOD = item("Meat");')
        self.assertIn('GIVE_ITEM 38, 1', a)

    def test_import(self):
        d = tempfile.mkdtemp(dir=TMP)
        open(os.path.join(d, 'lib.dws'), 'w').write('pub flag shared;\npub fn reward() { give_bits(7); shared = true; }\n')
        open(os.path.join(d, 'main.dws'), 'w').write('import "lib.dws";\nscript 1 { npc a = 5; on talk(a) { reward(); } }\n')
        p = B.compile_sources([os.path.join(d, 'main.dws')])
        self.assertIn('ADD_MONEY 7', '\n'.join(p.b.scripts[1]['events'][0][2]))
        self.assertIn('lib.shared', p.alloc.table)

    def test_asm_escape(self):
        self.assertIn('    CALL_ROUTINE 48', self.asm('asm("CALL_ROUTINE 48");'))


class Constructs(unittest.TestCase):
    """Milestone 1b: registry commands, labels, subs, loops, match, par, arrays, enums, groups."""
    def asm(self, body, head='', exe='original', **kw):
        p = compile_src(f'{head}\nscript 1 {{ npc a = 5; on talk(a) {{ {body} }} }}', exe=exe, **kw)
        return '\n'.join(p.b.scripts[1]['events'][0][2])

    def test_registry_commands(self):
        a = self.asm('entity_walk_to(5, 100, -20, 0, 0); set_obj_visibility(3, 1); call_routine(routine("shop")); '
                     'call_digimon_routine(routine("toilet")); give_item(item("Meat"), 2); switch(p7, x, y); x: y: end_section();')
        for s in ('ENTITY_WALK_TO 5, 100, -20, 0, 0', 'SET_OBJ_VISIBILITY 3, 1', 'CALL_ROUTINE 8', 'CALL_DIGIMON_ROUTINE 0',
                  'GIVE_ITEM 38, 2', 'SWITCH p7, u5_x, u5_y'):
            self.assertIn(s, a)

    def test_every_opcode_has_a_command(self):
        from dws import bytecode as bytecode
        from dws import registry
        for op, (mn, fmt) in bytecode.OPS.items():
            if mn not in registry.SPECIAL_OPS: self.assertIn(mn.lower(), registry.COMMANDS)

    def test_command_arity_error(self):
        e = errors_of('script 1 { on enter { entity_walk_to(5, 1); } }')
        self.assertIn('takes 5 argument', e[0])

    def test_unknown_routine(self):
        self.assertIn('no routine', errors_of('script 1 { on enter { call_routine(routine("nope")); } }')[0])

    def test_labels_goto_unless(self):
        a = self.asm('top: unless (p110 >= 3 || !trigger(5)) goto top; goto top;')
        self.assertIn('IF p110 >= 3, or not trigger 5, else u5_top', a); self.assertIn('JUMP_TO u5_top', a)
        self.assertIn('not defined', errors_of('script 1 { on enter { goto nowhere; } }')[0])
        self.assertIn('defined twice', errors_of('script 1 { on enter { a: a: } }')[0])

    def test_restart_operator(self):
        a = self.asm('unless ((trigger(5) ~> trigger(6)) && trigger(7)) goto z; z:')
        self.assertIn('IF trigger 5, trigger 6, and trigger 7, else', a)

    def test_sub_with_parameter_and_result(self):
        p = compile_src('sub big(n: u8) -> u8 { if (n >= 3) { return 1; } return 0; }\n'
                        'script 1 { npc a = 5; on talk(a) { let r = big(7); if (r == 1) { give_bits(1); } } }')
        code = '\n'.join(p.b.scripts[1]['events'][0][2]); subs = '\n'.join(p.b.scripts[1]['subs'])
        self.assertIn('JUMP_AND_LINK qsub_big_1', code); self.assertIn('SET_PSTAT p45, 7', code)
        self.assertIn('JUMP_RETURN', subs); self.assertIn('SET_PSTAT p46, 1', subs)
        self.assertIn('u8', errors_of('sub f(x: entity) { }\nscript 1 { npc a = 5; on talk(a) { f(a); } }')[0])

    def test_loops(self):
        a = self.asm('repeat (3) { wait(2); } for i in 0..4 { wait(1); } loop { break; }')
        self.assertIn('SET_PSTAT p45, 3', a); self.assertIn('REDUCE_PSTAT p45, 1', a)
        self.assertIn('IF p46 < 4', a); self.assertIn('ADD_TO_PSTAT p46, 1', a)

    def test_match_lowering(self):
        dense = self.asm('match (v) { 0 => give_bits(1), 1 => give_bits(2), 2 => give_bits(3), _ => give_bits(4) }', 'var v;')
        self.assertIn('SWITCH p7, ', dense); self.assertIn('IF p7 < 3', dense)
        sparse = self.asm('match (v) { 5 => give_bits(1), 9 => give_bits(2) }', 'var v;')
        self.assertNotIn('SWITCH', sparse); self.assertIn('IF p7 == 9', sparse)

    def test_par_awaits_all(self):
        a = self.asm('par { walk(a, 1, 2); walk(tamer, 3, 4); }')
        self.assertLess(a.index('ENTITY_WALK_TO TAMER'), a.index('WAIT_FOR_ENTITY 5')); self.assertIn('WAIT_FOR_ENTITY TAMER', a)

    def test_enum_group_array(self):
        head = 'enum Stage { None, Found = 5, Done }\ngroup Q { flag seen; var stage: Stage; flag[4] chests; var[3] n; }'
        a = self.asm('Q.stage = Stage.Found; Q.chests[2] = true; if (Q.chests[2] && Q.stage == Stage.Done) { Q.seen = true; }', head)
        self.assertIn('SET_PSTAT p7, 5', a); self.assertIn('SET_TRIGGER 720', a); self.assertIn('p7 == 6', a)
        self.assertIn('not a value of enum', errors_of(head + '\nscript 1 { on enter { Q.stage = 3; } }')[0])
        self.assertIn('outside', errors_of(head + '\nscript 1 { on enter { Q.chests[4] = true; } }')[0])
        self.assertIn('is an array', errors_of(head + '\nscript 1 { on enter { Q.chests = true; } }')[0])
        p = compile_src(head); self.assertEqual(p.alloc.sizes['x.Q.chests'], 4)

    def test_types_and_pools(self):
        self.assertIn('needs 32 bits', errors_of('var big: i32;')[0])
        self.assertEqual(errors_of('persistent var big: i32;', profile='extended-save'), [])
        e = errors_of(''.join(f'var v{i};' for i in range(11)))
        self.assertIn('no free saved pstats left', e[0]); self.assertIn('extended saved state', e[0])
        e = errors_of('flag[90] many;'); self.assertIn('in a row', e[0])
        p = compile_src(''.join(f'flag f{i};' for i in range(200)), profile='extended-save'); self.assertEqual(p.alloc.table['x.f199'], 199)

    def test_lock_profile_mismatch(self):
        d = tempfile.mkdtemp(dir=TMP); lock = os.path.join(d, 'story.lock')
        compile_src('flag a;', lock=lock, update_lock=True)
        with self.assertRaises(DwsError): compile_src('flag a;', lock=lock, profile='extended-save')

    def test_raw_pstats_and_new_conditions(self):
        a = self.asm('p110 = 5; if (stat(9) >= 3 && has_card(7) == 1 && !condition(2) && knows(tech("Spit Fire")) && w3 < 9) { return; }', exe='mods')
        self.assertIn('SET_PSTAT p110, 5', a)
        for s in ('stat 9 >= 3', 'card 7 == 1', 'not cond 2', 'move 2', 'w3 < 9'): self.assertIn(s, a)


class EngineExpanded(unittest.TestCase):
    """Capability checks (docs/mods/story-state-engine.md): the story-state profile compiles for --exe story-state (story flags above 799,
    32-bit variables, scene variables); original is untouched."""
    HEAD = 'persistent flag far = 16000; persistent flag near; persistent var big: i32; persistent var small: i16; session var sc: i16;'

    def asm(self, body, head=None, exe='story-state', profile='extended-save'):
        p = compile_src(f'{self.HEAD if head is None else head}\nscript 1 {{ npc a = 5; on talk(a) {{ {body} }} }}', exe=exe, profile=profile)
        return '\n'.join(p.b.scripts[1]['events'][0][2]), p

    def test_flags_are_triggers_from_800(self):
        a, p = self.asm('far = true; near = true; near = false; if (far && !near) { return; }')
        self.assertIn('SET_TRIGGER 16800', a); self.assertIn('SET_TRIGGER 800', a); self.assertIn('UNSET_TRIGGER 800', a)
        self.assertIn('trigger 16800, and not trigger 800', a)
        self.assertEqual(p.alloc.table['x.far'], 16000)               # the allocation (and the lock) hold the story bit

    def test_variables_use_the_story_opcodes(self):
        a, _ = self.asm('big = 100000; big += 5; big -= 2; big *= 3; big /= 4; big %= 7; small = -5; sc = 3; sc += 1; big += small; small = big;'
                        ' if (big > 70000 && sc == 4 && big >= small) { return; }')
        for ln in ('SET_V v0, 100000', 'ADD_V v0, 5', 'SUB_V v0, 2', 'MUL_V v0, 3', 'DIV_V v0, 4', 'MOD_V v0, 7', 'SET_V v1, -5', 'SET_V s0, 3',
                   'ADD_V s0, 1', 'ADD_VV v0, v1', 'COPY_V v1, v0', 'v0 > 70000', 'and s0 == 4', 'and v0 >= v1'):
            self.assertIn(ln, a)

    def test_ranges_follow_the_declared_type(self):
        self.assertIn('does not fit', errors_of(self.HEAD + 'script 1 { on enter { small = 40000; } }', exe='story-state', profile='extended-save')[0])
        self.assertIn('does not fit', errors_of(self.HEAD + 'script 1 { on enter { big = 3000000000; } }', exe='story-state', profile='extended-save')[0])
        self.assertIn('division by zero', errors_of(self.HEAD + 'script 1 { on enter { big /= 0; } }', exe='story-state', profile='extended-save')[0])

    def test_other_executables_refuse_story_state(self):
        for exe in ('original', 'mods', 'species'):
            e = errors_of(self.HEAD + 'script 1 { on enter { big = 5; } }', exe=exe, profile='extended-save')
            self.assertTrue(e and 'story-state' in e[0], (exe, e))
        e = errors_of('script 1 { on enter { asm("SET_V v1, 5"); } }', exe='mods')
        self.assertTrue(e and 'story-state engine' in e[0], e)
        e = errors_of('script 1 { on enter { asm("IF v1 > 5, else x"); asm("DELAY 1"); asm("x: END_SECTION"); } }', exe='original')
        self.assertTrue(e, 'a story IF clause was accepted by the original executable')

    def test_original_profile_is_unchanged_on_the_expanded_engine(self):
        for name in ('jijimon-errand', 'forest-challenge', 'dev-save', 'tokomon-sparring', 'new-house-story'):
            f = os.path.join(EXAMPLES, name + '.dws')
            a, _ = dws_bytes([f], 'mods'); b, _ = dws_bytes([f], 'story-state', profile='original')
            self.assertEqual(a, b, f'{name}: --exe story-state with the original profile differs from --exe mods')   # same font metrics
            o, _ = dws_bytes([f], 'original')
            self.assertEqual(hashlib.sha256(o['DG']).hexdigest(), GOLDEN[name]['DG'])          # and the original build is the golden one

    def test_the_expanded_example_assembles_and_disassembles(self):
        from dws import bytecode as bytecode
        got, prog = dws_bytes([os.path.join(EXAMPLES, 'expanded-state.dws')], 'story-state', profile='extended-save')
        self.assertGreater(len(got['DG']), 0)
        text = '\n'.join(prog.b.scripts[178]['events'][0][2])
        for ln in ('ADD_V v1000, 1', 'SET_TRIGGER 16800', 'ADD_VV v0, v1000', 'MUL_V v0, 3'): self.assertIn(ln, text)

    def test_opcode_round_trip_and_even_lengths(self):
        from dws import bytecode as bytecode
        src = ['SET_V v12, -7', 'ADD_V s3, 100000', 'SUB_V v1023, 1', 'COPY_V v1, s2', 'V_FROM_PSTAT p110, v5', 'PSTAT_FROM_V p111, s7',
               'ADD_VV v1, v2', 'SUB_VV v3, v4', 'MUL_V v0, 3', 'DIV_V v0, 2', 'MOD_V v0, 9',
               'IF v1 >= 5, and s2 == -3, or v4 != v5, and not trigger 16800, else L', 'L: END_SECTION']
        text = '.section 5 S\nS:\n' + '\n'.join('    ' + x if not x.startswith('L:') else x for x in src) + '\n'
        b, _ = bytecode.assemble_script(text, 'expanded-test')
        hdr, secs, ins, end, targets = bytecode.sweep(b)
        for off, n in ins: self.assertEqual(n % 2, 0, f'{b[off]:#x} has an odd length')
        labels = {t: f'L{t}' for t in targets}
        lines = [bytecode.dis_instr(b, o, n, labels)[0][0] for o, n in ins]
        self.assertEqual(lines[0], 'SET_V v12, -7'); self.assertEqual(lines[1], 'ADD_V s3, 100000'); self.assertEqual(lines[3], 'COPY_V v1, s2')
        self.assertEqual(lines[4], 'V_FROM_PSTAT p110, v5')
        self.assertTrue(lines[11].startswith('IF v1 >= 5, and s2 == -3, or v4 != v5'), lines[11])

    def test_saved_pool_alias_is_the_same_profile_and_locks_are_compatible(self):
        from dws.alloc import PROFILES
        self.assertIs(PROFILES['tier2'], PROFILES['tier2xl'])
        self.assertEqual(len(PROFILES['tier2'][('flag', 'save')].numbers), 16384)
        self.assertEqual(len(PROFILES['tier2'][('var', 'save')].numbers), 1024)

    def test_loop_temporaries_stay_pstats_in_expanded(self):
        a, _ = self.asm('repeat (3) { give_bits(1); } while (big < 3) { big += 1; }')
        self.assertIn('SET_PSTAT p45, 3', a); self.assertIn('v0 < 3', a)


class Scaffolding(unittest.TestCase):
    """dws new / dws doctor on a scratch story/ tree, and the real story/core library."""
    def setUp(self):
        from dws import scaffold
        self.sc = scaffold; self.root = tempfile.mkdtemp(dir=TMP); self.saved = scaffold.STORY
        scaffold.STORY = os.path.join(self.root, 'story')
        for d in ('core', 'base', 'mods'): os.makedirs(os.path.join(scaffold.STORY, d))
        for d in ('', 'core', 'base', 'mods'): open(os.path.join(scaffold.STORY, d, 'README.md'), 'w').write('x')

    def tearDown(self):
        self.sc.STORY = self.saved

    def test_new_and_doctor(self):
        files = self.sc.new('quest', 'kunemons-bed/feed-kunemon') + self.sc.new('npc', 'kunemons-bed/kunemon') + self.sc.new('mod', 'my-dlc')
        self.assertTrue(all(os.path.exists(f) for f in files))
        res = self.sc.doctor(self.sc.STORY)
        self.assertEqual([m for s, m in res if s == 'error' and 'gitignore' not in m], [])
        # the quest template compiles and allocates its stage variable
        q = os.path.join(self.sc.STORY, 'base/zones/kunemons-bed/quests/feed-kunemon.dws')
        prog = B.compile_sources([q]); self.assertIn('feed-kunemon.FeedKunemon.stage', prog.alloc.table)

    def test_doctor_finds_problems(self):
        d = os.path.join(self.sc.STORY, 'base/Bad_Zone'); os.makedirs(d)      # (base/zones and base/maphead are made from the disc: not checked)
        open(os.path.join(d, 'Big File.dws'), 'w').write('\n' * 3000)
        open(os.path.join(self.sc.STORY, 'x.bin'), 'w').write('')
        msgs = ' '.join(m for _, m in self.sc.doctor(self.sc.STORY))
        for s in ('no README.md', 'split it', 'does not belong', 'lower-case'): self.assertIn(s, msgs)

    def test_bad_names_and_mod_manifest(self):
        with self.assertRaises(ValueError): self.sc.new('zone', 'Bad Name')
        self.sc.new('mod', 'a-mod'); open(os.path.join(self.sc.STORY, os.path.join('mods', 'a-mod', 'mod.toml')), 'w').write('name = "other"\nversion = "x"\nrequires = ["ghost >= 1"]\n')
        msgs = ' '.join(m for s, m in self.sc.doctor(self.sc.STORY))
        self.assertIn('must equal the folder name', msgs); self.assertIn('version must look like', msgs); self.assertIn('requires "ghost"', msgs)

    def test_the_real_tree_is_healthy(self):
        self.sc.STORY = self.saved
        self.assertEqual([m for s, m in self.sc.doctor() if s == 'error'], [])

    def test_core_library_compiles(self):
        p = compile_src('import "%s/story/core/scene.dws";\nimport "%s/story/core/recruit.dws";\n'
                        'script 1 { npc a = 5; on talk(a) { fade_to_white(30); recruit(species("Agumon")); '
                        'if (is_recruited(species("Agumon")) && engine.result == 1) { engine.cutscene = true; } } }' % (ROOT, ROOT))
        code = '\n'.join(p.b.scripts[1]['events'][0][2])
        for s in ('SET_PSTAT p254, 30', 'CALL_ROUTINE 45', 'SET_TRIGGER 203', 'p255 == 1', 'SET_TRIGGER 44'): self.assertIn(s, code)


@unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/ (your own disc)')
class Decompiler(unittest.TestCase):
    """decompile -> port form -> compile -> the bytes of the disc, with no asm() left."""
    def test_whole_disc_round_trip_from_the_decompiler(self):
        from dws import roundtrip
        r = roundtrip.run(os.path.join(TMP, 'rt'), quiet=True)
        self.assertEqual((r['scripts'], r['identical']), (222, 222)); self.assertTrue(r['dg_identical']); self.assertTrue(r['maphead_identical'])
        self.assertEqual(r['asm'], 0); self.assertGreater(r['lifted'], 39000)

    def test_layout_round_trip(self):
        from dws import roundtrip
        r = roundtrip.run(os.path.join(TMP, 'rtl'), quiet=True, layout=True)
        self.assertEqual(r['identical'], 222); self.assertTrue(r['dg_identical']); self.assertTrue(r['maphead_identical'])
        base = os.path.join(TMP, 'rtl', 'base')
        for dp, dn, fn in os.walk(base): self.assertIn('README.md', fn, dp)

    def test_decompiled_source_holds_no_game_text(self):
        from dws import decomp
        scripts, mh, _ = decomp.decompile_all()
        for src in list(scripts.values()) + [mh]:
            for line in src.split('\n'):
                self.assertNotRegex(line.strip(), r'^"')           # a port form never quotes text rows
                if 'show_textbox' in line or 'set_selection' in line:
                    self.assertNotRegex(line, r'"[^"]*[a-z]{4} [a-z]{3}')

    def test_coverage_numbers(self):
        from dws import coverage
        c = coverage.run(os.path.join(TMP, 'cov'), quiet=True)
        self.assertEqual(c['total'], 36365); self.assertEqual(c['after'], c['total']); self.assertLess(c['before'], c['after'])


class Formatter(unittest.TestCase):
    def test_idempotent_and_canonical(self):
        src = 'flag a;\nscript 1 {\nnpc x = 5;\n  on talk(x) {\n if (a) {\nreturn;\n    }   \n\n\n\n  }\n}\n'
        f = format_source(src)
        self.assertEqual(format_source(f), f); self.assertIn('        if (a) {\n            return;\n        }\n', f)
        self.assertNotIn('\n\n\n', f)

    def test_examples_are_formatted(self):
        for p in glob.glob(os.path.join(ROOT, 'tools/dws/examples/*.dws')):
            s = open(p).read(); self.assertEqual(format_source(s), s, p)


@unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/ (your own disc)')
class TextRoundTrip(unittest.TestCase):
    """extract -> DWS that references keys only -> compile -> the original bytes."""
    @classmethod
    def setUpClass(cls):
        cls.bank = textx.extract()
        cls.bankfile = os.path.join(TMP, 'orig.en.json'); textx.write_bank(cls.bank, cls.bankfile)
        cls.orig = open(os.path.join(ROOT, 'extracted/SCN/DG.SCN'), 'rb').read()

    def test_keys_are_stable_and_positional(self):
        self.assertIn('s002.sec6.u0', self.bank); self.assertIn('s002.sec6.m0.o1', self.bank)
        self.assertTrue(any(k.startswith('m1230.u') for k in self.bank))
        # 3 927 utterances (4 514 pages) and 799 options of 330 menus: the 9 385 rows of the disc
        self.assertEqual(sum(1 for k in self.bank if '.u' in k), 3927); self.assertEqual(sum(1 for k in self.bank if '.o' in k), 799)
        self.assertEqual(sum(len(v) if isinstance(v[0], list) else 1 for k, v in self.bank.items() if '.u' in k), 4514)
        self.assertEqual(textx.extract(), self.bank)

    def test_bank_keeps_placeholders(self):
        self.assertTrue(any('{partner}' in json.dumps(v) or '{color' in json.dumps(v) for v in self.bank.values()))

    def roundtrip(self, sids, maphead=False):
        d = tempfile.mkdtemp(dir=TMP); srcs = []
        for s in sids:
            p = os.path.join(d, f's{s}.dws'); src = textx.keyed_script(s); open(p, 'w').write(src); srcs.append(p)
            for line in src.split('\n'):                    # a keyed source holds no game text, only keys
                if line.strip().startswith('"') and '"' in line.strip()[1:] and not line.strip().startswith('"{'):
                    self.fail(f'quoted text in a keyed source: {line}')
        if maphead:
            p = os.path.join(d, 'mh.dws'); open(p, 'w').write(textx.keyed_maphead()); srcs.append(p)
        prog = B.compile_sources(srcs, text=[self.bankfile])
        out = os.path.join(d, 'DG.SCN'); B.assemble(prog, out)
        return out, prog

    def test_scripts_round_trip_byte_exact(self):
        out, _ = self.roundtrip([2, 113, 178, 184])
        self.assertEqual(open(out, 'rb').read(), self.orig)

    def test_whole_disc_round_trip(self):
        """All 222 scripts and MAPHEAD: keys only in the source, the original bytes out."""
        scripts, mh = textx.keyed_all(); d = tempfile.mkdtemp(dir=TMP); srcs = []
        for sid, src in scripts.items():
            p = os.path.join(d, f's{sid:03d}.dws'); open(p, 'w').write(src); srcs.append(p)
        p = os.path.join(d, 'mh.dws'); open(p, 'w').write(mh); srcs.append(p)
        self.assertEqual(len(scripts), 222)
        prog = B.compile_sources(srcs, text=[self.bankfile]); out = os.path.join(d, 'DG.SCN'); B.assemble(prog, out)
        self.assertEqual(open(out, 'rb').read(), self.orig)
        self.assertEqual(open(prog.b.maphead, 'rb').read(), open(os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN'), 'rb').read())

    def test_kunemon_readable_is_the_original_section(self):
        """tools/dws/examples/kunemon-readable.dws is script 2 section 6 as a person writes it. Both are turned into a
        control-flow graph (jumps and labels are edges, redundant SET_DIALOG_OWNERs are skipped) and must be bisimilar: the same
        instructions with the same operands and text rows, reached in the same order. What differs is layout only:
        the disc has a duplicated unreachable JUMP_TO and jumps that go to jumps; the readable form emits SET_DIALOG_OWNER again
        after an animation (redundant, skipped) and writes the walk to the city twice (before the `while` and at its end) where
        the disc jumps back to one copy. The two food groups stay two arms: one list would change the IF chain, not the behaviour."""
        from dws import flowcmp
        d, _ = textx.disassemble()
        lines = open(os.path.join(d, 'script_002.scn.txt'), encoding='utf-8').read().split('\n')
        a = next(i for i, l in enumerate(lines) if l.startswith('sec6:')); b = next(i for i, l in enumerate(lines) if l.startswith('sec51:'))
        orig = lines[a + 1:b]
        src = os.path.join(ROOT, 'tools/dws/examples/kunemon-readable.dws')
        prog = B.compile_sources([src], text=[self.bankfile])
        ours = prog.b.scripts[2]['events'][0][2]
        r = flowcmp.compare(orig, ours)
        self.assertTrue(r['equal'], r)
        self.assertEqual((r['a']['unreachable'], r['a']['instructions']), (1, 82))        # the duplicated `goto L9`
        self.assertEqual(sum(1 for l in ours if l.strip().startswith('SET_DIALOG_OWNER')) -
                         sum(1 for l in orig if l.strip().startswith('SET_DIALOG_OWNER')), 1)
        self.assertEqual(sum(1 for l in ours if 'ENTITY_WALK_TO 6' in l) - sum(1 for l in orig if 'ENTITY_WALK_TO 6' in l), 1)
        out = os.path.join(tempfile.mkdtemp(dir=TMP), 'DG.SCN'); B.assemble(prog, out)      # and it assembles
        # the check is not vacuous: a changed operand, a swapped branch or a dropped instruction is caught
        for old, new in (('DELAY 20', 'DELAY 21'), ('p254 == 255, else', 'p254 == 254, else'), ('SET_TRIGGER 232', 'SET_TRIGGER 233'),
                         ('ADD_TO_PSTAT p1, 1', 'ADD_TO_PSTAT p1, 2'), ('IF p101 < 3', 'IF p101 < 4')):
            bad = [l.replace(old, new) for l in ours]
            self.assertNotEqual(bad, ours, old); self.assertFalse(flowcmp.compare(orig, bad)['equal'], old)
        self.assertFalse(flowcmp.compare(orig, [l for l in ours if 'CALL_ROUTINE 12' not in l])['equal'])

    def test_in_list_condition(self):
        p = compile_src('var v: u8; script 1 { npc a = 5; on talk(a) { if (v in [1, 3, 5]) { v = 2; } '
                        'if (v == 9 || v in [item("Meat"), 4]) { v = 3; } } }')
        code = '\n'.join(p.b.scripts[1]['events'][0][2])
        self.assertRegex(code, r'IF p(\d+) == 1, or p\1 == 3, or p\1 == 5, else')
        self.assertRegex(code, r'IF p(\d+) == 9, or p\1 == 38, or p\1 == 4, else')
        errs = errors_of('var v: u8; flag f; script 1 { npc a = 5; on talk(a) { if (f && v in [1, 2]) { v = 2; } } }')
        self.assertTrue(errs and 'cannot follow' in errs[0], errs)

    def test_missing_bank_message(self):
        d = tempfile.mkdtemp(dir=TMP); p = os.path.join(d, 's.dws'); open(p, 'w').write(textx.keyed_script(2))
        saved = B.TextBank.load_defaults
        B.TextBank.load_defaults = lambda self, sources=(), extra=(): None      # as if text/original did not exist
        try:
            prog = B.compile_sources([p])
            with self.assertRaises(DwsError) as c: B.assemble(prog, os.path.join(d, 'o.SCN'))
            self.assertIn('extract the texts from your own disc', str(c.exception))
        finally:
            B.TextBank.load_defaults = saved


class SugarOfTheBeautifier(unittest.TestCase):
    """The language additions the beautifier needs; each lowers to instructions the compiler already had."""
    SRC = 'var v: u8; script 1 { npc a = 5; on talk(a) { %s } }'

    def code(self, body, **kw):
        return '\n'.join(compile_src(self.SRC % body, **kw).b.scripts[1]['events'][0][2])

    def test_choice_cancel_branch_and_or_cancel(self):
        c = self.code('choice { "Yes" => { v = 1; } "No" => { v = 2; } cancel => { v = 3; } }')
        sel = c.index('END_SELECTION'); self.assertIn('SET_PSTAT p', c[sel:].split('JUMP_TO')[0])          # the cancel code follows END_SELECTION
        c = self.code('choice { "Yes" => { v = 1; } "No" or cancel => { v = 2; } }')
        self.assertRegex(c, r'END_SELECTION\n\s+JUMP_TO (\w+_opt\d+)\n(?s:.*)\1:\n\s+SET_PSTAT p\d+, 2')       # the triangle goes to the second option
        errs = errors_of(self.SRC % 'choice { "a" or cancel => { } "b" => { } cancel => { } }')
        self.assertTrue(errs and 'not both' in errs[0], errs)

    def test_choice_owner(self):
        self.assertIn('SET_DIALOG_OWNER 255\n    SET_SELECTION', self.code('choice(narrator) { "a" => { } "b" => { } }'))
        self.assertIn('SET_DIALOG_OWNER TAMER\n    SET_SELECTION', self.code('choice { "a" => { } "b" => { } }'))

    def test_unless_break_continue_return(self):
        c = self.code('loop { unless (v < 3) break; v += 1; unless (v != 2) continue; v += 1; } unless (v == 9) return; v = 7;')
        self.assertRegex(c, r'IF p\d+ < 3, else (\w+_endloop\d+)')         # unless (c) break;  is the IF with the loop's exit as else
        self.assertRegex(c, r'IF p\d+ != 2, else (\w+_loop\d+)')           # continue: the loop's top
        self.assertEqual(c.count('END_SECTION'), 1)                          # unless (c) return;  jumps to an END_SECTION
        self.assertTrue(errors_of(self.SRC % 'unless (v == 1) break;'))

    def test_maphead_events_check_only(self):
        d = tempfile.mkdtemp(dir=TMP); p = os.path.join(d, 'm.dws')
        open(p, 'w').write('maphead { section(1230) replace { wait(5); } }')
        prog = B.compile_sources([p]); self.assertEqual(len(prog.b.mh_events), 1); self.assertEqual(prog.b.mh_events[0][0], 1230)
        with self.assertRaises(DwsError) as c: B.assemble(prog, os.path.join(d, 'DG.SCN'))
        self.assertIn('checked but not applied', str(c.exception))

    def test_flowcmp_ifs_are_tests_per_clause(self):
        """The engine folds an IF's clauses left to right (scriptIfInstruction): one test split over two IFs is the same program as
        one IF with all the clauses, in the same order (lift.merge_ifs relies on it for Kunemon 2:6 and Jijimon 178:5)."""
        from dws import flowcmp
        tail = ['L8:', '    DELAY 1', '    END_SECTION', 'L9:', '    DELAY 2', '    END_SECTION']
        two = ['    IF p254 == 1, or p254 == 2, else L7', '    CALL_ROUTINE 12', '    JUMP_TO L9', 'L7:',
               '    IF p254 == 3, or p254 == 4, else L8', '    CALL_ROUTINE 12', '    JUMP_TO L9'] + tail
        one = ['    IF p254 == 1, or p254 == 2, or p254 == 3, or p254 == 4, else L8', '    CALL_ROUTINE 12', '    JUMP_TO L9'] + tail
        self.assertTrue(flowcmp.compare(two, one)['equal'])
        self.assertFalse(flowcmp.compare(two[:5] + ['    CALL_ROUTINE 13'] + two[6:], one)['equal'])     # different then-code: two tests
        self.assertFalse(flowcmp.compare(two, [l.replace('p254 == 3, or p254 == 4', 'p254 == 4, or p254 == 3') for l in one])['equal'])
        both = ['    IF trigger 1, and trigger 2, else L', '    IF trigger 3, else L', '    DELAY 1', 'L:', '    DELAY 2', '    END_SECTION']
        self.assertTrue(flowcmp.compare(both, ['    IF trigger 1, and trigger 2, and trigger 3, else L', '    DELAY 1', 'L:', '    DELAY 2',
                                               '    END_SECTION'])['equal'])
        self.assertFalse(flowcmp.compare(both, ['    IF trigger 1, and trigger 2, or trigger 3, else L', '    DELAY 1', 'L:', '    DELAY 2',
                                                '    END_SECTION'])['equal'])               # (a and b) or c is not a and b and c

    def test_flowcmp_negated_tests_swap_branches(self):
        """`unless (c) J` and `if (!c) { J }` are one program: a negated test is the test with its branches swapped."""
        from dws import flowcmp
        a = ['    IF trigger 1, and p3 >= 2, else L', '    END_SECTION', 'L:', '    DELAY 1', '    END_SECTION']
        b = ['    IF not trigger 1, or p3 < 2, else L2', '    DELAY 1', '    END_SECTION', 'L2:', '    END_SECTION']
        self.assertTrue(flowcmp.compare(a, b)['equal'])
        self.assertFalse(flowcmp.compare(a, [l.replace('p3 < 2', 'p3 <= 2') for l in b])['equal'])
        self.assertFalse(flowcmp.compare(a, [l.replace('or p3', 'and p3') for l in b])['equal'])

    def test_flowcmp_handles_calls_and_switches(self):
        from dws import flowcmp
        a = ['    JUMP_AND_LINK L1', '    END_SECTION', 'L1:', '    DELAY 5', '    JUMP_RETURN']
        self.assertTrue(flowcmp.compare(a, a)['equal'])
        self.assertFalse(flowcmp.compare(a, [l.replace('DELAY 5', 'DELAY 6') for l in a])['equal'])          # the callee is compared
        sw = ['    SWITCH p7, L1, L2', 'L1:', '    DELAY 1', '    END_SECTION', 'L2:', '    DELAY 2', '    END_SECTION']
        self.assertFalse(flowcmp.compare(sw, [l.replace('DELAY 2', 'DELAY 3') for l in sw])['equal'])      # every switch arm is compared


@unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/ (your own disc)')
class Beautifier(unittest.TestCase):
    """tools/dws/lift.py: the literal form -> readable DWS, every section proven against the disc (milestone 6)."""

    @classmethod
    def setUpClass(cls):
        from dws import readable, lift
        cls.readable, cls.lift = readable, lift
        cls.lifted, cls.mh, cls.names = readable.lift_disc()

    def test_kunemon_automatically_is_the_original_and_the_hand_written_twin(self):
        from dws import flowcmp
        lf = next(l for l in self.lifted[2] if l.sec.label == 'sec6')
        body = '\n'.join(lf.body)
        self.assertEqual(lf.level, 3)
        for want in ('choice {', 'walk_away(', 'join_city_camera(', 'battle(foes: [kunemon])', 'engine.picker_mode', '} else if (engine.arg == 255) {',
                     'engine.arg in [item("Meat"), item("Giant Meat"), item("Sirloin"), item("Supercarrot"), item("Hawk radish")', 'animate(kunemon, anim.idle)'):
            self.assertIn(want, body)
        # the disc's two food tests are one (lift.merge_ifs) and the declined exit is where the choice ends: no label is left
        self.assertNotIn('goto', body); self.assertEqual(lf.status, 'readable')
        self.assertGreater(body.index('s002.sec6.u9'), body.index('s002.sec6.u8'))
        # the same graph as the hand-written readable twin (both are bisimilar to the disc, hence to each other)
        src = os.path.join(ROOT, 'tools/dws/examples/kunemon-readable.dws')
        bank = os.path.join(TMP, 'orig.en.json'); textx.write_bank(textx.extract(), bank)
        twin = B.compile_sources([src], text=[bank]); ev = twin.b.scripts[2]['events'][0]
        self.assertTrue(flowcmp.compare(lf.sec.lines, twin.b.gen_event(*ev))['equal'])
        # the proof is not vacuous: a changed operand, a swapped branch or a dropped instruction is refused
        tmp = tempfile.mkdtemp(dir=TMP); npcs = lf.npcs
        imports = self.names.import_paths({'engine.arg', 'engine.picker_mode', 'engine.cutscene', 'engine.prosperity', 'walk_away', 'join_city_camera', 'glances', 'anim'})
        ok, why = self.lift.verify(lf, lf.body, npcs, imports, self.names, tmp); self.assertTrue(ok, why)
        for old, new in (('looks: 3', 'looks: 4'), ('engine.arg == 255', 'engine.arg == 254'), ('animate(kunemon, 28)', 'animate(kunemon, 27)'),
                         ('say(kunemon, text("s002.sec6.u9"));', ''), ('item("Supercarrot"),', 'item("Meat"),'),
                         ('item("Moldy Meat")]', 'item("Moldy Meat"), item("Sirloin")]'),
                         ('text("s002.sec6.u8"));', 'text("s002.sec6.u8"), prosperity: 2);')):
            bad = [l.replace(old, new) for l in lf.body]
            self.assertNotEqual(bad, lf.body, old)
            self.assertFalse(self.lift.verify(lf, bad, npcs, imports, self.names, tmp)[0], old)

    def test_whole_disc_every_section_is_proven_or_left_in_the_port_form(self):
        rs = self.readable.rows(self.lifted, self.mh); sm = self.readable.summarize(rs)
        self.assertEqual(sm['DG']['sections'], 1553); self.assertEqual(sm['MAPHEAD']['sections'], 281)
        for k in ('DG', 'MAPHEAD', 'all'):
            d = sm[k]; self.assertEqual(d['readable'] + d['shared-exit'] + d['partial'] + d['literal'] + d['port-only'], d['sections'])
            self.assertGreater(d['readable'], d['sections'] * 0.75); self.assertGreater(d['saved'], 0)
        # the sections that stay in the literal form are the jump tables (a section that starts with two JUMP_TO: the engine indexes it, entry i at section + 4 i + 2),
        # and each of them compiles to the very same instruction stream: DG 102/168/209/213 section 10 (the cup tables, 22 boxes), MAPHEAD 1220-1230 (the shop
        # tables), 1235-1238, 1240, 1243 (the texts of the shops and the trader)
        # and the data those tables point into (DG 102/168/209/213 section 11, the cups' DATA rows: their rows are `shared L:` labels the tables jump to)
        # and, where a script would outgrow the engine's buffer, the sections written as their own instruction stream to fit it (`lift.fit`:
        # section 51 of the library scripts 199-202, 16 KB each, and one shared block of MAPHEAD and of its copy, script 0)
        table = lambda sec: self.lift.jump_table(sec) or bool(getattr(sec, 'shared_at', None))
        lit_ok = lambda lf: table(lf.sec) or getattr(lf, 'compact', False)
        tables = sorted((sid, lf.sec.label) for sid, lst in self.lifted.items() for lf in lst if table(lf.sec))
        lit = sorted((sid, lf.sec.label) for sid, lst in self.lifted.items() for lf in lst if lf.status == 'literal')
        self.assertTrue(set(tables) <= set(lit)); self.assertGreaterEqual(len(tables), 20)
        self.assertTrue(all(lit_ok(lf) for lst in self.lifted.values() for lf in lst if lf.status == 'literal'))
        self.assertLessEqual(sum(1 for lst in self.lifted.values() for lf in lst if lf.status == 'literal' and not table(lf.sec)), 6)
        self.assertTrue(all(lf.same_layout for lst in self.lifted.values() for lf in lst if table(lf.sec) or getattr(lf, 'compact', False)))
        self.assertTrue(all(lit_ok(lf) for lf in self.mh if lf.status == 'literal'))
        self.assertEqual(sum(1 for lf in self.mh if lf.status == 'literal' and table(lf.sec)), 17)
        # no jump into another section's code is left (`goto original(L)`): code other sections reach is a `shared` block of the script
        self.assertEqual(sum(1 for lst in list(self.lifted.values()) + [self.mh] for lf in lst if 'original(' in '\n'.join(self.readable.shared_names(l, lf.sec) for l in lf.body)), 0)
        self.assertGreater(sm['all']['shared_blocks'], 30)
        d = sm['all']; self.assertGreater(d['readable'] + d['shared-exit'], 0.93 * d['sections'])
        self.assertEqual(sm['all']['port-only'], 0)                  # the 26 wide sections of script 0 are events too (`section(1220) replace`)
        self.assertGreaterEqual(sm['all']['readable'] + sm['all']['literal'], 0.98 * sm['all']['sections'])       # goto-free, the jump tables (literal on purpose) apart
        self.assertGreaterEqual(sm['all']['readable'], 0.97 * sm['all']['sections'])
        for lst in list(self.lifted.values()) + [self.mh]:
            for lf in lst: self.assertTrue((lf.level is None) == (lf.status == 'port-only'))

    def test_unfolded_sections_are_goto_free_and_proven(self):
        """The unfolding structurer (tools/dws/unfold.py): a menu that re-asks, shared leaves, `SWITCH`, selections without END_SELECTION."""
        by = lambda sid, n: next(l for l in self.lifted[sid] if l.sec.sid == n)
        lf = by(108, 82)                                           # a training menu whose options jump into each other's code
        body = '\n'.join(lf.body)
        self.assertEqual((lf.status, lf.gotos), ('readable', 0))
        self.assertIn('loop {', body); self.assertNotIn('goto', body)
        lf = by(78, 5); body = '\n'.join(lf.body)                   # SWITCH as `match (v, clamp)`: no bound check, like the original
        self.assertEqual(lf.status, 'readable'); self.assertIn('match (p34, clamp) {', body)
        self.assertIn('choice(keep)', '\n'.join(by(95, 81).body))   # a menu reached with the dialog owner already set
        self.assertIn('choice(open)', '\n'.join(by(130, 81).body))  # the code after SET_SELECTION is the cancel path
        rs = self.readable.rows(self.lifted, self.mh)
        self.assertLess(sum(1 for r in rs if r['status'] == 'partial'), 0.02 * len(rs))
        # the proof is not vacuous for it either: a swapped option or a dropped statement is refused
        tmp = tempfile.mkdtemp(dir=TMP); lf = by(78, 5)
        imports = self.names.import_paths({'anim'})
        for old, new in (('p34 += 1;', 'p34 += 2;'), ('0 => {', '1 => {')):
            bad = [l.replace(old, new, 1) for l in lf.body]
            self.assertNotEqual(bad, lf.body, old)
            self.assertFalse(self.lift.verify(lf, bad, lf.npcs, imports, self.names, tmp)[0], old)

    def test_wide_sections_of_script_0_are_events(self):
        lf = next(l for l in self.lifted[0] if l.sec.sid == 1245)
        self.assertEqual(lf.status, 'readable'); self.assertIn('warp_to(', '\n'.join(lf.body))
        hdr, _ = self.readable.event_header(lf, self.names); self.assertEqual(hdr, 'section(1245) replace')
        src, left = self.readable.script_source(0, self.lifted[0], self.names)
        self.assertIn('section(1245) replace {', src); self.assertFalse(any('above 254' in why for _, why in left))
        self.assertEqual(sum(1 for l in self.lifted[0] if l.status == 'port-only'), 0)
        self.assertIn('ids are 1-254', '\n'.join(errors_of('script 1 { section(1245) replace { give_bits(1); } }')))        # script 0 only
        self.assertEqual(errors_of('script 0 { section(1245) replace { give_bits(1); } }'), [])

    def test_animation_names_come_from_the_engine(self):
        from dws import anims
        scene = open(os.path.join(ROOT, 'story/core/scene.dws'), encoding='utf-8').read()
        self.assertIn(anims.enum_source(), scene)                      # the language file and the table are one
        self.assertEqual(anims.name_of('tamer', 3), 'tamer_run'); self.assertEqual(anims.name_of('npc', 4), 'run')
        self.assertEqual(anims.name_of('partner', 15), 'hungry'); self.assertIsNone(anims.name_of('npc', 15))   # care slots: partner models only
        self.assertIsNone(anims.name_of('npc', 29)); self.assertIsNone(anims.name_of('tamer', 20))              # nothing in the engine names them
        text = '\n'.join('\n'.join(l.body) for lst in self.lifted.values() for l in lst)
        self.assertIn('animate(tamer, anim.', text); self.assertIn('animate(tamer, 20);', text)
        self.assertNotIn('animate(kunemon, anim.hungry)', text)

    def test_fallback_levels(self):
        """When a richer level is refused the section is still lifted at the next one (here: sugar is switched off by making level 3 and 2 fail)."""
        lift = self.lift; names = self.names
        tmp = tempfile.mkdtemp(dir=TMP)
        d, _ = textx.disassemble()
        text = open(os.path.join(d, 'script_002.scn.txt'), encoding='utf-8').read()
        for lv in (3, 2, 1, 0):
            res = lift.lift_script_text(text, 'script', 2, 'script_002', names, tmp, (lv,))
            self.assertTrue(all(r.level == lv for r in res), lv)
        lv1 = '\n'.join(next(r for r in lift.lift_script_text(text, 'script', 2, 's', names, tmp, (1,)) if r.sec.label == 'sec6').body)
        lv0 = '\n'.join(next(r for r in lift.lift_script_text(text, 'script', 2, 's', names, tmp, (0,)) if r.sec.label == 'sec6').body)
        self.assertIn('choice {', lv1); self.assertNotIn('say(', lv1); self.assertIn('show_textbox(', lv1)
        self.assertNotIn('choice', lv0); self.assertIn('unless (', lv0)

    def test_written_files_are_proven_again_and_canonical(self):
        out = os.path.join(TMP, 'readable-base'); stats = {}
        sel = {sid: self.lifted[sid] for sid in (2, 22, 178)}
        self.readable.write(out, sel, [], self.names, stats)
        n = sum(1 for sid in sel for lf in sel[sid] if lf.level is not None)
        self.assertGreaterEqual(stats['proven_events'], n - 3)           # (a dead copy of a section is not an event)
        files = glob.glob(os.path.join(out, 'zones', '*', 's*', 'script.dws')); self.assertEqual(len(files), 3)
        for f in files:
            src = open(f, encoding='utf-8').read(); self.assertEqual(format_source(src), src)
            self.assertNotIn('"I', src)                                     # keys, never the game's words
        self.readable.write(os.path.join(TMP, 'readable-mh'), {}, self.mh[:20], self.names, stats)
        self.assertTrue(glob.glob(os.path.join(TMP, 'readable-mh', 'maphead', 'screen*.dws')))

    def test_names_and_npcs(self):
        self.assertEqual(self.names.npc_name(2, 6), 'kunemon')               # the species MAPHEAD places in slot 1 of Kunemon's Bed
        self.assertEqual(self.names.npc_name(2, 11), 'slot6')                 # no species known: named by its slot, as the Python view does
        self.assertEqual(self.names.npc_name(77, 7), 'vermilimon2')           # two of a species: `<species><slot>`
        self.assertEqual(self.names.vars[254], 'engine.arg'); self.assertEqual(self.names.flags[44], 'engine.cutscene')
        self.assertEqual(self.names.vars[21], 'key_chains')                    # story/names.toml

    def test_proposed_names(self):
        """story/names.toml entries written as `7 = { name = "x", status = "proposed", confidence, evidence }`: the name works as any other, every proposal says
        where it was learnt, no name is used for two numbers, and nothing of the game's own text is in the evidence (keys only)."""
        import collections, re
        n = self.names
        self.assertEqual(n.vars[107], 'date_hour'); self.assertEqual(n.flags[5], 'mojyamon_traded.set1_row1'); self.assertEqual(n.proposed['date_hour']['status'], 'proposed')
        self.assertGreater(len(n.proposed), 100)
        for nm, p in n.proposed.items():
            self.assertEqual(p['status'], 'proposed', nm); self.assertIn(p['confidence'], ('high', 'medium'), nm)
            self.assertGreater(len(p['evidence']), 20, nm); self.assertNotIn('"', p['evidence'], nm)
            self.assertRegex(nm, r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$')
        names = list(n.vars.values()) + list(n.flags.values())
        self.assertEqual([k for k, c in collections.Counter(names).items() if c > 1], [])


class CityRules(unittest.TestCase):
    """Capability checks (docs/mods/city-rules.md): the C rules of the city as a `city { }` declaration and a table in MAPHEAD.
    The C reader against the C original (tools/dws/testing/city_equivalence.py, gcc) and the emulator scenarios are run by hand; these are the fast checks."""
    CITY = os.path.join(ROOT, 'story/base/city/city.dws')

    @classmethod
    def setUpClass(cls):
        from dws import city, citycli, presence
        cls.city, cls.citycli, cls.presence = city, citycli, presence
        cls.have_src = os.path.exists(os.path.join(ROOT, 'decomp/src/main/main.c'))

    def test_the_declaration_is_what_the_original_c_says(self):
        if not self.have_src: self.skipTest('decomp/src missing')
        spec = self.city.extract_original()
        self.assertEqual(open(self.CITY, encoding='utf-8').read(), self.city.to_dws(spec))
        self.assertEqual(self.city.encode(self.citycli.load_spec(self.CITY)), self.city.encode(spec))
        self.assertEqual(self.city.decode(self.city.encode(spec)), spec)                       # the table decodes to the same rules

    def test_original_rules_by_value(self):
        spec = self.citycli.load_spec(self.CITY); St = self.city.State
        self.assertEqual(len(spec['top_map']['rows']), 11)                                      # 12 screens, 0xA8 is the default
        self.assertEqual(spec['top_map']['default'], 0xA8)
        top = lambda *rec: self.city.top_map_of(spec['top_map'], St(triggers={200 + r for r in rec}))
        self.assertEqual(top(), 0xA8); self.assertEqual(top(46), 0xA9); self.assertEqual(top(25, 46), 0xAA)          # Vegiemon before Palmon
        self.assertEqual(top(21), 0xAB); self.assertEqual(top(20), 0xA8)                                           # Angemon alone: no change
        self.assertEqual(top(20, 14), 0xAE); self.assertEqual(top(20, 14, 21, 25), 0xB3)
        rev = lambda *rec, p1=0: self.city.top_map_of(spec['revival'], St(triggers={200 + r for r in rec}, pstats={1: p1}))
        self.assertEqual(rev(), 218); self.assertEqual(rev(20), 205); self.assertEqual(rev(14), 205); self.assertEqual(rev(p1=50), 205); self.assertEqual(rev(p1=49), 218)
        lv = St.levels()
        self.assertEqual(self.city.prosperity_of(spec['prosperity'], St(triggers={200 + s for s in range(3, 0x3b)})), 100)   # the 47 recruits add exactly 100
        self.assertEqual(self.city.prosperity_of(spec['prosperity'], St(triggers={211, 239, 253})), 3)                 # Numemon, Sukamon, Nanimon: 1 each
        self.assertEqual(spec['start']['bits'], 50000); self.assertEqual(spec['start']['lives'], 3); self.assertEqual(len(spec['start']['inventory']), 30)

    def test_table_is_a_maphead_section_for_expanded_only(self):
        src = os.path.join(ROOT, 'tools/dws/examples/expanded-city-rules.dws')
        self.assertTrue(errors_of(open(src).read(), exe='original')[0].startswith('') and 'story-state' in errors_of(open(src).read(), exe='original')[0])
        d, prog = dws_bytes([src], 'story-state')
        from dws import bytecode as bytecode
        hdr, secs = bytecode.parse_header(d['MAPHEAD']); off = dict(secs)[self.city.SECTION]
        spec = self.citycli.load_spec(src); blob = self.city.encode(spec)
        self.assertEqual(d['MAPHEAD'][off:off + len(blob)], blob)
        back = self.city.decode(blob)
        self.assertEqual(back['start']['bits'], 77777); self.assertEqual(back['start']['lives'], 5); self.assertEqual(back['start']['inventory'], spec['start']['inventory'])
        self.assertNotIn('shop_maps', back)                                    # not declared: the engine's built-in (original) list
        self.assertEqual(self.city.top_map_of(back['top_map'], self.city.State(triggers={200 + 21, 200 + 46})), 172)

    def test_two_city_declarations_cannot_name_a_block_twice(self):
        e = errors_of('city { shop_maps: [1]; }\ncity { shop_maps: [2]; }', exe='story-state')
        self.assertTrue(e and 'twice' in e[0], e)

    def test_range_errors(self):
        e = errors_of('city { top_map { screen(70000) when recruited(Angemon); default screen(1); } }', exe='story-state')
        self.assertTrue(e and 'does not fit' in e[0], e)

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/')
    def test_presence_of_jijimons_house(self):
        P = self.presence; rules, _ = P.presence_rules(205); sc = {'lets': [], 'npcs': rules}
        by = {(slot, sp): P.cond_text(c) for slot, sp, talk, c in rules}
        self.assertEqual(by[(0, 117)], 'always'); self.assertEqual(by[(1, 142)], 'recruited(Angemon)'); self.assertEqual(by[(2, 30)], 'always')
        st = lambda *tr: P.Concrete(triggers=set(tr))
        self.assertEqual(P.evaluate(sc, st()), P.run_original(205, st())[0]); self.assertEqual(P.evaluate(sc, st(220)), P.run_original(205, st(220))[0])
        self.assertIn(1, P.run_original(205, st(220))[0]); self.assertNotIn(1, P.run_original(205, st())[0])

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/')
    def test_presence_rules_equal_the_original_instructions(self):
        import random
        P = self.presence; rng = random.Random(5)
        for sid in (204, 206, 178, 180, 117):                                # date, random draw, counters, flags
            sc = P.screen_form(sid); n, full, mm = P.verify_screen(sid, sc, rng, cap=4000)
            self.assertIsNone(mm, (sid, mm)); self.assertGreater(n, 3)
        self.assertEqual(P.screen_form(205)['form'], 'flat'); self.assertEqual(P.screen_form(180)['form'], 'circuit')   # File City: named conditions
        sc = P.screen_form(204); sc['npcs'] = sc['npcs'][:-1] + [(sc['npcs'][-1][0], sc['npcs'][-1][1], 0, ('true',))]  # negative control: a wrong rule is caught
        self.assertIsNotNone(P.verify_screen(204, sc, rng)[2])

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/')
    def test_presence_declaration_parses_back(self):
        P = self.presence
        text = self.city.to_dws({'presence': {178: P.screen_form(178), 180: P.screen_form(180)}})
        p = os.path.join(tempfile.mkdtemp(prefix='c-', dir=TMP), 'p.dws'); open(p, 'w').write(text)
        spec = self.citycli.load_spec(p)
        import random
        for sid in (178, 180):
            n, full, mm = P.verify_screen(sid, spec['presence'][sid], random.Random(1), cap=3000)
            self.assertIsNone(mm, mm)

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/')
    def test_why(self):
        import io, contextlib, argparse
        from dws import cityproof
        def run(what, **kw):
            a = argparse.Namespace(what=what, screen=kw.get('screen'), trigger=kw.get('trigger', []), recruit=kw.get('recruit', []), pstat=[], hour=9, day=0, random=[])
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): cityproof.why(a)
            return buf.getvalue()
        self.assertIn('ABSENT', run('Angemon', screen=205)); self.assertIn('PRESENT', run('Angemon', screen=205, recruit=['Angemon']))
        self.assertIn('screen 168', run('top_map')); self.assertIn('screen 174', run('top_map', recruit=['Angemon', 'Monzaemon']))

    def test_the_c_reader_equals_the_c_original(self):
        import shutil
        if not (shutil.which('gcc') and self.have_src and os.path.exists(os.path.join(ROOT, 'build/decomp-story-state/src/main/city_rules.c'))):
            self.skipTest('needs gcc, decomp/ and build/decomp-story-state')
        r = subprocess.run([sys.executable, os.path.join(HERE, 'tools/dws/testing/city_equivalence.py'), '--quick'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:]); self.assertIn('ALL EQUIVALENCE CHECKS PASSED', r.stdout)


class StoryPlacementFeatures(unittest.TestCase):
    """Story placement and presence features: `city { presence }` compiled into MAPHEAD for
    the slots a program places, `flag(name)` in presence conditions, `place(..., map:)` for a new screen, a list of screens in
    `place` and a range in `presence`, a pinned enum variable, and the source map (`--srcmap`), which must not change a byte."""

    def maphead_section(self, prog, screen):
        """the screen's MAPHEAD section as the compiler wrote it (the assembly text of the run)"""
        text = open(os.path.join(prog.b.run_dir, 'scn', 'maphead', 'maphead.scn.txt')).read()
        return re.search(rf'^sec{screen}:.*?(?=^sec\d+:|\Z)', text, re.S | re.M).group(0)

    def src(self, body):
        p = os.path.join(tempfile.mkdtemp(prefix='p-', dir=TMP), 'x.dws'); open(p, 'w').write(body)
        return p

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/')
    def test_presence_rules_of_placed_slots_are_compiled(self):
        p = self.src('persistent flag joined = 12002;\n'
                     'place(species("Gekomon"), screen: 218, slot: 4, at: (450, -650), like: 1);\n'
                     'place(species("Gekomon"), screen: 218, slot: 5, at: (150, -350), like: 1);\n'
                     'city { presence { screen(218) { npc Gekomon slot 4 when not flag(joined); } } }\n'
                     'city { presence { screen(219) { npc Gekomon slot 0 when flag(joined); } } }\n'          # presence merges by screen
                     'script 178 { npc g = 9; on talk(g) replace { joined = true; } }\n')
        d, prog = dws_bytes([p], 'story-state', profile='extended-save')
        sec = self.maphead_section(prog, 218)
        self.assertRegex(sec, r'IF not trigger 12802, else (\w+)[^\n]*\n\s+LOAD_DIGIMON 110[^\n]*\n\s+SET_DIGIMON 110, 4, 0')   # the rule, autotalk 0
        self.assertRegex(sec, r'SET_SCRIPT[^\n]*\n\s+LOAD_DIGIMON 110[^\n]*\n\s+SET_DIGIMON 110, 5, 1')                   # no rule: unconditional
        e = errors_of('place(species("Gekomon"), screen: 218, slot: 4, at: (450, -650), like: 1);\n'
                      'city { presence { screen(218) { npc Botamon slot 4; } } }', exe='story-state', profile='extended-save')
        self.assertEqual(e, [])                                                    # the species check is the backend's (assemble)
        p2 = self.src('place(species("Gekomon"), screen: 218, slot: 4, at: (450, -650), like: 1);\n'
                      'city { presence { screen(218) { npc Botamon slot 4; } } }')
        with self.assertRaises(Exception) as c: dws_bytes([p2], 'story-state', profile='extended-save')
        self.assertIn('presence rule names species', str(c.exception))
        self.assertTrue(any('not a declared flag' in x for x in errors_of('city { presence { screen(218) { npc Gekomon slot 4 when flag(nope); } } }', exe='story-state', profile='extended-save')))

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/')
    def test_place_on_a_list_of_screens_and_presence_ranges(self):
        p = self.src('const TWO = [205, 206];\nflag f;\nplace(species("Gekomon"), screen: TWO, slot: 3, at: (0, 0));\n'
                     'city { presence { screen(205..=206) { npc Gekomon slot 3 when flag(f); } } }\n'
                     'script 165 { on enter { f = true; } }\n')
        prog = B.compile_sources([p], 'story-state', profile='extended-save')
        self.assertEqual([(s, k) for s, k, *_ in prog.b.placements], [(205, 3), (206, 3)])
        self.assertEqual(prog.b.city['presence'][205]['npcs'][0][3], prog.b.city['presence'][206]['npcs'][0][3])
        self.assertEqual(prog.b.city['presence'][205]['npcs'][0][3][0], 'trig')    # flag(f) resolved to its trigger

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/')
    def test_place_with_the_mods_own_map(self):
        import dwmap
        m = dwmap.MapFile(open(os.path.join(ROOT, 'extracted/MAP/MAP1/MAYO01.MAP'), 'rb').read())
        own = os.path.join(tempfile.mkdtemp(prefix='m-', dir=TMP), 'MGEN07.MAP'); open(own, 'wb').write(m.build())
        p = self.src(f'place(species("Puppetmon"), screen: 239, slot: 0, map: "{own}", hp: 900);\n'
                     'script new for screen 239 empty { npc p = 5; on talk(p) replace { battle(foes: [p]); } }\n')
        d, prog = dws_bytes([p], 'story-state', profile='extended-save')
        self.assertIn('MAP/MAP17/MGEN07.MAP', d)                                   # written where the disc has that name
        self.assertEqual(dwmap.MapFile(d['MAP/MAP17/MGEN07.MAP']).digimon[0]['type'], 181)
        self.assertRegex(self.maphead_section(prog, 239), r'SET_SCRIPT 222, 239[^\n]*\n(.*\n)*?\s+SET_DIGIMON 181, 0, 1')
        self.assertTrue(any('not found' in x for x in errors_of('place(species("Puppetmon"), screen: 239, slot: 0, map: "no/such.MAP");', exe='story-state', profile='extended-save')))

    def test_place_uses_this_builds_screen_content_before_authored_map_path(self):
        from dws import backend as BE
        from unittest.mock import patch
        folder = tempfile.mkdtemp(prefix='release-maps-', dir=TMP)
        own = os.path.join(folder, 'MGEN07.MAP')
        with open(own, 'wb') as f:
            f.write(b'this builds map')
        stale = os.path.join(TMP, 'old-maps', 'MGEN07.MAP')
        os.makedirs(os.path.dirname(stale), exist_ok=True)
        source = self.src(f'place(species("Puppetmon"), screen: 239, slot: 0, map: "{stale}");')
        # A fresh release has no authored-path alias. A stale developer build must
        # not take precedence either. Both .py new_screen and .dws place reach here.
        with patch.object(BE, 'SCREEN_DIRS', [folder]):
            for exists in (False, True):
                if exists:
                    with open(stale, 'wb') as f:
                        f.write(b'another builds map')
                prog = B.compile_sources([source], 'story-state', profile='extended-save')
                self.assertEqual(prog.b.placements[0][3]['map'], own)
        with patch.object(BE, 'SCREEN_DIRS', []):
            prog = B.compile_sources([source], 'story-state', profile='extended-save')
            self.assertEqual(prog.b.placements[0][3]['map'], stale)

    def test_a_pinned_variable_of_an_enum_declared_in_the_same_file(self):
        self.assertEqual(errors_of('enum E { A, B }\npersistent var s: E = 900;\nscript 178 { on enter { s = E.B; } }', exe='story-state', profile='extended-save'), [])

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/')
    def test_the_source_map_changes_no_byte(self):
        from dws import backend as BE
        src = os.path.join(ROOT, 'tools/dws/examples/first-quest.dws')
        a, _ = dws_bytes([src], 'original')
        BE.SRCMAP = True
        try:
            prog = B.compile_sources([src], 'original')
            d = tempfile.mkdtemp(prefix='sm-', dir=TMP); out = os.path.join(d, 'DG.SCN'); sm = os.path.join(d, 'map.json')
            B.assemble(prog, out, 'original', srcmap=sm)
        finally:
            BE.SRCMAP = False
        self.assertEqual(open(out, 'rb').read(), a['DG'])
        m = json.load(open(sm))
        self.assertIn('178', m)
        where = [w for o, w in m['178']]
        self.assertTrue(all(w == '-' or re.match(r'.*first-quest\.dws:\d+$', w) for w in where), where)
        self.assertIn('-', where)                                                   # the end of each event
        self.assertEqual([o for o, _ in m['178']], sorted(o for o, _ in m['178']))


class RandFlowTests(unittest.TestCase):
    """tools/dws/randflow.py: the instructions that draw random numbers are the same, in the same order, on every path of a section of two builds
    (docs/developing.md, "Random numbers")."""
    SRC = ('.section 5 S\nS:\n    SET_DIALOG_OWNER 5\n    STORE_RANDOM p110, 99\n    IF p110 <= 24, else A\n    SPAWN_ITEM 44, 46, 45\n    JUMP_TO J\nA:\n    DELAY 3\n'
           'J:\n    STORE_RANDOM p110, 3\n    IF p110 <= 1, else B\n    SET_TRIGGER 9\nB:\n    END_SECTION\n')

    @staticmethod
    def blob(text):
        from dws import bytecode as bytecode
        return bytecode.assemble_script(text, 'randflow-test')[0]

    def same(self, a, b):
        from dws import randflow as R
        return R.check_script(self.blob(a), self.blob(b))

    def test_the_consumers_are_counted_and_equal_layouts_pass(self):
        from dws import randflow as R
        b = self.blob(self.SRC); e = R.section_entries(b)[5]
        self.assertEqual(sorted(R.CONSUMERS[k[0]] for k in R.multiset(b, e).elements()), ['STORE_RANDOM', 'STORE_RANDOM'])
        self.assertEqual(self.same(self.SRC, self.SRC), [])
        # layout only: a threaded jump, a duplicated END_SECTION, dead code, a redundant owner
        other = self.SRC.replace('    JUMP_TO J\n', '    JUMP_TO K\nK:\n    JUMP_TO J\n').replace('B:\n    END_SECTION\n', 'B:\n    END_SECTION\n    STORE_RANDOM p110, 7\n    END_SECTION\n')
        self.assertEqual(self.same(self.SRC, other), [])

    def test_a_changed_removed_added_or_reordered_draw_is_caught(self):
        r = lambda t: [(k, d[:40]) for _, k, d in self.same(self.SRC, t)]
        self.assertTrue(r(self.SRC.replace('p110, 3', 'p110, 4')))                                # another operand: another roll
        self.assertTrue(r(self.SRC.replace('    STORE_RANDOM p110, 3\n', '')))                      # a draw removed
        self.assertTrue(r(self.SRC.replace('    DELAY 3\n', '    DELAY 3\n    STORE_RANDOM p111, 2\n')))      # a draw added on one path
        swapped = self.SRC.replace('    STORE_RANDOM p110, 99\n    IF p110 <= 24, else A', '    STORE_RANDOM p110, 3\n    IF p110 <= 24, else A').replace('J:\n    STORE_RANDOM p110, 3\n', 'J:\n    STORE_RANDOM p110, 99\n')
        self.assertTrue(r(swapped))                                                                # two draws in the other order
        self.assertTrue(r(self.SRC.replace('    SPAWN_ITEM 44, 46, 45\n', '    CALL_ROUTINE 12\n')))      # a routine call (it may draw) in place of another instruction

    def test_copying_the_join_into_the_arms_changes_the_multiset_not_the_paths(self):
        from dws import randflow as R
        dup = ('.section 5 S\nS:\n    SET_DIALOG_OWNER 5\n    STORE_RANDOM p110, 99\n    IF p110 <= 24, else A\n    SPAWN_ITEM 44, 46, 45\n    STORE_RANDOM p110, 3\n    IF p110 <= 1, else B\n    SET_TRIGGER 9\n'
               'B:\n    END_SECTION\nA:\n    DELAY 3\n    STORE_RANDOM p110, 3\n    IF p110 <= 1, else C\n    SET_TRIGGER 9\nC:\n    END_SECTION\n')
        rows = R.report(self.blob(self.SRC), self.blob(dup))
        self.assertEqual([(r[3], r[4]) for r in rows], [(False, True)])          # multiset differs (2 against 3 draws in the text), the sequences are equal

    def test_recursive_subroutines_do_not_blow_up(self):
        t = ('.section 5 S\nS:\n    JUMP_AND_LINK F\n    END_SECTION\nF:\n    STORE_RANDOM p110, 3\n    IF p110 <= 1, else G\n    JUMP_AND_LINK F\nG:\n    JUMP_RETURN\n')
        self.assertEqual(self.same(t, t), [])
        self.assertTrue(self.same(t, t.replace('p110, 3', 'p110, 4')))

    @unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/ (your own disc)')
    def test_real_scripts_original_against_itself_and_mutated(self):
        """Script 2 (Kunemon, a STORE_RANDOM pair in section 254 and the food quest): the original against its own disassembly assembled again, and against edits."""
        from dws import bytecode as bytecode
        from dws import randflow as R
        d, _ = textx.disassemble()
        text = open(os.path.join(d, 'script_002.scn.txt'), encoding='utf-8').read()
        orig = open(os.path.join(ROOT, 'extracted/SCN/DG.SCN'), 'rb').read(); offs = bytecode.container_entries(orig); blob = orig[offs[2]:offs[3]]
        again = bytecode.assemble_script(text, 'script_002')[0]
        self.assertEqual(R.check_script(blob, again), [])
        self.assertEqual(text.count('STORE_RANDOM'), 2)
        gone = text.replace('    STORE_RANDOM p110, 99', '    DELAY 1', 1)
        self.assertEqual([(s, k) for s, k, _ in R.check_script(blob, bytecode.assemble_script(gone, 'x')[0])][:1], [(254, 'multiset')])
        other = text.replace('STORE_RANDOM p110, 99', 'STORE_RANDOM p110, 98', 1)          # another roll
        self.assertTrue(R.check_script(blob, bytecode.assemble_script(other, 'x')[0]))

    @unittest.skipUnless(os.path.exists(os.path.join(ROOT, 'build/sweep/readable-DG.SCN')), 'needs the discs of the sweep (tools/dws/testing/sweep.py discs)')
    def test_all_sections_of_the_original_against_reorder_and_readable(self):
        """All 1 553 sections (DG.SCN and MAPHEAD; the 1 834 of the beautifier CSV count MAPHEAD's 281 twice): the same consumers in the same order on every path. The
        multiset itself differs in the 4 sections where the readable build copies a join into the arms of an if, and in Kunemon's 2:6, where the disc's two
        food tests (each with its own `remove_chosen_item`) are one test with one call (lift.merge_ifs): the same call on every path."""
        from tools.dev import story_test as T
        from dws import randflow as R
        discs = T.load_discs(); S = {k: T.Scripts(discs[k]['dg'], discs[k]['maphead']) for k in ('orig', 'reorder', 'readable')}
        for alt in ('reorder', 'readable'):
            n = 0; copies = []
            for sid in sorted(S['orig'].raw):
                for sec, ca, cb, same_set, same_seq, note in R.report(S['orig'].raw[sid], S[alt].raw[sid]):
                    n += 1; self.assertTrue(same_seq, (alt, sid, sec, note))
                    if not same_set: copies.append((sid, sec))
            self.assertEqual(n, 1553)
            self.assertEqual(copies, [] if alt == 'reorder' else [(2, 6), (126, 81), (130, 81), (209, 5), (215, 6)])


@unittest.skipUnless(HAVE_EXTRACTED, 'needs extracted/ (your own disc)')
class StoryBuild(unittest.TestCase):
    """tools/dws/basebuild.py: story/base (made from the disc) is the source of DG.SCN and MAPHEAD.SCN; overrides of mods."""

    @classmethod
    def setUpClass(cls):
        from dws import basebuild as BB
        cls.BB = BB
        BB.ensure_base(log=lambda m: None)
        cls.dir = tempfile.mkdtemp(prefix='story-', dir=TMP)

    def build(self, name, sources=(), mods=None, mods_root=None, base=None):
        out = os.path.join(self.dir, name, 'DG.SCN')
        kw = {'mods_root': mods_root} if mods_root else {}
        if base is not None: kw['base'] = base
        prog, report, run, mh = self.BB.build(list(sources), out, mods=mods, log=lambda m: None, **kw)
        return out, mh, report

    def mod(self, root, name, files, toml=''):
        for rel, text in files.items():
            p = os.path.join(root, name, 'overrides', rel); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'w', encoding='utf-8').write(text)
        os.makedirs(os.path.join(root, name), exist_ok=True)
        open(os.path.join(root, name, 'mod.toml'), 'w').write(f'name = "{name}"\nversion = "0.1.0"\n{toml}')

    def test_no_mod_is_the_disc_section_by_section(self):
        """Without mods, every section of every script and of MAPHEAD runs what the disc's runs (flowcmp from each entry)."""
        base = original_story()
        dg, mh, rep = self.build('nomod', mods=[], base=base)
        self.assertEqual(self.BB.verify(B.BE.DG_SCN, B.BE.MAPHEAD_SCN, dg, mh, log=lambda m: None), 0)
        # the containers are made from story/base alone (step 2): every script, its section table and every section (shared code has
        # its own blocks; 199-202 fit their buffer); the disc gives only DG.SCN's size
        self.assertTrue(any(re.search(r'generated from story/base: 222 scripts and MAPHEAD, \d+ events, nothing of the disc kept', r) for r in rep), rep)
        dis = os.path.join(os.path.dirname(dg), 'story', 'dis')
        self.assertTrue(open(os.path.join(dis, 'script_102.scn.txt')).readline().startswith('; script 102: generated from the story sources'))
        self.assertEqual(open(os.path.join(dis, 'header.bin'), 'rb').read(), bytes(2048))
        # the negative control: the verifier sees a changed section
        dg2, mh2, _ = self.build('devsave', [os.path.join(ROOT, 'tools/dws/examples/dev-save.dws')], mods=[], base=base)
        out = []
        self.assertEqual(self.BB.verify(dg, mh, dg2, mh2, log=out.append), 1)
        self.assertIn('script 178 sec5', '\n'.join(out))

    OVERRIDE = {   # the retired override example mod (overrides/ are deprecated; a Python mod writes a handler instead)
        'script_002/sec5.dws': 'script 2 {\n    npc redvegiemon5 = 5;\n    on talk(redvegiemon5) replace {\n'
                               '        say(redvegiemon5, "Psst. Take this instead.");\n        give(item("Meat"), 1);\n    }\n}\n',
        'script_002/sec254.patch': '--- story-section 2 254\n+++ override-example\n@@ -11,3 +11,3 @@\n         store_random(random_roll, 99);\n'
                                   '-        if (random_roll <= 24) {\n+        if (random_roll <= 49) {\n             spawn_item(item("Digimushrm"), 46, 45);\n'}

    def test_override_and_patch(self):
        """A mod with overrides/: section 5 of script 2 replaced by its own DWS, section 254 patched; nothing else changes."""
        root = tempfile.mkdtemp(prefix='mods-', dir=TMP); self.mod(root, 'override-example', self.OVERRIDE, 'enabled = false\n')
        dg, mh, _ = self.build('nomod2', mods=[])
        dg2, mh2, report = self.build('example', mods=['override-example'], mods_root=root)
        out = []
        self.assertEqual(self.BB.verify(dg, mh, dg2, mh2, log=out.append), 2)
        self.assertIn('script 2 sec5', '\n'.join(out)); self.assertIn('script 2 sec254', '\n'.join(out))
        self.assertTrue(any('override-example:2/254 (patch)' in r for r in report))
        self.assertTrue(any('deprecated' in r for r in report))
        # a mod with `enabled = false` is left out unless named
        self.assertFalse(any(o.mod == 'override-example' for o in self.BB.find_overrides(root)))
        self.assertTrue(any(o.mod == 'override-example' for o in self.BB.find_overrides(root, only=['override-example'])))

    def test_conflicts(self):
        root = tempfile.mkdtemp(prefix='mods-', dir=TMP)
        sec5 = 'script 2 {\n    npc redvegiemon5 = 5;\n    on talk(redvegiemon5) replace {\n        say(redvegiemon5, "Hi.");\n    }\n}\n'
        self.mod(root, 'a', {'script_002/sec5.dws': sec5}); self.mod(root, 'b', {'script_002/sec5.dws': sec5})
        with self.assertRaisesRegex(DwsError, r'overridden twice: mod a .*and mod b'):
            self.build('c1', mods_root=root)
        # an override and a source that replaces the same section
        dev = os.path.join(ROOT, 'tools/dws/examples/dev-save.dws')
        r2 = tempfile.mkdtemp(prefix='mods-', dir=TMP)
        self.mod(r2, 'c', {'script_178/sec5.dws': 'script 178 {\n    npc jijimon = 5;\n    on talk(jijimon) replace {\n        say(jijimon, "Hi.");\n    }\n}\n'})
        with self.assertRaisesRegex(DwsError, r'script 178 section 5 is replaced by one and also changed by another: .*dev-save.dws.*mod c'):
            self.build('c2', [dev], mods_root=r2)
        # the path says one section, the event is another
        r3 = tempfile.mkdtemp(prefix='mods-', dir=TMP); self.mod(r3, 'd', {'script_002/sec6.dws': sec5})
        with self.assertRaisesRegex(DwsError, r'override of script 2 section 6 \(by its path\) but has an event for script 2 section 5'):
            self.build('c3', mods_root=r3)
        # a patch made against something else
        r4 = tempfile.mkdtemp(prefix='mods-', dir=TMP)
        self.mod(r4, 'e', {'script_002/sec254.patch': '@@ -11,1 +11,1 @@\n-        if (random_roll <= 77) {\n+        if (random_roll <= 49) {\n'})
        with self.assertRaisesRegex(DwsError, r'hunk 1 .*does not match'):
            self.build('c4', mods_root=r4)
        # not a section path
        r5 = tempfile.mkdtemp(prefix='mods-', dir=TMP); self.mod(r5, 'f', {'kunemon.dws': sec5})
        with self.assertRaisesRegex(DwsError, r'an override is overrides/script_NNN/secN.dws'):
            self.build('c5', mods_root=r5)

    def test_maphead_override(self):
        """A MAPHEAD section replaced by an override (spliced into MAPHEAD.SCN)."""
        src, _ = self.BB.event_source(self.BB.BASE, 'maphead', 1)
        root = tempfile.mkdtemp(prefix='mods-', dir=TMP)
        self.mod(root, 'm', {'maphead/sec1.dws': src.replace('section(1) replace {', 'section(1) replace {\n        engine.cutscene = false;', 1)})
        dg, mh, _ = self.build('mh0', mods=[])
        dg2, mh2, _ = self.build('mh1', mods_root=root)
        out = []
        self.assertEqual(self.BB.verify(dg, mh, dg2, mh2, log=out.append), 1, out)
        self.assertIn('MAPHEAD sec1', '\n'.join(out))

    def test_apply_patch(self):
        text = 'a\nb\nc\nd\ne\n'
        self.assertEqual(self.BB.apply_patch(text, '@@ -2,3 +2,3 @@\n b\n-c\n+C\n d\n', 'x'), 'a\nb\nC\nd\ne\n')
        self.assertEqual(self.BB.apply_patch('z\n' + text, '@@ -2,3 +2,3 @@\n b\n-c\n+C\n d\n', 'x'), 'z\na\nb\nC\nd\ne\n')   # moved: found by context

    def test_authored_reproduction_checks_both_sides(self):
        sha = lambda b: hashlib.sha256(b).hexdigest()
        approved = {'a.py': {'original_sha256': sha(b'original'), 'authored_sha256': sha(b'edited'), 'reason': 'intentional edit'}}
        check = self.BB.reproduction_differences
        self.assertEqual(check({'a.py': b'edited'}, {'a.py': b'original'}, approved), [])
        self.assertEqual(check({'a.py': b'accident'}, {'a.py': b'original'}, approved), ['a.py'])
        self.assertEqual(check({'a.py': b'edited'}, {'a.py': b'generator drift'}, approved), ['a.py'])
        self.assertEqual(check({}, {}, approved), ['a.py'])
        self.assertEqual(check({'a.py': b'original'}, {'a.py': b'original'}, approved), ['a.py'])
        self.assertEqual(check({'other.py': b'edited'}, {'other.py': b'original'}, {}), ['other.py'])

    def test_minitoml_reads_names_toml(self):
        from dws import minitoml
        p = os.path.join(ROOT, 'story/names.toml')
        if minitoml.tomllib: self.assertEqual(minitoml.loads(open(p, encoding='utf-8').read()), minitoml.tomllib.load(open(p, 'rb')))


def show_code(path, exe='original'):
    """The assembly lines of every event a story file compiles to (`dws show`)."""
    prog = B.compile_sources([path], exe, profile='extended-save' if exe == 'story-state' else 'original')
    return [l for info in prog.b.scripts.values() for sec, rep, code, ents, p in info['events'] for l in code]


def PL_text_keys(path):
    from dws.py import lower as PL
    return PL.lower_file(path)[0].texts


def errors_of_py(path):
    try:
        B.compile_sources([path])
    except B.DwsErrors as e:
        return '\n'.join(x.render() for x in e.errors)
    return ''


class PythonView(unittest.TestCase):
    """The story language: the Python view of the base (tools/dws/py/view.py, milestone 3b) and its stubs (dws types)."""

    @classmethod
    def setUpClass(cls):
        from dws import basebuild as BB
        BB.ensure_base(log=lambda m: None)
        cls.base = BB.BASE

    def view(self, sid):
        return open(glob.glob(os.path.join(self.base, 'zones', '*', f's{sid:03d}-*', 'script.py'))[0], encoding='utf-8').read()

    def test_every_view_is_python(self):
        import ast
        files = glob.glob(os.path.join(self.base, 'zones', '*', '*', 'script.py')) + [os.path.join(self.base, 'maphead', 'hooks.py')]
        self.assertEqual(len(files), 223)
        for f in files: ast.parse(open(f, encoding='utf-8').read(), f)

    def test_forms(self):
        v = self.view(77)
        self.assertIn('region = screen(Screen.ancient_glacial_region_80)', v)
        self.assertIn('vermilimon4 = region.npc(Species.Vermilimon, slot=4)', v)
        self.assertIn('recruitable(vermilimon0, line=t5.u0)', v)
        self.assertIn('recruitable(vermilimon4, line=t9.u0, joins=Species.Yanmamon)', v)     # the disc's quirk stays explicit
        self.assertIn('roll = random.roll(99)\n    if roll <= 14:', v)                               # the draw, then its test (one form)
        self.assertIn('sections(254, 5, 6, 7, 8, 9, 10)', v)
        self.assertNotIn('"I', v)                                                               # keys, never the game's words
        v = self.view(2)
        self.assertIn('@kunemon.on_talk(scene=True)', v); self.assertNotIn('dws(', v)            # Kunemon reads as Python (review §d)
        for want in ('    if ask(yes=t6.m0.o0, no=t6.m0.o1):\n        pick = pick_item()\n        if pick is Picked.EMPTY:\n',
                     '        elif pick is Picked.CANCELLED:\n            pass\n        elif pick in (Item.Meat, Item.GiantMeat,',
                     'take_picked()\n', 'walk_away(1219, 984, looks=3)', '    say(t6.u9)\n'):
            self.assertIn(want, v)
        v = self.view(178)
        self.assertIn('    if debug_test_npcs:\n        return tokomon.talk()\n', v)                     # `unless (!c) goto sec6;`
        self.assertNotIn('pass\n    else:', v)
        self.assertIn('swing_door(', self.view(61)); self.assertIn('if partner.species in (Species.', self.view(87))
        self.assertIn('if not recruited(Species.Koromon) and not recruited(Species.Punimon) and back_dimension_portal != 0 and '
                      'recruited(Species.Botamon) and recruited(Species.Yuramon):', v)
        self.assertIn('forest: ScreenRef', open(os.path.join(ROOT, 'typings/dw/base/native_forest_2.pyi')).read())

    def test_views_lower_to_the_proven_story(self):
        """M4a: every view lowered (tools/dws/py/lower.py) and proven against the disc's sections; the build from the views is the
        build from the DWS, byte for byte."""
        from dws import readable, basebuild as BB
        from dws.py import lower as PL
        lifted, mhl, _ = readable.lift_disc(only={2, 18, 77, 102, 178, 216})
        proven, bad = PL.check_base(self.base, lifted, [], log=lambda m: None)
        self.assertEqual(bad, []); self.assertGreater(proven, 60)
        d = tempfile.mkdtemp(prefix='frompy-', dir=TMP)
        for label, base in (('original', original_story()), ('authored', self.base)):
            out = {}
            for k, fp in (('dws', False), ('py', True)):
                o = os.path.join(d, label, k, 'DG.SCN')
                _, _, _, mh = BB.build([], o, base=base, mods=[], log=lambda m: None, from_py=fp)
                out[k] = (open(o, 'rb').read(), open(mh, 'rb').read())
            self.assertEqual(out['dws'], out['py'], label)

    def test_shared_jump_return_keeps_the_call_frame(self):
        """Amida's L24 must return to step1 before its path flag and trap tests; helpers that fall through still inline."""
        from dws.py import lower as PL
        p = os.path.join(TMP, 'shared-return.py')
        for ending in ('    raw.jump_return()\n',
                       '    if trigger(5):\n        raw.jump_return()\n',
                       '    dws("jump_return();")\n'):
            with self.subTest(ending=ending):
                open(p, 'w').write('from dw import *\nforest = screen(18)\n'
                                   '@forest.on_step(1)\ndef step1():\n    L24()\n    give(bits=7)\n    helper()\n'
                                   'def L24():\n    give(bits=3)\n' + ending +
                                   'def helper():\n    give(bits=11)\n')
                _, sc, _ = PL.lower_file(p)
                sc = re.sub(r"(    // @py \d+)+$", "", sc, flags=re.M)
                self.assertIn('gosub L24;\n        give_bits(7);\n        give_bits(11);', sc)
                self.assertNotIn('gosub helper;', sc)
                self.assertIn('jump_return();', sc)

    def test_lowering_errors_are_human(self):
        p = os.path.join(TMP, 'bad.py')
        open(p, 'w').write('from dw import *\nbed = screen(1)\nk = bed.npc(Species.Kunemon, slot=1)\n@k.on_talk\ndef talk():\n    x = 3\n')
        e = errors_of_py(p)
        self.assertIn('bad.py:6:5: error: an assignment is not part of the story language', e)
        open(p, 'w').write('from dw import *\nimport os\n')
        self.assertIn('plain `import` is not part of the story language', errors_of_py(p))
        open(p, 'w').write('from dw import *\nbed = screen(1)\n@bed.on_enter\ndef enter():\n    say("hi")\n')
        self.assertIn('without a speaker is only for `on_talk`', errors_of_py(p))

    def test_guards_lower_to_one_if(self):
        """`if c: return` is `unless (!c) return;` (De Morgan, comparisons flipped); a test with no negated form stays an if."""
        from dws.py import lower as PL
        p = os.path.join(TMP, 'guard.py')
        open(p, 'w').write('from dw import *\nbed = screen(1)\nk = bed.npc(Species.Kunemon, slot=1)\n@k.on_talk\ndef talk():\n'
                           '    if trigger(5) and bits >= 30:\n        return\n    if partner.species in (Species.Agumon,):\n        return\n'
                           '    say("hi")\n')
        _, sc, _ = PL.lower_file(p)
        self.assertIn('unless (!trigger(5) || bits < 30) return;', sc)
        self.assertIn('store_digimon_type(partner_type);', sc); self.assertIn('if (partner_type in [species(', sc)

    def test_stubs_are_current(self):
        from dws.py import stubs
        self.assertEqual(stubs.write(check=True, log=lambda m: None), 0)


class PythonMods(unittest.TestCase):
    """The story language for mods (milestone 4b): guards, quests as bits, new NPCs, ownership, hashed text."""

    @classmethod
    def setUpClass(cls):
        from dws import basebuild as BB
        BB.ensure_base(log=lambda m: None)              # (the views and stubs of the local disc, current with the tools)

    def mod(self, files, mod='m-a', toml='[save]\nflags = "717-726"\nvars = "9-10"\n'):
        """A scratch mod (story/mods/<mod>/src/ under a temporary root); `toml`: its mod.toml (None: none)."""
        root = tempfile.mkdtemp(prefix='mods-', dir=TMP)
        d = os.path.join(root, 'story', 'mods', mod, 'src'); os.makedirs(d)
        if toml is not None: open(os.path.join(root, 'story', 'mods', mod, 'mod.toml'), 'w').write(f'name = "{mod}"\n' + toml)
        for name, text in files.items(): open(os.path.join(d, name), 'w').write(text)
        return root, [os.path.join(d, n) for n in files]

    def lowered(self, path):
        from dws.py import lower as PL
        m, sc, mh = PL.lower_file(path)
        return re.sub(r'(    // @py \d+)+$', '', (m.decl_text or '') + (sc or '') + (mh or ''), flags=re.M)     # without the source-map marks

    def test_quest_presence_recruitment_and_new_screen(self):
        _, (house, forest, arena, quest) = self.mod({
            'house.py': 'from dw import *\nfrom dw.base.jijimons_house import tokomon\nfrom .quest import Visit\n'
                        'house = screen(Screen.jijimons_house)\n'
                        'guest = house.npc(Species.Gekomon, at=(450, -650), behaves_like=tokomon, when=Visit.before(Visit.JOINED))\n'
                        'resident = house.npc(Species.Gekomon, at=(150, -350), behaves_like=tokomon, when=Visit.JOINED)\n'
                        '@guest.on_talk(when=Visit.NONE, scene=True)\ndef ask():\n    say("Hello")\n'
                        '@guest.on_talk(when=Visit.FOUND, scene=True)\ndef join():\n'
                        '    send_to_city(line="Welcome", prosperity=2)\n    advance(Visit.JOINED)\n',
            'forest.py': 'from dw import *\nfrom dw.base.native_forest_2 import forest\nfrom .quest import Visit\n'
                         '@forest.on_enter(when=Visit.ASKED)\ndef enter():\n    warp(239, entry=2)\n',
            'arena.py': 'from dw import *\narena = new_screen(239, map="build/test/ARENA.MAP")\n'
                        'opponent = arena.npc(Species.Puppetmon)\n@opponent.on_talk(scene=True)\ndef talk():\n'
                        '    if fight(opponent, escape=False) != "won":\n        say("Try again")\n        return\n',
            'quest.py': 'from dw import *\nclass Visit(Quest):\n'
                        '    NONE = auto()\n    ASKED = auto()\n    FOUND = auto()\n    JOINED = auto()\n',
        }, toml='[save]\nflags = "12000-12010"\nvars = "9-10"\n')
        t = self.lowered(house)
        self.assertIn('place(species(110), screen: 218, slot: 4, at: (450, -650), like: 1);', t)
        self.assertIn('npc species(110) slot 4 when not flag(Visit_b0) or not flag(Visit_b1);', t)
        self.assertIn('npc species(110) slot 5 when flag(Visit_b0) and flag(Visit_b1);', t)
        self.assertIn('on talk(guest) replace {', t)
        self.assertIn('if (!Visit_b0 && !Visit_b1) {', t)
        self.assertIn('} else if (!Visit_b0 && Visit_b1) {', t)
        self.assertIn('join_city_camera(guest, species(110), 8, 11, text("m-a.', t)
        t = self.lowered(forest)
        self.assertIn('on enter {', t)
        self.assertNotIn('on enter replace', t)
        self.assertIn('warp_to(239, 2, 255);', t)
        t = self.lowered(arena)
        self.assertIn('script new for screen 239 empty {', t)
        self.assertRegex(t, r'battle\(foes: \[opponent\]\);\s+if \(!won\) \{')
        self.assertIn('pub flag Visit_b0 = 12000;', self.lowered(quest))

    def test_guards_ownership_and_errors(self):
        head = 'from dw import *\nfrom dw.base.jijimons_house import jijimon\n'
        root, (p,) = self.mod({'a.py': head + 'flag_x = flag()\n@jijimon.on_talk\ndef talk():\n    say("Hi")\n'})
        self.assertIn('needs `when=`', errors_of_py(p))
        root, (p,) = self.mod({'a.py': head + 'x = flag()\n@jijimon.on_talk(when=x, scene=True)\ndef talk():\n    say("Hi")\n'})
        t = self.lowered(p)
        self.assertIn('on talk(jijimon) {', t); self.assertIn('if (x) {', t); self.assertIn('engine.cutscene = true;', t)
        self.assertIn('return;', t)                                                             # the first match answers
        house = 'from dw import *\nhouse = screen(Screen.jijimons_house)\ng = house.npc(Species.Gekomon, slot=4, at=(1, 2))\n'
        _, (a,) = self.mod({'a.py': house}, 'm-a'); _, (b,) = self.mod({'b.py': house}, 'm-b')
        try:
            B.compile_sources([a, b], 'story-state'); e = ''
        except B.DwsErrors as x:
            e = '\n'.join(y.render() for y in x.errors)
        self.assertIn('this new NPC goes in slot 5', e)                                          # (slot=4 twice: the second is 5)
        from dws.py import lower as PL
        house = house.replace('slot=4, ', '')
        _, (a,) = self.mod({'a.py': house}, 'm-a'); _, (b,) = self.mod({'b.py': house}, 'm-b')
        B.compile_sources([a, b], 'story-state')                                                      # two mods: slots 4 and 5, in order
        self.assertIn('slot: 5,', open(PL.lowered_path(b, 'script')).read())
        root, (p,) = self.mod({'a.py': house + '@house.on_enter(scene=True)\ndef enter():\n    narrator.say("x")\n'})
        self.assertIn('`scene=True` only works on on_talk', errors_of_py(p))

    def test_ranges_lock_srcmap_why(self):
        """M5: a mod's reserved range and its lock; the source map points at the .py; `dws why` prints the guard chain."""
        from dws.py import lower as PL, why as PW
        src = ('from dw import *\nclass Q(Quest):\n    A = auto()\n    B = auto()\nok = flag()\n'
               'house = screen(Screen.jijimons_house)\ng = house.npc(Species.Gekomon, slot=4, at=(1, 2), when=Q.B)\n'
               '@g.on_talk(when=Q.A)\ndef first():\n    say("One.")\n    advance(Q.B)\n'
               '@g.on_talk\ndef later():\n    say("Two.")\n')
        root, (p,) = self.mod({'a.py': src}, 'm-r')
        mdir = os.path.join(root, 'story', 'mods', 'm-r')
        open(os.path.join(mdir, 'mod.toml'), 'w').write('name = "m-r"\n[save]\nflags = "12100-12109"\n')
        prog = B.compile_sources([p], 'story-state', profile='extended-save')         # (the lock is read from the mod's own folder)
        self.assertFalse(os.path.exists(os.path.join(mdir, 'save.lock')))         # (written when the whole command succeeded)
        B.save_locks()
        self.assertEqual(json.load(open(os.path.join(mdir, 'save.lock')))['flags'], {'Q_b0': 12100, 'ok': 12101})
        self.assertEqual(prog.alloc.table['m_r.Q_b0'], 12100)
        lowered = PL.lowered_path(p, 'script')
        lm = PL.LINEMAP[os.path.abspath(lowered)]
        self.assertTrue(lm[0].endswith('a.py'))
        line = next(k for k, l in enumerate(open(lowered).read().split('\n'), 1) if 'say(g, text(' in l and 'One' not in l and lm[1].get(k) == 10)
        self.assertTrue(line)
        out = []
        old = PW.mods_files; PW.mods_files = lambda: [p]
        try: self.assertTrue(PW.why('g', 'Q=B', out=out.append))
        finally: PW.mods_files = old
        t = '\n'.join(out)
        self.assertIn('there when: Q.B', t); self.assertIn('1. first (line 9): when Q.A', t); self.assertIn('[false]', t)
        self.assertIn('2. later (line 13): always  <- answers', t)

    def test_examples_mod_builds(self):
        """story/mods/examples: each Python example compiles alone (they share Jijimon's house), with no deprecation warning."""
        for p in sorted(glob.glob(os.path.join(ROOT, 'story/mods/examples/src/*.py'))):
            prog = B.compile_sources([p])
            self.assertFalse([w for w in prog.warn.render() if 'deprecated' in w], p)
            B.assemble(prog, os.path.join(tempfile.mkdtemp(dir=TMP), 'DG.SCN'))
        lock = json.load(open(os.path.join(ROOT, 'story/mods/examples/save.lock')))
        self.assertTrue(all(780 <= n <= 799 for n in lock['flags'].values()))

    def test_ask_keywords_and_every_error(self):
        """ask's keywords are bound by name (yes is the top option whatever
        the order), `not has(x, n)` is `has(x) < n`, and every error of a file is reported in one run (a case at its line)."""
        head = 'from dw import *\nfrom dw.base.jijimons_house import jijimon\nseen = flag()\n@jijimon.on_talk(when=not seen)\ndef talk():\n'
        root, (p,) = self.mod({'a.py': head + '    if ask(no="Nope", yes="Sure"):\n        say("A")\n    if not has(Item.Meat, 2):\n'
                                            '        say("B")\n'})
        t = self.lowered(p)
        from dws.py import lower as PL
        self.assertLess(t.index(PL.text_key('m-a', 'Sure')), t.index(PL.text_key('m-a', 'Nope')))
        self.assertIn(f'text("{PL.text_key("m-a", "Nope")}") or cancel', t)
        self.assertIn('if (has(item(38)) < 2) {', t)
        root, (p,) = self.mod({'a.py': head + '    x = 3\n    if ask(yes="a", maybe="b"):\n        say("A")\n'
                                            '    match choose(left="L", right="R"):\n        case "rigth":\n            say("C")\n'
                                            '    if won:\n        say("D")\n'})
        e = errors_of_py(p)
        for want in ('a.py:6:5: error: an assignment', 'a.py:7:8: error: ask() takes exactly yes= and no=', 'maybe= is not one',
                     "a.py:10:14: error: no option ['rigth']", 'a.py:12:8: error: "won" is not a name'):
            self.assertIn(want, e)

    def test_owning_vs_adding(self):
        """Intuitiveness 3: modules by screen name, new_screen, take_over owns a base NPC (a species swap writes its own
        talk), npc() on a slot the game uses is an error, a `return` in a handler added to the base's enter is refused."""
        head = 'from dw import *\n'
        root, (p,) = self.mod({'a.py': head + 'from dw.base.s178 import jijimon\n'})
        self.assertIn('script 178 is screen dw.base.jijimons_house', errors_of_py(p))
        root, (p,) = self.mod({'a.py': head + 'house = screen(Screen.jijimons_house)\ng = house.npc(Species.Gekomon, slot=0, at=(1, 2))\n'})
        e = errors_of_py(p)
        self.assertIn('slot 0 of this screen is taken: Jijimon (jijimon in the base)', e)
        self.assertIn('g = take_over(jijimon, species=...)', e); self.assertIn('a new NPC goes in slot 4', e)
        src = (head + 'from dw.base.native_forest_0 import modokibetamon1\nv = take_over(modokibetamon1, species=Species.RedVegiemon)\n'
               '@v.on_talk\ndef talk():\n    recruitable(v, line="Grr!")\n')
        root, (p,) = self.mod({'a.py': src})
        t = self.lowered(p)
        self.assertIn('place(species(77), screen: 0, slot: 1);', t); self.assertIn('on talk(v) replace {', t)
        self.assertIn('npc v = 6;', t); self.assertIn('recruit(species(77));', t)
        root, (p,) = self.mod({'a.py': src.split('@v')[0] + '@modokibetamon1.on_talk(when=True)\ndef t2():\n    say("x")\n'})
        e = errors_of_py(p)
        self.assertIn('v = take_over(modokibetamon1) owns its talk, but no handler answers it', e)
        self.assertIn('modokibetamon1 is taken over as v: write its handlers on v', e)
        root, (p,) = self.mod({'a.py': head + 'from dw.base.jijimons_house import house\nseen = flag()\n'
                                            '@house.on_enter(when=not seen)\ndef e():\n    if trigger(5):\n        return\n    seen.set()\n'})
        self.assertIn('`return` in a handler added to the base\'s on_enter ends the screen\'s section', errors_of_py(p))
        root, (p,) = self.mod({'a.py': head + 'h = screen(239, new=True)\n'})
        self.assertIn('new_screen(239, map="...")', errors_of_py(p))
        from dws import basebuild as BB
        BB.ensure_base(log=lambda m: None)
        v = open(glob.glob(os.path.join(BB.BASE, 'zones', '*', 's176-*', 'script.py'))[0]).read()
        self.assertIn('piximon = shop_.npc(Species.Piximon173, slot=4)', v)        # the .MAP slot 4 is entity 6
        self.assertIn('    piximon.say(t82.u0)', v); self.assertIn('keeper.play(28)', v)

    def test_names_of_items_4_to_10(self):
        """Intuitiveness 4-10: behaves_like= and when= on npc(), recruit, entry=, ms everywhere, objects[n].animate(k),
        sound.jingle(), offense=; the old names are errors that name the new one."""
        head = 'from dw import *\nfrom dw.base.jijimons_house import house, tokomon\nq = flag()\n'
        root, (p,) = self.mod({'a.py': head + 'g = house.npc(Species.Gekomon, slot=4, at=(450, -650), behaves_like=tokomon, when=q, offense=9)\n'
                                            '@g.on_talk\ndef talk():\n    recruit(Species.Gekomon)\n    warp(239, entry=2)\n'
                                            '    wait(1000)\n    fade_to_white(1000)\n    walk_away(1, 2, pause=500)\n'
                                            '    objects[12].animate(1)\n    sound.jingle()\n'})
        t = self.lowered(p)
        for want in ('place(species(110), screen: 218, slot: 4, at: (450, -650), like: 1, off: 9);', 'npc species(110) slot 4 when flag(q);',
                     'recruit(species(110));', 'warp_to(239, 2, 255);', 'wait(20);', 'engine.arg = 20;\n', 'call_routine(routine("fade_to_white"));',
                     'walk_away(g, 1, 2, pause: 10);', 'engine.object = 12;', 'engine.animation = 1;',
                     'call_routine(routine("reset_object_animation"));', 'sound(8, 11);'):
            self.assertIn(want, t)
        root, (p,) = self.mod({'a.py': head + 'g = house.npc(Species.Gekomon, slot=4, at=(1, 2), like_slot=1, appears=q)\n'
                                            '@g.on_talk\ndef talk():\n    join_city(Species.Gekomon)\n    warp(239, exit=2)\n'
                                            '    wait(ticks=3)\n    wait(333)\n'})
        e = errors_of_py(p)
        for want in ('like_slot= is now behaves_like=', 'join_city(...) is now recruit(...)', 'warp(..., exit=k) is now entry=k',
                     'wait(ticks=n) is gone', '333 ms: the game counts time in steps of 50 ms'):
            self.assertIn(want, e)
        from dws import basebuild as BB
        v = ''.join(open(f).read() for f in glob.glob(os.path.join(BB.BASE, 'zones', '*', '*', 'script.py')))
        for want in ('objects[41].animate(1)', 'sound.jingle()', 'recruit(Species.', ', entry=', 'fade_to_white(2000)', 'partner.add(offense=5)'):
            self.assertIn(want, v)
        for gone in ('engine.object.set(', ', exit=', 'call(Routine.fade_to_white', 'off='):    # (dws hatches keep DWS)
            self.assertNotIn(gone, v)

    def test_second_review_errors(self):
        """dws-python-intuitiveness-2.md 2, 3, 6-8: every error at the .py line in Python words (the compiler's and the back
        end's too, through the source map), a mod that saves state reserves its range, stage comparisons, silent acceptances."""
        head = 'from dw import *\nhouse = screen(Screen.jijimons_house)\n'
        q = 'class Q(Quest):\n    A = auto()\n    B = auto()\n    C = auto()\n'
        # 3: no [save] flags / vars in mod.toml: an error at the declaration with the line to add
        root, (p,) = self.mod({'a.py': 'from dw import *\n' + q + 'n = counter()\n'}, toml=None)
        from unittest.mock import patch
        from dws.py import lower as PL
        with patch.object(PL, 'free_range', side_effect=lambda kind, size: '717-726' if kind == 'flags' else '7-9'):
            e = errors_of_py(p)
        self.assertIn('a.py:2:1: error: mod m-a reserves no save flags in mod.toml', e); self.assertIn('[save]\n        flags = "717-726"', e)
        self.assertIn('a.py:6:5: error: mod m-a reserves no save vars', e); self.assertIn('vars = "', e)
        with patch.object(PL, 'free_range', return_value=None):
            exhausted = errors_of_py(p)
        self.assertIn('flags = "FIRST-LAST"', exhausted)
        self.assertIn('vars = "FIRST-LAST"', exhausted)
        root, (p,) = self.mod({'a.py': 'from dw import *\nok = flag()\n'}, toml='[save]\nvars = "9-10"\n')
        self.assertIn('add to ', errors_of_py(p)); self.assertIn('(under [save]):\n        flags = "', errors_of_py(p))
        # 6: Horn.stage == Horn.X is Horn.X; other uses of .stage say what to write
        root, (p,) = self.mod({'a.py': head + q + 'g = house.npc(Species.Gekomon, slot=4, at=(1, 2))\n@g.on_talk\ndef talk():\n'
                                            '    if Q.stage == Q.C:\n        say("c")\n    if Q.stage != Q.A:\n        say("not a")\n'})
        t = self.lowered(p)
        self.assertIn('if (Q_b1) {', t); self.assertIn('if (Q_b0 || Q_b1) {', t)
        root, (p,) = self.mod({'a.py': head + q + 'g = house.npc(Species.Gekomon, slot=4, at=(1, 2))\n@g.on_talk\ndef talk():\n'
                                            '    if Q.stage:\n        say("x")\n    if Q.stage < Q.C:\n        say("y")\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:10:8: error: Q.stage is a stage, not a yes/no', e); self.assertIn('a.py:12:8: error: stages are compared with == and !=', e)
        # 8: guard messages in Python words; chained screen(...).npc(...)
        root, (p,) = self.mod({'a.py': head + 'f = flag()\ng = house.npc(Species.Gekomon, slot=4, at=(1, 2))\n'
                                            '@g.on_talk(when=partner.species == Species.Agumon)\ndef a():\n    say("x")\n'
                                            '@g.on_talk(when=(f and has(Item.Meat)) or (not f and has(Item.Sirloin)))\ndef b():\n    say("y")\n'
                                            'h = screen(Screen.jijimons_house).npc(Species.Agumon, slot=5, at=(1, 2))\n'})
        e = errors_of_py(p)
        self.assertIn("a.py:5:17: error: a guard (when=) tests saved state; the partner's species is read when a line runs", e)
        self.assertIn('two handlers with the same body', e)
        self.assertIn('a.py:11:5: error: name the screen first', e)
        # 7: two NPCs in one slot, a new NPC without at=, the same slot in two files of a mod
        root, (p,) = self.mod({'a.py': head + 'g = house.npc(Species.Gekomon, slot=4, at=(1, 2))\nh = house.npc(Species.Agumon, slot=4, at=(1, 2))\n'
                                            'k = house.npc(Species.Agumon)\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:4:5: error: slot 4 of this screen is already g (line 3)', e)
        self.assertIn('a.py:5:5: error: a new NPC needs at=(x, z)', e)
        root, (a, b) = self.mod({'a.py': head + 'g = house.npc(Species.Gekomon, slot=4, at=(1, 2))\n',
                                 'b.py': head + 'h = house.npc(Species.Agumon, slot=4, at=(1, 2))\n'})
        try: B.compile_sources([a, b]); e = ''
        except B.DwsErrors as x: e = '\n'.join(y.render() for y in x.errors)
        self.assertIn('b.py:3:36: error: screen 218 has 4 placed Digimon; this new NPC goes in slot 5 (slots are filled in order, '
                      'the new NPCs of the files and mods compiled together in their order)', e)
        # 2: an error of the back end (a placement the .MAP refuses) at the npc() line of the .py, no traceback
        root, (p,) = self.mod({'a.py': head + '\ng = house.npc(Species.Gekomon, slot=4, at=(-30000, 2))\n'})
        prog = B.compile_sources([p])
        with self.assertRaises(B.DwsError) as cm: B.assemble(prog, os.path.join(tempfile.mkdtemp(dir=TMP), 'DG.SCN'))
        self.assertEqual(cm.exception.pos[1:], (4, 1)); self.assertTrue(cm.exception.pos[0].endswith('a.py'))
        self.assertIn('outside the map', cm.exception.render())
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'text', 'sync', 'no-such-mod'], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn('no mod "no-such-mod" written in Python', r.stderr)

    def test_free_save_range_uses_only_unreserved_numbers(self):
        from unittest.mock import patch
        from dws.py import lower as PL
        root = tempfile.mkdtemp(dir=TMP)
        mod = os.path.join(root, 'story', 'mods', 'reserved'); os.makedirs(mod)
        with patch.object(PL, 'ROOT', root):
            self.assertEqual(PL.free_range('flags'), '717-726')
            self.assertEqual(PL.free_range('vars', 3), '7-9')
            manifest = os.path.join(mod, 'mod.toml')
            open(manifest, 'w').write('[save]\nflags = "717-794"\nvars = "7-13"\n')
            self.assertEqual(PL.free_range('flags'), '795-799')
            self.assertEqual(PL.free_range('vars', 3), '14-15')
            open(manifest, 'w').write('[save]\nflags = "717-799"\nvars = "7-15"\n')
            self.assertIsNone(PL.free_range('flags'))
            self.assertIsNone(PL.free_range('vars'))

    def test_presence_everywhere_and_limits(self):
        """dws-python-intuitiveness-2.md 1, 4, 5: npc(..., when=) builds on the original engine (MAPHEAD IF, no story-state
        table); screen(a, b).npc() places on each screen; slots 8-15, imported species and the heap are refused at the
        npc() line by `check` (not only when the disc is built)."""
        head = 'from dw import *\nfrom dw.base.native_forest_2 import forest, goblimon0\n'
        root, (p,) = self.mod({'a.py': head + 'g = forest.npc(Species.Gabumon, slot=5, at=(500, 900), behaves_like=goblimon0,\n'
                                            '               when=not recruited(Species.Gabumon))\n@g.on_talk\ndef talk():\n    say("Hi")\n'})
        prog = B.compile_sources([p])                                   # the original engine (original)
        report, run = B.assemble(prog, os.path.join(tempfile.mkdtemp(dir=TMP), 'DG.SCN'))
        mh = open(os.path.join(run, 'scn', 'maphead', 'maphead.scn.txt')).read()
        self.assertIn('IF not trigger 217, else dws_presence_2_5\n    LOAD_DIGIMON 17\n    SET_DIGIMON 17, 5, 0', mh)
        self.assertFalse([r for r in report if 'city table' in r])     # no section 1260 below story-state
        root, (p,) = self.mod({'a.py': 'from dw import *\ntwo = screen(Screen.native_forest_4, Screen.lava_cave_30)\n'
                                       'g = two.npc(Species.Gekomon, slot=0, at=(100, 100), when=recruited(Species.Palmon))\n'})
        t = self.lowered(p)
        self.assertIn('place(species(110), screen: [4, 30], slot: 0, at: (100, 100));', t)
        self.assertIn('screen(4) {', t); self.assertIn('screen(30) {', t)
        root, (p,) = self.mod({'a.py': 'from dw import *\ntwo = screen(Screen.arena_lobby_208, Screen.arena_lobby_223)\n'
                                       'g = two.npc(Species.Gekomon, slot=3, at=(100, 100))\n'})
        self.assertIn('the same new slot on each, and here it differs: screen 208: slot 1, screen 223: slot 3', errors_of_py(p))
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.file_city_176 import city_176, yuramon\n'
                                       'v = city_176.npc(Species.Gabumon, slot=8, at=(300, -1500), behaves_like=yuramon)\n'
                                       'm = city_176.npc(Species.Mushroomon, slot=9, at=(300, -1500))\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:3:5: error: slot 8: the original engine has NPC slots 0-7', e)
        self.assertIn('a.py:4:5: error: Species.Mushroomon is not one of the original game\'s 180 species', e)
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.native_forest_3 import forest, aruraumon1\n\n'
                                       'g = forest.npc(Species.Gabumon, slot=5, at=(900, 1200), behaves_like=aruraumon1)\n'})
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'check', p], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertNotIn('Traceback', r.stderr)
        self.assertIn('a.py:4:1: error: screen 3 would need', r.stderr); self.assertIn('python3 tools/dws.py slots 3 lists both', r.stderr)
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'slots', '3'], capture_output=True, text=True)
        self.assertRegex(r.stdout, r'heap \(measured, as `check` tests it.*\): \d+ KB free now on the original engine')

    def test_third_review_chests(self):
        """dws-python-intuitiveness-3.md 1: spawn_chest(item, at=, opened=a flag of the mod, facing=); the old six numbers are
        an error naming the new form (no traceback)."""
        head = 'from dw import *\nfrom dw.base.centar_clinic import clinic\nopened = flag()\n@clinic.on_enter(when=not opened)\ndef chest():\n'
        root, (p,) = self.mod({'a.py': head + '    spawn_chest(Item.Medicine, at=(100, 200), opened=opened, facing=1024)\n'})
        self.assertIn('spawn_chest(item(14), 100, 0, 200, 1024, opened);', self.lowered(p))
        self.assertEqual(errors_of_py(p), '')
        root, (p,) = self.mod({'a.py': head + '    spawn_chest(Item.Medicine, at=(100, 200), opened=trigger(760))\n'})
        self.assertIn('spawn_chest(item(14), 100, 0, 200, 0, 760);', self.lowered(p))
        root, (p,) = self.mod({'a.py': head + '    spawn_chest(Item.Medicine, 100, 0, 200, 50, opened)\n'})
        self.assertIn('a.py:6:5: error: a chest is spawn_chest(Item.X, at=(x, z), opened=a_flag, facing=0)', errors_of_py(p))
        root, (p,) = self.mod({'a.py': head + '    spawn_chest(Item.Medicine, at=(100, 200), opened=opened, facing=50)\n'})
        self.assertIn('facing=50: a chest faces 0, 1024, 2048 or 3072', errors_of_py(p))

    def test_third_review_waiting(self):
        """dws-python-intuitiveness-3.md 2: last_day.set(clock.day) on every engine (STORE_DATE, then COPY_PSTAT on the
        original engine, V_FROM_PSTAT on story-state); `clock.day - last_day >= n` on story-state (a scene variable, the 30-day year),
        refused on the original engine at its .py line; the clock against a counter, `%` and other arithmetic refused with
        the form to use; an elif chain reads the stored clock once (as the disc does)."""
        head = ('from dw import *\nfrom dw.base.jijimons_house import house\nlast_day = counter()\n'
                'g = house.npc(Species.Gotsumon, slot=4, at=(450, -650))\n@g.on_talk\ndef talk():\n')
        root, (p,) = self.mod({'a.py': head + '    last_day.set(clock.day)\n'})
        self.assertIn('store_date(date_year);\n        last_day = date_day;', self.lowered(p))
        self.assertIn('    COPY_PSTAT p106, p9', '\n'.join(show_code(p)))
        self.assertIn('    V_FROM_PSTAT p106, v9', '\n'.join(show_code(p, 'story-state')))
        root, (p,) = self.mod({'a.py': head + '    if clock.day - last_day >= 3:\n        say("Ready.")\n'})
        t = self.lowered(p)
        self.assertIn('temp var py_days;', t)
        self.assertIn('py_days = date_day;\n        py_days -= last_day;\n        if (py_days < 0) { py_days += 30; }\n'
                      '        if (py_days >= 3) {', t)
        self.assertIn('a.py:7:8: error: `clock.day - last_day` needs the story-state engine', errors_of_py(p))
        code = '\n'.join(show_code(p, 'story-state'))
        self.assertIn('V_FROM_PSTAT p106, s0\n    SUB_VV s0, v9\n    IF s0 < 0, else', code); self.assertIn('ADD_V s0, 30', code)
        root, (p,) = self.mod({'a.py': head + '    if clock.day != last_day:\n        say("x")\n'})
        self.assertIn('the clock is compared with a number', errors_of_py(p))
        root, (p,) = self.mod({'a.py': head + '    if clock.day % 7 == 0:\n        say("x")\n'})
        self.assertIn('no `%`', errors_of_py(p)); self.assertIn('clock.day == 7', errors_of_py(p))
        root, (p,) = self.mod({'a.py': head + '    if clock.hour < 6:\n        say("a")\n    elif clock.hour < 12:\n        say("b")\n'
                                              '    elif partner.species == Species.Agumon:\n        say("c")\n'})
        t = self.lowered(p)
        self.assertEqual(t.count('store_date(date_year);'), 1); self.assertIn('} else if (date_hour < 12) {', t)
        self.assertIn('} else {\n            store_digimon_type(partner_type);', t)      # a value the first test did not store

    def test_third_review_shop(self):
        """dws-python-intuitiveness-3.md 3: shop(Item.A, ...) in a talk is the game's ritual with the talking NPC as the
        owner (engine.arg = its entity: slot 2 of Birdra Transport is entity 7, not Birdramon's 5)."""
        head = ('from dw import *\nfrom dw.base.birdra_transport import transport, leomon\n'
                'm = transport.npc(Species.Gotsumon, slot=2, at=(-100, -560), behaves_like=leomon)\n@m.on_talk\ndef talk():\n')
        root, (p,) = self.mod({'a.py': head + '    shop(Item.SmRecovery, Item.Meat)\n'})
        t = self.lowered(p)
        self.assertIn('alias flag py_stock_a_0 = 384;', t); self.assertIn('alias flag py_stock_a_38 = 422;', t)
        self.assertIn('py_stock_a_0 = true;\n        py_stock_a_38 = true;\n        engine.picker_mode = false;\n        engine.arg = 7;\n'
                      '        call_routine(routine("shop"));\n        py_stock_a_0 = false;\n        py_stock_a_38 = false;', t)
        self.assertIn('    SET_TRIGGER 384\n    SET_TRIGGER 422\n    UNSET_TRIGGER 3\n    SET_PSTAT p254, 7\n    CALL_ROUTINE 8\n'
                      '    UNSET_TRIGGER 384\n    UNSET_TRIGGER 422', '\n'.join(show_code(p)))
        self.assertEqual(errors_of_py(p), '')
        root, (p,) = self.mod({'a.py': head + '    shop()\n'})
        self.assertIn('shop(Item.A, Item.B, ...): the items it sells', errors_of_py(p))
        root, (p,) = self.mod({'a.py': head.replace('@m.on_talk\ndef talk():', '@transport.on_enter(when=trigger(5))\ndef e():')
                                       + '    shop(Item.Meat)\n'})
        self.assertIn('opened by the NPC being talked to', errors_of_py(p))

    def test_third_review_at(self):
        """dws-python-intuitiveness-3.md 4: the wall error and `dws slots` give the box of the walkable tiles and the overlay
        command with the screen's .MAP; the overlay draws a labelled grid."""
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.birdra_transport import transport, leomon\n'
                                       'm = transport.npc(Species.Gotsumon, slot=2, at=(500, -400), behaves_like=leomon)\n'})
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'check', p], capture_output=True, text=True)
        self.assertIn('a.py:3:1: error: (500, -400) is a wall tile (55,54) of screen 207', r.stderr)
        self.assertIn('hint: the walkable tiles are inside x -450..450, z -950..-150', r.stderr)
        self.assertIn('python3 tools/dwmap.py overlay extracted/MAP/MAP14/ROOM12.MAP room12.png', r.stderr)
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'slots', 'birdra_transport'], capture_output=True, text=True)
        self.assertIn('on a walkable tile: the walkable tiles are inside x -450..450, z -950..-150', r.stdout)
        import dwmap
        m = dwmap.MapFile(open(os.path.join(ROOT, 'extracted/MAP/MAP14/ROOM12.MAP'), 'rb').read())
        self.assertEqual(dwmap.walk_box(m), (-450, 450, -950, -150))
        t = dwmap.TfsFile(open(os.path.join(ROOT, 'extracted/MAP/MAP14/ROOM12.TFS'), 'rb').read())
        _, _, plain = dwmap.render_overlay(m, t); _, _, grid = dwmap.render_overlay(m, t, grid=True)
        yellow = lambda rows: sum(r.count(bytes((255, 255, 0))) for r in rows)
        self.assertGreater(yellow(grid), yellow(plain))                               # the labels (X 0, Z -500...)

    def test_third_review_mod_folder(self):
        """dws-python-intuitiveness-3.md 5: `check story/mods/NAME` is the mod (src/*.dws, src/*.py); a sibling's error is
        said once and the files that import it are not compiled (no `import ...decl.dws: file not found`); `new mod`
        describes the Python layout."""
        q = 'from dw import *\nclass Q(Quest):\n    A = auto()\n    B = auto()\n'
        a = 'from dw import *\nfrom dw.base.jijimons_house import jijimon\nfrom .quests import Q\n@jijimon.on_talk(when=Q.B)\ndef t():\n    say("Hi")\n'
        root, (pq, pa, pb) = self.mod({'quests.py': q, 'a.py': a, 'b.py': a}, 'm-casc', toml=None)
        mod = os.path.dirname(os.path.dirname(pa))
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'check', mod], capture_output=True, text=True)
        self.assertEqual(r.stderr.count('error:'), 1); self.assertIn('quests.py:2:1: error: mod m-casc reserves no save flags', r.stderr)
        self.assertNotIn('decl.dws', r.stderr); self.assertIn('1 error', r.stderr)
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'check', pa], capture_output=True, text=True)
        self.assertEqual(r.stderr.count('error:'), 1); self.assertNotIn('decl.dws', r.stderr)
        open(os.path.join(mod, 'mod.toml'), 'w').write('name = "m-casc"\n[save]\nflags = "717-726"\n')
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'check', mod], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(r.stdout.split('\n')[0], 'ok: m-casc, 2 events')
        from dws import scaffold
        saved = scaffold.STORY
        try:
            scaffold.STORY = os.path.join(tempfile.mkdtemp(dir=TMP), 'story'); scaffold.new('mod', 'm-new')
            d = os.path.join(scaffold.STORY, 'mods', 'm-new')
            self.assertIn('`src/*.py`, the story in Python', open(os.path.join(d, 'README.md')).read())
            self.assertIn('python3 tools/dws.py check ' + '/'.join(('story', 'mods', 'm-new')), open(os.path.join(d, 'README.md')).read())
            self.assertIn('one `.py` per place', open(os.path.join(d, 'src', 'README.md')).read())
            self.assertNotIn('DWS', open(os.path.join(d, 'src', 'README.md')).read())
        finally:
            scaffold.STORY = saved

    def test_third_review_one_form(self):
        """dws-python-intuitiveness-3.md 6: an unknown partner stat lists the Python names only (no off/def/brains); a
        taken-over NPC's handler that ends `return x.talk()` goes on into the base's talk (its section, kept)."""
        head = 'from dw import *\nfrom dw.base.jijimons_house import tokomon\n'
        root, (p,) = self.mod({'a.py': head + 'seen = flag()\n@tokomon.on_talk(when=not seen)\ndef t():\n    if partner.brains >= 3:\n'
                                              '        say("x")\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:6:8: error: unknown partner stat "brains"', e); self.assertIn('stats: species, offense, defense, speed, brain,', e)
        self.assertNotIn(' off,', e); self.assertNotIn('brains,', e)
        root, (p,) = self.mod({'a.py': head + 'toko = take_over(tokomon)\n@toko.on_talk\ndef t():\n    say("One more line.")\n'
                                              '    return tokomon.talk()\n'})
        t = self.lowered(p)
        self.assertIn('on talk(toko) replace {', t); self.assertIn('goto sec6;', t)

    def test_third_review_quiet(self):
        """dws-python-intuitiveness-3.md 7: `check` says the files it was given and the events; `--build` leaves out the
        sections it adds for a new slot, the container's rearrangement and its size unless -v; `lower` prints one import block."""
        src = ('from dw import *\nfrom dw.base.centar_clinic import clinic, coelamon\n'
               'p = clinic.npc(Species.Penguinmon, slot=2, at=(-600, -300), behaves_like=coelamon)\n@p.on_talk\ndef t():\n    say("Cough.")\n')
        root, (p,) = self.mod({'clinic.py': src})
        dws = [sys.executable, os.path.join(ROOT, 'tools/dws.py')]
        r = subprocess.run(dws + ['check', p], capture_output=True, text=True)
        self.assertEqual(r.stdout.split('\n')[0], 'ok: clinic.py, 1 event')
        out = os.path.join(tempfile.mkdtemp(dir=TMP), 'DG.SCN')
        quiet = subprocess.run(dws + ['check', p, '--build', '-o', out], capture_output=True, text=True).stdout
        loud = subprocess.run(dws + ['check', p, '--build', '-o', out, '-v'], capture_output=True, text=True).stdout
        for noise in ('section 7: new (', 'already there'):
            self.assertNotIn(noise, quiet); self.assertIn(noise, loud)
        from dws import cli
        rep = ['script 3 section 7: inserted at the start (18 lines)', 'script 173 section 7: new (68 lines)',
               'warning: had to rearrange: entry 0 shrunk to 1 sector\n  script_000.scn.txt: slot 13 \u2192 1 sectors\n'
               'note: DG.SCN ends up at 782336 bytes (804864 the original); build-disc.py pads it\nout.SCN: 782336 bytes']
        self.assertEqual(cli.report_lines(rep), ['script 3 section 7: inserted at the start (18 lines)', 'out.SCN: 782336 bytes'])
        self.assertEqual(len(cli.report_lines(rep, verbose=True)), 6)
        for kept in ('screen 213 slot 2: new Penguinmon', 'heap: needs', 'MAPHEAD.SCN: ', 'FILE: MAP/MAP15/ROOM04.MAP='):
            self.assertIn(kept, quiet)
        low = subprocess.run(dws + ['lower', p], capture_output=True, text=True).stdout
        self.assertEqual(low.count('story/core/engine.dws'), 1)

    def test_third_review_views(self):
        """dws-python-intuitiveness-3.md 8: one random-draw form (`roll = random.roll(n)`, then `roll` is the draw: STORE_RANDOM
        random_roll, n and random_roll, the bytes of the disc's form); the inline draw in a test and a second name are errors."""
        head = 'from dw import *\nfrom dw.base.centar_clinic import coelamon\nc = take_over(coelamon)\n@c.on_talk\ndef t():\n'
        root, (p,) = self.mod({'a.py': head + '    roll = random.roll(3)\n    if roll == 0:\n        say("a")\n        return\n'
                                              '    if roll == 1:\n        say("b")\n'})
        t = self.lowered(p)
        self.assertIn('store_random(random_roll, 3);\n        if (random_roll == 0) {', t)
        self.assertEqual(t.count('store_random'), 1); self.assertIn('if (random_roll == 1) {', t)
        root, (p,) = self.mod({'a.py': head + '    if random.roll(3) == 0:\n        say("a")\n'})
        self.assertIn('a random draw is kept before it is compared: roll = random.roll(n)', errors_of_py(p))
        root, (p,) = self.mod({'a.py': head + '    roll = random.roll(3)\n    other = random.roll(5)\n    say("a")\n'})
        self.assertIn('the game keeps one random draw (the last): draw again into roll', errors_of_py(p))

    def test_third_review_messages(self):
        """dws-python-intuitiveness-3.md 9: an NPC's when= with an item says that presence tests flags (items are saved
        too); `text sync` takes a mod's folder wherever it is."""
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.jijimons_house import house, tokomon\n'
                                       'g = house.npc(Species.Gekomon, slot=4, at=(450, -650), behaves_like=tokomon, when=has(Item.Meat))\n'})
        e = errors_of_py(p)
        self.assertIn('when= cannot test `has(Item.Meat)`: who stands on the screen is decided by its setup, whose rule tests flags '
                      'and the clock only (quest stages, flag(), recruited(...), trigger(n), clock.hour...)', e)
        self.assertIn('hint: test items, counters and stats with an `if` in a handler', e)
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.jijimons_house import jijimon\nx = flag()\n'
                                       '@jijimon.on_talk(when=not x)\ndef t():\n    say("Hello there.")\n'}, 'm-sync')
        mod = os.path.dirname(os.path.dirname(p))
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'text', 'sync', mod + '/'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn('m-sync: 1 line -> ', r.stdout)
        self.assertTrue(os.path.exists(os.path.join(mod, 'text', 'en.json')))
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'text', 'sync', os.path.join(root, 'nothing')],
                           capture_output=True, text=True)
        self.assertIn('no mod written in Python here (src/*.py, or `sources` in its mod.toml)', r.stderr); self.assertNotIn('story/mods/story/mods', r.stderr)

    def test_deprecations(self):
        d = os.path.join(TMP, 'story', 'mods', 'm-old', 'src'); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, 'x.dws'); open(p, 'w').write('script 178 { on enter { give_bits(1); } }\n')
        prog = B.compile_sources([p])
        self.assertTrue(any('deprecated: write it in Python' in w for w in prog.warn.render()))

    def test_quests_defs_and_text(self):
        from dws.py import lower as PL
        self.assertEqual(PL.text_key('m', 'Hi  there'), PL.text_key('m', 'Hi there'))
        src = ('from dw import *\nclass Q(Quest):\n    A = auto()\n    B = auto()\n    C = auto()\n'
               'n = counter()\nhouse = screen(Screen.jijimons_house)\ng = house.npc(Species.Gekomon, slot=4, at=(1, 2))\n'
               'def pay(b: int):\n    give(bits=b)\n    n.add(1)\n'
               '@g.on_talk\ndef talk():\n    match Q.stage:\n        case Q.A:\n            pay(10)\n            advance(Q.C)\n'
               '        case Q.B | Q.C:\n            say("Again?")\n    if Q.reached(Q.B) and n >= 2:\n        say("Twice.")\n')
        root, (p,) = self.mod({'a.py': src})
        t = self.lowered(p)
        self.assertIn('if (!Q_b0 && !Q_b1) {', t); self.assertIn('give_bits(10);', t); self.assertIn('n += 1;', t)
        self.assertIn('Q_b0 = false;\n', t); self.assertIn('Q_b1 = true;', t)
        self.assertIn('if ((Q_b0 || Q_b1) && n >= 2) {', t)                                  # the group comes first (IF folds left to right)
        from dws.py import textsync
        mods = os.path.join(root, 'story', 'mods')
        textsync.sync('m-a', log=lambda m: None, mods=mods)
        en = json.load(open(os.path.join(mods, 'm-a/text/en.json')))
        k = PL.text_key('m-a', 'Twice.'); self.assertEqual(en[k], 'Twice.'); self.assertEqual(en['_where'][k], 'a.py:21 talk: g (Gekomon) says')
        json.dump({k: 'Dos veces.'}, open(os.path.join(mods, 'm-a/text/es.json'), 'w'))
        open(p, 'w').write(src.replace('"Twice."', '"Twice!"'))
        textsync.sync('m-a', log=lambda m: None, mods=mods)
        es = json.load(open(os.path.join(mods, 'm-a/text/es.json')))
        self.assertEqual(es, {PL.text_key('m-a', 'Twice!'): '~fuzzy Dos veces.'})               # the edited line keeps its translation

    def check_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py')] + list(args), capture_output=True, text=True)

    def test_fourth_review_sections(self):
        """dws-python-intuitiveness-4.md 1: a new NPC in a slot free on screen 208 but Airdramon's on screen 223 (script 168
        serves both) answers on a talk section no NPC of the script uses (8, not 6), and `check` says why; the view and the
        stub name the screen each NPC stands on; take_over and behaves_like use that screen."""
        lobby = ('from dw import *\nfrom dw.base.arena_lobby_208 import lobby_208\n'
                 'pilgrim = lobby_208.npc(Species.Gotsumon, at=(-500, 600))\n@pilgrim.on_talk\ndef t():\n    say("Clunk.")\n')
        root, (p,) = self.mod({'lobby.py': lobby})
        t = self.lowered(p)
        self.assertIn('place(species(68), screen: 208, slot: 1, at: (-500, 600), section: 8);', t)
        self.assertIn('npc pilgrim = 8;', t)
        r = self.check_cli('check', p)
        self.assertIn('lobby.py:3: note: pilgrim (slot 1 of screen 208) answers on talk section 8: section 6 is airdramon\'s, '
                      'slot 1 of screen 223', r.stdout)
        prog = B.compile_sources([p])
        rep, _ = B.assemble(prog, os.path.join(tempfile.mkdtemp(dir=TMP), 'DG.SCN'))
        self.assertIn('script 168 section 8: new (', '\n'.join(rep))
        self.assertNotIn('script 168 section 6', '\n'.join(rep))                            # Airdramon's talk stays the base's
        view = open(os.path.join(ROOT, 'story/base/zones/arena-lobby/s168-208-223/script.py')).read()
        self.assertIn('airdramon = lobby_223.npc(Species.Airdramon131, slot=1)', view)
        stub = open(os.path.join(ROOT, 'typings/dw/base/arena_lobby_208.pyi')).read()
        self.assertIn('airdramon: NPC    # slot 1 of screen 223, Airdramon131', stub)
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.arena_lobby_208 import airdramon\n'
                                       'x = take_over(airdramon, species=Species.Gotsumon)\n@x.on_talk\ndef t():\n    say("Clunk.")\n'})
        self.assertIn('place(species(68), screen: 223, slot: 1);', self.lowered(p))
        root, (p,) = self.mod({'a.py': lobby.replace('at=(-500, 600)', 'at=(-500, 600), behaves_like=airdramon')
                                            .replace('import lobby_208', 'import lobby_208, airdramon')})
        self.assertIn('airdramon stands on screen 223, not on this one', errors_of_py(p))

    def test_fourth_review_compose(self):
        """dws-python-intuitiveness-4.md 2: two npc(when=) on one screen from two files (or two mods) compose: the slots are
        taken in load order without slot=, the presence rules of the screen merge; slot= may say it and must be that one."""
        npc = ('from dw import *\nfrom dw.base.native_forest_2 import forest, goblimon0\n{f} = flag()\n'
               '{n} = forest.npc(Species.Goblimon, at={at}, behaves_like=goblimon0, when=not {f})\n'
               '@{n}.on_talk\ndef t():\n    say("Gobu.")\n    {f}.set()\n')
        root, (a, b) = self.mod({'a.py': npc.format(f='a_done', n='a', at='(-1000, -500)'),
                                 'b.py': npc.format(f='b_done', n='b', at='(-1500, -1000)')})
        r = self.check_cli('check', os.path.dirname(a))
        self.assertIn('ok: src, 2 events', r.stdout, r.stderr)
        self.assertFalse(r.stderr)
        from dws.py import lower as PL
        self.assertIn('slot: 6,', open(PL.lowered_path(b, 'script')).read())
        prog = B.compile_sources([a, b])
        self.assertEqual(sorted(r[0] for r in prog.b.city['presence'][2]['npcs']), [5, 6])
        root, (a, b) = self.mod({'a.py': npc.format(f='a_done', n='a', at='(-1000, -500)'),
                                 'b.py': npc.format(f='b_done', n='b', at='(-1500, -1000)').replace('behaves_like', 'slot=5, behaves_like')})
        r = self.check_cli('check', os.path.dirname(a))
        self.assertNotIn('is not an NPC of this file', r.stderr)
        self.assertIn('b.py:4:58: error: screen 2 has 5 placed Digimon; this new NPC goes in slot 6 (slots are filled in order, '
                      'the new NPCs of the files and mods compiled together in their order)', r.stderr)
        _, (c,) = self.mod({'c.py': npc.format(f='c_done', n='c', at='(-1500, -1000)')}, 'm-b', toml='[save]\nflags = "727-736"\n')
        prog = B.compile_sources([a.replace('a.py', 'a.py'), c])
        self.assertEqual(sorted(r[0] for r in prog.b.city['presence'][2]['npcs']), [5, 6])     # two mods: 5 and 6

    def test_fourth_review_heap(self):
        """dws-python-intuitiveness-4.md 3: `dws slots` measures a species as `check` does (the setup with one more Digimon on
        its worst path): the largest it says fits is accepted by `check`, the smallest it says is too big is refused; a
        species already on the screen is listed as costing its instance data only."""
        r = self.check_cli('slots', 'green_gym')
        m = re.search(r'\(original engine\) the largest that fit: (.*?); too big: (\w+) ', r.stdout)
        fit, big = m.group(1).split(', ')[-1].split()[0], m.group(2)
        self.assertIn('already on this screen (its model is loaded once: another one costs a few KB of instance data): Koromon', r.stdout)
        npc = 'from dw import *\nfrom dw.base.green_gym import gym, koromon\nx = gym.npc(Species.{}, at=(500, -1500), behaves_like=koromon)\n'
        for sp, ok in ((fit, True), (big, False), ('Koromon', True)):
            root, (p,) = self.mod({'a.py': npc.format(sp)})
            r = self.check_cli('check', p)
            self.assertEqual(r.returncode == 0, ok, (sp, r.stdout, r.stderr))

    def test_fourth_review_lock(self):
        """dws-python-intuitiveness-4.md 4: a check that fails writes no save.lock (a name that never compiled takes no number);
        a full range is reported at the declaration, with the way out; a pin outside the engine's numbers at its line."""
        head = 'from dw import *\nfrom dw.base.jijimons_house import jijimon\n'
        bad = head + 'last_hour = counter()\n@jijimon.on_talk(when=last_hour == 0)\ndef t():\n    if clock.hour - last_hour >= 2:\n        say("x")\n'
        root, (p,) = self.mod({'a.py': bad}, toml='[save]\nvars = "20-20"\n')
        lock = os.path.join(os.path.dirname(os.path.dirname(p)), 'save.lock')
        self.assertNotEqual(self.check_cli('check', p).returncode, 0)
        self.assertFalse(os.path.exists(lock))
        ok = bad.replace('    if clock.hour - last_hour >= 2:\n        say("x")\n', '    say("x")\n')
        open(p, 'w').write(ok)
        self.assertEqual(self.check_cli('check', p).returncode, 0); self.assertEqual(json.load(open(lock)), {'vars': {'last_hour': 20}})
        open(p, 'w').write(ok.replace('last_hour', 'other'))
        e = self.check_cli('check', p).stderr
        self.assertIn('a.py:3:9: error: the vars range 20-20 of m-a (mod.toml) is full: save.lock gives its numbers to last_hour', e)
        self.assertIn('remove it there if no saved game uses it', e)
        open(os.path.join(os.path.dirname(os.path.dirname(p)), 'mod.toml'), 'w').write('name = "m-a"\n[save]\nvars = "20-25"\n')
        e = self.check_cli('check', p).stderr
        self.assertIn('a.py:3:1: error: var "m_a.other" pinned to 21, which is not in the free range', e)
        self.assertIn("a mod's [save] range in its mod.toml must be inside the free numbers", e)

    def test_fourth_review_forms(self):
        """dws-python-intuitiveness-4.md 5-7: `match fight(x)` with a case per outcome is one battle; two tests of fight(x) in a
        row are refused; `if not ask(...)` is the menu with its branches swapped; `pick == Item.X` and `!=` lower."""
        head = 'from dw import *\nfrom dw.base.green_gym import koromon\ndone = flag()\n@koromon.on_talk(when=not done)\ndef t():\n'
        body = ('    match fight(koromon, escape=False):\n        case "won":\n            say("W")\n        case "lost":\n'
                '            say("L")\n        case "fled":\n            say("F")\n'
                '    match fight(koromon):\n        case "won" | "fled":\n            say("WF")\n        case _:\n            say("L")\n'
                '    if not ask(yes="Y", no="N"):\n        say("no")\n'
                '    pick = pick_item()\n    if pick == Item.Medicine:\n        say("m")\n    elif pick != Item.Meat:\n        say("n")\n')
        root, (p,) = self.mod({'a.py': head + body})
        t = self.lowered(p)
        from dws.py import lower as PL
        k = lambda w: f'text("{PL.text_key("m-a", w)}")'
        self.assertIn('battle(foes: [koromon]);\n            if (won) {\n                say(koromon, ' + k('W') + ');\n'
                      '            } else if (lost) {\n                say(koromon, ' + k('L') + ');\n            } else {\n'
                      '                say(koromon, ' + k('F') + ');\n            }\n', t)
        self.assertIn('if (won || fled) {', t)
        self.assertIn(k('Y') + ' => {}\n                ' + k('N') + ' or cancel => {\n                    say(koromon, ' + k('no'), t)
        self.assertIn('if (engine.arg == 14) {', t); self.assertIn('} else if (engine.arg != 38) {', t)
        self.assertEqual(errors_of_py(p), '')
        root, (p,) = self.mod({'a.py': head + '    if fight(koromon) == "fled":\n        return\n    if fight(koromon) == "won":\n'
                                            '        say("W")\n    elif fight(koromon) == "lost":\n        say("L")\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:8:8: error: a second fight(koromon) right after the first: each fight(...) is a battle of its own', e)
        self.assertIn('a.py:10:10: error: a second fight(koromon)', e)
        self.assertIn('hint: the outcomes of one battle: match fight(koromon): case "won": ... case "lost": ... case "fled": ...', e)
        root, (p,) = self.mod({'a.py': head + '    if fight(koromon) == "lost":\n        say("Again!")\n    say("Round two.")\n'
                                            '    if fight(koromon) == "won":\n        say("W")\n'})
        self.assertEqual(errors_of_py(p), '')                                                # a rematch, with a line between
        root, (p,) = self.mod({'a.py': head + '    match fight(koromon):\n        case "won":\n            say("W")\n'
                                            '        case "draw":\n            say("D")\n'})
        self.assertIn('a.py:9:14: error: a battle\'s outcome is "won", "lost" or "fled", not \'draw\'', errors_of_py(p))

    def test_fourth_review_small(self):
        """dws-python-intuitiveness-4.md 8-10: the wall error names the nearest walkable point; spawn_item(item, at=(x, z)) in
        world units (the views print the tile's centre); a name of the language is refused as a mod's name; `dws why` takes
        a mod's folder; a chest in a talk is refused; stat(n)/condition(n) are the partner's (and the tamer's) names;
        partner.level; which .MAP slot a new NPC without behaves_like= copies."""
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.native_forest_2 import forest, goblimon1\n'
                                       'x = forest.npc(Species.Gotsumon, at=(-500, 800), behaves_like=goblimon1)\n'})
        self.assertIn('a.py:3:1: error: (-500, 800) is a wall tile (44,41) of screen 2; the nearest walkable point is (-250, 850)',
                      self.check_cli('check', p).stderr)
        head = 'from dw import *\nfrom dw.base.native_forest_2 import forest\nseen = flag()\n@forest.on_enter(when=not seen)\ndef e():\n'
        root, (p,) = self.mod({'a.py': head + '    spawn_item(Item.Digimushrm, at=(-350, -950))\n'})
        self.assertIn('spawn_item(item(', self.lowered(p)); self.assertIn(', 46, 59);', self.lowered(p))
        root, (p,) = self.mod({'a.py': head + '    spawn_item(Item.Digimushrm, 46, 59)\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:6:5: error: an item on the ground is spawn_item(Item.X, at=(x, z))', e)
        self.assertIn('hint: the tile (46, 59) is at=(-350, -950); at=(x, z) is a point in world units', e)
        views = ''.join(open(f).read() for f in glob.glob(os.path.join(ROOT, 'story/base/zones/*/*/script.py')))
        self.assertEqual(len(re.findall(r'spawn_item\(Item\.\w+, at=\(-?\d+, -?\d+\)\)', views)), views.count('spawn_item('))
        for bad in ('stat(', 'condition(', 'tamer_level'):
            self.assertNotIn('    if ' + bad, views)
        root, (p,) = self.mod({'a.py': 'from dw import *\nshop = flag()\n'})
        self.assertIn('a.py:2:1: error: `shop` is a name of the story language', errors_of_py(p))
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.jijimons_house import house, tokomon\n'
                                       'pilgrim = house.npc(Species.Gotsumon, at=(450, -650), behaves_like=tokomon)\n'})
        r = self.check_cli('why', 'pilgrim', os.path.dirname(os.path.dirname(p)))
        self.assertIn('pilgrim: ', r.stdout); self.assertIn('a.py:3, screen 218, slot 4', r.stdout)
        r = self.check_cli('why', 'pilgrim')
        self.assertIn('error: "pilgrim": no NPC of that name in the mods written in Python', r.stderr)
        self.assertIn('a mod elsewhere: python3 tools/dws.py why pilgrim PATH/TO/MOD', r.stderr)
        talk = 'from dw import *\nfrom dw.base.green_gym import koromon\ndone = flag()\n@koromon.on_talk(when=not done)\ndef t():\n'
        root, (p,) = self.mod({'a.py': talk + '    spawn_chest(Item.Medicine, at=(100, 200), opened=done)\n'})
        self.assertIn("a.py:6:5: error: a chest is spawned in the screen's setup: on_enter", errors_of_py(p))
        root, (p,) = self.mod({'a.py': talk + '    if stat(3) >= 100:\n        say("a")\n    if condition(64):\n        say("b")\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:6:8: error: stat(3) is partner.brain', e); self.assertIn('a.py:8:8: error: condition(64) is partner.sick', e)
        root, (p,) = self.mod({'a.py': talk + '    if partner.sick or tamer.level >= 3:\n        tamer.add(level=1)\n'
                                              '    if partner.level == Level.champion:\n        say("c")\n'})
        t = self.lowered(p)
        self.assertIn('if (condition(64) || stat(21) >= 3) {', t); self.assertIn('add_stat(21, 1);', t)
        self.assertIn('store_digimon_type(partner_type);\n            if (partner_type in [species(5), species(6), ', t)
        root, (p,) = self.mod({'a.py': talk.replace('when=not done', 'when=partner.level >= Level.rookie') + '    say("x")\n'})
        self.assertIn("a guard (when=) tests saved state; the partner's species is read when a line runs", errors_of_py(p))
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.dragon_eye_lake_6 import lake\nx = lake.npc(Species.Gotsumon, at=(1500, -2000))\n'})
        self.assertIn("a.py:3: note: x behaves like the .MAP's slot 0 (Seadramon134: no NPC walks a path here, so the last slot); "
                      "behaves_like= picks another", self.check_cli('check', p).stdout)


    def test_fifth_review_numbers(self):
        """dws-python-intuitiveness-5.md 1-2: what the assembler refused at a generated line is refused at the .py line (an
        imported species tested on the original engine, a counter compared past 255); on --exe species / story-state the partner's
        species is read from the wide register and partner.level knows every species with a `partner` block; an error the
        assembler still finds names the story file and the section, without the warnings of other scripts."""
        talk = 'from dw import *\nfrom dw.base.jijimons_house import jijimon\n@jijimon.on_talk(when=trigger(760))\ndef t():\n'
        root, (p,) = self.mod({'a.py': talk + '    if partner.species == Species.Guilmon:\n        say("G.")\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:5:8: error: Species.Guilmon is imported (content/species): the partner can be one only on a disc built '
                      'with --exe species or --exe story-state', e)
        for exe in ('species', 'story-state'):
            code = '\n'.join(show_code(p, exe))
            self.assertIn('STORE_DIGIMON_TYPE_W w63', code); self.assertIn('IF w63 == 433', code); self.assertNotIn('p103', code)
        root, (p,) = self.mod({'a.py': talk + '    if partner.level == Level.rookie:\n        say("R.")\n'})
        self.assertIn('partner_type in [species(3), species(4), species(17)', self.lowered(p))     # the original engine: 1-62
        code = '\n'.join(show_code(p, 'story-state'))
        self.assertIn('IF w63 == 3, or w63 == 4, ', code)
        for imported in (180, 433): self.assertIn(f', or w63 == {imported}', code)            # Veemon, Guilmon: rookies too
        root, (p,) = self.mod({'a.py': talk + '    if partner.species != Species.Agumon:\n        say("A.")\n'})
        self.assertIn('IF w63 != 3', '\n'.join(show_code(p, 'species')))                    # (a partner 259 is not an Agumon)
        self.assertIn('p103 != 3', '\n'.join(show_code(p)))
        root, (p,) = self.mod({'a.py': 'from dw import *\nfrom dw.base.jijimons_house import jijimon\nn = counter()\n'
                                       '@jijimon.on_talk(when=trigger(760))\ndef t():\n    n.add(1)\n    if n >= 300:\n        say("Many.")\n'})
        self.assertIn('a.py:7:5: error: n is a byte on this engine (0-255): `n >= 300` would always be false', errors_of_py(p))
        self.assertIn('    IF v', '\n'.join(show_code(p, 'story-state')))                            # a 32-bit story variable there
        work = tempfile.mkdtemp(dir=TMP)
        open(os.path.join(work, 'script_178.scn.txt'), 'w').write('sec5:\n    ; --- dws (x_py.script.dws)\n    SHOW_TEXTBOX\n'
                                                                  '        "a (b)"\n    ; --- end dws\n')
        self.assertEqual(B.asm_where("script_178.scn.txt:4: character '(' has no glyph", work).split('  (')[0],
                         "x_py.script.dws, script 178 section 5: character '(' has no glyph")

    def test_fifth_review_files(self):
        """dws-python-intuitiveness-5.md 3, 6-8: a sibling file of constants only is importable; importing an NPC or a def
        from another file says what crosses files; a def that speaks as the NPC being talked to is inlined in each talk
        (`return closed()` too); the clock's hint says `== 0` (the same day), the year's that only days are counted."""
        consts = 'from dw import *\nFOODS = (Item.Meat, Item.Sirloin)\nOPEN_FROM = 8\n'
        cook = ('from dw import *\nfrom dw.base.native_forest_2 import forest\nfrom .constants import FOODS, OPEN_FROM\n'
                'cook = forest.npc(Species.Vegiemon, at=(-500, 1800))\n'
                'def closed():\n    say("Closed.")\n'
                '@cook.on_talk(when=trigger(760))\ndef early():\n    if clock.hour < OPEN_FROM:\n        return closed()\n    say("Early.")\n'
                '@cook.on_talk\ndef t():\n    if clock.hour >= 18:\n        closed()\n        return\n'
                '    pick = pick_item()\n    if pick in FOODS:\n        take_picked()\n')
        root, (a, b) = self.mod({'constants.py': consts, 'cook.py': cook})
        r = self.check_cli('check', os.path.dirname(a))
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn('ok: src, 1 event', r.stdout)
        t = self.lowered(b)
        self.assertNotIn('constants_py.decl.dws', t); self.assertEqual(t.count('say(cook, text("m-a.'), 3)
        self.assertNotIn('shared closed', t); self.assertIn('if (date_hour < 8) {\n                say(cook,', t)
        root, (a, b, c) = self.mod({'npcs.py': 'from dw import *\nfrom dw.base.native_forest_2 import forest\n'
                                               'cook = forest.npc(Species.Vegiemon, at=(-500, 1800))\norders = counter()\n',
                                    'helpers.py': 'from dw import *\ndef paid():\n    narrator.say("Paid.")\n',
                                    'cook.py': 'from dw import *\nfrom .npcs import cook, orders\nfrom .helpers import paid\n'
                                               '@cook.on_talk\ndef t():\n    paid()\n'})
        e = self.check_cli('check', os.path.dirname(a)).stderr
        self.assertIn('cook.py:2:1: error: cook is an NPC of npcs.py', e); self.assertIn('cook.py:3:1: error: paid is a def of helpers.py', e)
        self.assertIn("hint: a file imports another's quests, flags, counters and constants; an NPC stays in the file of its screen", e)
        self.assertIn('helpers.py:2:1: error: paid: a def is used in the file that has it, and this file has no screen', e)
        self.assertNotIn('is not an NPC of this file', e); self.assertEqual(e.count('error:'), 3)
        day = ('from dw import *\nfrom dw.base.dragon_eye_lake_6 import lake\nlast_day = counter()\nfirst = counter()\n'
               '@lake.on_enter(when=trigger(760))\ndef e():\n    if clock.day == last_day:\n        narrator.say("a")\n'
               '    if clock.year - first >= 1:\n        narrator.say("b")\n')
        root, (p,) = self.mod({'a.py': day}, toml='[save]\nvars = "13-15"\n')
        e = errors_of_py(p)
        self.assertIn('hint: the days since a kept day: clock.day - last_day >= 1 (another day), == 0 (the same day)', e)
        self.assertIn('hint: only days are counted (on the 30-day year: a wait up to 29 days)', e)

    def test_fifth_review_font(self):
        """dws-python-intuitiveness-5.md 5: a character the target's font lacks is an error at the .py line (not at the
        assembler's); an accent the original font lacks is a note at its line, and kept with --exe mods."""
        talk = 'from dw import *\nfrom dw.base.jijimons_house import jijimon\n@jijimon.on_talk(when=trigger(760))\ndef t():\n'
        root, (p,) = self.mod({'a.py': talk + '    if ask(yes="Join (500 bits)", no="No & no"):\n        say("{player}: yes, 50%")\n'})
        e = errors_of_py(p)
        self.assertIn("a.py:5:16: error: `(` `)` have no glyph in the original executable's font: the mod executables have them", e)
        self.assertIn('a.py:5:38: error: `&` has no glyph', e); self.assertIn('a.py:6:13: error: `%` has no glyph', e)
        root, (p,) = self.mod({'a.py': talk + '    say("¿Qué tal, señor?")\n'})
        r = self.check_cli('check', p)
        self.assertIn("a.py:5: note: ¿ é ñ: the original executable's font has no accents, so they are drawn plain (¿ left out)", r.stdout)
        self.assertNotIn('note:', self.check_cli('check', '--exe', 'mods', p).stdout)

    def test_font_punctuation_per_executable(self):
        """docs/mods/font.md: ( ) & % / … [ ] # * ~ @ – — ♪ (F05D-F06B) are kept for an executable that has them,
        refused at the .py line for one built before them (the extra glyphs it has: its .elf, or --font-glyphs), and the
        assembler refuses them too (never drawn as another glyph); … – — have a plain form (a note)."""
        talk = 'from dw import *\nfrom dw.base.jijimons_house import jijimon\n@jijimon.on_talk(when=trigger(760))\ndef t():\n'
        line = '    say("Jijimon (the elder) & friends: 50% off, 2/3… [Note] #1 *star* ~wave~ @home: 1–2 days—maybe ♪")\n'
        root, (p,) = self.mod({'a.py': talk + line})
        self.assertIn('ok: a.py', self.check_cli('check', '--exe', 'mods', '--font-glyphs', '44', p).stdout)
        r = self.check_cli('check', '--exe', 'story-state', '--font-glyphs', '29', p)
        self.assertIn('a.py:5:9: error: `(` `)` `&` `%` `/` `[` `]` `#` `*` `~` `@` have no glyph in the target executable '
                      '(--font-glyphs 29): it has 29 extra glyphs, built before these were added', r.stderr)
        self.assertIn('hint: rebuild that executable (patch 0024 has ( ) & % / … [ ] # * ~ @ – — ♪ since 2026-10-14', r.stderr)
        root, (p,) = self.mod({'a.py': talk + '    say("Wait… so—that ♪")\n'})
        r = self.check_cli('check', '--exe', 'mods', '--font-glyphs', '29', p)
        self.assertIn('a.py:5: note: … — ♪: the font of the target executable (--font-glyphs 29) has no glyphs for them, so they '
                      'are drawn plain (… as ..., — as -, ♪ left out); a rebuild of it keeps them', r.stdout)
        out = os.path.join(tempfile.mkdtemp(prefix='fontp-', dir=TMP), 'DG.SCN')
        r = self.check_cli('compile', '--exe', 'mods', '--font-glyphs', '44', p, '-o', out)
        self.assertEqual(r.returncode, 0, r.stderr)
        dg = open(out, 'rb').read()
        for code in (0xF062, 0xF06A, 0xF06B):                                  # … — ♪ as their own glyphs
            self.assertIn(code.to_bytes(2, 'big'), dg)
        # the assembler: a character past the executable's glyphs is an error, not another glyph
        from dws import bytecode as bytecode
        with self.assertRaisesRegex(bytecode.BytecodeError, r"character '\(' is extra glyph F05D and the target executable has the first 29"):
            bytecode.text_units('a (b)', 'x', {'font': 'mods', 'font_glyphs': 29}, lambda m: None)
        self.assertEqual(bytecode.text_units('a (b)', 'x', {'font': 'mods', 'font_glyphs': 44}, lambda m: None),
                         [bytes.fromhex('8281 8140 f05d 8282 f05e')])

    def test_fifth_review_hover(self):
        """dws-python-intuitiveness-5.md 9: every verb of the stub has a docstring (pyright shows it on hover), and the
        members of Screen, Item and the repeated species have one each."""
        from dws.py import stubs
        t = stubs.init_pyi()
        api = t.split('\nclass Species')[0]                  # (the language; raw.<command> below is the hatch, by name)
        bare = [l for l in api.split('\n') if re.match(r'\s*def (?!__)\w+\(.*\) -> \S+: \.\.\.$', l)]
        self.assertEqual([l for l in bare if 'Callable[[_F], _F]' not in l], [])
        self.assertIn('    jijimons_house = 218    # Jijimon\'s house\n    """Jijimon\'s house: screen 218, script 178', t)
        self.assertIn('    Meat = 38\n    """', t)
        self.assertIn('    Kunemon152 = 152\n    """Another Kunemon of the game\'s species table (id 152; Species.Kunemon is id', t)

    def test_fifth_review_small(self):
        """dws-python-intuitiveness-5.md 10: a warp entry and a step/use tile the screen's map lacks are refused (slots lists
        the triggers), and a warp at the end of a talk leaves no unreachable code; a new NPC named like an imported one; an
        unknown [save] key; name= not the folder; has(x) >= n; a statement at the top; fight(Species.X); a tight heap; a
        line that leaves one word for its last page; --lang reads the mod's own text/."""
        talk = 'from dw import *\nfrom dw.base.jijimons_house import house, jijimon, tokomon\n'
        root, (p,) = self.mod({'a.py': talk + '@jijimon.on_talk(when=trigger(760))\ndef t():\n    warp(Screen.native_forest_2, entry=9)\n'})
        self.assertIn('a.py:5:40: error: screen 2 has no entry 9: its entries are 0, 1, 2, 3', errors_of_py(p))
        root, (p,) = self.mod({'a.py': talk + '@jijimon.on_talk(when=trigger(760))\ndef t():\n    warp(Screen.native_forest_2, entry=1)\n'})
        r = self.check_cli('check', p)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertNotIn('unreachable', r.stderr)
        root, (p,) = self.mod({'a.py': talk + '@house.on_step(10, when=trigger(760))\ndef s():\n    narrator.say("x")\n'
                                              '@house.on_use(2, when=trigger(760))\ndef u():\n    narrator.say("y")\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:3:16: error: screen 218 has no step trigger 10: its map triggers step 0', e); self.assertNotIn('use trigger', e)
        out = self.check_cli('slots', '218').stdout
        self.assertIn('step triggers (@screen.on_step(t) runs when the tamer steps on one of its tiles):\n  step 0: 16 tiles', out)
        self.assertIn('  use 2: 15 tiles, the first at (650, -250)', out)
        root, (p,) = self.mod({'a.py': talk + 'jijimon = house.npc(Species.Gotsumon, at=(-450, -650), behaves_like=tokomon)\n'})
        self.assertIn("a.py:3:11: error: jijimon is the base's NPC imported above: a new NPC needs a name of its own", errors_of_py(p))
        root, (p,) = self.mod({'a.py': 'from dw import *\nseen = flag()\n'}, toml='[save]\nflag = "717-726"\nflags = "717-726"\n')
        self.assertIn('mod.toml: unknown key `flag` in [save]: `flags`', errors_of_py(p))
        root, (p,) = self.mod({'a.py': talk + '@jijimon.on_talk(when=trigger(760))\ndef t():\n    say("Hello.")\n'})
        open(os.path.join(os.path.dirname(os.path.dirname(p)), 'mod.toml'), 'w').write('name = "other"\n')
        self.assertIn('note: name = "other" is not the folder\'s name (m-a)', self.check_cli('check', p).stdout)
        root, (p,) = self.mod({'a.py': talk + '@jijimon.on_talk(when=trigger(760))\ndef t():\n    if has(Item.Meat) >= 2:\n        say("a")\n'
                                              '    fight(Species.Agumon)\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:5:8: error: has(...) is a yes/no: the count goes inside it', e); self.assertIn('hint: has(Item.Meat, 2)', e)
        self.assertIn('a.py:7:11: error: fight: someone on the screen is expected (an NPC, tamer, partner or narrator), not a species', e)
        root, (p,) = self.mod({'a.py': 'from dw import *\nsay("Hello.")\n'})
        self.assertIn('a.py:2:1: error: a statement is not allowed at the top of a story file', errors_of_py(p))
        root, (p,) = self.mod({'a.py': talk + 'keeper = house.npc(Species.Unimon, at=(450, -650), behaves_like=tokomon)\n'
                                              '@keeper.on_talk\ndef t():\n    say("Rocks, roots and recoveries. Members pay less: 500 bits, once, '
                                              'and the back shelf is yours.")\n'})
        r = self.check_cli('check', p)
        self.assertIn('(tight: it fits on the worst path the setup can take', r.stdout)
        self.assertIn('a.py:6:5: warning: this line fills 1 box page and leaves only "yours." for the last one', r.stderr)
        root, (p,) = self.mod({'a.py': talk + '@jijimon.on_talk(when=trigger(760))\ndef t():\n    say("Hello.")\n'})
        mdir = os.path.dirname(os.path.dirname(p)); elsewhere = os.path.join(tempfile.mkdtemp(dir=TMP), 'story', 'mods', 'm-a')
        shutil.copytree(mdir, elsewhere)                                          # (a mod outside the repository's story/mods)
        key = next(iter(PL_text_keys(os.path.join(elsewhere, 'src', 'a.py'))))
        os.makedirs(os.path.join(elsewhere, 'text')); json.dump({key: 'Hola.'}, open(os.path.join(elsewhere, 'text', 'es.json'), 'w'))
        prog = B.compile_sources([os.path.join(elsewhere, 'src', 'a.py')], lang='es')
        self.assertIn('Hola', '\n'.join(l for info in prog.b.scripts.values() for e in info['events'] for l in e[2]))

    HOUSE = 'from dw import *\nfrom dw.base.jijimons_house import house, jijimon, tokomon\n'

    def test_sixth_review_translation(self):
        """dws-python-intuitiveness-6.md 1, 3, 7: a ~fuzzy translation is not shipped (English, a warning at the line); a bank
        value is checked against the font at its line; missing keys, keys that are no line of the mod and a language no bank
        has are said; text sync writes en.json in source order with who says each line; text review MOD."""
        from dws.py import textsync
        root, (p,) = self.mod({'a.py': self.HOUSE + 'c = house.npc(Species.Gotsumon, at=(450, -650), behaves_like=tokomon)\n'
                                                   '@c.on_talk\ndef t():\n    say("First page.", "Second page.")\n'
                                                   '    if ask(yes="Sure", no="Not now"):\n        narrator.say("Done.")\n'})
        mods = os.path.join(root, 'story', 'mods'); mdir = os.path.join(mods, 'm-a')
        textsync.sync('m-a', log=lambda m: None, mods=mods)
        en = json.load(open(os.path.join(mdir, 'text', 'en.json'), encoding='utf-8'))
        keys = [k for k in en if not k.startswith('_')]
        self.assertEqual([en[k] for k in keys], ['First page.', 'Second page.', 'Sure', 'Not now', 'Done.'])      # source order
        self.assertEqual(en['_where'][keys[0]], 'a.py:6 t: c (Gotsumon) says, page 1 of 2')
        self.assertEqual(en['_where'][keys[2]], "a.py:7 t: option yes of the tamer's menu")
        self.assertEqual(en['_where'][keys[4]], 'a.py:8 t: the narrator says'); self.assertIn('the sources win', en['_about'])
        es = {keys[0]: 'Primera (página).', keys[1]: '~fuzzy Segunda.', keys[2]: 'Claro', 'm-a.deadbeef': 'x', 's178.sec5.u0': 'y'}
        json.dump(es, open(os.path.join(mdir, 'text', 'es.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        r = self.check_cli('check', '--lang', 'es', '--exe', 'mods', mdir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f'a.py:6:24: warning: es.json: {keys[1]} is marked ~fuzzy', r.stderr)
        self.assertIn(f'warning: 2 of 5 lines of m-a have no es translation (they stay English): {keys[3]} (a.py:7 t, option no), '
                      f'{keys[4]} (a.py:8 t)', r.stderr)
        self.assertIn('warning: es.json has 2 key(s) that are no line of m-a: m-a.deadbeef, s178.sec5.u0', r.stderr)
        self.assertIn("a line of the game (s178.sec5.u0) is not changed by a mod's bank", r.stderr)
        prog = B.compile_sources([p], exe='mods', lang='es')
        code = '\n'.join(l for info in prog.b.scripts.values() for e in info['events'] for l in e[2])
        self.assertIn('Primera (p', code); self.assertIn('"Second page."', code); self.assertNotIn('fuzzy', code)
        r = self.check_cli('check', '--lang', 'es', mdir)                       # the original executable: no ( )
        self.assertIn(f'a.py:6:9: error: es.json, {keys[0]}: `(` `)` have no glyph in the original executable\'s font', r.stderr)
        r = self.check_cli('check', '--lang', 'xy', mdir)
        self.assertIn('error: --lang xy: no bank of the build is in xy: m-a has no text/xy.json', r.stderr)
        self.assertIn('hint: the languages these mods have: es', r.stderr)
        textsync.sync('m-a', log=lambda m: None, mods=mods)                     # a key that was never a line stays (check says it)
        self.assertIn('m-a.deadbeef', json.load(open(os.path.join(mdir, 'text', 'es.json'), encoding='utf-8')))
        out = os.path.join(root, 'review')
        r = self.check_cli('text', 'review', mdir, '-o', out)
        self.assertIn('m-a: 5 lines', r.stdout); self.assertIn('es: 3 to do', r.stdout)
        self.assertIn('(~fuzzy)', open(os.path.join(out, 'index.html'), encoding='utf-8').read())

    def test_sixth_review_menus(self):
        """dws-python-intuitiveness-6.md 2, 4: a menu option wider than the row, and more options than the box has rows, are
        refused at the line (in a translation too, naming its key)."""
        head = self.HOUSE + '@jijimon.on_talk(when=trigger(760))\ndef t():\n'
        root, (p,) = self.mod({'a.py': head + '    if ask(yes="A very long option that will never fit in the narrow menu box", no="No"):\n'
                                              '        say("x")\n'})
        self.assertIn('error: menu option "A very long option that will never fit in the narrow menu box" is 61 units', errors_of_py(p))
        four = '    match {}choose(a="One", b="Two", c="Three", d="Four"):\n        case "a":\n            say("1")\n        case _:\n            pass\n'
        root, (p,) = self.mod({'a.py': head + four.format('')})
        e = errors_of_py(p)
        self.assertIn('a.py:5:5: error: a menu of 4 options: the box shows 3 rows under the speaker\'s name, so "Four" would not be drawn', e)
        self.assertIn('hint: narrator.choose(...) has no name row: 4 options', e)
        root, (p,) = self.mod({'a.py': head + four.format('narrator.').replace('say("1")', 'narrator.say("1")')})
        self.assertEqual(errors_of_py(p), '')

    def test_sixth_review_schedule(self):
        """dws-python-intuitiveness-6.md 5: a new NPC's presence may test the clock; the setup reads it (STORE_DATE p105) and
        tests the hour, on every engine."""
        root, (p,) = self.mod({'a.py': self.HOUSE + 'g = house.npc(Species.Bakemon, at=(-450, -650), behaves_like=tokomon, '
                                                   'when=clock.hour >= 20 or clock.hour < 5)\n@g.on_talk\ndef t():\n    say("Boo.")\n'})
        self.assertIn('npc species(37) slot 4 when clock.hour >= 20 or clock.hour < 5;', self.lowered(p))
        prog = B.compile_sources([p]); rep, run = B.assemble(prog, os.path.join(tempfile.mkdtemp(dir=TMP), 'DG.SCN'))
        mh = open(os.path.join(run, 'scn', 'maphead', 'maphead.scn.txt'), encoding='utf-8').read()
        self.assertIn('    STORE_DATE p105\n    IF p107 >= 20, or p107 < 5, else dws_presence_218_4\n    LOAD_DIGIMON 37', mh)
        root, (p,) = self.mod({'a.py': self.HOUSE + 'g = house.npc(Species.Bakemon, at=(-450, -650), behaves_like=tokomon, '
                                                   'when=has(Item.Meat))\n'})
        e = errors_of_py(p)
        self.assertIn('an NPC\'s when= cannot test `has(Item.Meat)`: who stands on the screen is decided by its setup, whose rule tests '
                      'flags and the clock only', e)
        self.assertIn('to send the NPC away by one, `npc.leave()` in an on_enter', e)

    def test_sixth_review_escapes(self):
        """dws-python-intuitiveness-6.md 8: {item Item.X} is the item's name as the game shows it; an escape the game does not
        have, or an item that does not exist, is an error at the line."""
        head = self.HOUSE + '@jijimon.on_talk(when=trigger(760))\ndef t():\n'
        root, (p,) = self.mod({'a.py': head + '    narrator.say("Received a {item Item.Digimushrm}.")\n'})
        code = '\n'.join(l for info in B.compile_sources([p]).b.scripts.values() for e in info['events'] for l in e[2])
        self.assertIn('"Received a {item 44}."', code)
        root, (p,) = self.mod({'a.py': head + '    narrator.say("A {itm 44} and a {item Item.Digimushroom}.")\n'})
        e = errors_of_py(p)
        self.assertIn('a.py:5:18: error: unknown escape {itm 44}: did you mean {item ...}?', e)
        self.assertIn('error: no Item.Digimushroom in {item Item.Digimushroom}: did you mean Item.Digimushrm?', e)

    def test_sixth_review_named_lines(self):
        """A named line t("name") with its English in the mod's text/en.json, mixed with lines written in
        place; a name en.json lacks is an error with the nearest; an unused one a note; a changed English is listed, not fuzzy."""
        from dws.py import textsync
        root, (p,) = self.mod({'a.py': self.HOUSE + 'g = house.npc(Species.Tokomon, at=(150, -350), behaves_like=tokomon)\n'
                                                   '@g.on_talk\ndef t():\n    say(t("greeter.hello"), "In place.")\n'
                                                   '    if ask(yes=t("greeter.yes"), no="No"):\n        narrator.say(t("bow"))\n'})
        mdir = os.path.join(root, 'story', 'mods', 'm-a'); os.makedirs(os.path.join(mdir, 'text'))
        en = {'greeter.hello': 'Hello, {player}!', 'greeter.yes': 'Yes', 'bow': 'The greeter bows.', 'unused': 'Nobody.'}
        json.dump(en, open(os.path.join(mdir, 'text', 'en.json'), 'w'))
        r = self.check_cli('check', mdir)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn('note: the named line "unused" is used by no file of m-a', r.stdout)
        code = '\n'.join(l for info in B.compile_sources([p]).b.scripts.values() for e in info['events'] for l in e[2])
        self.assertIn('"Hello, {player}!"', code); self.assertIn('"The greeter bows."', code)
        mods = os.path.join(root, 'story', 'mods'); textsync.sync('m-a', log=lambda m: None, mods=mods)
        got = json.load(open(os.path.join(mdir, 'text', 'en.json'), encoding='utf-8'))
        self.assertEqual(got['greeter.hello'], 'Hello, {player}!'); self.assertEqual(got['_where']['greeter.yes'], "a.py:7 t: option yes of the tamer's menu")
        json.dump({'greeter.hello': '¡Hola, {player}!'}, open(os.path.join(mdir, 'text', 'es.json'), 'w'), ensure_ascii=False)
        textsync.sync('m-a', log=lambda m: None, mods=mods)
        got['greeter.hello'] = 'Hello there, {player}!'; json.dump(got, open(os.path.join(mdir, 'text', 'en.json'), 'w'))
        textsync.sync('m-a', log=lambda m: None, mods=mods)
        es = json.load(open(os.path.join(mdir, 'text', 'es.json'), encoding='utf-8'))
        self.assertEqual(es['greeter.hello'], '¡Hola, {player}!'); self.assertEqual(es['_changed'], {'greeter.hello': 'Hello, {player}!'})
        r = self.check_cli('check', '--lang', 'es', '--exe', 'mods', mdir)
        self.assertIn('note: the English of "greeter.hello" (a.py:6 t, page 1 of 2) changed since it was translated', r.stdout)
        src = open(p).read(); open(p, 'w').write(src.replace('t("bow")', 't("bwo")'))
        self.assertIn('a.py:8:24: error: no line "bwo" in the text/en.json of m-a: did you mean bow?', errors_of_py(p))

    def test_sixth_review_small(self):
        """dws-python-intuitiveness-6.md 6, 9, 10 and the single-page boxes: the script past 16 KB in the writer's terms; disc
        --text-source; two NPCs on one tile; a warning per page at its line; why after take_over and on a flag; former species
        names; a new language of the game as a folder; a table line of MAPHEAD that wraps to a second page."""
        msg = B.script_too_big(178, 68232, tempfile.mkdtemp(dir=TMP))
        self.assertIn('script 178 (jijimons_house) is 68232 bytes and a script holds 16384 (MAP_SCRIPT_BUFFER', msg)
        self.assertIn('new_screen', msg)
        self.assertIn('--text-source SOURCE', self.check_cli('disc', '--help').stdout)
        self.assertIn("each mod's text/LANG.json", re.sub(r'\s+', ' ', self.check_cli('check', '--help').stdout))
        a = 'a = house.npc(Species.Gotsumon, at=(450, -650), behaves_like=tokomon)\n@a.on_talk\ndef t():\n'
        b = 'b = house.npc(Species.Tokomon, at=(450, -620), behaves_like=tokomon)\n@b.on_talk\ndef u():\n'
        root, (p,) = self.mod({'a.py': self.HOUSE + a + '    say("Hello there, my friend, how are things going in the city?",\n'
                                                       '        "Jijimon was young then. Yes, he was! He had hair, or so he says, and nobody can prove otherwise.")\n' + b + '    say("Hi.")\n'})
        r = self.check_cli('check', p)
        self.assertIn('note: screen 218 slot 5: the new Tokomon at (450, -620) stands on the tile of slot 4 (Gotsumon at (450, -650))', r.stdout)
        self.assertIn('a.py:7:9: warning: this line fills 1 box page and leaves only "otherwise." for the last one', r.stderr)
        root, (p,) = self.mod({'r.py': 'from dw import *\nfrom dw.base.restaurant_215 import giromon\ndj = take_over(giromon)\n'
                                               '@dj.on_talk\ndef talk():\n    say("Bzzt.")\n'})
        r = self.check_cli('why', 'giromon', os.path.dirname(os.path.dirname(p)))
        self.assertIn('giromon: an NPC of the base story (script 175, slot 6), taken over by m-a as dj', r.stdout)
        self.assertIn('1. talk (line 5): always', r.stdout)
        r = self.check_cli('why', 'meat_farm_explained')
        self.assertIn("meat_farm_explained: not an NPC; a name of the game's story", r.stdout); self.assertEqual(r.returncode, 0)
        root, (p,) = self.mod({'a.py': self.HOUSE + 'x = house.npc(Species.Rockmon, at=(450, -650), behaves_like=tokomon)\n'})
        self.assertIn('error: no species "Rockmon": it was renamed Species.Golemon', errors_of_py(p))
        self.assertIn('Formerly Rockmon', open(os.path.join(ROOT, 'typings/dw/__init__.pyi'), encoding='utf-8').read())
        from dws.textbank import TextBank, single_page_keys
        with self.assertRaisesRegex(ValueError, 'TEXT=xx: no text/xx/ \\(a text source is a folder text/<name>/'):
            TextBank('en', 'xx')
        self.assertIn('m1230.u14', single_page_keys())
        tb = TextBank('en', 'us'); tb.us_pages['m1230.u14'] = 1; tb.origin['m1230.u14'] = os.path.join(ROOT, 'text/ours/x.json')
        self.assertIn('m1230.u14 takes 2 pages in text/ours/x.json, and the game shows it one page', tb.single_page_overflow('m1230.u14', 2))
        self.assertIsNone(tb.single_page_overflow('m1230.u14', 1)); self.assertIsNone(tb.single_page_overflow('s178.sec5.u0', 4))

if __name__ == '__main__':
    unittest.main(verbosity=1)
