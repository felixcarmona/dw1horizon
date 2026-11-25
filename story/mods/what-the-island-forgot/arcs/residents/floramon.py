# Native Forest 4: Floramon guards a seed that wants patience; a Sweet Nut wakes it (consumed, once). No fight. Its home
# is the Market Shed (district/market-shed.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_FLORAMON

forest = screen(Screen.native_forest_4)
floramon = forest.npc(Species.Floramon, at=(2550, 800), range=0, still=True, when=not recruited(Species.Floramon) or trigger(50))


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Floramon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (district/market-shed.py).
@forest.on_enter(when=recruited(Species.Floramon) and engine.game_beaten)
def challenge_away_floramon():
    if challenger != CH_FLORAMON or challenge_won:
        floramon.leave()


def challenge_floramon():
    if challenger != CH_FLORAMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("floramon.challenge.retry"))
        else:
            say(t("floramon.challenge.intro1"), t("floramon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(floramon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("floramon.challenge.won"))
                give(Item.BigBerry)
                give(bits=1500)
                narrator.say(t("floramon.challenge.reward"))
                challenge_won.set()
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
                send_to_city(line="Floramon joined the city!", species=Species.Floramon)
        else:
            say("It likes sweet things. A {item Item.SweetNut} might wake it, if you ever find one.")
