# First quest: Jijimon has a gift for a curious Tamer. A flag, a counter, a menu, items and bits.
#   python3 tools/dws.py check story/mods/examples/src/first_quest.py --build
from dw import *
from dw.base.jijimons_house import jijimon

reward_taken = flag()       # Jijimon gave the gift
visits = counter()          # talks since then

@jijimon.on_talk(when=reward_taken)
def again():
    visits.add(1)
    say("I have nothing more to give, but your company is a gift in itself.")
    if visits >= 3:
        say("You keep coming back. That is the spirit of a true Tamer!")

@jijimon.on_talk(when=not reward_taken)
def gift():
    say("Ah, there you are! I have been waiting for someone curious. Would you like a small gift?")
    if ask(yes="Yes, please", no="Not now"):
        say("Take these two Meat and some bits. A good Tamer is always well fed.")
        give(Item.Meat, 2, bits=500)
        reward_taken.set()
        tamer.say("Thank you, Jijimon!")
    else:
        say("Hm, maybe next time. The offer stands.")
