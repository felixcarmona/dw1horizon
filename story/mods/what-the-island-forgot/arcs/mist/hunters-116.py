# Misty Trees (screen 116, §3.1d): with the fog kept, the hunters cannot find the forest: its DarkLizardmon are not here.
from dw import *
from dw.base.misty_trees_116 import trees, darklizardmon5, darklizardmon6
from ...state import fog_kept

@trees.on_enter(when=fog_kept)
def hidden_forest():
    darklizardmon5.leave()
    darklizardmon6.leave()
