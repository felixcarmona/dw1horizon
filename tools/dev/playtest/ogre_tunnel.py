#!/usr/bin/env python3
"""Capture the actual Ogre takeover scene in a selected language on a 2 MB disc.

  xvfb-run -a python3 tools/dev/playtest/ogre_tunnel.py DISC --exe EXE --card CARD --language en

Use a disc containing the requested language. Flags 149/150/151 select the
already-seen entrance, cleared fortress and not-yet-seen takeover. The test
steps onto section 51, lets the scene finish, then frames the sign and captures
it. Screenshots and a JSON result stay under --out.
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
from tools import dwmap


def bit(e, n):
    ram = e.ram()
    return bool(ram[e.A('SCRIPT_STATE+245') - 0x80000000 + n//8] & (1 << (n % 8)))


def place(e, x, z):
    e.poke('TAMER_POSITION_DATA+0x78', struct.pack('<3i', x, 0, z))
    e.poke('TAMER_ENTITY+0x10', struct.pack('<3i', x << 15, 0, z << 15))


def call(e, name, args):
    # Call from gameLoop and restore its return address on the following entry.
    gl, fn = e.A('gameLoop'), e.A(name)
    vals = list(args) + [0] * (4-len(args))
    e.run('lua', f'''
if OG and OG.bp then OG.bp:remove() end
OG = {{phase=0, done=false}}
OG.bp = PCSX.addBreakpoint({gl}, 'Exec', 4, 'ogre-proof', function()
 local r=PCSX.getRegisters()
 if OG.phase==0 then
  OG.ra=r.GPR.n.ra
  r.GPR.n.a0={vals[0]}; r.GPR.n.a1={vals[1]}; r.GPR.n.a2={vals[2]}; r.GPR.n.a3={vals[3]}
  r.GPR.n.ra={gl}; r.pc={fn}; OG.phase=1
 else
  r.GPR.n.ra=OG.ra; OG.done=true; OG.bp:remove()
 end
end)
return 'armed'
''')
    for _ in range(120):
        e.wait(.25)
        if e.run('lua', 'return OG.done').strip() == 'true': return
    raise AssertionError(f'{name} did not return')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--language', choices=('en', 'es'), default='en')
    ap.add_argument('--out', default='build/ogre-playtest'); ap.add_argument('--port', type=int, default=39188)
    ap.add_argument('--map', help='expected localized MAYO11.MAP (default: beside the supplied executable build)')
    a = ap.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = Emu(a.disc, a.exe, a.port, str(out/'emu'))
    for name, (addr, _, _) in elf_symbols(a.exe+'.elf').items(): e.table.setdefault(name, addr)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    result = {'language': a.language}
    try:
        e.start(a.card); assert e.continue_game() == 0
        e.wait(5); assert e.in_control()
        result['ram_bytes'] = len(e.ram())
        want = 0 if a.language=='en' else 1
        if e.peek('MOD_LANG', 'i') != want: call(e, 'modSetLanguage', [want])
        assert e.peek('MOD_LANG', 'i') == want, 'requested language is absent from this disc'
        e.poke('MOD_OPT_SIGNS', struct.pack('<i', 1))
        e.poke('MOD_OPT_STORY', struct.pack('<i', 0))
        e.gs('set', 'hour=10', 'minute=0', 'gametime_running=0')
        for n,v in ((149,1),(150,1),(151,0)): e.gs('trigger',str(n),str(v))
        assert e.warp(7), 'screen 7 did not load'
        e.wait(2); place(e, -850, -550)
        for _ in range(20):
            e.wait(.5)
            if bit(e,151): break
        assert bit(e,151), 'section 51 did not set the takeover flag'
        assert e.in_control(100), 'the takeover scene did not finish'
        # LocalMapObjectInstance is 34 bytes; flag is byte 33, after 35 tiles
        # of 20 bytes each. The script's visibility value 1 hides a frame.
        flags = [e.peek(f'MAP_TILE_DATA+{35*20+i*34+33}', 'b') for i in (5,6)]
        assert flags == [1,0], flags
        result.update(screen=e.peek('CURRENT_SCREEN','h'), takeover_seen=True, instance_flags=flags)
        expected = Path(a.map) if a.map else (Path(a.exe).resolve().parents[1]
                    / 'lang-signs-base' / a.language / 'MAP/MAP1/MAYO11.MAP')
        m = dwmap.MapFile(expected.read_bytes())
        vram = e.api('/api/v1/gpu/vram/raw')
        for raw in m.tims:
            tim = dwmap.TIM(raw)
            actual = b''.join(vram[((tim.y+y)*1024+tim.x)*2:
                                  ((tim.y+y)*1024+tim.x+tim.w)*2] for y in range(tim.h))
            assert actual == tim.pixels, 'uploaded sprite TIM differs from the localized build'
        result['texture_uploads_match'] = True
        place(e,-2900,-600); e.wait(3)
        call(e,'closeBox',[0])  # Hide the clock so the complete name is readable.
        call(e,'unsetCameraFollowPlayer',[])
        call(e,'tickCameraMoveTo',[-5000,2000,30])
        e.wait(4)
        e.run('pause')
        first=out/(a.language+'-after-scene.png'); second=out/(a.language+'-paused.png')
        e.run('shot',str(first)); e.wait(.5); e.run('shot',str(second))
        assert first.read_bytes()==second.read_bytes(), 'pause did not produce identical screenshots'
        result['paused_screenshots_identical']=True
        e.run('save',str(out/(a.language+'-after-scene.state')))
    except BaseException as error:
        result['error']=str(error)
        e.run('shot',str(out/(a.language+'-failure.png')),check=False)
        raise
    finally:
        (out/(a.language+'-result.json')).write_text(json.dumps(result,indent=2)+'\n')
        e.stop()
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
