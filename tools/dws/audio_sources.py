#!/usr/bin/env python3
"""The house theme's MIDI and synthesized instruments (docs/mods/sound.md § 8.2).

Writes OUTDIR/canon.mid: variations on the ground bass of Pachelbel's Canon in D (public
domain), a format-1 MIDI of five tracks with explicit note-offs, written for the
instruments of the File City font (0x1C): lead on program 6, arpeggios on 3, bass on 2,
pad on 0, percussion on 5. CYCLES rounds of the eight-chord ground (4 bars each, 92 bpm);
the default (28 rounds, about 5 minutes) gives a SEQ of 0x7280 bytes, more than the original SEQ_BUFFER (0x5800)
and less than the current sequence buffer (0x8000).

  tools/dws/audio_sources.py build/house-theme-source [CYCLES]
  tools/sound.py add-font build/house-theme-source/canon.mid --instruments 0x1c -o build/audio-bank/FAALL.VHB --loop
  tools/sound.py set-bgm 218 0x22 -o build/audio-bank/MAPHEAD.SCN       # Jijimon's house plays font 34

It also writes two large instruments for the SPU allocation proof (§ 8.3), 44.1 kHz:
OUTDIR/pad.wav (a looped detuned-saw string pad, root A3, 2.6 s, about 75 KB of ADPCM) and
OUTDIR/bell.wav (a one-shot FM bell, root A4, 1.5 s, about 43 KB): with them a font's body
grows past the original 0xE800-byte music slot.
"""
import math, os, struct, sys

Q = 480                                   # ticks per quarter
BAR = 4 * Q
# the ground: D A Bm F#m G D G A, two beats each (two chords per bar)
CHORDS = [(50, (0, 4, 7)), (45, (0, 4, 7)), (47, (0, 3, 7)), (42, (0, 3, 7)),
          (43, (0, 4, 7)), (50, (0, 4, 7)), (43, (0, 4, 7)), (45, (0, 4, 7))]
SCALE = [2, 4, 6, 7, 9, 11, 13]           # D major (pitch classes from C)


def vlq(v):
    b = [v & 0x7F]; v >>= 7
    while v:
        b.append(0x80 | (v & 0x7F)); v >>= 7
    return bytes(reversed(b))


def track(evs):
    evs = sorted(evs, key=lambda e: (e[0], e[1]))     # by tick; at the same tick, note-offs (0) first
    d = bytearray(); now = 0
    for t, _, b in evs:
        d += vlq(t - now) + b; now = t
    d += b'\x00\xff\x2f\x00'
    return b'MTrk' + struct.pack('>I', len(d)) + bytes(d)


def note(evs, ch, t, k, dur, vel, gap=30):
    evs.append((t, 1, bytes([0x90 | ch, k, vel])))
    evs.append((t + max(10, dur - gap), 0, bytes([0x90 | ch, k, 0])))


def chord_tones(i, lo, hi):
    root, iv = CHORDS[i % 8]
    pcs = {(root + x) % 12 for x in iv}
    return [k for k in range(lo, hi + 1) if k % 12 in pcs]


def scale_step(k, n):
    """k moved n steps along the D major scale."""
    pcs = sorted(p % 12 for p in SCALE)
    idx = [x for x in range(k - 14, k + 15) if x % 12 in pcs]
    i = min(range(len(idx)), key=lambda j: abs(idx[j] - k))
    return idx[max(0, min(len(idx) - 1, i + n))]


def main(out, cycles):
    os.makedirs(out, exist_ok=True)
    meta = [(0, 0, b'\xff\x51\x03' + int(60e6 / 92).to_bytes(3, 'big')), (0, 0, b'\xff\x03\x0cCanon (long)')]
    lead = [(0, 0, b'\xc1\x06'), (0, 0, b'\xb1\x07\x6c'), (0, 0, b'\xb1\x0a\x40')]
    arp = [(0, 0, b'\xc2\x03'), (0, 0, b'\xb2\x07\x50'), (0, 0, b'\xb2\x0a\x30')]
    bass = [(0, 0, b'\xc3\x02'), (0, 0, b'\xb3\x07\x78')]
    pad = [(0, 0, b'\xc4\x00'), (0, 0, b'\xb4\x07\x40'), (0, 0, b'\xb4\x0a\x50')]
    drums = [(0, 0, b'\xc5\x05'), (0, 0, b'\xb5\x07\x58')]
    canon = [78, 76, 74, 73, 71, 69, 71, 73]          # the famous upper line, half notes
    t = 0; prev = 78
    for cyc in range(cycles):
        var = cyc % 6
        for i in range(8):                            # one chord = two beats
            c0 = t + i * 2 * Q
            root = CHORDS[i][0]
            # bass: the ground in quarters (root, fifth / octave)
            note(bass, 3, c0, root - 12, Q, 104)
            note(bass, 3, c0 + Q, root - 12 + (7 if cyc % 2 else 12), Q, 92)
            # pad: the chord once per two beats, from the second round on
            if cyc >= 1:
                for k in chord_tones(i, 62, 74)[:3]:
                    note(pad, 4, c0, k, 2 * Q, 52, gap=10)
            # arpeggio in sixteenths, from the third round on
            if cyc >= 2:
                tones = chord_tones(i, 62, 86)
                pat = [0, 1, 2, 3, 2, 1, 2, 3] if cyc % 2 else [0, 2, 1, 3, 0, 2, 1, 3]
                for s in range(8):
                    note(arp, 2, c0 + s * Q // 4, tones[pat[s] % len(tones)], Q // 4, 70 + (12 if s % 4 == 0 else 0), gap=12)
            # lead: a different variation each round
            if var == 0:
                note(lead, 1, c0, canon[i], 2 * Q, 100); prev = canon[i]
            elif var == 1:
                for b in range(2):
                    k = scale_step(canon[i], b); note(lead, 1, c0 + b * Q, k, Q, 100); prev = k
            elif var == 2:
                for e in range(4):
                    k = scale_step(canon[i], [0, -1, -2, 1][e]); note(lead, 1, c0 + e * Q // 2, k, Q // 2, 96); prev = k
            elif var == 3:
                ct = chord_tones(i, 66, 86)
                for e in range(4):
                    k = ct[(e + i) % len(ct)]; note(lead, 1, c0 + e * Q // 2, k, Q // 2, 96); prev = k
            elif var == 4:
                for s in range(8):
                    k = scale_step(canon[i] + 12 if canon[i] < 74 else canon[i], [0, 1, 0, -1, -2, -1, -2, -3][s])
                    note(lead, 1, c0 + s * Q // 4, k, Q // 4, 90, gap=10); prev = k
            else:
                note(lead, 1, c0, canon[(i + 4) % 8] + 12 if canon[(i + 4) % 8] < 72 else canon[(i + 4) % 8], Q * 3 // 2, 100)
                note(lead, 1, c0 + Q * 3 // 2, scale_step(canon[(i + 5) % 8], 1), Q // 2, 90)
            # percussion: kick (60) on beats, snare-ish (64) on the off beats, from round 2
            if cyc >= 1:
                note(drums, 5, c0, 60, Q // 2, 100)
                note(drums, 5, c0 + Q, 64 if cyc >= 2 else 60, Q // 2, 90)
        t += 8 * 2 * Q
    # final chord
    note(bass, 3, t, 38, 4 * Q, 110); note(lead, 1, t, 74, 4 * Q, 100)
    for k in (62, 66, 69):
        note(pad, 4, t, k, 4 * Q, 60, gap=10)
    tracks = [meta, lead, arp, bass, pad, drums]
    data = b'MThd' + struct.pack('>IHHH', 6, 1, len(tracks), Q) + b''.join(track(x) for x in tracks)
    open(os.path.join(out, 'canon.mid'), 'wb').write(data)
    secs = (t + 4 * Q) / Q * 60 / 92
    print(f'{out}/canon.mid: {cycles} rounds, {t // BAR + 1} bars, {secs:.0f} s, {len(data)} bytes of MIDI')


def write_wav(path, pcm, rate, root, loop=None):
    d = struct.pack(f'<{len(pcm)}h', *pcm)
    fmt = struct.pack('<HHIIHH', 1, 1, rate, rate * 2, 2, 16)
    smpl = struct.pack('<9I', 0, 0, int(1e9 / rate), root, 0, 0, 0, 1 if loop else 0, 0)
    if loop:
        smpl += struct.pack('<6I', 0, 0, loop[0], loop[1] - 1, 0, 0)
    body = (b'fmt ' + struct.pack('<I', 16) + fmt + b'smpl' + struct.pack('<I', len(smpl)) + smpl
            + b'data' + struct.pack('<I', len(d)) + d)
    open(path, 'wb').write(b'RIFF' + struct.pack('<I', 4 + len(body)) + b'WAVE' + body)


def instruments(out):
    rate = 44100
    f0 = 220.0; per = rate / f0                      # A3
    n = int(round(per * round(2.6 * f0)))            # whole periods: the loop closes cleanly
    lp = (int(round(per * round(1.1 * f0))), n)
    pcm = []
    for i in range(n):
        t = i / rate; v = 0.0
        for k, det in enumerate((1.0, 1.0 + 1 / 220, 1.0 - 1 / 220)):   # three saws, beating once a second
            ph = (f0 * det * t) % 1.0
            v += sum(math.sin(2 * math.pi * h * ph * 1.0) / h for h in range(1, 9)) * (0.33 if k == 0 else 0.3)
        env = min(1.0, t / 0.25)
        pcm.append(int(max(-1, min(1, v * 0.32 * env)) * 30000))
    write_wav(os.path.join(out, 'pad.wav'), pcm, rate, 57, lp)
    f0 = 440.0; n = int(1.5 * rate); pcm = []
    for i in range(n):
        t = i / rate
        v = math.sin(2 * math.pi * f0 * t + 2.2 * math.exp(-3 * t) * math.sin(2 * math.pi * f0 * 3.5 * t))
        pcm.append(int(v * math.exp(-2.4 * t) * min(1, t / 0.003) * 28000))
    write_wav(os.path.join(out, 'bell.wav'), pcm, rate, 69)
    print(f'{out}/pad.wav, {out}/bell.wav')


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 28)
    instruments(sys.argv[1])
