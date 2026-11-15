"""Guard Cannondramon's retained battle finishes and unchanged field motion."""
from tools.retained_finish_testcase import RetainedFinishCase


class CannondramonFinishes(RetainedFinishCase):
    sid = 405
    slots = (42,)
