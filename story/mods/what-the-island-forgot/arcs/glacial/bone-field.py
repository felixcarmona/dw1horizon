# 306, the Bone Field (§3.1f, §5.7): where the old war ended. MasterTyrannomon, who guided the tamer here, and a
# Brachiomon, who left the slow meadow, tell what they half remember (fragment M11): the man did not die, he went down.
from dw import *
from ...state import post_guided, memories, m11_field, memory_news, bone_field_visited

field = new_screen(306, map="build/what-the-island-forgot-maps/screens/BONE01.MAP")
chest_bone_field = flag()
master = field.npc(Species.MasterTyrannomon, at=(900, 1900), range=0, when=post_guided)
elder = field.npc(Species.Brachiomon, at=(1500, 2300), range=0, when=post_guided)

@field.on_enter
def enter():
    bone_field_visited.set()
    spawn_chest(Item.HPChip, at=(-900, 700), opened=chest_bone_field)
    music(13)                     # the Speedy Region's

@master.on_talk(when=not m11_field, scene=True)
def how_it_ended():
    face(tamer)
    tamer.face(master)
    say("This is where it ended. Ninety years ago, or a hundred. I was smaller than you.")
    elder.say("They came from beyond, with fire that was not fire.", "We stood together at the middle of the island, every kind of us.")
    say("And we won. The others were gone without a trace. But their leader... he did not die.")
    tamer.say("Then what happened to him?")
    say("He went down. Into the ground, into the island itself. I saw it with these eyes.")
    elder.say("Since that day the ground here has been hungry. Time runs to bone.")
    m11_field.set()
    memories.add(1)
    memory_news.set()
    tamer.say("Went down... into the island?")

@master.on_talk
def keeps_watch():
    say("My post is this field now. Somebody should remember it.")

@elder.on_talk(when=m11_field)
def the_small_one():
    # the optional layer of §2.8, never confirmed by anyone: the child who would not fight, whom the island kept
    say("There was a small one with them. He would not raise a hand against us.")
    say("When it ended, the island kept him. I do not know what he became.", "Something that is neither one of them nor one of us.")

@elder.on_talk
def elder_talk():
    say("Time flows fast here. Do not stay long, little ones.")
