"""Gazimon's four-limb prowl and trot with head, ear and tail follow-through.

The paced DW2 clip carried the front claws with the body. Both arms now
fold, lift and reach as forelegs, in a four-beat walk and diagonal trot.
The compound hind chain keeps its hock articulation and native link lengths.

Battle slot 0x21 stays the twin of the field idle (rewritten here where it is stored): the source's own battle idle
loops with a seam of 0.063 heights and main's does not (tools/models/battle_qa.py). The other battle slots are the source's.
"""
from tools.models.field_animations import supported

PROFILE = dict(
    species=285, source='5db8be4f5a11f34ec2f2e0a9dd4647e82d47045a40c14932c8a62c6a25e678f3',
    parents=[-1, 0, 1, 2, 2, 2, 1, 6, 7, 1, 9, 10, 1, 12, 13, 14, 12, 16, 17, 18, 12, 20, 21, 22],
    body=1, rest={13: [18, 0, 0]}, legs=[(6, 7, 8, .25), (9, 10, 11, .75), (16, 18, 19, .5), (20, 22, 23, 0)],
    secondary=[(12, 1.5, .6), (2, 2.5, .45), (3, 1.5, .9), (4, 2, .8), (5, -2, 1), (13, 3, .7), (14, 4, 1), (15, 5, 1.3)],
    foot_centres={19: (0, -15), 23: (0, -15)},
    step=12, clear=4,
    slots={
        **{slot: dict(ticks=24, speed=0, bob=1.2, pitch=.7, yaw=1.5, roll=.8,
                      duty=1, lift=0) for slot in (0, 1, 33)},
        2: dict(ticks=12, speed=18, bob=3, pitch=3, yaw=4, roll=3, drop=8,
                duty=.5, slip=.3, lift=20, lifts={19: 12, 23: 12}, curl=20, roll_foot=6),
        3: dict(ticks=18, speed=12, bob=1.5, pitch=1.5, yaw=2, roll=1.5, drop=14,
                duty=.5, slip=.3, lift=15, curl=15, roll_foot=5),
        4: dict(ticks=10, speed=35, bob=4, pitch=4, yaw=4, roll=3, drop=10,
                duty=.35, slip=.3, lift=25, curl=28, roll_foot=9, lifts={19: 8, 23: 8}, phases={8: 0, 23: 0, 11: .5, 19: .5}),
    },
)

# Needs keep a readable face and planted support, with a slight tired lean.
for _slot in (1, 14, 15, 16, 17, 18, 19):
    PROFILE['slots'][_slot] = dict(PROFILE['slots'][1], pitch_bias=2)

# Finite happiness gestures wag and settle while keeping the claws planted.
PROFILE['slots'][5] = dict(PROFILE['slots'][0], ticks=28, loop=False, bob=2,
                           pitch=2, yaw=4, roll=2, secondary_scale=1.5)
PROFILE['slots'][7] = dict(PROFILE['slots'][0], ticks=28, loop=False, bob=1,
                           pitch=1, pitch_bias=3, yaw=2, roll=1, secondary_scale=.6)


def build(data, skeleton):
    return supported.build(data, skeleton, PROFILE)
