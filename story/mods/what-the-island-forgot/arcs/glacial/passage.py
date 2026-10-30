# 305, the Passage (§5.7): MasterTyrannomon's secret trail from the Glacial Region to the Bone Field. Its music.
from dw import *

passage = new_screen(305, map="build/what-the-island-forgot-maps/screens/PASS01.MAP")
chest_passage = flag()

@passage.on_enter
def enter():
    spawn_chest(Item.SpeedLeaf, at=(0, 500), opened=chest_passage)
    music(14)                     # the Glacial Region's
