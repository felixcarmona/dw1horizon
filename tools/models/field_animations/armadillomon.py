"""Armadillomon's scurrying walk and trot, written from the paws up (quadruped.py).

Armadillomon (185) is a small armoured quadruped: short sprawled legs (the forelegs about 80 units long under
shoulders 75 above the floor, the thighs reaching out sideways) and big clawed forepaws. Its imported run was an
8-tick cycle in which the body bounced while the legs flapped in place (foot lift 13, the feet travelling with the
body: slip 100-113 % of its travel); the walk had the same look. Legs this short cover the field speeds only with
a quick cadence, so both gaits are short cycles in which each paw stands still on the floor while the body passes
over it and then sweeps forward to its next landing:

- Walk (slot 2): a lateral sequence (left hind, left fore, right hind, right fore) a quarter cycle apart, 55 %
  stance, 10 ticks at 20 units per tick, a footstep at each forepaw's touchdown.
- Run (slot 4): a trot, diagonal pairs together with a short flight between them, 8 ticks at 35 units per tick,
  the body low and rolling with the pairs, a footstep at each forepaw's touchdown.
- The condition walk (slot 3) is the field pace pass's: this walk 1.5 times slower at 2/3 of its speed
  (content/models/imports/pace.json). The idle and every other program stay as imported.
"""
from tools.models.field_animations import quadruped

PROFILE = dict(
    species=185, name='Armadillomon',
    source='f94cdab3f149ae6b1ed7f31a7c4a146c308ea133472e76c93018d251e422adca',
    parents=[-1, 0, 1, 2, 3, 3, 3, 2, 7, 8, 2, 10, 11, 1, 13, 14, 1, 16, 17, 1, 19, 20, 1],
    pelvis=1, chest=2, neck=None, head=3,
    # (upper, lower, paw, side (+1 right), front)
    legs={'RF': (7, 8, 9, 1, True), 'LF': (10, 11, 12, -1, True), 'RH': (13, 14, 15, 1, False), 'LH': (16, 17, 18, -1, False)},
    tail=(19, 20, 21), loose=((5, 1), (6, -1)),
    pole={True: [1, -0.3, 0.3], False: [0.6, -0.4, -0.6]},   # elbows and knees out, as the sprawled legs stand
    sole={True: [0, 22, -40], False: [0, 28, -10]},          # the point of the sole a paw rolls about (paw bone space)
    reach={'front': -50, 'hind': -17},                        # the sole pivot's place ahead of the shoulder / hip
    fold={True: 22, False: 30},                               # closest a swinging wrist / hock comes to its root
    clear=3.5,                                                # a standing sole is held this high (rounding)
    gaits={
        2: dict(name='walk', kind='walk', ticks=9, speed=18,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.5, 'RH': 0.5, 'RF': 0.5, 'LF': 0.5},
                lift={'front': 16, 'hind': 14}, curl={'front': 25, 'hind': 20}, peel={'front': 20, 'hind': 15},
                reach={'front': 0, 'hind': 0}, out={'front': 10, 'hind': 5}, snap=False, slip=0.05,
                height=4, tilt=0, chest_up=0, neck=0, nod=1.5, bob=1.5, pitch=1, flex=0.5, roll=2.5, yaw=3, head=0.5,
                tail=6, loose=4, steps=('LF', 'RF')),
        4: dict(name='run', kind='trot', ticks=8, speed=35,
                touchdown={'LF': 0.0, 'RH': 0.0, 'RF': 0.5, 'LH': 0.5},
                duty={'LH': 0.32, 'RH': 0.32, 'RF': 0.32, 'LF': 0.32},
                lift={'front': 20, 'hind': 16}, curl={'front': 30, 'hind': 25}, peel={'front': 25, 'hind': 20},
                reach={'front': 0, 'hind': 0}, out={'front': 15, 'hind': 5}, snap=True, slip=0.08,
                height=6, tilt=0, chest_up=0, neck=0, nod=2, bob=2.5, pitch=1.5, flex=1, roll=3, yaw=3, head=0.5,
                tail=8, loose=6, steps=('LF', 'RF')),
    },
)


def build(data, skeleton):
    return quadruped.build(data, skeleton, PROFILE)
