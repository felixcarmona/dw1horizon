# Jijimon's house (218): Jijimon counts what the city remembers (story-bible.md §2.6, §3.8): after each memory fragment, the
# next time the tamer comes home Jijimon says how much the city remembers now (told on entering, so it needs no talk).
# Screen 205 is the same house once the city has grown (jijimons-house-205.py): keep the two in step.
from dw import *
from dw.base.jijimons_house import house, jijimon
from ..state import memories, memory_news, root2, root3

# Later, of their own will: SkullGreymon after "Let him rest" (R2) and Angemon after "Open it and stay" (R3) come back to the
# city and Jijimon tells it. Those choices set memory_news, told at the first homecoming below, so this is the next one. A
# 0.0.2 save that lost them recovers here too.
@house.on_enter(when=root2 and not recruited(Species.SkullGreymon) and not memory_news)
def the_bones_came_back():
    jijimon.say("Mm, mm... SkullGreymon walked into the square last night, all by himself.",
                "He had his rest, Myotismon says. Nobody called him. He went straight to the Arena.")
    recruit(Species.SkullGreymon, prosperity=3)

@house.on_enter(when=root3 and not recruited(Species.Angemon) and not memory_news)
def angemon_came_home():
    jijimon.say("Mm, mm... Angemon came back this morning, my boy.",
                "The ice has all run down, he says. A wall of water needs no door.")
    recruit(Species.Angemon, prosperity=3)

@house.on_enter(when=memory_news)
def what_the_city_remembers():
    jijimon.say("Mm, mm... Something came back to me just now, my boy. Something old.")
    if memories == 1:
        jijimon.say("The city remembers one thing it had forgotten.")
    elif memories <= 3:
        jijimon.say("The city remembers a few of the things it had forgotten. Keep going.")
    elif memories <= 5:
        jijimon.say("The city remembers many things it had forgotten now.", "The old ones talk about it in the square.")
    else:
        jijimon.say("So much is coming back... Ho ho. I haven't felt this clear-headed in eighty years.")
    memory_news.clear()
