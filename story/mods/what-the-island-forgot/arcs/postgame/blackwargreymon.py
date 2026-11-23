# Mt. Infinity 225, the summit, once Digitamamon has left it for the city (it only stands there after the ending): BlackWarGreymon waits where
# Machinedramon fell. An optional fight above the final one, for partners trained past the story; nobody is recruited and
# nothing depends on it. The first win pays two chips once; after that it fights again whenever it is asked, for nothing.
# It pays no bits (a fight that can be repeated must not be a source of money).
from dw import *
from ...state import summit_duel_won

summit = screen(Screen.mt_infinity_225)
blackwargreymon = summit.npc(Species.BlackWarGreymon, at=(0, 900), hp=11000, mp=9999, offense=1100, defense=900, speed=900, brain=900,
                             bits=0, range=0, still=True, when=recruited(Species.Digitamamon))


@blackwargreymon.on_talk
def talk():
    if summit_duel_won:
        say("You came back. Good. Again.")
        if fight(blackwargreymon) == "won":
            say("Still not the answer. But closer.")
        return
    say("The machine fell here. I felt it from the other side of the island.")
    say("I guard nothing and I serve nobody. I only want to know what strength is for.")
    say("Show me yours.")
    if fight(blackwargreymon) == "won":
        say("So that is what it is for.")
        say("Take these. I will be here when you want to ask me again.")
        give(Item.OffChip)
        narrator.say("Received the {item Item.OffChip}.")
        give(Item.DefChip)
        narrator.say("Received the {item Item.DefChip}.")
        summit_duel_won.set()
