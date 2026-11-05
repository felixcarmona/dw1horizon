#!/usr/bin/env python3
"""Photograph the real title/card-menu Yes/No renderers on a 2 MB boot.

Usage: xvfb-run -a python3 tools/dev/playtest/yes_no_menus.py DISC --exe EXE --card CARD --out OUT
Each forced menu executes the game's ordinary text and menu renderers; no save/delete confirmation is submitted.
"""
from pathlib import Path
import argparse
import json
import struct
import sys
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols
from tools.dev.playtest.ogre_tunnel import call


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--port', type=int, default=38685)
    ap.add_argument('--languages', default='en,es,pt-br,fr,de,it,ja,ca')
    ap.add_argument('--fonts', default='0,1,2')
    ap.add_argument('--menus', default='format,new,load,delete,retry,overwrite,battle,save,clear-save')
    a = ap.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = Emu(a.disc, a.exe, a.port, str(out/'emu'))
    for name, (addr, _, _) in elf_symbols(e.exe+'.elf').items(): e.table.setdefault(name, addr)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    # The title has its own loop. Hijack its next logic tick, before it builds GPU packets.
    e.table['gameLoop'] = e.A('tickMainMenu')
    result = {'ram_bytes': None, 'screens': []}
    def put(name, value): e.poke(name, struct.pack('<i', value))
    try:
        e.start(a.card); e.wait(60); e.to_title()
        result['ram_bytes'] = len(e.ram())
        for lang in a.languages.split(','):
            idx = ('en','es','pt-br','fr','de','it','ja','ca').index(lang)
            put('TARGET_MENU', 0); e.wait(1); call(e, 'modSetLanguage', [idx])
            assert e.peek('MOD_LANG', 'i') == idx
            for font in map(int, a.fonts.split(',')):
                call(e, 'modSetFont', [font])
                for name, menu, action in (('format',1,0), ('new',15,0), ('load',24,1), ('delete',34,2),
                                            ('retry',19,0), ('overwrite',48,0), ('battle',50,0),
                                            ('save',66,0), ('clear-save',69,0)):
                    if name not in a.menus.split(','):continue
                    put('MEMORY_CARD_ERROR', -1); put('CONNECTED_CARDS', 1)
                    put('MAIN_MENU_ACTION', action); put('TARGET_MENU', menu); e.wait(1.2)
                    path = out / f'{lang}-font{font}-{name}.png'
                    e.run('shot', str(path))
                    result['screens'].append(dict(language=lang, font=font, menu=menu, file=path.name,
                                                   current=e.peek('CURRENT_MENU', 'i')))
                    print(path.name, flush=True)
                    put('TARGET_MENU', 0); e.wait(.3)
        result['ok'] = all(s['menu'] == s['current'] for s in result['screens'])
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        e.stop()
    assert result['ok'], 'a requested menu did not remain open'


if __name__ == '__main__': main()
