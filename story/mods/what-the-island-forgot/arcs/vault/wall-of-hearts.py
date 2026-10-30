# 310, the Vault, the Wall of Hearts (§3.7, §5.5): everything the island has forgotten, frozen in a wall of ice. Angemon
# can open it, but the one who opens it must stay as its door. "Stay" (R3): the wall melts (fragment M7, and the end
# of the legend, M4, if Cherrymon has not told it), Angemon leaves the city for good and keeps the door (311); "Come to
# the city": the original, the wall stays frozen.
from dw import *
from ...state import root3, vault_kept, memories, m4_legend, m7_thaw, memory_news

vault = new_screen(310, map="build/what-the-island-forgot-maps/screens/VALT01.MAP")
angemon = vault.npc(Species.Angemon, at=(0, 800), range=0, when=recruited(Species.Angemon) and not root3 and not vault_kept)

@vault.on_enter
def enter():
    music(18)                     # the Ice Sanctuary's

@angemon.on_talk(scene=True)
def the_door():
    face(tamer)
    tamer.face(angemon)
    say("You found it. The Wall of Hearts.")
    say("Everything this island has forgotten is frozen here.", "The old town, the old roads, the faces of friends who left for the cold.")
    tamer.say("Whoa... That's what's in the ice? Can we get it out?")
    say("I can open it. But the one who opens it must stay as its door.")
    tamer.say("You mean you'd never come back to the city?")
    say("I would keep the door, here in the Sanctuary. And the island would remember.", "Choose, {player}. I will do as you say.")
    if ask(yes="Open it and stay", no="Come to the city"):
        say("So be it. I offer up my soul.")
        sound(8, 9)
        fade_to_white(2000)
        wait(1000)
        root3.set()
        m7_thaw.set()
        memories.add(1)
        memory_news.set()
        if not m4_legend:
            m4_legend.set()
            memories.add(1)
            memory_news.set()
        unrecruit(Species.Angemon)
        warp(311, entry=0)
    else:
        say("Then my place is in your city. The wall will wait.")
        vault_kept.set()
