"""Nefertimon retains the faint while its recovery opening prevents a clean join."""
from tools.retained_finish_testcase import RetainedFinishCase


class NefertimonFinishes(RetainedFinishCase):
    sid = 198
    slots = (43,)


from tools.battle_retry_testcase import BattleRetryCase


class NefertimonRetry(BattleRetryCase):
    sid = 198
