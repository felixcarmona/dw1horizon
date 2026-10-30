"""The Card Battle fixed-point animation player, using flat integer channels."""
import struct
from .arraymath import Array, float64

FIELDS = (0, 1, 2, 4, 5, 6, 8, 9, 10)
SHIFTS = (20, 20, 20, 16, 16, 16, 16, 16, 16)
KEY_BYTES = 772


def _cdiv(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def play(raw, nbones):
    nk = struct.unpack_from('<I', raw)[0]
    if not nk:
        return Array([], (0, nbones, 9), float64), [], False
    durations, events_k, keys = [], [], []
    for i in range(nk):
        offset = 4 + i * KEY_BYTES
        dur, event = struct.unpack_from('<hh', raw, offset)
        durations.append(dur); events_k.append(event)
        key = struct.unpack_from('<384h', raw, offset + 4)
        keys.append([key[bone * 12 + field] for bone in range(nbones) for field in FIELDS])
    loop = struct.unpack_from('<h', raw, 4 + 4 + 22)[0]
    shifts = SHIFTS * nbones
    value = [v << s for v, s in zip(keys[0], shifts)]
    velocity = [0] * len(value)
    frames, events = [], []

    def current():
        return [(_cdiv(v, 1 << 20) if j % 9 < 3 else v >> 16) for j, v in enumerate(value)]

    order = list(range(nk)) + ([loop] if loop >= 0 else [])
    for i, c in enumerate(order):
        if i + 1 < len(order): n = order[i + 1]
        elif loop >= 0: n = c + 1 if c + 1 < nk else loop
        else: n = None
        if events_k[c]: events.append((len(frames) // (nbones * 9), events_k[c]))
        dur = durations[c]
        pose = current(); target = keys[c]
        following, dn = (target, 1) if n is None else (keys[n], 2 * durations[n])
        value = [v << shift for v, shift in zip(pose, shifts)]
        accel1, accel2 = [], []
        for old, p1, p2, shift, vel in zip(value, target, following, shifts, velocity):
            slope = _cdiv((p1 << shift) - old, 2 * dur)
            outgoing = _cdiv((p2 - p1) << shift, dn)
            arrive = _cdiv(outgoing + slope, 2)
            mid = 2 * slope - _cdiv(arrive + vel, 2)
            accel1.append(_cdiv(mid - vel, dur)); accel2.append(_cdiv(arrive - mid, dur))
        for tick in range(2 * dur):
            frames.extend(current())
            value = [v + vel for v, vel in zip(value, velocity)]
            accel = accel1 if tick < dur else accel2
            velocity = [vel + a for vel, a in zip(velocity, accel)]
    frames.extend(current())
    return Array([float(v) for v in frames], (len(frames) // (nbones * 9), nbones, 9), float64), events, loop >= 0
