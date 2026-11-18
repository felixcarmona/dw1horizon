"""How big an own finisher effect reads in the game, measured on the emulator's recording of the finisher
(tools/dev/playtest/finisher_targets.py writes finisher.mp4), with a floor so a small effect cannot ship.

The measure, on the recording at 30 fps and 320x240, below the 24 rows of the HUD:
- effect pixels: those whose colour differs from the pixel's median over the whole recording by at least DIFF
  (summed over R, G and B; the battle camera is fixed, so the median is the field), dim and coloured effects
  included; a cross erosion then drops the one- and two-pixel lines of the HP bars, the damage numbers and the
  text;
- area: the share of the picture they cover, smoothed over three frames; `area` is its peak;
- height: the rows they span at that peak frame, as a share of the picture's height;
- seconds: how long the area stays above a fifth of its peak.

The floor and the ceiling come from the 48 vanilla finishers (species 5-65) measured this way on 2026-11-15:
area smallest 0.011, lower quartile 0.034, median 0.051, top 0.442. An own effect under FLOOR would read
smaller than every vanilla finisher and fails; over CEILING it would be bigger than any of vanilla's and fails
too. (Vanilla's own small finishers, a punch or a short projectile, are where the lower quartile comes from:
scaling such a technique up does not make it read bigger, it only draws a bigger punch.)

content/battle/effect-presence.json keeps one measurement per own-effects.json entry, with the SHA-1 of the
entry it was measured on (its sounds and pins left out): an entry changed since its measurement is stale and fails until it
is measured again. A measurement may carry "waived" (why it may ship outside the bounds for now); measuring the
entry again drops it.

    python -m tools.efepresence measure VIDEO...            print the measures
    python -m tools.efepresence record KEY VIDEO            store KEY's measure (an own-effects.json key)
    python -m tools.efepresence check                       floor, ceiling and freshness of every entry
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, 'content', 'battle', 'own-effects.json')
TABLE = os.path.join(ROOT, 'content', 'battle', 'effect-presence.json')
W, H, FPS, HUD = 320, 240, 30, 24
DIFF = 120                          # summed |R|+|G|+|B| difference from the pixel's median that makes an effect pixel
FLOOR = 0.011                       # vanilla's smallest finisher
CEILING = 0.45                      # vanilla's biggest finisher, 0.442


def frames(path):
    import numpy as np
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={FPS},scale={W}:{H}', '-f', 'rawvideo',
                        '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, H, W, 3).astype(np.int16)


def measure(path):
    """{area, height, seconds} of a finisher recording (see the module's notes)."""
    import numpy as np
    f = frames(path)
    raw = np.abs(f - np.median(f, axis=0)).sum(-1) >= DIFF
    raw[:, :HUD] = False
    eff = np.zeros_like(raw)
    eff[:, 1:-1, 1:-1] = (raw[:, 1:-1, 1:-1] & raw[:, :-2, 1:-1] & raw[:, 2:, 1:-1]
                          & raw[:, 1:-1, :-2] & raw[:, 1:-1, 2:])
    area = np.convolve(eff.reshape(len(f), -1).sum(1) / ((H - HUD) * W), np.ones(3) / 3, 'same')
    k = int(area.argmax())
    rows = np.where(eff[k].sum(1) >= 2)[0]
    height = (rows.max() - rows.min()) / (H - HUD) if len(rows) else 0.0
    seconds = float((area > max(0.002, 0.2 * area[k])).sum()) / FPS
    return dict(area=round(float(area[k]), 4), height=round(float(height), 3), seconds=round(seconds, 2))


def entry_hash(e):
    """SHA-1 of an own-effects.json entry without its sounds (they do not change the picture) and its pins (they
    follow from the rest)."""
    e = {k: v for k, v in json.loads(json.dumps(e)).items() if k not in ('sounds', 'hit_sound')}
    if isinstance(e.get('compose'), dict):
        e['compose'].pop('sounds', None)
    for kind in ('dw3', 'dcb'):
        if isinstance(e.get(kind), dict):
            e[kind].pop('pin', None)
            e[kind].pop('pins', None)
    return hashlib.sha1(json.dumps(e, sort_keys=True).encode()).hexdigest()


def load(path):
    with open(path) as f:
        return json.load(f)


def check(spec, table):
    """The reasons the table fails for the spec (empty when every entry passes)."""
    fails = []
    for key, e in spec.items():
        if key == 'note':
            continue
        m = table.get(key)
        if m is None:
            fails.append(f'{key} {e["name"]}: never measured')
        elif m['entry'] != entry_hash(e):
            fails.append(f'{key} {e["name"]}: changed since it was measured')
        elif not FLOOR <= m['area'] <= CEILING and not m.get('waived'):
            fails.append(f'{key} {e["name"]}: area {m["area"]} outside {FLOOR}-{CEILING}')
    return fails


def save(table):
    note = table.pop('note', None)
    out = {'note': note} if note else {}
    out.update(sorted(table.items(), key=lambda kv: int(kv[0])))
    with open(TABLE, 'w') as f:
        f.write('{\n' + ',\n'.join(f'  {json.dumps(k)}: {json.dumps(v)}' for k, v in out.items()) + '\n}\n')


def main(argv):
    if argv[:1] == ['measure']:
        for p in argv[1:]:
            print(json.dumps(dict(video=p, **measure(p))), flush=True)
    elif argv[:1] == ['record'] and len(argv) == 3:
        spec, table = load(SPEC), load(TABLE) if os.path.exists(TABLE) else {}
        table[argv[1]] = dict(measure(argv[2]), entry=entry_hash(spec[argv[1]]))
        save(table)
        print(argv[1], table[argv[1]])
    elif argv[:1] == ['check']:
        fails = check(load(SPEC), load(TABLE))
        print('\n'.join(fails) or 'every own effect within the presence floor and ceiling')
        raise SystemExit(1 if fails else 0)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
