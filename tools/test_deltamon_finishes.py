"""Guard Deltamon's retained battle finishes and unchanged field motion."""
from tools.retained_finish_testcase import RetainedFinishCase


class DeltamonFinishes(RetainedFinishCase):
    sid = 292
    slots = (42, 43, 44)
