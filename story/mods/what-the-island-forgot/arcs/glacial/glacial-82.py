# 82, the Ancient Glacial Region, the Tyrannomon path (§3.1f): once Tyrannomon has gone to the city its old master keeps
# watch here, and it is the only one who knows the "secret passage". To show the way it must leave its post: "Guide
# me" opens the mouth in the ferns (maps/koda03-passage.py, step trigger 1) and it goes ahead to the Bone Field;
# "Stay at your post" closes the passage for good.
from dw import *
from dw.base.ancient_glacial_region_82 import region, mastertyrannomon
from ...state import post_guided, post_kept

@mastertyrannomon.on_talk(when=recruited(Species.Tyrannomon) and not post_guided and not post_kept)
def the_passage():
    say("Heh... How many years since I last stood guard here?")
    tamer.say("Tyrannomon said there's a secret passage around here. Do you know it?")
    say("Know it? I walked it when I was younger than that numbskull.", "It leads to the field where the old war ended. The bones are still there.")
    say("But if I show you the way, I leave my post.", "Without a keeper the fast side eats the slow one.",
        "The old ones who live slowly here would have to move on.")
    if ask(yes="Guide me", no="Stay at your post"):
        say("So be it, boy from the analog world. The trail leaves the path in the ferns to the east.", "I will go ahead.")
        post_guided.set()
        walk_away(650, 1250, looks=2)
        leave()
    else:
        say("A wise answer. Some doors are better left shut.")
        post_kept.set()

@region.on_enter(when=post_guided)
def gone_ahead():
    mastertyrannomon.leave()

@region.on_step(1, when=post_guided)
def into_the_trail():
    warp(305, entry=0)

@region.on_step(1, when=not post_guided)
def thick_ferns():
    tamer.say("The ferns are really thick here... I can't get through.")
    tamer.walk(650, 1250)
