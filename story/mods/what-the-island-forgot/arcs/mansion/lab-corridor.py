# 68, the Underground Lab's corridor (§3.4): with the Grey Lord's bones at rest (R2) the lab is no longer worth guarding,
# and its DarkLizardmon patrol is gone, until SkullGreymon walks out and the lab is worth guarding again.
from dw import *
from dw.base.underground_lab_68 import lab, darklizardmon1, darklizardmon2, darklizardmon3, darklizardmon4, darklizardmon5
from ...state import root2

@lab.on_enter(when=root2 and not recruited(Species.SkullGreymon))
def emptied():
    darklizardmon1.leave()
    darklizardmon2.leave()
    darklizardmon3.leave()
    darklizardmon4.leave()
    darklizardmon5.leave()
