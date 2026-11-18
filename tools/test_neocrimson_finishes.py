"""NeoCrimson's authored victory and unchanged recovery regressions."""
from tools.battle_finish_testcase import FinishCase
from tools.models.neocrimson_contacts import audit


class NeoCrimsonFinishes(FinishCase):
    sid = 402

    def test_floor_landing_and_support(self):
        report = audit(self.data, self.sk)
        self.assertTrue(report['passed'], report)


from tools.battle_retry_testcase import BattleRetryCase


class NeocrimsonRetry(BattleRetryCase):
    sid = 402
