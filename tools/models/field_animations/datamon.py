"""Datamon's quiet scan and four-footed mechanical shuffle.

The short lower chains take small alternating diagonal steps. The carrier
rocks with the load, with delayed elbow and wrist motion instead of the
SkullGreymon donor's large arm gestures. Metal footsteps follow touchdowns.
"""
from tools.models.field_animations import supported

PROFILE = dict(
    species=294, source='c273be8010677258627ffcafb24ee50a85010cadcf12ff0306aa4a80992778a2',
    parents=[-1, 0, 1, 2, 3, 4, 1, 6, 7, 8, 1, 10, 11, 12, 1, 14, 15, 16, 1, 1, 19, 20, 21, 1, 1, 24, 25, 26],
    body=1, legs=[(2, 3, 5, 0), (6, 7, 9, .5), (10, 11, 13, .5), (14, 15, 17, 0)],
    rest={19: [0, 0, 8], 24: [0, 0, -8]},
    secondary=[(19, 6, .4), (20, 9, .7), (21, 6, 1), (22, 4, 1.4),
               (24, -6, .4), (25, -9, .7), (26, -6, 1), (27, -4, 1.4)],
    step=21, clear=3, target_error=8,
    slots={
        **{slot: dict(ticks=24, speed=0, bob=1, pitch=.6, yaw=1.5, roll=.7,
                      duty=1, lift=0) for slot in (0, 1, 33)},
        2: dict(ticks=10, speed=15, bob=2, pitch=1.5, yaw=3, roll=2.5, drop=8,
                duty=.45, slip=.4, lift=12, curl=14, roll_foot=4),
        3: dict(ticks=15, speed=10, bob=.7, pitch=.4, yaw=.7, roll=.7, drop=8,
                duty=.45, slip=.4, lift=6, curl=10, roll_foot=3),
        4: dict(ticks=8, speed=35, bob=2, pitch=2, yaw=3, roll=3, drop=12,
                duty=.3, slip=.4, lift=16, curl=20, roll_foot=5),
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
