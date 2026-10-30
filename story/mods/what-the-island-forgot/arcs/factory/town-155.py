# Factorial Town (screen 155, §3.5): with the factory kept shut there is no work for its Geremon and PlatinumSukamon.
from dw import *
from dw.base.factorial_town_155 import town, geremon0, geremon1, geremon2, platinumsukamon3, platinumsukamon4, platinumsukamon5
from ...state import factory_kept_shut

@town.on_enter(when=factory_kept_shut)
def gone():
    geremon0.leave()
    geremon1.leave()
    geremon2.leave()
    platinumsukamon3.leave()
    platinumsukamon4.leave()
    platinumsukamon5.leave()
