# The story's saved state (design/story-bible.md §3, §8): the roots broken, the memory fragments read, and each decision's
# window. Every file of the story imports what it needs from here.
from dw import *

# The Great Canyon (§3.2). When Ogremon escapes down the elevator the chase is offered; it stays offered (the Shaft's
# lift may be ridden back up) until the Engine Room is settled, or until the tamer leaves the fortress without it.
class Canyon(Quest):
    OPEN = auto()         # the fortress not cleared yet, or cleared and the chase not answered
    CHASING = auto()      # "After him!": the way down is open
    SETTLED = auto()      # the Motor broken or left, or the chase turned down: the shaft is closed for good

root1 = flag()            # R1: the Motor broken (the canyon sinks, the crack stays open)
birdramon_gone = flag()   # R1's price: Birdramon fought the tamer at the bridge and left the island

# MasterTyrannomon's post (§3.1f): guided, the secret passage to the Bone Field opens and the slow side loses its keeper
# (the Brachiomon move on); kept, the passage stays shut for good.
post_guided = flag()
post_kept = flag()

# The collection (§3.4): SkullGreymon kept (the original: to the Arena) or laid to rest (R2: the bones go back to the
# rune circle, the Crypt under the basement opens, SkullGreymon never joins).
root2 = flag()

# The soul (§3.7): at the Wall of Hearts Angemon offers to open it and stay as its door (R3: Angemon leaves the city for
# good, the island remembers), or comes back to the city (the original; the wall stays frozen).
root3 = flag()
vault_kept = flag()

# Mt. Infinity (§3.9): Devimon's shortcut (only with R2) skips the climb from 247 to the Infinity Engine room, and
# Megadramon with it.
shortcut_taken = flag()

# The memory the city keeps (§2.6): one flag per fragment, and their count, which the endings read.
memories = counter()
m5_notebook = flag()      # M5: Analogman's first notebook, in the Engine Room
m2_stone = flag()         # M2: Leomon read the second stone, in the shrine's second chamber (304)
m11_field = flag()        # M11: MasterTyrannomon and Brachiomon tell how the war ended, on the Bone Field (306)
m6_notebook = flag()      # M6: Analogman's second notebook, among SkullGreymon's bones in the lab (67)
m9_library = flag()       # M9: Myotismon reads the library's old writing in the Crypt (308)
m4_legend = flag()        # M4: the end of the legend ("Not fight: call"): from Cherrymon, or the melted wall
m7_thaw = flag()          # M7: the Wall of Hearts melted
m12_shore = flag()        # M12: the wet notebook of the human ship on the Drowned Shore (309)
m8_birdramon = flag()     # M8: Birdramon carried another human up the mountain (the way up, Birdra Transport)
notebook3 = flag()        # the third notebook, in the Infinity Engine room (312): read on every path, not a fragment

# The ending (§3.10, §4): the key chain given to Analogman at the summit (KC: the tamer stays, ending 4.3).
key_given = flag()

# Something new was remembered since Jijimon last counted (he tells it at the next talk, jijimons-house.py).
memory_news = flag()

# The gear (§3.6): to the Robot House (the original: the Toys' song, Monzaemon) or to Andromon (the archive complete, M3
# counted twice: it holds the war; Monzaemon never joins).
gear_for_andromon = flag()
m3_archive = flag()       # M3 complete: Andromon reads the whole war from the archive, with the old gear

# Airdramon (§3.9): in the ambush in the city Jijimon shouts not to kill him. Held back, he is healed (the original, AIR);
# fought to the end, he dies in the square: no Airdramon at the summit, another flier must come, or nobody (ending 4.4).
airdramon_killed = flag()

# The kennel of the Seam (design/arc-seam.md, §3.8): H, the named hunter beaten; the Gekomon in its cage goes to the city.
hunter_beaten = flag()

# WaruSeadramon (§3.3): after the cave, Whamon offers to chase him off. Chased: five days with no ferry, then the sea is
# safe. Let go: the first crossing to Factorial Town after Giromon has joined, WaruSeadramon ambushes them at its dock;
# lost, Whamon is hurt and the ferry is closed for ten days.
seadramon_chased = flag()
seadramon_let_go = flag()
whamon_left_day = counter()
# Year + 1 (1-100); the previously unused saved slot is zero in older saves.
# An undated old wait is retired on the next dock visit rather than guessing its age.
whamon_left_year = counter()
sea_ambush_fought = flag()
whamon_hurt = flag()

# The rumours (§3.0): Yuramon offers to spread the word that a human has come. Spread: the island hears of the tamer
# sooner (Greymon comes at prosperity 10, not 15), and so do the hunters (a Gururumon at night in Native Forest and in
# Gear Savanna from the start). Kept quiet: the original pace.
rumours_asked = flag()
rumours_spread = flag()
greymon_armed_by_old_disc = flag()    # 0.0.2 set it with Greymon's challenge on entering File City: see arcs/rumours/yuramon.py

# The fog (§3.1d): Cherrymon clears it after its tale (the original) or keeps the forest hidden: then no hunters in
# Misty Trees, and the end of the legend (M4) only comes after Toy Town, when the tamer asks it to clear the fog.
fog_kept = flag()

# The hunters (§3.8): each root broken raises Analogman's alarm, and the hunters ambush the tamer once in that root's
# land at night, each time stronger; with H (the kennel's hunter beaten) they come with no escort.
ambush1_fought = flag()
ambush2_fought = flag()
ambush3_fought = flag()

# The factory (§3.5): after the town reopens, Andromon asks whether to restart the factory (the original) or put all its
# power into the archive (M3+: the archive tells where the three stations are; the remodelling machine is off for good,
# the Geremon and PlatinumSukamon of the town leave).
factory_asked = flag()
factory_kept_shut = flag()
m3_stations = flag()      # M3+: the archive, with all the power, tells of the three stations (counts one)

# The crater cleft is a return route, unlocked on every Bone Field arrival (including old saves).
bone_field_visited = flag()

# Shared first sighting of either rumour hunter in Native Forest or Gear Savanna.
hunter_noticed = flag()
HUNTER_PRESENT_PSTAT = 120  # unsaved night-model witness, reset on either hunter screen
