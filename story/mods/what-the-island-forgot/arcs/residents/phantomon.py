# Grey Lord's Mansion 56, Soulmon's gallery, at night only (the brief's 60 reads no NPC list): Phantomon carries things for
# those who no longer need them. A fight at the Mansion's strength. Its home is the Secret Item Shop (city/secret-item-shop.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_PHANTOMON

gallery = screen(Screen.grey_lords_mansion_56)
phantomon = gallery.npc(Species.Phantomon, at=(-500, -400), hp=3400, mp=3600, offense=620, defense=330, speed=130, brain=250, bits=700,
                        range=0, still=True, when=clock.hour >= 20 or recruited(Species.Phantomon))


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Phantomon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (city/secret-item-shop.py).
@gallery.on_enter(when=recruited(Species.Phantomon))
def challenge_away_phantomon():
    if not engine.game_beaten or challenger != CH_PHANTOMON or challenge_won:
        phantomon.leave()


def challenge_phantomon():
    if challenger != CH_PHANTOMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("phantomon.challenge.retry"))
        else:
            say(t("phantomon.challenge.intro1"), t("phantomon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(phantomon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("phantomon.challenge.won"))
                give(Item.EnemyRepel)
                give(bits=4000)
                narrator.say(t("phantomon.challenge.reward"))
                challenge_won.set()
                run(1150, 650)
                leave()


@phantomon.on_talk
def talk():
    if recruited(Species.Phantomon):
        challenge_phantomon()
    else:
        say("I carry things for those who no longer need them.")
        if fight(phantomon) == "won":
            say("Your name stays on my list a little longer. Do you have a shop for me?")
            send_to_city(line="Phantomon joined the city!", species=Species.Phantomon)
