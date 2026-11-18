"""Kyubimon's native victory and retained faint and get-up regressions."""
from tools.native_finish_testcase import NativeFinishCase


class KyubimonFinishes(NativeFinishCase):
    sid = 409
    slots = (43, 44)


from tools.battle_retry_testcase import BattleRetryCase


class KyubimonRetry(BattleRetryCase):
    sid = 409
