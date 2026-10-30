#!/usr/bin/env bash
# Boots DISC.cue on the card build/states/file-city.mcd (copied), waits for the title menu, continues the
# saved game and warps to the Arena Lobby (screen 208), then saves build/<NAME>-lobby.state.
# EMU_PORT must be set; about 3 minutes (the interpreter is slow, the intro movies cannot be skipped early).
#   EMU_PORT=38060 tools/dev/playtest/enter_arena_lobby.sh build/portraits.cue portraits
set -euo pipefail
cd "$(dirname "$0")/../../.."
DISC=$1; NAME=$2
python3 tools/dev/emulator.py stop >/dev/null 2>&1 || true
sleep 2
cp build/states/file-city.mcd build/$NAME-file-city.mcd
EMU_ARGS="-interpreter -debugger" python3 tools/dev/emulator.py start "$DISC" --card build/$NAME-file-city.mcd | tail -1
# START skips the intro movies; the title shows "PRESS START" (a START opens the menu: a box with white text)
.venv/bin/python - <<'PY'
import subprocess, sys, time
from tools.image import Image
t0 = time.time()
def shot():
    subprocess.run([sys.executable, 'tools/dev/emulator.py', 'shot', 'build/tolobby-title.png'], capture_output=True)
    try:
        return Image.open('build/tolobby-title.png').convert('RGB')
    except Exception:
        return None
while time.time() - t0 < 300:
    time.sleep(4)
    im = shot()
    if im is None:
        continue
    w, h = im.size
    yel = sum(1 for x in range(w * 55 // 100, w * 95 // 100) for y in range(h * 90 // 100, h * 98 // 100)
              if im.getpixel((x, y))[0] > 200 and im.getpixel((x, y))[1] > 170 and im.getpixel((x, y))[2] < 90)
    white = sum(1 for x in range(70, 250) for y in range(48, 108) if min(im.getpixel((x, y))) > 200)
    if yel > 40 and white > 150:
        break
    subprocess.run([sys.executable, 'tools/dev/emulator.py', 'press', 'START', '20'], capture_output=True)
else:
    sys.exit('the title menu never showed')
PY
sleep 2
python3 tools/dev/emulator.py seq "DOWN 8, wait 1, CROSS 10, wait 5, CROSS 10, wait 5, CROSS 10, wait 4, CROSS 10, wait 12" >/dev/null
sleep 25
python3 tools/dev/game_state.py warp 208 0
sleep 12
python3 tools/dev/emulator.py save build/$NAME-lobby.state
