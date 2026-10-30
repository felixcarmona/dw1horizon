#!/usr/bin/env bash
# script_text_e2e.sh: patch 0145 end to end. Two discs built with the same executable and tools/dws/examples/font-proof.dws, one with the story's
# texts as two-byte units (DISC_OFF, default build/fpu.cue) and one packed (DISC_ON, build/fpp.cue). Build them with
#   MAIN_STORY=tools/dws/examples/font-proof.dws PACK_ASCII=1 tools/build-full.sh fpp ;  MAIN_STORY=tools/dws/examples/font-proof.dws tools/build-full.sh fpu
# Jijimon is talked to (two pages, a choice, the shop menu, the shop, the amount box, the "bought" box) and after each step the rows showTextbox wrote
# (TEXTBOX_LINES_BUFFER) must be byte for byte the same on both discs: the pictures are not compared, the world around the box is animated.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=${EMU_PORT:-38147} EMU_ARGS="-interpreter -debugger" DW_SYMS=${DW_SYMS:-disc-full}
OUT=${OUT:-build/script-text-e2e}; mkdir -p $OUT build/savedrop
python3 -u - <<'PY'
import os, struct, subprocess, sys
sys.path.insert(0, 'tools/dev/playtest'); sys.path.insert(0, 'tools')
from species_proof import in_world, seq, run, E, G
from tools.dev import symbols as dwsyms
T = dwsyms.table(dwsyms.explicit_build(os.environ['DW_SYMS']))
OUT = os.environ.get('OUT', 'build/script-text-e2e')
STEPS = [('dialogue1', 'wait 1, CROSS 6, wait 8'), ('dialogue2', 'CROSS 6, wait 8'), ('choice', 'CROSS 6, wait 8'),
         ('shopmenu', 'CROSS 6, wait 6, CROSS 6, wait 8'), ('shop', 'CROSS 6, wait 10'), ('amount', 'CROSS 6, wait 8'), ('bought', 'CROSS 6, wait 8')]
def peek(addr, n):
    out = subprocess.run([sys.executable, 'tools/dev/emulator.py', 'peek', hex(addr), str(n)], capture_output=True, text=True).stdout
    return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in out.strip().split('\n')))
def rows():
    base = struct.unpack('<I', peek(T['TEXTBOX_LINES_PTR'], 4))[0]
    return peek(base, 0x800)
dumps = {}
for v, disc in (('off', os.environ.get('DISC_OFF', 'build/fpu.cue')), ('on', os.environ.get('DISC_ON', 'build/fpp.cue'))):
    card = f'build/savedrop/e2e-{v}.mcd'; open(card, 'wb').write(open('build/ids-saved.mcd', 'rb').read())
    run(E + ['stop']); run(E + ['start', disc, '--card', card])
    seq('wait 45, START 20, wait 6, START 20, wait 6')
    seq('DOWN 8, wait 1, CROSS 10, wait 5, CROSS 10, wait 5, CROSS 10, wait 4, CROSS 10, wait 14')
    for _ in range(6):                       # a dropped press leaves the continue menu open: confirm again
        if in_world(): seq('wait 12'); break
        seq('CROSS 10, wait 30')
    else: sys.exit('did not reach the world')
    run(G + ['approach', '0'])
    for name, s in STEPS:
        seq(s); dumps[v, name] = rows(); open(f'{OUT}/{v}-{name}.rows', 'wb').write(dumps[v, name])
    run(E + ['stop'])
bad = 0
for name, _ in STEPS:
    a, b = dumps['off', name], dumps['on', name]
    live = [i for i in range(0, 0x800, 64) if a[i:i + 64] != b[i:i + 64]]
    nonempty = sum(1 for i in range(0, 0x800, 64) if any(a[i:i + 64]))
    print('ok ' if not live else 'BAD', f'{name:10s} {nonempty} rows with text, differing rows: {[i // 64 for i in live]}', flush=True)
    bad += bool(live) or not nonempty
print('FAILED' if bad else 'all identical')
PY
