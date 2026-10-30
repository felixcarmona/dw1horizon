#!/usr/bin/env bash
# script_text.sh: patch 0145 in the emulator (disc build/pack.cue or DISC=...). showTextbox is called on one text stored two bytes a unit and on the
# same text with letters, digits, spaces and punctuation as one byte (bytecode.pack_units), for the dialogue box (0) and the other boxes (1, 3), and the
# rows it writes (TEXTBOX_LINES_PTR) and the width it returns must be byte for byte the same. The text holds every packable character, glyphs that stay
# two bytes (extra font glyphs, the pad buttons, a backslash), colour/tab/half-width codes, the 03 code (four bytes), the player's name and a pstat, and
# several rows.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=${EMU_PORT:-38145} EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/pack.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/st.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/st.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/st.state >/dev/null
python3 -u - <<'PY'
import os, re, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms; from dws import bytecode; import fontgen
T = dwsyms.table(os.environ.get('DW_BUILD', 'disc-full'))     # DW_BUILD=decomp-fo for an executable built with FONT=original
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, data): emu('poke', hex(addr), data.hex())
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
BLOB = 0x80050000
opts = {'font': 'mods'}
def units(s): return bytecode.text_units(s, 'test', opts, lambda w: None)
rows = [
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    'abcdefghijklmnopqrstuvwxyz',
    '0123456789 .,:;?!\'"+-=',
    'a\\\\b {color 6}red{color 1} {tab 3}x{half 4}y',
    '{raw 03 11 22 33}ok {player} {pstat 5}',
    'Mixed: áéñ ¿? ({sjis 819b}{sjis 81a0}) end.',
    '',
]
lines = []
for r in rows: lines += units(r)
def text(pack):
    out = b''.join((bytecode.pack_units(l) if pack else l) + b'\x0d\x00' for l in lines) + b'\x00\x00'
    if len(out) % 2: out = bytecode._even_text(out)
    return out + b'\x00\x00'
assert text(1) != text(0) and len(text(1)) < len(text(0))
def run(blob, box, wiped=0):
    emu('load', 'build/savedrop/st.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    poke(BLOB, blob); poke(T['SCRIPT_POINTER'], struct.pack('<I', BLOB))
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', f'showTextbox({box}, 255)'], env=dict(os.environ, CALLFN_PAUSE='1'),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1'); out = p.communicate(timeout=300)[0]
    v = int(re.search(r'\) = (\d+)', out).group(1))
    base = struct.unpack('<I', peek(T['TEXTBOX_LINES_PTR'], 4))[0]
    end = struct.unpack('<I', peek(T['SCRIPT_POINTER'], 4))[0]
    return v, peek(base, 0x800), end - BLOB
bad = 0
for box in (0, 1, 3):
    a = run(text(0), box); b = run(text(1), box)
    same = a[0] == b[0] and a[1] == b[1]
    print(f'{"ok " if same else "BAD"} box {box}: width {a[0]} / {b[0]}, rows {"identical" if a[1] == b[1] else "DIFFER"}; script pointer after the text: '
          f'{a[2]} (two bytes, {len(text(0)) - 2} long) / {b[2]} (packed, {len(text(1)) - 2} long)', flush=True)
    if not same:
        for i in range(0, 0x800, 64):
            if a[1][i:i + 64] != b[1][i:i + 64]: print('  row', i // 64, a[1][i:i + 64].hex(), '\n     ', b[1][i:i + 64].hex()); break
    # the end of the text must be where the encoder says it ends (a packed text stays even)
    same = same and a[2] == len(text(0)) - 2 and b[2] == len(text(1)) - 2
    if a[2] != len(text(0)) - 2 or b[2] != len(text(1)) - 2: print('BAD end of text', a[2], b[2], len(text(0)), len(text(1)))
    bad += not same
print('FAILED' if bad else 'all identical')
PY
tools/dev/emulator.py stop >/dev/null
