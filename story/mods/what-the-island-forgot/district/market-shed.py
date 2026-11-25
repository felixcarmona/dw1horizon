# 364, the Market Shed: Tapirmon, woken at Dragon Eye Lake, runs the stall (fruit and roots from all over the island) and
# sells a dream or two with them. Floramon, from the Native Forest, keeps the seed it guarded here: the Item Bank 211 has no
# heap for its model.
from dw import *
from ..state import challenger, challenge_won, CH_FLORAMON, CH_TAPIRMON

market_shed = new_screen(364, map="build/what-the-island-forgot-maps/screens/BARR08.MAP")
tapirmon = market_shed.npc(Species.Tapirmon, at=(0, 100), range=0, when=recruited(Species.Tapirmon))
floramon = market_shed.npc(Species.Floramon, at=(400, -150), range=0, when=recruited(Species.Floramon))


@tapirmon.on_talk
def talk():
    say("Fresh from every corner of the island! The dreams are free. The fruit is not.")
    shop(Item.HawkRadish, Item.BlueApple, Item.RedBerry, Item.SweetNut, Item.OrangeBana, Item.Supercarrot)


@floramon.on_talk
def talk():
    say("Tapirmon sells the dreams. I keep the seeds safe.", "Yours is growing. Everything grows here, even in the shade of a shed.")


# Resident challenges (content/tables/resident-challenges.json): the day one of them is out waiting at its old
# spot, it is not here.
@market_shed.on_enter
def challenger_out_floramon_tapirmon():
    if challenger == CH_FLORAMON and not challenge_won:
        floramon.leave()
    if challenger == CH_TAPIRMON and not challenge_won:
        tapirmon.leave()
