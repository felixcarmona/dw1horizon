"""Sorcermon (242) on native Angemon's rig and programs: the same body, cape and hair as Wizardmon.

Sorcermon is Wizardmon's body in other colours with a crystal staff: the same twenty bones, the same pieces and the
same rest pose. native_binding.py (recipe 242) fits it onto Angemon's skeleton the way recipe 241 fits Wizardmon, and
the cape, the hair tail and the arms follow the same rules (wizardmon_native.py): its wing-bone followers and the
upper arms held out in the field clips are used here unchanged. The one difference is that the followers' trailing
speed wraps around each endless loop (`closed`), so a loop ends on the pose it began from and the cape does not creep
a few degrees further with every pass.
"""
from tools.models.field_animations import wizardmon_native
from tools.models.field_animations.wizardmon_native import ARMS_OUT, FOLLOWERS  # noqa: F401


def build(data, skeleton):
    return wizardmon_native.build(data, skeleton, closed=True)
