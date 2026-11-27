#!/usr/bin/env python3
"""Prove the language file slot (file_table_us.c LANG_SLOT) on a 2 MB boot, with the disc's own LANGxx.BIN.

  xvfb-run -a python3 tools/dev/playtest/lang_slot.py DISC --exe EXE --out OUT --screen N [--boot en,es,ja]

For each --boot language a card whose saved options name it starts the game (the title sets the language from the
card), then the game runs modSetLanguage through every 2 MB language in turn. After every language change the slot's
rows in RAM must be that language's copies, each with the sector and size of its file in the disc's directory (the
layout of this very disc: a USA or a European or Japanese base), and nothing else. Screen --screen (one with
translated signs) is then entered: every '@' copy the game looks up (findFileEntry) must be a slot row. The time
modSetLanguage takes is counted in vertical blanks (Vcount). A save at Jijimon in the last language and a cold start
from that card must come back in it, with its slot. Screenshots and results.json go to --out.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools import isowriter as iw
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.load_camera import card_fixture
from tools.langpatch import elf_symbols

CODES = ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca')
FILE = {c: f'LANG{c[:2].upper()}.BIN' for c in CODES}


def call(e, name, *args):
    """Run `name` at gameLoop and pause on its return: (v0, vertical blanks it took)."""
    gl, vc = e.A('gameLoop'), e.A('Vcount') & 0x1fffff
    regs = '\n'.join(f'r.GPR.n.a{i}={v & 0xffffffff}' for i, v in enumerate(args))
    e.run('lua', f'''
      local function vcount() local m=PCSX.getMemPtr(); return m[{vc}]+m[{vc}+1]*256+m[{vc}+2]*65536 end
      LS_CALL={{done=false,phase=0}}
      LS_CALL.bp=PCSX.addBreakpoint({gl},'Exec',4,'lang-slot',function()
        local r=PCSX.getRegisters()
        if LS_CALL.phase==0 then
          LS_CALL.ra=r.GPR.n.ra; LS_CALL.v=vcount()
          {regs}
          r.GPR.n.ra={gl}; r.pc={e.A(name)}; LS_CALL.phase=1
        else
          LS_CALL.result=r.GPR.n.v0; LS_CALL.v=vcount()-LS_CALL.v; r.GPR.n.ra=LS_CALL.ra
          LS_CALL.done=true; LS_CALL.bp:remove(); PCSX.pauseEmulator()
        end
      end)
      PCSX.resumeEmulator()
    ''')
    for _ in range(600):
        if e.run('lua', 'return LS_CALL.done').strip() == 'true':
            out = int(e.run('lua', 'return LS_CALL.result').strip()) & 0xffffffff, int(e.run('lua', 'return LS_CALL.v').strip())
            e.run('resume')
            return out
        time.sleep(.1)
    raise AssertionError(f'{name} did not return')


def watch_lookups(e):
    """Record every language copy ('@' and its key, what modLangFile gives) the game looks up: the names findFileEntry
    is asked for (other files' callers) and modStoryFile is given (lookupFileTable, where findFileEntry is inlined)."""
    e.run('lua', f'''
      LS_NAMES={{}}; LS_WATCH={{}}
      local function record()
        local r=PCSX.getRegisters(); local m=PCSX.getMemPtr(); local p=r.GPR.n.a0 % 0x200000; local s={{}}
        for i=0,15 do local c=m[p+i]; if c==0 then break end; s[#s+1]=string.char(c) end
        local n=table.concat(s); if n:sub(1,1)=='@' then LS_NAMES[#LS_NAMES+1]=n end
      end
      LS_WATCH[1]=PCSX.addBreakpoint({e.A('findFileEntry')},'Exec',4,'lang-slot-find',record)
      LS_WATCH[2]=PCSX.addBreakpoint({e.A('modStoryFile')},'Exec',4,'lang-slot-story',record)
    ''')


def looked_up(e):
    names = e.run('lua', 'local t={} for _,n in ipairs(LS_NAMES) do t[#t+1]=n end; LS_WATCH[1]:remove(); '
                  'LS_WATCH[2]:remove(); return table.concat(t,",")').strip()
    return sorted(set(n for n in names.split(',') if n))


class Disc:
    def __init__(self, path):
        self.img = iw.Image(path[:-4] + '.bin' if path.endswith('.cue') else path)
        self.where = {p.split('/')[-1]: (lba, n) for p, (lba, n, xa) in self.img.files.items() if not xa}
        self.keys = {iw.filename_hash(n) & 0xFFFFFF: n for n in self.where}

    def group(self, code, slot):
        """the names a language's LANGxx.BIN writes into the slot, in order"""
        patch = self.img.read('SCN/' + FILE[code])
        for at, address, length in iw.lang_patch_runs(patch):
            if address <= slot[0] < address + length:
                rows = patch[at + slot[0] - address:at + slot[0] - address + 8 * slot[1]]
                keys = [int.from_bytes(rows[8 * i + 5:8 * i + 8], 'little') for i in range(slot[1])]
                return [self.keys[k] for k in keys if k]
        raise AssertionError(f'{FILE[code]}: no run writes the language file slot')


def slot_rows(e, slot):
    ram = e.ram()
    at = slot[0] & 0x1fffff
    return [int.from_bytes(ram[at + 8 * i:at + 8 * i + 8], 'little') for i in range(slot[1])]


def check_slot(e, disc, slot, code):
    """the slot in RAM holds exactly `code`'s copies, each at its sector and size on this disc"""
    want = disc.group(code, slot)
    rows = slot_rows(e, slot)
    for i, packed in enumerate(rows):
        if i >= len(want):
            assert packed == 0, (code, i, hex(packed))
            continue
        lba, size = disc.where[want[i]]
        expect = lba | iw.file_size_code(size) << 19 | (iw.filename_hash(want[i]) & 0xFFFFFF) << 40
        assert packed == expect, (code, i, want[i], hex(packed), hex(expect))
    return want


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=43411)
    ap.add_argument('--screen', type=int, required=True, help='a screen with translated signs (a .TFS copy)')
    ap.add_argument('--boot', default='en,es,ja', help='languages a saved card starts the game in')
    ap.add_argument('--switch', default=','.join(CODES), help='languages modSetLanguage then goes through')
    ap.add_argument('--save', default='es', help='the language saved at Jijimon and cold-started from (empty: none)')
    a = ap.parse_args(); out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    disc = Disc(a.disc)
    e = ProofEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for n, (address, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(n, address)
    result = dict(disc=Path(a.disc).name, boots=[], switches=[], save=None)
    try:
        for boot in a.boot.split(','):
            lang = CODES.index(boot)
            e.start(str(card_fixture(out, 112, [650, 0, 750], 3, False, 1, lang)))
            e.to_title()
            ram = e.ram()
            slot = struct.unpack_from('<II', ram, e.A('LANG_SLOT') & 0x1fffff)   # {FileEntry *entries; u32 count}
            assert e.peek('MOD_LANG', 'i', ram) == lang, ('title language', boot, e.peek('MOD_LANG', 'i', ram))
            group = check_slot(e, disc, slot, boot)
            e.run('shot', str(out / f'boot-{boot}-title.png'))
            assert e.continue_game() == 0
            check_slot(e, disc, slot, boot)
            row = dict(boot=boot, slot=len(group), signs=e.peek('MOD_OPT_SIGNS', 'i'))
            e.poke('MOD_OPT_SIGNS', struct.pack('<i', 1))   # MAP SIGNS TRANSLATED: the maps' copies are read
            watch_lookups(e)
            row['arrived'] = e.warp(a.screen)
            row['copies'] = looked_up(e)
            e.run('shot', str(out / f'boot-{boot}-screen-{a.screen}.png'))
            assert row['arrived'], row
            held = {f'@{iw.filename_hash(n) & 0xFFFFFF:08X}' for n in group}
            assert set(row['copies']) <= held, (boot, row['copies'])
            assert row['copies'], ('no translated copy loaded', boot)
            result['boots'].append(row); print(json.dumps(row), flush=True)
            if boot != a.boot.split(',')[-1]:
                continue
            for code in a.switch.split(','):
                lang = CODES.index(code)
                _, frames = call(e, 'modSetLanguage', lang)
                assert e.peek('MOD_LANG', 'i') == lang
                group = check_slot(e, disc, slot, code)
                watch_lookups(e)
                arrived = e.warp(a.screen if e.peek('CURRENT_SCREEN', 'h') != a.screen else 112)
                if e.peek('CURRENT_SCREEN', 'h') != a.screen:
                    arrived = arrived and e.warp(a.screen)
                copies = looked_up(e)
                held = {f'@{iw.filename_hash(n) & 0xFFFFFF:08X}' for n in group}
                assert arrived and set(copies) <= held and copies, (code, arrived, copies)
                e.run('shot', str(out / f'switch-{code}-screen-{a.screen}.png'))
                row = dict(language=code, frames=frames, slot=len(group), copies=copies)
                result['switches'].append(row); print(json.dumps(row), flush=True)
            if a.save:
                lang = CODES.index(a.save)
                call(e, 'modSetLanguage', lang)
                assert e.warp(218, 2) or e.in_control()
                e.save_at_jijimon()
                e.stop()
                saved = out / f'saved-{a.save}.mcd'; shutil.copy2(e.card_out(), saved)
                e.start(str(saved)); e.to_title()
                assert e.peek('MOD_LANG', 'i') == lang, ('saved language', e.peek('MOD_LANG', 'i'))
                group = check_slot(e, disc, slot, a.save)
                assert e.continue_game() == 0
                e.poke('MOD_OPT_SIGNS', struct.pack('<i', 1))
                watch_lookups(e)
                arrived = e.warp(a.screen); copies = looked_up(e)
                e.run('shot', str(out / f'saved-{a.save}-screen-{a.screen}.png'))
                held = {f'@{iw.filename_hash(n) & 0xFFFFFF:08X}' for n in group}
                assert arrived and set(copies) <= held and copies, (arrived, copies)
                result['save'] = dict(language=a.save, slot=len(group), copies=copies)
                print(json.dumps(result['save']), flush=True)
        for row in result['boots'] + result['switches'] + [result['save'] or dict(copies=[])]:
            row['files'] = [disc.keys.get(int(c[1:], 16), c) for c in row['copies']]
        (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    finally:
        e.stop()


if __name__ == '__main__':
    main()
