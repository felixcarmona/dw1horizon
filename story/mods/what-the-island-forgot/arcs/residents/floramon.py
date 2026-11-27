# Native Forest 4: Floramon guards a seed that wants patience; a Sweet Nut wakes it (consumed, once). No fight. Its home
# is the Market Shed (district/market-shed.py).
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_FLORAMON

forest = screen(Screen.native_forest_4)
floramon = forest.npc(Species.Floramon, at=(2550, 800), hp=590, mp=610, offense=120, defense=90, speed=115, brain=80, range=0, still=True, when=not recruited(Species.Floramon) or new_challenger == CH_FLORAMON, alone=new_challenger == CH_FLORAMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Floramon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (district/market-shed.py).

def challenge_floramon():
    if new_challenger != CH_FLORAMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("floramon.challenge.retry"))
        else:
            say(t("floramon.challenge.intro1"), t("floramon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(floramon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("floramon.challenge.won"))
                give(Item.BigBerry)
                give(bits=1500)
                narrator.say(t("floramon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(3150, -800)
                leave()


@floramon.on_talk
def talk():
    if recruited(Species.Floramon):
        challenge_floramon()
    else:
        say("Shh. This seed only opens for someone patient.")
        if has(Item.SweetNut):
            if ask(yes="Offer a {item Item.SweetNut}", no="Leave it be"):
                take(Item.SweetNut)
                say("It woke up! I'm taking it somewhere safe.")
                walk_away(2550, -250, looks=3)
                send_to_city(line="Floramon joined the city!", species=Species.Floramon, camera=False)
        else:
            say("It likes sweet things. A {item Item.SweetNut} might wake it, if you ever find one.")
