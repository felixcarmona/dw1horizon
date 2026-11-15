"""Match DCB script sounds to the native battle bank, without exporting disc data.

DCB_IMAGE=disc.bin python -m tools.dcbsound > cues.json

Only derived ticks and sound ids are printed. SE0.PAK in A.DRV contains a two-word
header, a standard VAB header and its ADPCM body. Sound ids select successive tones
(program = id // 16, key = 60 + id % 16), as in DW1's SB bank. Matching compares
SPU-pitched, looped and enveloped notes by duration, RMS envelope and spectrum.
"""
import json
import os
import struct

import numpy as np

from tools import dcbeffect as C, dcbefe, efescript, sound

RATE = 22050


def bank(image):
    data = C.drv(image, 'A.DRV')['SE0.PAK']
    size = sound.vh_size(struct.unpack_from('<H', data, 8 + 18)[0])
    if struct.unpack_from('<I', data, 4)[0] != size:
        raise ValueError('SE0.PAK: unexpected VAB header size')
    total = struct.unpack_from('<I', data, 8 + 12)[0]
    return sound.Vab(data[8:8 + size], data[8 + size:8 + total])


def battle_ids(archive):
    """The 62 constant battle sounds called by the original effect scripts."""
    ids = set()
    for start in range(0, len(archive), efescript.CHUNK):
        inst = efescript.disassemble(archive[start:start + efescript.CHUNK])
        for pc, (text, _) in inst.items():
            before = inst.get(pc - 6, ('', 0))[0]
            if text == 'sub playSound' and before.startswith('push '):
                sid = int(before[5:])
                if sid >= 0:
                    ids.add(sid)
    return sorted(ids)


def render(vab, sid, seconds=4):
    """One tone at its sound-effect key; looped notes released after one second.

    Same pitch, ADPCM interpolation and ADSR helpers as sound.render. Mono is
    sufficient for matching: pan is not part of an effect's acoustic identity.
    """
    prog, tone = divmod(sid, 16)
    t = vab.tones[prog][tone]
    if not t['vag'] or not t['vol']:
        return np.zeros(1)
    pcm, loop, end = sound.adpcm_decode(vab.vags[t['vag'] - 1], with_loop=True)
    end = end or len(pcm)
    pitch = sound.note_rate(t, 60 + tone) / RATE
    env = sound.Envelope(t['adsr1'], t['adsr2'])
    gain = t['vol'] / 127 * vab.progs[prog]['mvol'] / 127 * vab.hdr['mvol'] / 127
    out = np.zeros(int(seconds * RATE))
    phase = 0.0
    for i in range(len(out)):
        if loop is not None and i == RATE:
            env.phase, env.wait = 'R', 0
        lev = env.tick(2) / 32767
        if phase >= end:
            if loop is None:
                break
            phase = loop + (phase - end) % max(1, end - loop)
        j = int(phase)
        nxt = j + 1 if j + 1 < end else (loop if loop is not None else j)
        out[i] = (pcm[j] + (pcm[nxt] - pcm[j]) * (phase - j)) / 32768 * lev * gain
        phase += pitch
        if env.phase == 'R' and env.level == 0:
            break
    return out


def features(pcm):
    """Duration, normalized 32-bin loudness shape and 32 log-frequency bands."""
    peak = np.max(np.abs(pcm))
    if peak < 1e-10:
        return None
    active = np.flatnonzero(np.abs(pcm) > peak * .01)
    pcm = pcm[:active[-1] + 1]
    energy = float(np.sqrt(np.mean(pcm ** 2)))
    shape = np.array([np.sqrt(np.mean(x ** 2)) if len(x) else 0
                      for x in np.array_split(pcm, 32)])
    shape /= max(np.linalg.norm(shape), 1e-12)
    padded = np.pad(pcm, (0, max(0, 1024 - len(pcm))))
    frames = np.lib.stride_tricks.sliding_window_view(padded, 1024)[::512]
    power = np.mean(np.abs(np.fft.rfft(frames * np.hanning(1024))) ** 2, axis=0)
    freq = np.fft.rfftfreq(1024, 1 / RATE)
    edges = np.geomspace(20, RATE / 2, 33)
    spectrum = np.array([power[(freq >= a) & (freq < b)].sum() for a, b in zip(edges, edges[1:])])
    spectrum = np.sqrt(spectrum / max(spectrum.sum(), 1e-12))
    return len(pcm) / RATE, shape, spectrum, energy


def distance(a, b):
    return (abs(np.log(a[0] / b[0])) * .35
            + np.linalg.norm(a[1] - b[1]) * 1.5 + np.linalg.norm(a[2] - b[2]) * 2)


def sound_events(trace):
    return [(step, args[0]) for step, cmd, args in trace.events if cmd == 3 and args]


def cues(cast, hit, match, loudness):
    """60 Hz ticks relative to the first drawn spawn, and loudest hit-script note.

    A silent source tone is omitted; a script without calls has an explicit empty
    list, suppressing the generic start/launch sounds just like the other ports.
    """
    first, _ = dcbefe.window(cast)
    events = sorted(sound_events(cast), key=lambda e: (e[0], -loudness.get(e[1], 0)))
    sounds = [[max(0, (step - first) * 2), match[sid]] for step, sid in events
              if sid in match]
    sounds = [list(cue) for cue in dict.fromkeys(map(tuple, sounds))]
    impacts = [(loudness[sid], -step, sid) for step, sid in sound_events(hit) if sid in match] if hit else []
    result = {'sounds': sounds}
    if impacts:
        result['hit_sound'] = match[max(impacts)[2]]
    return result


def derive(image, spec, archive, sb):
    source = bank(image)
    target = sound.VhbFile(sb).chunks[0].vab
    candidates = {sid: features(render(target, sid)) for sid in battle_ids(archive)}
    candidates = {sid: f for sid, f in candidates.items() if f is not None}
    disc = C.Disc(image)
    scripts = disc.scripts()
    traces = {key: (C.trace(scripts[e['dcb']['attack']], e['dcb']['attack']),
                    C.trace(scripts[e['dcb']['hit']], e['dcb']['hit']))
              for key, e in spec.items() if isinstance(e, dict) and 'dcb' in e}
    ids = {sid for pair in traces.values() for tr in pair for _, sid in sound_events(tr)}
    match, loudness = {}, {}
    for sid in sorted(ids):
        f = features(render(source, sid))
        if f is not None:
            match[sid] = min(candidates, key=lambda dst: (distance(f, candidates[dst]), dst))
            loudness[sid] = f[3]
    return {key: cues(*pair, match, loudness) for key, pair in traces.items()}


if __name__ == '__main__':
    with open('content/battle/own-effects.json') as f:
        spec = json.load(f)
    with open('extracted/ETCHI/EFEDAT.EFE', 'rb') as f:
        archive = f.read()
    print(json.dumps(derive(os.environ['DCB_IMAGE'], spec, archive, sound.resolve('SB')), indent=2))
