# File City, Yuramon the rumour-teller (script 162, §3.0): the first talk and the offer to spread the word of the human.
# With the word spread, Jijimon's talk arms Greymon's challenge sooner: jijimon-news.py.
from dw import *
from dw.names import *
from dw.base.file_city_168 import city_168, yuramon
from ...state import greymon_armed_by_old_disc, rumours_asked, rumours_spread

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

@city_168.on_enter(when=greymon_armed_by_old_disc and greymon_challenge_ready)
def forget_old_challenge():
    # A save from 0.0.2 may hold him armed on entering the city, for whatever partner: Jijimon's talk arms him again.
    greymon_armed_by_old_disc.clear()
    greymon_challenge_ready.clear()
