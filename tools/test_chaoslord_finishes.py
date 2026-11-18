"""Guard ChaosLord's retained battle finishes and unchanged field motion."""
from tools.retained_finish_testcase import RetainedFinishCase


class ChaosLordFinishes(RetainedFinishCase):
    sid = 289
    slots = (43,)


from tools.battle_retry_testcase import BattleRetryCase


class ChaoslordRetry(BattleRetryCase):
    sid = 289
