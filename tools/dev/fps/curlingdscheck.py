#!/usr/bin/env python3
"""Tick-exact DuckStation curling replay from free control in File City.

Usage: DS_DISPLAY=... DS_GDB_PORT=... DS_MAP=... curlingdscheck.py OUT
The tool enters screen 136 through exit 1 and seeds the SDK RNG at setup.
Input is supplied after polling, before logic. No physics is patched.
The .jsonl file records every tick; the .json file summarizes the full match.
Debugger pauses affect wall time, so measure free-running performance separately.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
import socket
import re
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev import duckstation as ds

ds.sym = lru_cache(None)(ds.sym)


class BatchGDB(ds.GDB):
    def cmd(self, packet, reply=True):
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        result = super().cmd(packet, reply)
        return result

    def batch(self, packets):
        encoded = [p.encode() for p in packets]
        self.s.sendall(b''.join(b'$'+p+b'#%02x' % (sum(p)&255) for p in encoded))
        replies = []
        for packet in packets:
            while True:
                match = re.search(rb'\$([^#]*)#..', self.buf)
                if match:
                    self.buf = self.buf[match.end():]
                    value = match.group(1).decode()
                    if value.startswith(('S', 'T')) and packet != 'c':
                        continue  # unsolicited stop after UI frame stepping
                    replies.append(value)
                    break
                chunk = self.s.recv(65536)
                if not chunk:
                    raise ConnectionError('debugger disconnected')
                self.buf += chunk
        return replies


def main():
    out = Path(sys.argv[1])
    g = BatchGDB()
    g.s.settimeout(60)
    setup = ds.sym('KAR_setupMatch')
    # Stop immediately after gameLoop polls the pad, before any logic uses it.
    # This also observes completion after KAR stops receiving callbacks.
    image = (Path(ds.MAP).parent/'SLUS_010.32').read_bytes()
    load = struct.unpack_from('<I', image, 0x18)[0]
    loop = ds.sym('gameLoop')
    poll = ds.sym('pollInputGame')
    sites = [loop+i+8 for i in range(0, 128, 4)
             if struct.unpack_from('<I', image, 0x800+loop-load+i)[0] ==
             (0x0c000000 | ((poll >> 2) & 0x03ffffff))]
    if len(sites) != 1:
        raise RuntimeError('cannot find gameLoop pad call')
    tick = sites[0]
    def bp(address, on):
        result = g.cmd('%s0,%x,4' % ('Z' if on else 'z', address))
        if result != 'OK':
            raise RuntimeError('breakpoint: '+repr(result))
    started = time.monotonic()
    digest = hashlib.sha256()
    presentation = []
    checkpoints = {6:'aim',8:'power',11:'throw',16:'tally'} if os.environ.get('DS_CHECKPOINTS') else {}
    pending = None
    late_checkpoint = False
    last_tick = None
    saves = Path(ds.BIN)/'savestates'

    states = {}
    finished = False
    previous, age, previous_pad = -1, 0, 0
    tick_base = None
    first_recorded = None
    bp(tick, False)
    g.write(ds.sym('SCRIPT_STATE')+458, bytes([1]))
    g.write(ds.sym('TAMER_SUB_STATE'), bytes([0]))
    g.write(ds.sym('TARGET_MAP'), struct.pack('<h', 136))
    g.write(ds.sym('CURRENT_EXIT'), bytes([1]))
    g.write(ds.sym('TAMER_STATE'), bytes([5, 0]))
    bp(setup, True)
    print('waiting for setup', flush=True)
    try:
        print(g.cmd('c'), flush=True)
        g.write(0x80008464, struct.pack('<I', 0x12345678))
        if 'DS_CHECK_MODE' in os.environ:
            g.write(ds.sym('MOD_FPS_MODE_RUN'), struct.pack('<I', int(os.environ['DS_CHECK_MODE'])))
        tick_base = int.from_bytes(g.read(ds.sym('MOD_FPS_TICKS'), 4), 'little')+1
        bp(setup, False)
        # Let the ten intro calibration ticks run without debugger pauses.
        # A stop inside a measured tick can change the observed budget. Stop
        # only at the one-time cadence assignment, after measurements finish.
        elf = Path(ds.MAP).with_suffix('')
        table = subprocess.check_output(['readelf', '-sW', str(elf)], text=True)
        history = re.search(r'^\s*\d+: ([0-9a-f]+)\s+(\d+) OBJECT\s+LOCAL.* KAR_MOD$', table, re.M)
        if history and os.environ.get('DS_FREE_WARMUP', '1') != '0':
            size = int(history[2])
            function = re.search(r'^\s*\d+: [0-9a-f]+\s+(\d+) FUNC\s+GLOBAL.* KAR_tick$', table, re.M)
            address = ds.sym('KAR_tick')
            code = g.read(address, int(function[1]))
            words = struct.unpack('<%dI' % (len(code)//4), code)
            stores = [i for i,w in enumerate(words)
                      if w >> 26 == 43 and w & 65535 == size-4]
            if len(stores) != 1:
                raise RuntimeError('cannot locate one-time cadence assignment')
            index = stores[0]-1
            branch = words[index]
            if branch >> 26 != 4 or (branch >> 16) & 1023:
                raise RuntimeError('cadence store must follow an unconditional branch')
            ready = address+index*4
            bp(ready, True)
            print('free intro calibration', g.cmd('c'), flush=True)
            bp(ready, False)
        bp(tick, True)
        g.s.settimeout(10)
        with out.with_suffix('.jsonl').open('w') as stream:
            n = -1
            for attempt in range(20000):
                stop = g.cmd('c')
                if not stop.startswith(('T', 'S')):
                    raise RuntimeError('unexpected stop '+repr(stop))
                requests = [('MAIN_D_80135244', 4), ('MAIN_D_8013523E', 2),
                            ('MAIN_D_80135238', 2), ('KAR_D_8005B5A0', 2048)]
                packets = ['m%x,%x' % (ds.sym(name), size) for name,size in requests]
                packets += ['m%x,%x' % (ds.sym('KAR_D_8005B5A0')+2048, 556),
                            'm80008464,4', 'm%x,%x' % (ds.sym('MOD_FPS_RENDERS'),
                            ds.sym('MOD_PERF_LATE')-ds.sym('MOD_FPS_RENDERS')+4),
                            'm%x,4' % ds.sym('Vcount')]
                fields = [bytes.fromhex(v) for v in g.batch(packets)]
                counter_offset = ds.sym('MOD_FPS_TICKS')-ds.sym('MOD_FPS_RENDERS')
                real_tick = struct.unpack_from('<I', fields[6], counter_offset)[0]
                if real_tick == last_tick:
                    continue  # an asynchronous stop, not another logic tick
                if last_tick is not None and real_tick != last_tick+1:
                    raise RuntimeError('missed logic tick')
                last_tick = real_tick
                n = real_tick-tick_base
                if first_recorded is None:
                    first_recorded = n
                    if n:
                        previous, age = 1, n-1
                state = struct.unpack('<I', fields[0])[0]
                age = age+1 if state == previous else 0
                if state != previous:
                    print(n, state, flush=True)
                previous = state
                if pending:
                    name, stamp = pending
                    fresh = [p for p in saves.glob('*.sav') if p.stat().st_mtime_ns > stamp]
                    if fresh:
                        path = max(fresh, key=lambda p:p.stat().st_mtime_ns)
                        if path.stat().st_size > 100000:
                            shutil.copyfile(path, out.parent/(name+'.sav'))
                            pending = None
                name = None
                if state in checkpoints and pending is None:
                    name = checkpoints.pop(state)
                elif (os.environ.get('DS_CHECKPOINTS') and state == 11 and
                      not late_checkpoint and pending is None and fields[3][1]+fields[3][869] >= 9):
                    name = 'late-throw'
                    late_checkpoint = True
                if name:
                    stamp = max((p.stat().st_mtime_ns for p in saves.glob('*.sav')),default=0)
                    ds.focus(ds.window())
                    subprocess.run(['xdotool','key','F2'],env=ds.ENV,check=True)
                    pending = name, stamp
                counters = fields[6]
                first = ds.sym('MOD_FPS_RENDERS')
                stats = {name: struct.unpack_from('<I', counters, ds.sym(name)-first)[0]
                         for name in ['MOD_FPS_RENDERS','MOD_FPS_TICKS','MOD_PERF_LATE']}
                presentation.append(dict(tick=n, state=state, vcount=int.from_bytes(fields[7],'little'), **stats))
                power = struct.unpack('<h', fields[1])[0]
                raw = fields[3]+fields[4]
                physics = []
                for p in range(3):
                    row = raw[p*868:(p+1)*868]
                    live_fields = [row[:6].hex()]
                    for i in range(5):
                        stone = row[8+i*172:8+(i+1)*172]
                        # Exclude padding, drawing objects and matrices.
                        live_fields.append((stone[:18]+stone[20:32]+
                                       stone[148:154]+stone[156:168]).hex())
                    physics.append(live_fields)
                item = dict(tick=n, state=state, power=power,
                            aim=struct.unpack('<h', fields[2])[0],
                            rng=fields[5].hex(), stones=physics)
                line = json.dumps(item, sort_keys=True, separators=(',', ':'))+'\n'
                stream.write(line)
                digest.update(line.encode())
                states[state] = states.get(state, 0)+1
                if state == 20:
                    finished = True
                    break
                pad = 0
                if state == 6:
                    if age < 10:
                        pad = 0x2000
                    elif age == 30:
                        pad = 0x40
                elif state == 8:
                    if power >= 1500:
                        pad = 0x40
                elif state != 11 and age % 12 == 0:
                    pad = 0x40
                replies = g.batch(['M%x,4:%s' % (ds.sym(name), struct.pack('<I', value).hex())
                                   for name,value in [('POLLED_INPUT_PREVIOUS', previous_pad),
                                                      ('POLLED_INPUT', pad),
                                                      ('CHANGED_INPUT', pad & ~previous_pad)]])
                if replies != ['OK']*3:
                    raise RuntimeError('pad writes failed')
                if n % 100 == 0:
                    stream.flush()
                    print('tick', n, 'wall', round(time.monotonic()-started, 1), flush=True)
                previous_pad = pad
        result = dict(finished=finished, ticks=n+1, recorded_ticks=len(presentation), recording_first_tick=first_recorded, states=states,
                      seed='12345678', sha256=digest.hexdigest(),
                      scores=[raw[p*868] for p in range(2)],
                      thrown=[raw[p*868+1] for p in range(2)],
                      wall_seconds=round(time.monotonic()-started, 3))
        out.with_suffix('.presentation.json').write_text(json.dumps(presentation)+'\n')
        out.with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result), flush=True)
    finally:
        bp(setup, False)
        bp(tick, False)
        g.close()


if __name__ == '__main__':
    main()
