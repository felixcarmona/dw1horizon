# Grey Lord's Mansion 59, the dead-end room off the hall (the brief's 54 reads no NPC list): Wizardmon reads a book whose
# pages have gone blank. It joins once the city has grown (prosperity 20: recruits only add to it, so it is no dead end).
# Its home is the Scrap Office (district/scrap-office.py).
from dw import *

room = screen(Screen.grey_lords_mansion_59)
wizardmon = room.npc(Species.Wizardmon, at=(0, 300), range=0, when=not recruited(Species.Wizardmon))


@wizardmon.on_talk
def talk():
    say("The words are leaving. I need someone who still remembers things.")
    if engine.prosperity >= 20:
        say("A whole city that remembers you? Then I will read there.")
        send_to_city(line="Wizardmon joined the city!", species=Species.Wizardmon)
    else:
        say("Come back when you have read more of this island.")
