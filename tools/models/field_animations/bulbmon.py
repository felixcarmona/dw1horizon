"""Bulbmon's planted machinery idle and staggered radial-foot walk.

The imported Piximon routing played a step in idle and spinning happy/unhappy field gestures. Its four supports now carry the body's weight while the long
arms and antenna trail its roll. Idle variants scan without lifting feet.
"""
from tools.models.field_animations import supported

PROFILE = dict(
    species=313, source='15ff90ea4768e59c44208b985e3ad95049e7e55ce4de8810c1371705863451c4',
    parents=[-1, 0, 1, 1, 3, 4, 5, 1, 7, 8, 1, 10, 11, 1, 13, 14, 1, 16, 17, 18, 1, 20, 21],
    body=1, rest={3: [0, 0, -14], 16: [0, 0, 14]}, legs=[(7, 8, 9, 0), (10, 11, 12, .5), (13, 14, 15, .75), (20, 21, 22, .25)],
    secondary=[(2, 1.8, .7), (3, 1.5, .3), (4, 2, .7), (5, 1.5, 1.1), (6, 1, 1.5),
               (16, -1.5, .3), (17, -2, .7), (18, -1.5, 1.1), (19, -1, 1.5)],
    step=21, clear=4, foot_centres={9: (0, 25), 12: (0, -25)},
    slots={
        **{slot: dict(ticks=24, speed=0, bob=.8, pitch=.5, yaw=1.5, roll=.6,
                      duty=1, lift=0) for slot in (0, 1, 33)},
        2: dict(ticks=12, speed=18, bob=1.5, pitch=1, yaw=2, roll=1.5, drop=10,
                duty=.5, slip=.3, lift=20, curl=15, roll_foot=6),
        3: dict(ticks=18, speed=12, bob=1, pitch=.8, yaw=1.5, roll=1, drop=10,
                duty=.5, slip=.3, lift=16, curl=12, roll_foot=5),
        4: dict(ticks=10, speed=36, bob=2, pitch=1.5, yaw=2.5, roll=2, drop=12,
                duty=.3, slip=.3, lift=25, curl=20, roll_foot=8),
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
