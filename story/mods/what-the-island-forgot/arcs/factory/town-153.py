# Factorial Town (screen 153, §3.5): with the factory kept shut there is no work for its Geremon and PlatinumSukamon.
from dw import *
from dw.base.factorial_town_153 import town, geremon2, geremon3
from ...state import factory_kept_shut

@town.on_enter(when=factory_kept_shut)
def gone():
    geremon2.leave()
    geremon3.leave()
