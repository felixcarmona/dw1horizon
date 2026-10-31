# File City, Yuramon the rumour-teller (script 162, §3.0): the first talk, the offer to spread the word of the human; and,
# with the word spread, Greymon's challenge armed at prosperity 10 instead of the game's 15 (libraries/s210).
from dw import *
from dw.names import *
from dw.base.file_city_168 import city_168, yuramon
from ...state import greymon_heard_of_tamer, rumours_asked, rumours_spread

@yuramon.on_talk(when=not rumours_asked)
def the_word():
    say("Ehehe! A human, a real human, in File City! Nobody out there knows yet...")
    say("Want me to tell everyone? My rumours go suuuper far.", "The whole island would know by tomorrow!")
    rumours_asked.set()
    if ask(yes="Spread it", no="Keep it quiet"):
        say("Leave it to me! Everyone will hear about you. Eeeveryone!")
        rumours_spread.set()
    else:
        say("Okaaay. It'll be our secret, then. Ehehe.")

@city_168.on_enter(when=rumours_spread and not greymon_heard_of_tamer and engine.prosperity >= 10 and not greymon_challenge_ready and not recruited(Species.Greymon))
def greymon_heard():
    # Once only. His step tiles ring the door of Jijimon's house, where a defeat wakes the tamer: armed on every entry,
    # the fight (no escape) would come back each time the tamer steps out. Lost, the game's own way brings him back.
    greymon_heard_of_tamer.set()
    greymon_challenge_ready.set()
