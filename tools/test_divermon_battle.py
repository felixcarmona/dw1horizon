"""Reviewed harpoon stride and unchanged field gait."""
from tools.battle_stride_testcase import BattleStrideCase


class DivermonBattleTest(BattleStrideCase):
    sid = 304
    changed_slots = (35,)
    author_module = "tools.models.divermon_battle"
