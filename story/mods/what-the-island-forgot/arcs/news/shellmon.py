# File City's lower town, Shellmon the newsman (script 163, §3.8): each root broken makes the news once, the next time
# the tamer talks to Shellmon; then its own talk.
from dw import *
from dw.names import *
from dw.base.file_city_180 import shellmon
from ...state import root1, root2, root3, m3_archive

news_r1 = flag()
news_r2 = flag()
news_r3 = flag()
news_m3 = flag()

@shellmon.on_talk(when=shellmon_newspaper_started and root1 and not news_r1)
def canyon_sinking():
    say("Extra, extra! Shell News! \"Great Canyon sinking!\"", "The high ground drops a little every night. Pretty clever of me to notice, huh?")
    news_r1.set()

@shellmon.on_talk(when=shellmon_newspaper_started and root2 and not news_r2)
def doors_open():
    say("Extra, extra! Shell News! \"Myotismon closes his collection!\"", "The famous bones are laid to rest under the mansion.",
        "Nobody knows why. Except me, of course.")
    news_r2.set()

@shellmon.on_talk(when=shellmon_newspaper_started and root3 and not news_r3)
def freezeland_thaw():
    say("Extra, extra! Shell News! \"Freezeland thaw?\"", "Mr. M, interviewed by yours truly: \"I can go home.\"")
    news_r3.set()

@shellmon.on_talk(when=shellmon_newspaper_started and m3_archive and not news_m3)
def what_the_factory_remembers():
    say("Shell News Special! \"What the Factory remembers!\"", "Andromon's archive tells the whole war. Read all about it!")
    news_m3.set()
