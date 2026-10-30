# File City, Kokatorimon the sculptor (script 162, §3.7): with the Wall of Hearts melted (R3) the island remembers, and
# Kokatorimon, who could never say "what on earth was I picturing", knows it at last. Once; then its own talk.
from dw import *
from dw.base.file_city_168 import kokatorimon
from ...state import root3

angel_remembered = flag()

@kokatorimon.on_talk(when=root3 and not angel_remembered)
def an_angel():
    say("{player}! Behold! It came back to me this very morning!")
    say("An angel. I was picturing an angel.", "Wings of light, standing over the ice... Now, why would I have forgotten that?")
    angel_remembered.set()
