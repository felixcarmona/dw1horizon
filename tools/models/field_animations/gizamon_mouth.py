"""Gizamon's mouth: the jaw (bone 3, hinged under the back of the head) drops a little and the snout (bone 2) lifts,
showing the painted inside of the mouth, then both close again.

Idle: the native idle bob is played several times in a row and the mouth opens once, slowly, in the middle, like a
breath; it is shut on the first and last tick, so the loop and the hand-over to every other clip see a closed mouth.
Walk, condition walk and run: the mouth opens a little between footfalls and is shut on each footfall (the clips'
step sounds fall at phase 0 and one half), so it pants in step with the gait.

Both bones turn about their own x axis only (positive x drops the jaw tip, negative x lifts the snout), and the jaw
is turned back by the snout's lift first, so the lower jaw itself drops by `jaw` units at the widest. The jaw is its
own mesh hinged inside the head: no vertex is shared, nothing tears.
"""
import math

HEAD, JAW = 2, 3


def _ease(u):
    u = min(1.0, max(0.0, u))
    return math.sin(math.pi * u) ** 2


def open_pose(pose, amount, cfg):
    """Open the mouth of one pose by `amount` (0 shut, 1 the widest)."""
    lift = round(cfg['head'] * amount)
    pose[HEAD][3] -= lift
    pose[JAW][3] += lift + round(cfg['jaw'] * amount)


def gait(pose, phase, cfg):
    """Walk, condition walk and run: shut on each footfall, open between them."""
    open_pose(pose, _ease((2 * phase) % 1), cfg)


def idle(frames, cfg):
    """The idle clip (its last tick equal to its first) played cfg['repeats'] times, with one slow opening over
    ticks cfg['open'] of the longer loop."""
    body = [[list(bone) for bone in pose] for pose in frames[:-1]]
    out = [[list(bone) for bone in pose] for _ in range(cfg['repeats']) for pose in body]
    out.append([list(bone) for bone in frames[-1]])
    start, end = cfg['open']
    for tick, pose in enumerate(out):
        open_pose(pose, _ease((tick - start) / (end - start)), cfg)
    return out
