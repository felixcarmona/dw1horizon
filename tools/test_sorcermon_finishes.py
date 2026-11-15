"""Guard Sorcermon's retained battle finishes and unchanged field motion."""
from tools.retained_finish_testcase import RetainedFinishCase


class SorcermonFinishes(RetainedFinishCase):
    sid = 242
    slots = (44,)


from tools.battle_stride_testcase import BattleStrideCase


class SorcermonRetry(BattleStrideCase):
    sid = 242
    changed_slots = (35,)
