# Factorial Town (screen 154, §3.5): with the factory kept shut there is no work for its Geremon and PlatinumSukamon.
from dw import *
from dw.base.factorial_town_154 import town, platinumsukamon1, platinumsukamon2
from ...state import factory_kept_shut

@town.on_enter(when=factory_kept_shut)
def gone():
    platinumsukamon1.leave()
    platinumsukamon2.leave()
