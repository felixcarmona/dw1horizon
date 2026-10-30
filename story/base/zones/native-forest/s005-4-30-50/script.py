# The Python view of script 5 of DG.SCN: screen 4 Native Forest, screen 30 Lava Cave, screen 50 Grey Lord's Mansion, screen 61 Grey Lord's Mansion, screen 65 Grey Lord's Mansion, screen 84 Ancient Speedy Region, screen 126 Drill Tunnel, screen 140 Volume Villa.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

forest = screen(Screen.native_forest_4)
cave = screen(Screen.lava_cave_30)
mansion_50 = screen(Screen.grey_lords_mansion_50)
mansion_61 = screen(Screen.grey_lords_mansion_61)
mansion_65 = screen(Screen.grey_lords_mansion_65)
region = screen(Screen.ancient_speedy_region_84)
tunnel = screen(Screen.drill_tunnel_126)
villa = screen(Screen.volume_villa_140)
slot0 = forest.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot1 = forest.npc(None, slot=1)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot2 = forest.npc(None, slot=2)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot3 = forest.npc(None, slot=3)    # no NPC of the .MAP in this slot; the script spawns what stands here

@slot0.on_talk
def talk():    # section 5
    return slot1.talk()

@slot1.on_talk
def talk():    # section 6
    return slot2.talk()

@slot2.on_talk
def talk():    # section 7
    return slot3.talk()

@slot3.on_talk
def talk():    # section 8
    raw.end_script()

# the section table, in the order of the original header
sections(5, 6, 7, 8)
