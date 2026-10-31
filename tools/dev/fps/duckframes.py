#!/usr/bin/env python3
"""Capture every DuckStation refresh with the FrameStep hotkey (F12).

Usage: DS_DISPLAY=... DS_GDB_PORT=... DS_MAP=... duckframes.py DIR [FRAMES]
Requires Software rendering and Hotkeys/FrameStep=Keyboard/F12. A persistent
GDB connection and UI frame stepping leave the console paused between refreshes.
Each PNG has a RAM sample and must advance Vcount by exactly one. X11 readback
uses libX11 through ctypes, without optional Python imaging dependencies.
"""
import ctypes as c
import json
import os
from pathlib import Path
import struct
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev import duckstation as ds
from tools import image
from tools.dev.fps.curlingdscheck import BatchGDB


class XImage(c.Structure):
    _fields_ = [(n, t) for n, t in [
        ('width', c.c_int), ('height', c.c_int), ('xoffset', c.c_int),
        ('format', c.c_int), ('data', c.c_void_p), ('byte_order', c.c_int),
        ('bitmap_unit', c.c_int), ('bitmap_bit_order', c.c_int),
        ('bitmap_pad', c.c_int), ('depth', c.c_int),
        ('bytes_per_line', c.c_int), ('bits_per_pixel', c.c_int)]]


class WindowCapture:
    def __init__(self):
        self.lib = c.CDLL('libX11.so.6')
        self.lib.XOpenDisplay.argtypes = [c.c_char_p]
        self.lib.XOpenDisplay.restype = c.c_void_p
        self.lib.XGetImage.argtypes = [c.c_void_p, c.c_ulong, c.c_int,
                                      c.c_int, c.c_uint, c.c_uint, c.c_ulong, c.c_int]
        self.lib.XGetImage.restype = c.POINTER(XImage)
        self.lib.XDestroyImage.argtypes = [c.POINTER(XImage)]
        self.display = self.lib.XOpenDisplay(ds.DISPLAY.encode())
        if not self.display:
            raise RuntimeError('cannot open display')
        self.window = int(ds.window())
        geo = subprocess.check_output(['xdotool', 'getwindowgeometry', '--shell',
                                       str(self.window)], env=ds.ENV, text=True)
        values = dict(line.split('=') for line in geo.splitlines())
        self.size = int(values['WIDTH']), int(values['HEIGHT'])
        self.encoder = None

    def begin(self, directory):
        width, height = self.size
        self.encoder = subprocess.Popen([
            'ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo',
            '-pixel_format', 'bgra', '-video_size', '%dx%d' % (width,height),
            '-framerate', '60', '-i', 'pipe:0', '-vf',
            'scale=320:240:flags=neighbor,format=rgb24', '-c:v', 'png',
            str(directory/'%06d.png')], stdin=subprocess.PIPE)

    def finish(self):
        if self.encoder:
            self.encoder.stdin.close()
            if self.encoder.wait():
                raise RuntimeError('frame encoder failed')

    def shot(self, path):
        width, height = self.size
        ptr = self.lib.XGetImage(self.display, self.window, 0, 0, width, height,
                                c.c_ulong(-1).value, 2)
        if not ptr:
            raise RuntimeError('XGetImage failed')
        try:
            obj = ptr.contents
            if obj.bits_per_pixel != 32 or obj.bytes_per_line != width*4:
                raise RuntimeError('expected packed 32-bit X11 pixels')
            raw = c.string_at(obj.data, width*height*4)
            if self.encoder:
                self.encoder.stdin.write(raw)
                return
            data = bytearray(raw)
            data[0::4], data[2::4] = data[2::4], data[0::4]
            data[3::4] = bytes([255])*(width*height)
            image.frombytes('RGBA', self.size, bytes(data)).convert('RGB').resize(
                (320, 240), image.Resampling.NEAREST).save(path)
        finally:
            self.lib.XDestroyImage(ptr)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    capture = WindowCapture()
    capture.begin(out)
    ds.focus(str(capture.window))
    raw_fd = os.environ.get('DS_RAM_FD')
    raw_base = int(os.environ.get('DS_RAM_BASE', '0'))
    g = None if raw_fd else BatchGDB()
    if raw_fd:
        subprocess.run(['xdotool', 'key', 'space'], env=ds.ENV, check=True)
        time.sleep(.25)
    names = ['Vcount', 'MOD_FPS_TICKS', 'MOD_FPS_RENDERS', 'MOD_RENDER_PASS',
             'MOD_RENDER_ALPHA', 'MOD_STACK_GUARD_HITS', 'MOD_INTERP_STATS+8', 'MAIN_D_80135244', 'MOD_PERF_LATE',
             'MOD_RENDER_CADENCE', 'MAIN_D_80135238', 'MAIN_D_8013523E',
             'MOD_PERF_TICK_MAX','MOD_PERF_RENDER_MAX','MOD_PERF_TICK_SUM',
             'MOD_PERF_RENDER_SUM','MOD_PERF_GPU_SUM','MOD_PERF_P0END',
             'MAP_TILE_X','MAP_TILE_Y','MOD_TFS_STATS+4','MOD_TFS_STATS+12',
             'MOD_TFS_STATS+16','MOD_TFS_STATS+44','MOD_TFS_STATS+52',
             'MOD_TFS_STATS+56','MOD_TFS_STATS+60','MOD_TFS_STATS+64']
    addresses = {n: ds.sym(n) for n in names}
    def read():
        if raw_fd:
            return {n: int.from_bytes(os.pread(int(raw_fd), 4, raw_base+(a&0x1fffff)), 'little')
                    for n,a in addresses.items()}
        return {n: int.from_bytes(bytes.fromhex(value), 'little')
                for n,value in zip(addresses, g.batch(
                    ['m%x,4' % a for a in addresses.values()]))}
    geometry = bool(os.environ.get('DS_CURLING_GEOMETRY'))
    if geometry:
        history = int(re.search(r'^\s*\.bss\.kar_mod\s+(0x[0-9a-f]+)',
                                Path(ds.MAP).read_text(), re.M)[1], 16)
        plain_read = read
        def memory(address, size):
            if raw_fd:
                return os.pread(int(raw_fd), size, raw_base+(address&0x1fffff))
            return g.read(address, size)
        def read():
            result = plain_read()
            entity = int.from_bytes(memory(ds.sym('ENTITY_TABLE'), 4), 'little')
            bone = int.from_bytes(memory(entity+4, 4), 'little')
            result['geometry'] = dict(
                stones=memory(ds.sym('KAR_D_8005B5A0'), 2604).hex(),
                history=memory(history, 944).hex(), bones=memory(bone, 1360).hex())
            return result
    previous = read()['Vcount']
    try:
        with (out/'ram.jsonl').open('w') as stream:
            for n in range(count):
                subprocess.run(['xdotool', 'key', '--clearmodifiers', 'F12'],
                               env=ds.ENV, check=True)
                for attempt in range(100):
                    time.sleep(.01)
                    row = read()
                    if row['Vcount'] != previous:
                        break
                else:
                    raise RuntimeError('FrameStep did not advance Vcount')
                delta = (row['Vcount']-previous) & 0xffffffff
                if delta != 1:
                    raise RuntimeError('FrameStep advanced %d refreshes' % delta)
                previous = row['Vcount']
                time.sleep(.04)  # let the UI present the completed software frame to X11
                capture.shot(out/('%06d.png' % n))
                stream.write(json.dumps(dict(f=n, **row))+'\n')
                if n % 60 == 0:
                    print(n, row, flush=True)
    finally:
        if g:
            g.close()
        else:
            subprocess.run(['xdotool', 'key', 'space'], env=ds.ENV, check=True)
        capture.finish()


if __name__ == '__main__':
    main()
