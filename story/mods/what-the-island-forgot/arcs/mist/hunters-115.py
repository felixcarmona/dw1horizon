# Misty Trees (screen 115, §3.1d): with the fog kept, the hunters cannot find the forest: its DarkLizardmon are not here.
from dw import *
from dw.base.misty_trees_115 import trees, darklizardmon3, darklizardmon4
from ...state import fog_kept

@trees.on_enter(when=fog_kept)
def hidden_forest():
    darklizardmon3.leave()
    darklizardmon4.leave()
