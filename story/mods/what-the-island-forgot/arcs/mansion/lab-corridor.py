# 68, the Underground Lab's corridor (§3.4): with the Grey Lord's bones at rest (R2) the lab is no longer worth guarding,
# and its DarkLizardmon patrol is gone.
from dw import *
from dw.base.underground_lab_68 import lab, darklizardmon1, darklizardmon2, darklizardmon3, darklizardmon4, darklizardmon5
from ...state import root2

@lab.on_enter(when=root2)
def emptied():
    darklizardmon1.leave()
    darklizardmon2.leave()
    darklizardmon3.leave()
    darklizardmon4.leave()
    darklizardmon5.leave()
