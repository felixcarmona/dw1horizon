"""Battle animations: the unpacked format and the game's player, re-run tick by tick.

Unpacked (unpack.py) an animation is

    u32 K                           number of keys
    K x 772 bytes:
        i16 duration, i16 event     event: a sound/effect cue (0 = none), not decoded
        32 x 24 bytes, one per skeleton entry:
            i16 rx, ry, rz, mode    rotation, 4096 = one turn
            i16 tx, ty, tz, pad     added to the bone's joint offset
            i16 sx, sy, sz, loop    scale, 4096 = 1.0

Entries 0..B-1 are the bones; entry B is an extra one the player keeps but
does not attach to a mesh (not decoded). `loop` of entry 0 of key 0 is the
key the animation goes back to after the last one (-1: it stops).

The player (SLUS_013.28: setup 0x80022100, curves 0x80021aa8/0x80021b60,
per tick 0x80022b98 -> 0x80021df8 -> 0x80021c18) does not interpolate
linearly. Going to key c takes 2*D ticks (D = duration of key c at speed 1.0).
Each channel keeps a value, a velocity and two accelerations: the velocity
moves linearly from its current value to a midpoint during the first D
ticks and from there to the arrival velocity during the next D, the arrival
velocity being the mean of the slopes into and out of key c, and the
midpoint chosen so that the value lands exactly on key c. Rotations use
20 fractional bits, translations and scales 16. This module repeats that
integer arithmetic so the exported frames are the ones the game shows.
"""
import struct

from tools.derive import arraymath as np

KEY = 772
ENTRIES = 32


def parse(raw):
    """-> (durations, events, keys (K, 32, 12) int16)"""
    k = struct.unpack_from("<I", raw, 0)[0]
    durations, events, keys = [], [], np.zeros((k, ENTRIES, 12), np.int64)
    for i in range(k):
        dur, ev = struct.unpack_from("<hh", raw, 4 + KEY * i)
        durations.append(dur)
        events.append(ev)
        keys[i] = np.frombuffer(raw, "<i2", ENTRIES * 12, 4 + KEY * i + 4).reshape(ENTRIES, 12)
    return durations, events, keys


def loop_key(keys):
    return int(keys[0, 0, 11])


def _cdiv(a, b):
    """C integer division (truncates toward zero), elementwise."""
    q = np.abs(a) // abs(b)
    return np.where((a < 0) != (b < 0), -q, q)


def _half(a):
    return _cdiv(a, 2)


# channels: rotation xyz (fields 0-2, 20 bits), translation (4-6, 16), scale (8-10, 16)
FIELDS = np.array([0, 1, 2, 4, 5, 6, 8, 9, 10])
SHIFT = np.array([20, 20, 20, 16, 16, 16, 16, 16, 16])


from tools.derive.dcbplayer import play
