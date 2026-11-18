"""Keep GrapLeomon's decoded clips intact when replacement studies fail."""
from tools.battle_retry_testcase import BattleRetryCase


class GrapLeomonTechniques(BattleRetryCase):
    sid = 306
    changed_slots = ()
    review_env = 'BATTLE_TECHNIQUE_REVIEW'
