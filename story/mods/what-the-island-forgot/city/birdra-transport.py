# Birdra Transport (207): Hawkmon, from the Great Canyon, keeps the flight log. And Birdramon, once the city has
# grown (prosperity 35), remembers the other human it carried (fragment M8, story-bible.md §3.2): the way up.
from dw import *
from dw.names import *
from dw.base.birdra_transport import transport, leomon, birdramon
from ..state import memories, m8_birdramon, memory_news

hawkmon = transport.npc(Species.Hawkmon, at=(250, -350), behaves_like=leomon, when=recruited(Species.Hawkmon))


@hawkmon.on_talk
def talk():
    say("Birdramon flies, I write it down. From this window I see the whole city.", "Still nobody asks, but now I keep a log.")


@birdramon.on_talk(when=not m8_birdramon and engine.prosperity >= 35, scene=True)
def the_other_one():
    say("Kid. You asked me once if I'd ever carried a human.")
    tamer.say("Huh? Did I?")
    say("I carried another one once. Up the mountain. For a fee...", "I didn't ask what he was.")
    tamer.say("Another human? Here? When?!")
    say("Long time ago. He paid, he went up. He never called for the ride down.")
    m8_birdramon.set()
    memories.add(1)
    memory_news.set()
