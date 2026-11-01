# Jijimon's house (218): Jijimon counts what the city remembers (story-bible.md §2.6, §3.8): after each memory fragment, the
# next time the tamer comes home Jijimon says how much the city remembers now (told on entering, so it needs no talk).
from dw import *
from dw.base.jijimons_house import house, jijimon
from ..state import memories, memory_news

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
