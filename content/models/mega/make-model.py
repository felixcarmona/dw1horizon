#!/usr/bin/env python3
"""The demo Mega's model: WarGreymon from Digimon Digital Card Battle (card model 173).

The card game draws WarGreymon with a DW1-style model (docs/mods/models.md § 10,
"Importing from Digimon Digital Card Battle"); tools/dcb2mmd.py reads it and
tools/mmdport.build_partner makes the partner set from `wargreymon-dcb.json`:

- mesh and texture as they are: 20 bones (+ the entity), 501 vertices, 621
  primitives, 14 palettes, the 256×128 image; native units (473 tall in its
  modelling pose, below MetalGreymon), nothing reduced;
- the everyday slots (walk, run, idle, eat, sleep, care, the evolution pose...)
  and nine technique slots retargeted from Greymon (GREY.MMD): the species uses
  Greymon's moves (plus Infinity Burn), so those slots keep the timing their
  effects were made for; the technique slots are retargeted onto the card game's
  crouched battle idle (CROUCHED_SLOTS below);
- the card game's own animations on the battle slots: battle idle, hit (front and
  back), victory, knocked down, and five technique slots (Fire Tower, Prominence
  Beam, Meltdown, Infinity Burn and the finisher, Mega Flame).

The finisher uses `wg_gaia`, made here: the card game's anim_01 (WarGreymon rises
with its arms spread and gathers the Gaia Force / Terra Force) with its height
cut to a quarter, so it charges in place instead of flying 450 units up.

Budget: 29.4 KB of TMD + the animations must fit PARTNER_MODEL_BUFFER (100 352
bytes): the retargeted slots are keyed at tol 14 (1.2°), the card clips at tol 8,
and the clip ranges are cut to fit (99 870 bytes; tol 13 made 100 486 bytes once the
shared converters changed, 2026-10-12).

Writes OUT_DIR/WarGreymon.MMD, .TIM (ALLTIM-style entry), .skeleton.json (the
"model.skeleton" of content/species/373-wargreymon.json) and the glTF of the clips. Runs under the card-game
project's virtual environment (numpy, unicorn): it re-runs itself with
$DCB_ROOT/.venv/bin/python, as tools/dcb2mmd.py does.

Usage (from the repository root):
  python3 content/models/mega/make-model.py [OUT_DIR]      default build/models
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DCB_ROOT = os.environ.get('DCB_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), 'digimoncardbattle'))
SPEC = os.path.join(HERE, 'wargreymon-dcb.json')
GAIA_FROM = 'anim_01'
GAIA_LIFT = 0.25            # fraction of the card game's rise kept in the finisher
BATTLE_IDLE = 0x21
# technique slots retargeted from Greymon. The card game's battle idle (0x21) is a
# crouch, Greymon's techniques start and end in its idle: retargeted onto WarGreymon's
# modelling pose (upright) they would jump from the crouch and back. These slots are
# retargeted a second time with the battle idle's first pose as the target's rest, so
# they start and end in the crouch (blending ticks instead costs ~4 KB of keys).
CROUCHED_SLOTS = ['0x2e', '0x30', '0x32', '0x33', '0x35', '0x36', '0x37', '0x38', '0x39']


def _venv():
    try:
        import numpy  # noqa: F401
        import unicorn  # noqa: F401
    except ImportError:
        py = os.path.join(DCB_ROOT, '.venv', 'bin', 'python')
        if os.path.exists(py) and not os.environ.get('MEGA_MAKE_REEXEC'):
            os.environ['MEGA_MAKE_REEXEC'] = '1'
            os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])
        raise SystemExit(f'make-model: needs numpy and unicorn (the venv of {DCB_ROOT})')


def gaia(model):
    """anim_01 with the model root's height (card bone 0 = DW1 bone 1) lowered: the
    rise above the first tick is scaled by GAIA_LIFT."""
    import mmdport
    a = model.anims[GAIA_FROM]
    y0 = a.frames[0][0][1][1]
    frames = []
    for f in a.frames:
        q, t, s = f[0]
        t = (t[0], y0 + (t[1] - y0) * GAIA_LIFT, t[2])
        frames.append([(q, t, s)] + list(f[1:]))
    return mmdport.Anim(frames, a.fps, False)


def battle_idle_pose(path, typ, nb):
    """First engine pose of the battle idle slot of a built MMD (bone 0 cleared)."""
    import mmd
    import retarget
    m = mmd.MMD.load(path, typ)
    smp, _, _ = retarget.play(m.anims.anims[m.anims.table[BATTLE_IDLE]], nb, BATTLE_IDLE, max_ticks=1)
    pose = [list(v) for v in smp[0]]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return pose


def build(model, spec, stem, out_dir):
    import mmd
    import mmdport
    quiet = dict(log=lambda *a: None)
    nb = len(model.bones) + 1
    # 1. the battle idle's pose (the card game's anim_00 through import-anim)
    probe = dict(spec, retarget=[], clips={'0x21': spec['clips']['0x21']})
    mmdport.build_partner(model, probe, stem + '.MMD', stem + '.TIM', out_dir, **quiet)
    idle = battle_idle_pose(stem + '.MMD', spec['type'], nb)
    # 2. the technique slots retargeted onto the crouch
    rest_pose = mmdport.rest_pose
    mmdport.rest_pose = lambda _model: [list(v) for v in idle]
    try:
        mmdport.build_partner(model, dict(spec, retarget=CROUCHED_SLOTS, clips={}),
                              stem + '-crouched.MMD', stem + '.TIM', out_dir)
    finally:
        mmdport.rest_pose = rest_pose
    crouched = mmd.MMD.load(stem + '-crouched.MMD', spec['type'])
    os.remove(stem + '-crouched.MMD')
    # 3. everything else, then the crouched slots replace the upright ones
    mmdport.build_partner(model, dict(spec, skip=spec.get('skip', []) + CROUCHED_SLOTS),
                          stem + '.MMD', stem + '.TIM', out_dir)
    m = mmd.MMD.load(stem + '.MMD', spec['type'])
    for s in CROUCHED_SLOTS:
        s = int(s, 0)
        m.anims.table += [None] * (s + 1 - len(m.anims.table))
        m.anims.table[s] = len(m.anims.anims)
        m.anims.anims.append(crouched.anims.anims[crouched.anims.table[s]])
    data = m.build()
    if len(data) > mmdport.PARTNER_MMD_MAX:
        raise SystemExit(f'{stem}.MMD: {len(data)} bytes do not fit PARTNER_MODEL_BUFFER '
                         f'({mmdport.PARTNER_MMD_MAX})')
    open(stem + '.MMD', 'wb').write(data)
    print(f'{stem}.MMD: {len(data)} bytes with the crouched techniques '
          f'({mmdport.PARTNER_MMD_MAX - len(data)} free)')


def main():
    _venv()
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    os.chdir(ROOT)
    import dcb2mmd
    import mmdport
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'models')
    spec = json.load(open(SPEC))
    model = dcb2mmd.load(spec['dcb'])
    model.anims['wg_gaia'] = gaia(model)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, spec['name'])
    build(model, spec, stem, out_dir)
    json.dump(dict(bones=[list(x) for x in mmdport.skeleton(model)]), open(stem + '.skeleton.json', 'w'))
    print(f'{stem}.MMD, .TIM, .skeleton.json')


if __name__ == '__main__':
    main()
