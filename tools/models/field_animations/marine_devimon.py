"""MarineDevimon's supported stride and breathing sea-demon idle.

A SkullGreymon performance bent the whole torso forward for locomotion and
swung the long claws into the ground. The native limb lengths now support
an upright stride. Claws, shoulder tendrils, fins and head trail the body's
weight shifts on separate phases, with feet planted throughout the idles.
"""
from tools.models.field_animations import supported

PROFILE = dict(
    species=279, source='3ffa4e3dfde029dce5d133659eb10964db32717fc016250fc099040a5ea4db55',
    parents=[-1, 0, 1, 2, 3, 4, 2, 6, 7, 2, 9, 10, 1, 12, 1, 1, 1, 1, 1, 18, 19, 1, 21, 22, 1, 24, 25, 1, 27, 28, 1, 30],
    body=1, rest={3: [15, 0, 0], 24: [-6, 0, 0], 27: [-6, 0, 0], 18: [-5, 0, 0], 21: [-5, 0, 0]},
    legs=[(6, 7, 8, 0), (9, 10, 11, .5)],
    secondary=[(2, 1.5, .4), (3, 2, .8), (4, 3, 1.1), (5, 4, 1.4),
               (12, 1, .6), (13, 1.5, 1), (14, 1.5, .6), (15, -1.5, .8),
               (16, 1.5, .6), (17, -1.5, .8),
               (18, 2, .6), (19, 3, 1), (20, 4, 1.4),
               (21, -2, .6), (22, -3, 1), (23, -4, 1.4),
               (24, 2.5, .5), (25, 3.5, .9), (26, 4.5, 1.3),
               (27, -2.5, .5), (28, -3.5, .9), (29, -4.5, 1.3), (30, 1.2, .6), (31, 1.2, 1)],
    step=16, clear=4,
    slots={
        **{slot: dict(ticks=24, speed=0, bob=1.5, pitch=.8, yaw=1.8, roll=1,
                      duty=1, lift=0) for slot in (0, 1, 33)},
        2: dict(ticks=16, speed=18, bob=3, pitch=2, yaw=3, roll=2.5,
                duty=.6, slip=.2, lift=24, curl=16, roll_foot=7),
        3: dict(ticks=24, speed=12, bob=2, pitch=1.5, yaw=2.5, roll=2,
                duty=.6, slip=.2, lift=18, curl=12, roll_foot=6),
        4: dict(ticks=12, speed=38, bob=4, pitch=3, yaw=4, roll=3,
                duty=.35, slip=.2, lift=35, curl=22, roll_foot=10),
    },
)

# Needs keep a readable face and planted support, with a slight tired lean.
for _slot in (1, 14, 15, 16, 17, 18, 19):
    PROFILE['slots'][_slot] = dict(PROFILE['slots'][1], pitch_bias=2)

# Field happiness gestures are finite; battle idle (33) is a separate loop.
PROFILE['slots'][5] = dict(PROFILE['slots'][0], ticks=28, loop=False, bob=2,
                           pitch=2, yaw=4, roll=2, secondary_scale=1.2)
PROFILE['slots'][7] = dict(PROFILE['slots'][0], ticks=28, loop=False, bob=1,
                           pitch=1, pitch_bias=3, yaw=2, roll=1, secondary_scale=.6)


def build(data, skeleton):
    return supported.build(data, skeleton, PROFILE)
