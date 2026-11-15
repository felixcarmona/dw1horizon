"""Guard Sorcermon's retained battle finishes and unchanged field motion."""
from tools.retained_finish_testcase import RetainedFinishCase


class SorcermonFinishes(RetainedFinishCase):
    sid = 242
    slots = (44,)


from tools.battle_retry_testcase import BattleRetryCase


class SorcermonRetry(BattleRetryCase):
    sid = 242
