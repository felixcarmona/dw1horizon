"""Armadillomon's scurrying walk and trot, written from the paws up (quadruped.py).

Armadillomon (185) is a small armoured quadruped with short, sprawled legs and big clawed forepaws. Each paw
plants while the body passes over it, then curls and sweeps forward to the next landing. The pelvis and chest
roll over the supporting legs; the head steadies and the ears and tail follow the stride with a delay.

- Walk (slot 2): a lateral sequence (left hind, left fore, right hind, right fore), 12 ticks at 22 units per tick.
  Longer swings, rolling weight shifts and delayed head, ears and tail motion keep the short legs loose.
- Run (slot 4): diagonal pairs plant in turn over 10 ticks, with longer swings between the stances. The
  diagonal trot keeps its paws planted at 45 units per tick, matching Agumon and Gabumon's run.
- The pace pass derives the condition walk from this walk (18 ticks at 14.7 units per tick).
  The mesh and all non-field programs stay exact. The final result is baked into the plain model delta.
"""
from tools.models.field_animations import quadruped

PROFILE = dict(
    species=185, name='Armadillomon',
    source='17da46e0c9a69e2b757cfb212c2c27b459b2cf1674bc732a692c5a0def7e029b',
    parents=[-1, 0, 1, 2, 3, 3, 3, 2, 7, 8, 2, 10, 11, 1, 13, 14, 1, 16, 17, 1, 19, 20, 1],
    pelvis=1, chest=2, neck=None, head=3,
    # (upper, lower, paw, side (+1 right), front)
    legs={'RF': (7, 8, 9, 1, True), 'LF': (10, 11, 12, -1, True), 'RH': (13, 14, 15, 1, False), 'LH': (16, 17, 18, -1, False)},
    tail=(19, 20, 21), loose=((5, 1), (6, -1)),
    pole={True: [1, -0.3, 0.3], False: [0.6, -0.4, -0.6]},   # elbows and knees out, as the sprawled legs stand
    sole={True: [0, 22, -40], False: [0, 28, -10]},          # the point of the sole a paw rolls about (paw bone space)
    reach={'front': -50, 'hind': -17},                        # the sole pivot's place ahead of the shoulder / hip
    fold={True: 22, False: 30},                               # closest a swinging wrist / hock comes to its root
    clear=5,                                                # a standing sole is held this high (rounding)
    gaits={
        2: dict(name='walk', kind='walk', ticks=12, speed=22,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.4, 'RH': 0.4, 'RF': 0.4, 'LF': 0.4},
                lift={'front': 16, 'hind': 14}, curl={'front': 25, 'hind': 20}, peel={'front': 20, 'hind': 15},
                reach={'front': 0, 'hind': 0}, out={'front': 10, 'hind': 5}, snap=False, slip=0.05,
                height=4, tilt=0, chest_up=0, neck=0, nod=2, bob=2, pitch=1, flex=0.5, roll=3.5, yaw=4, head=0.5,
                tail=9, loose=6, steps=('LF', 'RF')),
        4: dict(name='run', kind='trot', ticks=10, speed=45,
                touchdown={'LF': 0.0, 'RH': 0.0, 'RF': 0.5, 'LH': 0.5},
                duty={'LH': 0.2, 'RH': 0.2, 'RF': 0.2, 'LF': 0.2},
                lift={'front': 20, 'hind': 16}, curl={'front': 30, 'hind': 25}, peel={'front': 25, 'hind': 20},
                reach={'front': 0, 'hind': 0}, out={'front': 15, 'hind': 5}, snap=True, slip=0.08,
                height=6, tilt=0, chest_up=0, neck=0, nod=2, bob=2.5, pitch=1.5, flex=1, roll=3, yaw=3, head=0.5,
                tail=8, loose=6, steps=('LF', 'RF')),
    },
)


def build(data, skeleton):
    return quadruped.build(data, skeleton, PROFILE)
