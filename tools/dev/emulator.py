#!/usr/bin/env python3
"""Harness for testing discs in PCSX-Redux headless (-no-ui mode + web server).

Usage:
  emulator.py start [DISC.cue] [--keep-cards] [--card FILE.mcd]
                                  starts the emulator (default build/gcc.cue if it exists, otherwise the
                                  original image) with fresh memory cards; state in build/emu-PORT.json
                                  (EMU_PORT=38091 for a second instance; EMU_ARGS="-8mb" for extra options)
  emulator.py stop                     stops it
  emulator.py status                   running? frames, execution state
  emulator.py wait SEC                 waits SEC seconds
  emulator.py shot [output.png]        screenshot (what the GPU displays)
  emulator.py vram [output.bin]        VRAM dump (1 MB; tools/dev/vram_image.py renders it)
  emulator.py record OUTPUT.mp4 SEC [FPS]  records video of the screen; can run in parallel with 'seq'
                                  to record while playing. With sound if started with EMU_AUDIO=FILE.raw
                                  (SDL 'disk' driver: raw f32le stereo 44.1 kHz of everything played)
  emulator.py peek ADDR [LEN]          reads RAM (hex); ADDR as RAM address (0x80xxxxxx) or offset
  emulator.py poke ADDR HEXBYTES       writes RAM
  emulator.py press BUTTON [FRAMES]    holds a button for N frames (START, CROSS, UP, ...)
  emulator.py lua CODE                 runs Lua inside the emulator and prints the result
  emulator.py save [FILE.state]        full save state (CPU, RAM, VRAM, SPU...): reproduces the exact state
  emulator.py load [FILE.state]        loads a save state (also on a freshly started emulator)
  emulator.py pause | resume           pauses / resumes emulation
  emulator.py ramdump > ram.bin        the 2 MB of raw RAM (used by tools/dev/game_state.py)
  emulator.py seq "START 20, wait 6, CROSS 10, shot a.png, save b.state"   sequence of steps (or a file)
                                  step "until ADDR SIZE VALUE [BUTTON|NONE] [MAX]": presses until RAM equals VALUE
                                  step "talk ADDR SIZE VALUE [MAX]": X only with text/choice open, until VALUE
                                  ADDR can be a symbol (MONEY, PARTNER_ENTITY+0x38): it is resolved
                                  for the loaded executable (original or GCC build)
  emulator.py log [N]                  last N lines of the emulator output

Example session:
  tools/dev/emulator.py start build/gcc.cue && tools/dev/emulator.py wait 45 && tools/dev/emulator.py press START 20
  tools/dev/emulator.py wait 5 && tools/dev/emulator.py shot build/title.png && tools/dev/emulator.py stop
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import json, os, subprocess, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dwsyms

ROOT = _DEV_ROOT
EMU = os.path.join(ROOT, '.tools/emu/pcsx-redux-zip/squashfs-root/AppRun')
PORT = int(os.environ.get('EMU_PORT', '38090'))     # EMU_PORT=38091 allows another instance in parallel
HOME = os.environ.get('EMU_HOME') or os.path.join(ROOT, '.tools/emu/home' + ('' if PORT == 38090 else f'-{PORT}'))   # portable mode: pcsx.json + memcards here (EMU_HOME=dir: another one, e.g. the 8 MB tests)
STATE = os.path.join(ROOT, f'build/emu-{PORT}.json')
HANDLERS = os.path.join(ROOT, 'tools/emu-handlers.lua')
BUTTONS = 'SELECT L3 R3 START UP RIGHT DOWN LEFT L2 R2 L1 R1 TRIANGLE CIRCLE CROSS SQUARE'.split()


def state():
    return json.load(open(STATE)) if os.path.exists(STATE) else None


def alive(st):
    try:
        os.kill(st['pid'], 0); return True
    except (ProcessLookupError, PermissionError, TypeError):
        return False


def api(path, data=None, timeout=15):
    st = state()
    if not st or not alive(st): sys.exit('the emulator is not running (emulator.py start)')
    req = urllib.request.Request(f'http://127.0.0.1:{st["port"]}{path}', data=data, method='POST' if data is not None else 'GET')
    return urllib.request.urlopen(req, timeout=timeout).read()


def press(button, frames=10):
    """Hold a pad button for N frames (60 per second) and release it."""
    r = api(f'/api/v1/lua/press?button={button}').decode()
    try:
        time.sleep(int(frames) / 60.0)
    finally:
        api(f'/api/v1/lua/release?button={button}')
    return f'{r} {frames}'


def build():
    """'orig' or 'gcc' depending on the loaded executable (computed once per start)."""
    if os.environ.get('DW_SYMS'):        # an explicit build (a name or a path): registered in this process too
        return dwsyms.explicit_build(os.environ['DW_SYMS'])
    st = state()
    if st and st.get('build'): return st['build']
    ram = api('/api/v1/cpu/ram/raw'); b = dwsyms.detect_build(ram)
    if b is None: return 'orig'          # not loaded yet (or unknown executable): not stored
    if st: st['build'] = b; json.dump(st, open(STATE, 'w'))
    return b


def addr(s):
    """RAM address -> offset. Accepts 0x80..., offsets or symbols (MONEY, PARTNER_ENTITY+0x38)."""
    if not __import__('re').fullmatch(r'0x[0-9A-Fa-f]+|\d+', s.strip()):
        v = dwsyms.resolve(s, build())
    else:
        v = int(s, 0)
    return v - 0x80000000 if v >= 0x80000000 else v


ACTIVE_INSTRUCTION = 'ACTIVE_INSTRUCTION'


def ram_val(ram, off, n):
    return int.from_bytes(ram[off:off + n], 'little')


def record(out, secs, fps=30):
    """Captures /api/v1/screen/still at ~fps for secs seconds and encodes an MP4 (×2, H.264).
    If the emulator was started with EMU_AUDIO, the sound of the same span is cut from the raw
    capture and muxed (AAC); the video is then timed by the audio (emulated time)."""
    import tempfile, shutil
    tmp = tempfile.mkdtemp(prefix='rec-', dir=os.path.join(ROOT, 'build'))
    audio = (state() or {}).get('audio')
    n = 0; t0 = time.time(); period = 1.0 / fps
    capture_times = []
    a0 = os.path.getsize(audio) if audio else 0
    try:
        while time.time() - t0 < secs:
            t = time.time()
            open(os.path.join(tmp, f'{n:06d}.png'), 'wb').write(api('/api/v1/screen/still'))
            capture_times.append((t, time.time()))
            n += 1
            time.sleep(max(0.0, period - (time.time() - t)))
        a1 = os.path.getsize(audio) if audio else 0
        real_fps = n / (time.time() - t0)
        ffmpeg = os.path.expanduser('~/.local/bin/ffmpeg')
        cmd = [ffmpeg, '-y', '-loglevel', 'error']
        if audio:
            a0 -= a0 % 8; a1 -= a1 % 8                     # f32le stereo frames
            with open(audio, 'rb') as f:
                f.seek(a0); pcm = f.read(a1 - a0)
            open(os.path.join(tmp, 'audio.raw'), 'wb').write(pcm)
            asecs = len(pcm) / 8 / 44100
            real_fps = n / asecs if asecs else real_fps
            cmd += ['-framerate', f'{real_fps:.3f}', '-i', os.path.join(tmp, '%06d.png'),
                    '-f', 'f32le', '-ar', '44100', '-ac', '2', '-i', os.path.join(tmp, 'audio.raw'),
                    '-c:a', 'aac', '-b:a', '160k', '-shortest']
        else:
            cmd += ['-framerate', f'{real_fps:.3f}', '-i', os.path.join(tmp, '%06d.png')]
        cmd += ['-vf', 'scale=iw*2:ih*2:flags=neighbor,pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode: sys.exit(r.stderr)
        # Audio determines MP4 duration, so wall time alone cannot identify a
        # frame. Keep the observed screen-fetch interval beside each frame.
        import hashlib
        with open(str(out) + '.frames.json', 'w') as f:
            json.dump(dict(schema=1, video=str(out), recorder_sha256=hashlib.sha256(
                open(__file__, 'rb').read()).hexdigest(), requested_seconds=secs,
                encoded_fps=round(real_fps, 3),
                timing_scope='Screen-fetch wall intervals; scalar samples remain independently observed.',
                frames=[dict(index=i, video_seconds=i / round(real_fps, 3),
                             wall_start=start, wall_end=end)
                        for i, (start, end) in enumerate(capture_times)]), f)
        print(f'{out}: {n} frames, {real_fps:.1f} fps, {secs:.0f} s' + (f', sound {asecs:.1f} s' if audio else ''))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def start(disc, keep_cards=False):
    import socket
    with socket.socket() as sk:                      # refuse to start if something already listens there:
        if sk.connect_ex(('127.0.0.1', PORT)) == 0:  # requests would silently go to the other emulator
            sys.exit(f'port {PORT} is already in use (another emulator?); stop it or use EMU_PORT')
    st = state()
    if st and alive(st): sys.exit(f'an emulator is already running (pid {st["pid"]}); emulator.py stop first')
    os.makedirs(HOME, exist_ok=True); os.makedirs(os.path.dirname(STATE), exist_ok=True)
    if not os.path.exists(os.path.join(HOME, 'pcsx.json')): open(os.path.join(HOME, 'pcsx.json'), 'w').write('{}\n')
    if not keep_cards:   # the PCSX-Redux nightly crashes when loading cards the game has already saved to
        for c in ('memcard1.mcd', 'memcard2.mcd'):
            if os.path.exists(os.path.join(HOME, c)): os.remove(os.path.join(HOME, c))
    if not os.path.exists(EMU): sys.exit(f'missing {EMU} (see tools/README.md)')
    disc = os.path.abspath(disc)
    out = open(os.path.join(ROOT, f'build/emu-{PORT}.out'), 'w')
    env = dict(os.environ, SDL_AUDIODRIVER='dummy')
    if os.environ.get('EMU_AUDIO'):   # capture the sound: SDL3 'disk' driver → raw f32le stereo 44.1 kHz
        env.pop('SDL_AUDIODRIVER')    # (the emulator then runs at the pace the driver pulls, ~1.3× real time)
        env.update(SDL_AUDIO_DRIVER='disk', SDL_AUDIO_DISK_OUTPUT_FILE=os.path.abspath(os.environ['EMU_AUDIO']))
    cmd = [EMU, '-no-ui', '-stdout', '-run', '-iso', disc,
           '-memcard1', os.path.join(HOME, 'memcard1.mcd'), '-memcard2', os.path.join(HOME, 'memcard2.mcd'),
           '-webserver', '-webserver-port', str(PORT), '-exec', f"dofile('{HANDLERS}')"]
    cmd += os.environ.get('EMU_ARGS', '').split()   # e.g. EMU_ARGS=-8mb
    p = subprocess.Popen(cmd, cwd=HOME, stdout=out, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    st = dict(pid=p.pid, port=PORT, disc=disc, started=time.time())
    if os.environ.get('EMU_AUDIO'): st['audio'] = os.path.abspath(os.environ['EMU_AUDIO'])
    json.dump(st, open(STATE, 'w'))
    for _ in range(40):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/v1/execution-flow', timeout=2).read()
            # our handlers (emu-handlers.lua, run by -exec) are registered after the web server answers: a call
            # to /lua/eval or /lua/load right after start got a 404 (save-robustness block 10, two emulators at once)
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/v1/lua/eval?code=return%201', timeout=2).read() != b'1':
                continue
            print(f'emulator pid {p.pid}, port {PORT}, disc {os.path.basename(disc)}'); return
        except Exception:
            if p.poll() is not None: sys.exit('the emulator has exited; see build/emu.out')
    sys.exit('the web server does not respond; see build/emu.out')


def stop():
    st = state()
    if st and alive(st):
        os.kill(st['pid'], 15); time.sleep(1)
        if alive(st): os.kill(st['pid'], 9)
        print('stopped')
    if os.path.exists(STATE): os.remove(STATE)


def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    cmd, rest = a[0], a[1:]
    if cmd == 'start':
        keep = '--keep-cards' in rest; rest = [r for r in rest if r != '--keep-cards']
        card = None
        if '--card' in rest:                    # --card FILE.mcd: install it as memory card 1
            k = rest.index('--card'); card = rest[k + 1]; del rest[k:k + 2]; keep = True
            os.makedirs(HOME, exist_ok=True)
            import shutil; shutil.copy(card, os.path.join(HOME, 'memcard1.mcd'))
        default = os.path.join(ROOT, 'build/gcc.cue')
        start(rest[0] if rest else (default if os.path.exists(default) else os.path.join(ROOT, 'Digimon World (USA).cue')), keep)
    elif cmd == 'stop': stop()
    elif cmd == 'status':
        st = state(); print('not running' if not st or not alive(st) else f'pid {st["pid"]} port {st["port"]} disc {os.path.basename(st["disc"])}')
        if st and alive(st): print('flow', api('/api/v1/execution-flow').decode())
    elif cmd == 'wait': time.sleep(float(rest[0]))
    elif cmd == 'shot':
        out = rest[0] if rest else os.path.join(ROOT, 'build/shot.png'); open(out, 'wb').write(api('/api/v1/screen/still')); print(out)
    elif cmd == 'vram':
        out = rest[0] if rest else os.path.join(ROOT, 'build/vram.bin'); open(out, 'wb').write(api('/api/v1/gpu/vram/raw')); print(out)
    elif cmd == 'peek':
        off, n = addr(rest[0]), int(rest[1], 0) if len(rest) > 1 else 16
        ram = api('/api/v1/cpu/ram/raw'); b = ram[off:off + n]
        for i in range(0, len(b), 16): print(f'{0x80000000 + off + i:08x}  {b[i:i + 16].hex(" ")}')
    elif cmd == 'poke':
        off, data = addr(rest[0]), bytes.fromhex(rest[1])
        api(f'/api/v1/cpu/ram/raw?offset={off}&size={len(data)}', data=data); print(f'wrote {len(data)} bytes at {0x80000000 + off:08x}')
    elif cmd == 'press':
        b = rest[0].upper(); frames = rest[1] if len(rest) > 1 else '10'
        if b not in BUTTONS: sys.exit('buttons: ' + ' '.join(BUTTONS))
        print(press(b, frames))
    elif cmd == 'lua':
        code = ' '.join(rest)
        if len(urllib.parse.quote(code)) < 150:   # the URL (percent-encoded) must stay short
            print(api('/api/v1/lua/eval?code=' + urllib.parse.quote(code)).decode())
        else:   # the web server does not accept long URLs: the code goes in a file
            f = os.path.join(ROOT, f'build/emu-eval-{PORT}.lua'); open(f, 'w').write(code)
            print(api('/api/v1/lua/eval?file=' + urllib.parse.quote(f)).decode())
    elif cmd == 'ramdump':
        sys.stdout.buffer.write(api('/api/v1/cpu/ram/raw'))
    elif cmd == 'seq':
        # sequence of steps separated by commas or lines: "START 20, wait 6, shot x.png, save y.state, DOWN 8"
        text = open(rest[0]).read() if rest and os.path.exists(rest[0]) else ' '.join(rest)
        text = ','.join(l.split('#', 1)[0] for l in text.splitlines())   # per-line comments, before splitting on commas
        for step in [x.strip() for x in text.split(',') if x.strip()]:
            w = step.split(); cmd2 = w[0].upper()
            if cmd2 == 'WAIT': time.sleep(float(w[1]))
            elif cmd2 in BUTTONS: print(press(cmd2, w[1] if len(w) > 1 else 10))
            elif cmd2 == 'SHOT': open(w[1], 'wb').write(api('/api/v1/screen/still')); print(w[1])
            elif cmd2 == 'UNTIL':
                # until ADDR SIZE VALUE [BUTTON] [MAX]: presses BUTTON (CROSS) every 3 s until RAM equals VALUE
                a2, n2, val = addr(w[1]), int(w[2]), int(w[3], 0); btn = w[4].upper() if len(w) > 4 else 'CROSS'
                tries = int(w[5]) if len(w) > 5 else 300
                for t in range(tries):
                    ram = api('/api/v1/cpu/ram/raw'); cur = int.from_bytes(ram[a2:a2 + n2], 'little')
                    if cur == val: print(f'until {w[1]} == {val:#x}: after {t} presses'); break
                    if btn != 'NONE': press(btn, 8)
                    time.sleep(3)
                else: sys.exit(f'until {w[1]} == {val:#x}: not met after {tries} tries (value {cur:#x})')
            elif cmd2 == 'TALK':
                # talk ADDR SIZE VALUE [MAX]: advances dialogs (X only if text or a choice is waiting)
                # until RAM equals VALUE
                a2, n2, val = addr(w[1]), int(w[2]), int(w[3], 0); tries = int(w[4]) if len(w) > 4 else 400
                ai = addr(ACTIVE_INSTRUCTION); presses = 0
                for t in range(tries):
                    ram = api('/api/v1/cpu/ram/raw'); cur = ram_val(ram, a2, n2)
                    if cur == val: print(f'talk {w[1]} == {val:#x}: after {presses} presses'); break
                    if ram[ai] in (0x1A, 0x10):
                        press('CROSS', 6); presses += 1
                    elif ram[ai] == 0x64:
                        # internal routine running (e.g. naming screen): X on the key under the cursor. The
                        # three-page keyboard (patch 0195) opens on A, and a full name moves the cursor to OK, so
                        # X alone types the name and confirms it (the old RIGHT, START steps left the grid: an
                        # empty tamer name, which OK refuses)
                        for _ in range(4):
                            press('CROSS', 6); time.sleep(1.2)
                        presses += 4
                    time.sleep(1.5)
                else: sys.exit(f'talk {w[1]} == {val:#x}: not met (value {cur:#x})')
            elif cmd2 in ('SAVE', 'LOAD'):
                state_file = os.path.abspath(w[1])
                response = api(f'/api/v1/lua/{cmd2.lower()}?file=' + urllib.parse.quote(state_file), timeout=60).decode()
                if cmd2 == 'SAVE' and response.startswith('ok '):
                    from tools.dev.snapshot import wait_complete
                    wait_complete(state_file)
                print(response)
            else: sys.exit(f'unknown step: {step}')
    elif cmd == 'record':
        # record OUTPUT.mp4 SECONDS [FPS]: records the emulator screen to video (no sound)
        out, secs = rest[0], float(rest[1]); fps = float(rest[2]) if len(rest) > 2 else 30
        record(out, secs, fps)
    elif cmd in ('save', 'load'):
        f = os.path.abspath(rest[0]) if rest else os.path.join(ROOT, 'build/emulator.state')
        response = api(f'/api/v1/lua/{cmd}?file=' + urllib.parse.quote(f), timeout=60).decode()
        if cmd == 'save' and response.startswith('ok '):
            from tools.dev.snapshot import wait_complete
            wait_complete(f)
        print(response)
    elif cmd in ('pause', 'resume'):
        api('/api/v1/execution-flow?function=' + ('pause' if cmd == 'pause' else 'start'), data=b''); print(cmd)
    elif cmd == 'log':
        n = int(rest[0]) if rest else 20; lines = open(os.path.join(ROOT, f'build/emu-{PORT}.out')).read().splitlines()
        print('\n'.join([l for l in lines if 'web api request' not in l][-n:]))
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main()
