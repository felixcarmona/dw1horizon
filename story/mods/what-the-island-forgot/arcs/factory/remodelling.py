# 162, Factorial Town, the remodelling machine (§3.5): with the factory kept shut its power is the archive's.
from dw import *
from dw.base.factorial_town_162 import guardromon0
from ...state import factory_kept_shut

@guardromon0.on_talk(when=factory_kept_shut)
def no_power():
    say("Remodeling unavailable. All power is assigned to the archive.")
