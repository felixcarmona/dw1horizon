# Misty Trees (screen 120, §3.1d): with the fog kept, the hunters cannot find the forest: its DarkLizardmon are not here.
from dw import *
from dw.base.misty_trees_120 import trees, darklizardmon
from ...state import fog_kept

@trees.on_enter(when=fog_kept)
def hidden_forest():
    darklizardmon.leave()
