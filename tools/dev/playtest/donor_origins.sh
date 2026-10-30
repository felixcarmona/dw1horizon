#!/usr/bin/env bash
# donor_origins.sh: calls getModDonorTechBoneOffset in the running game for each species of content/tables/effect-donors.json with a
# hand-made EFE table and prints the point it returns (needs the built disc; patch 0116). Expected values in the labels.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38111 EMU_ARGS="-interpreter -debugger"
ELF=${ELF:-build/full/exe/SLUS_010.32.elf}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/d.mcd
tools/dev/emulator.py start "${DISC:-build/full.cue}" --card build/savedrop/d.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 10 >/dev/null
python3 - <<'PY'
import subprocess, struct, sys
def poke(a, rows):
    b = b''.join(struct.pack('<5h', *r) for r in rows) + struct.pack('<h', -1)
    subprocess.run([sys.executable, 'tools/dev/emulator.py', 'poke', hex(a), b.hex()], capture_output=True)
base = 0x801E0000
tests = [(119, [(24,2,60,0,10)], 'shogun -> 4,0,-20,-190'), (70, [(14,6,94,0,0)], 'waru -> 6,7,113,28'),
         (117, [(34,5,25,0,0)], 'jijimon -> bone 4, x 16'), (116, [(40,4,70,0,0)], 'analogman -> bone 2, x 61'),
         (121, [(55,11,7,7,7)], 'cherrymon -> 11,25,55,0'), (94, [(23,4,10,10,10)], 'icemon -> 4,60,35,0'),
         (120, [(39,3,100,50,25)], 'king sukamon -> 3,171,85,42'), (119, [(5,1,1,1,1)], 'shogun no donor row -> NULL')]
calls = []
for i, (t, rows, _) in enumerate(tests):
    a = base + 0x40 * i; poke(a, rows); calls.append(f'getModDonorTechBoneOffset({t},{a})')
r = subprocess.run([sys.executable, 'tools/dev/playtest/call_function.py', *calls], capture_output=True, text=True).stdout.split('\n')
for (t, rows, exp), line in zip(tests, r):
    ptr = int(line.rsplit('=', 1)[1]) if '=' in line else 0
    got = 'NULL'
    if ptr:
        out = subprocess.run([sys.executable, 'tools/dev/emulator.py', 'peek', hex(ptr), '8'], capture_output=True, text=True).stdout.split()[1:]
        got = struct.unpack('<4h', bytes.fromhex(''.join(out)))
    print(f'{exp:40s} got {got}')
PY
tools/dev/emulator.py stop >/dev/null
