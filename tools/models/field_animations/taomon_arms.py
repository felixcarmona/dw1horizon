"""Taomon's sleeves clear its legs in the idle, walk, tired walk and run (species 315, slots 0 and 33, 2, 3 and 4).

Reproducible: the chibi overlay runs this on its own output (the manifest row's `post_generator`), so player builds make
it again from the turns stored in content/models/imports/taomon-arms.json. `--search TURNS.json` finds those turns
(slow: about two minutes of mesh clash tests); `--source CHIBI_OUTPUT.MMD --out AFTER.MMD` applies them offline for a
look; tools/test_taomon_arms.py checks the result tick by tick.

What was wrong. The walk, the tired walk and the run hold both arms in the idle's hanging pose, whatever the body
does, while the torso leans 40 to 80 degrees forward and the legs swing. The sleeves (bones 20-22 right, 25-27 left) are
wide and hang at the same height as the thighs and shins, so the same-side leg passes through its sleeve at every step
(up to 30 units deep, hundreds of vertices over a cycle), and the front and back aprons and, in the tired walk, the tail
pass through the sleeves too. The idle's right sleeve brushes the leg for a dozen ticks of its slow sway.

What this does. Only the two sleeves' first bones' rotation (bones 20 and 25) is rewritten, tick by tick, as a turn about the world's
fore-aft axis (the sleeve swings outward, away from the leg) and, on the few ticks where that is not enough (the run's
raised knee passes the shoulder), about the world's side axis (the arm swings back). Each turn is the smallest that
leaves the sleeve's three pieces clear of the legs, the aprons and the tail (the body keeps whatever it already
touched), then the series is made smooth and periodic and checked again tick by tick. The arms therefore keep their
hang and move out and back as the legs pass, a loose counter-motion instead of a frozen pose. Nothing else is touched:
the other bones, the root, the sounds, the ticks and the loops are the chibi overlay's values.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import numpy as np  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.articulation import replace_channels  # noqa: E402
from tools.models.field_animations.meshclash import Clash  # noqa: E402
from tools.models.field_animations.war_greymon import rotation  # noqa: E402

SPECIES, NB = 315, 29
SOURCE = '50c899cad6939fa4d7c4dee234e1dbf133667c719ba8101df92d4822c6507e89'   # the chibi overlay's output before this
TURNS = ROOT / 'content/models/imports/taomon-arms.json'
SLOTS = (0, 2, 3, 4)                                     # slot 33 shares the idle's program
ARMS = {'R': dict(bone=20, shoulder=19, parts=(20, 21, 22), sign=1), 'L': dict(bone=25, shoulder=24, parts=(25, 26, 27), sign=-1)}
MUST_CLEAR = {'leg': (4, 5, 6, 12, 13, 14), 'apron': (7, 15, 16, 17, 18), 'tail': (8, 9, 10)}
THIGH_TOP = (3, 11)                                           # the thighs' tops: the leaning torso puts the shoulders inside them on some run ticks
KEEP = {'body': (1, 2, 23)}                              # a brush, never a push in
BODY_DEPTH = 4.0                                         # how deep a sleeve may press the body (it already rests on it)
REACH = 44                                               # the largest swing back tried, degrees
COMFORT = 22                                             # the largest outward turn kept (a sleeve held out wider looks wrong)
MARGIN = 1.0                                             # degrees kept over the smallest clear turn
BLUR = (1, 2, 3, 2, 1)


def blur(values):
    n = len(values)
    total = sum(BLUR)
    half = len(BLUR) // 2
    return [sum(w * values[(i + k - half) % n] for k, w in enumerate(BLUR)) / total for i in range(n)]


def smooth_over(need, sweeps=12):
    """The smoothest periodic series that stays at or over `need` (blur, then raise to `need`, repeated)."""
    x = list(need)
    for _ in range(sweeps):
        x = [max(a, b) for a, b in zip(blur(x), need)]
    return x


class Arms:
    def __init__(self, model, clash=True):
        self.model = model
        self.clash = Clash(model, mmd.exe().skeleton[SPECIES]) if clash else None

    def pairs(self, pose, arm, world=None):
        world = self.clash.world(pose) if world is None else world
        parts = ARMS[arm]['parts']
        out = {}
        for k, bones in {**MUST_CLEAR, **KEEP, 'root': THIGH_TOP}.items():   # how many pairs and how deep
            out[k] = self.clash.clash(pose, parts, bones, world=world)
        return out

    def turned(self, pose, arm, outward, back):
        """`pose` with the sleeve's first bone turned `outward` about the world's fore-aft axis and `back` about its side
        axis (the shoulder piece stays where it is)."""
        bone = ARMS[arm]['bone']
        parent = np.array(mmd.bone_matrices(self.model, pose)[ARMS[arm]['shoulder']], float)[:3, :3]
        parent = parent / np.cbrt(abs(np.linalg.det(parent)))
        sign = ARMS[arm]['sign']
        turn = np.array(rotation([back, 0, -sign * outward]))
        out = copy.deepcopy(pose)
        local = np.array(mmd.rot_matrix(*pose[bone][3:6]))
        out[bone][3:6] = [round(v) for v in mmd.matrix_euler(parent.T @ turn @ parent @ local, pose[bone][3:6])]
        return out


def plan(arms, frames, arm, step=1):
    """Per tick (outward, back) degrees: the smallest clear turn, made smooth and periodic, then checked."""
    n = len(frames) - 1
    base = [arms.pairs(frames[t], arm) for t in range(n)]

    relaxed = set()                                      # ticks where the thigh's top cannot be cleared by any turn: the
    #                                                      sleeve then only has to stay out of the legs no deeper than it was

    def clear(t, outward, back):
        got = arms.pairs(arms.turned(frames[t], arm, outward, back), arm)
        for k, v in got.items():
            if k in MUST_CLEAR:
                ok = v[0] == 0 or (k == 'leg' and t in relaxed and v[1] <= base[t][k][1] + .5)
            elif k == 'root':
                ok = v[0] == 0 or (t in relaxed and v[1] <= base[t][k][1] + .5)
            else:
                ok = v[1] <= max(base[t][k][1], BODY_DEPTH)
            if not ok:
                return False
        return True

    def need_for(t):
        found = next((v for v in range(step, COMFORT + 1, step) if clear(t, v, 0)), None)
        if found is not None:
            return float(found), 0.0
        best = None                                      # outward is not enough: swing back too, the least of both
        for back in range(2, REACH + 1, 2):
            for outward in range(0, COMFORT + 1, 2):
                if clear(t, outward, back) and (best is None or outward + back < best[0]):
                    best = (outward + back, outward, back)
            if best:
                break
        return (float(best[1]), float(best[2])) if best else None

    need_out, need_back = [0.0] * n, [0.0] * n
    for t in range(n):
        if clear(t, 0, 0):
            continue
        got = need_for(t)
        if got is None:
            relaxed.add(t)
            got = need_for(t)
        if got is None:
            raise ValueError(f'Taomon arms: the {arm} arm cannot be cleared on tick {t}')
        need_out[t], need_back[t] = got
    margin_out = [v + MARGIN if v else 0.0 for v in need_out]
    margin_back = [v + MARGIN if v else 0.0 for v in need_back]
    out, back = smooth_over(margin_out), smooth_over(margin_back)
    for _ in range(60):                                  # where the smooth series fell short, take the nearest clear turn
        failing = [t for t in range(n) if not clear(t, out[t], back[t])]
        if not failing:
            break
        for t in failing:
            cands = sorted((abs(o - out[t]) + abs(b - back[t]), o, b) for o in range(0, COMFORT + 1)
                           for b in range(0, REACH + 1, 2) if abs(o - out[t]) <= 8 and abs(b - back[t]) <= 8)
            near = next((c for c in cands if clear(t, c[1], c[2])), None)
            if near is None:
                raise ValueError(f'Taomon arms: the {arm} arm has no clear turn near the smooth one on tick {t}')
            margin_out[t] = max(margin_out[t], near[1] + MARGIN if near[1] else 0.0)
            margin_back[t] = max(margin_back[t], near[2] + MARGIN if near[2] else 0.0)
        out, back = smooth_over(margin_out), smooth_over(margin_back)
    else:
        raise ValueError(f'Taomon arms: the {arm} arm is not clear after smoothing on ticks {failing}')
    return list(zip(out, back))


def search(arms, frames):
    """{arm: {'outward': [...], 'back': [...]}} for the clip's ticks (the closing sample is not listed)."""
    notes = {}
    for arm in ARMS:
        series = plan(arms, frames, arm)
        notes[arm] = dict(outward=[round(v, 1) for v, _ in series], back=[round(b, 1) for _, b in series])
    return notes


def new_frames(arms, frames, turns):
    """The clip's frames with both sleeves turned as `turns` say; the closing sample repeats the first."""
    out = copy.deepcopy(frames)
    n = len(frames) - 1
    for arm, series in turns.items():
        assert len(series['outward']) == len(series['back']) == n
        bone = ARMS[arm]['bone']
        for t in range(n):
            out[t][bone][3:6] = arms.turned(frames[t], arm, series['outward'][t], series['back'][t])[bone][3:6]
        out[n][bone][3:6] = out[0][bone][3:6]
    return out


def parse(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = SPECIES
    return model


def build(data, skeleton, turns=None):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(skeleton) != NB:
        raise ValueError('Taomon arms require the chibi overlay output they were reviewed on')
    model = parse(data, skeleton)
    arms = Arms(model, clash=False)
    result = copy.deepcopy(model)
    stored = json.loads(TURNS.read_text()) if turns is None else turns
    for slot in SLOTS:
        index = model.anims.table[slot]
        assert sum(1 for v in model.anims.table[:33] if v == index) == 1
        frames, loop, _ = animsheet.slot_frames(model, NB, slot)
        frames = [[[int(round(v)) for v in bone] for bone in pose] for pose in frames]
        samples = new_frames(arms, frames, stored[str(slot)])
        channels = {(ARMS[a]['bone'], c) for a in ARMS for c in (3, 4, 5)}
        result.anims.anims[index] = replace_channels(model.anims.anims[index], samples, loop, NB, channels, tolerance=0)
    output = result.build()
    effective = parse(output, skeleton)
    assert effective.tmd.build() == model.tmd.build()
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed_programs(model, effective),
                        storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path)
    p.add_argument('--search', type=Path, help='write the turns found for the source (slow)')
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    sk = json.loads(next((ROOT / 'content/species').glob('315-*.json')).read_text())['model']['skeleton']
    data = a.source.read_bytes()
    if a.search:
        if hashlib.sha256(data).hexdigest() != SOURCE:
            raise SystemExit('the source is not the chibi overlay output this was reviewed on')
        model = parse(data, sk)
        arms = Arms(model)
        found = {}
        for slot in SLOTS:
            frames = animsheet.slot_frames(model, NB, slot)[0]
            found[str(slot)] = search(arms, [[[int(round(v)) for v in bone] for bone in pose] for pose in frames])
        a.search.write_text(json.dumps(found, separators=(',', ':')) + '\n')
        return
    data, proof = build(data, sk)
    a.out.write_bytes(data)
    if a.report:
        a.report.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof['changed_slots']), proof['storage']['resident_bytes'], len(data))


if __name__ == '__main__':
    main()
