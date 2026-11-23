# Back Dimension 227, the world behind the portal that opens after the ending: BlackWarGreymon waits there, away from the
# wild Digimon. An optional fight above the final one, for partners trained past the story; nobody is recruited and
# nothing depends on it. The first win pays two chips once; after that it fights again whenever it is asked, for nothing.
# It pays no bits (a fight that can be repeated must not be a source of money). It does not stand on the summit, where
# Machinedramon fell: the setup of that screen can load both final bosses, and a third large model does not fit.
from dw import *
from ...state import rift_duel_won

rift = screen(Screen.back_dimension_227)
blackwargreymon = rift.npc(Species.BlackWarGreymon, at=(2100, 2000), hp=11000, mp=9999, offense=1100, defense=900, speed=900, brain=900,
                             bits=0, range=0, still=True, autotalk=False)


@blackwargreymon.on_talk
def talk():
    if rift_duel_won:
        say("You came back. Good. Again.")
        if fight(blackwargreymon) == "won":
            say("Still not the answer. But closer.")
        return
    say("The machine fell. I felt it even in here, behind the world.")
    say("I guard nothing and I serve nobody. I only want to know what strength is for.")
    say("Show me yours.")
    if fight(blackwargreymon) == "won":
        say("So that is what it is for.")
        say("Take these. I will be here when you want to ask me again.")
        give(Item.OffChip)
        narrator.say("Received the {item Item.OffChip}.")
        give(Item.DefChip)
        narrator.say("Received the {item Item.DefChip}.")
        rift_duel_won.set()
