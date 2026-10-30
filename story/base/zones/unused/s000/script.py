# The Python view of script 0 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(0)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot1 = lib.npc(None, slot=1)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot2 = lib.npc(None, slot=2)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot3 = lib.npc(None, slot=3)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot4 = lib.npc(None, slot=4)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot5 = lib.npc(None, slot=5)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot6 = lib.npc(None, slot=6)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot7 = lib.npc(None, slot=7)    # no NPC of the .MAP in this slot; the script spawns what stands here
t1241 = text.s000.sec1241
t1242 = text.s000.sec1242
t1244 = text.s000.sec1244
t1251 = text.s000.sec1251

@lib.section(0)
def sec0():    # section 0
    use_script(1, Screen.native_forest_0)
    engine.music_mode.set(0)
    music(1)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.ModokiBetamon)
        load(Species.RedVegiemon)
        spawn(Species.ModokiBetamon, slot=0, autotalk=True)
        spawn(Species.ModokiBetamon, slot=1, autotalk=True)
        spawn(Species.RedVegiemon, slot=2, autotalk=True)
        spawn(Species.RedVegiemon, slot=3, autotalk=True)
        spawn(Species.ModokiBetamon, slot=4, autotalk=True)
    else:
        load(Species.Dokunemon)
        spawn(Species.Dokunemon, slot=5, autotalk=True)
        spawn(Species.Dokunemon, slot=6, autotalk=True)
        spawn(Species.Dokunemon, slot=7, autotalk=True)

@lib.section(1)
def sec1():    # section 1
    use_script(2, Screen.kunemons_bed)
    engine.music_mode.set(0)
    music(1)
    if not recruited(Species.Kunemon):
        load(Species.Kunemon152)
        spawn(Species.Kunemon152, slot=1)
    if date_hour >= 7 and date_hour < 19 and recruited(Species.Kunemon):
        load(Species.RedVegiemon)
        spawn(Species.RedVegiemon, slot=0, autotalk=True)
        spawn(Species.RedVegiemon, slot=2, autotalk=True)
    if (date_hour < 7 or date_hour >= 19) and recruited(Species.Kunemon):
        load(Species.Dokunemon)
        spawn(Species.Dokunemon, slot=3, autotalk=True)
        spawn(Species.Dokunemon, slot=4, autotalk=True)

@lib.section(2)
def sec2():    # section 2
    use_script(3, Screen.native_forest_2)
    engine.music_mode.set(0)
    music(1)
    if not recruited(Species.Palmon):
        load(Species.Palmon164)
        spawn(Species.Palmon164, slot=2)
    else:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=0, autotalk=True)
        spawn(Species.Goblimon, slot=1, autotalk=True)
        spawn(Species.Goblimon, slot=3, autotalk=True)
        spawn(Species.Goblimon, slot=4, autotalk=True)

@lib.section(3)
def sec3():    # section 3
    use_script(4, Screen.native_forest_3)
    engine.music_mode.set(0)
    music(1)
    if not recruited(Species.Etemon):
        load(Species.Etemon162)
        spawn(Species.Etemon162, slot=0, autotalk=True)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Aruraumon)
        spawn(Species.Aruraumon, slot=2, autotalk=True)
    else:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=4, autotalk=True)
    if date_hour >= 7 and date_hour < 19 and recruited(Species.Etemon):
        load(Species.Aruraumon)
        spawn(Species.Aruraumon, slot=1, autotalk=True)
    if (date_hour < 7 or date_hour >= 19) and recruited(Species.Etemon):
        spawn(Species.Goblimon, slot=3, autotalk=True)

@lib.section(4)
def sec4():    # section 4
    use_script(5, Screen.native_forest_4)
    engine.music_mode.set(0)
    music(1)

@slot0.on_talk
def talk():    # section 5
    use_script(6, Screen.coela_point)
    engine.music_mode.set(0)
    music(1)
    load(Species.Coelamon)

@slot1.on_talk
def talk():    # section 6
    use_script(7, Screen.dragon_eye_lake_6)
    engine.music_mode.set(0)
    music(1)

@slot2.on_talk
def talk():    # section 7
    use_script(8, Screen.drill_tunnel_entrance)
    engine.music_mode.set(0)
    music(1)
    load(Species.MarketManager)

@slot3.on_talk
def talk():    # section 8
    use_script(9, Screen.dragon_eye_lake_8)
    engine.music_mode.set(0)
    music(1)

@slot4.on_talk
def talk():    # section 9
    use_script(10, Screen.digimon_bridge_9)
    engine.music_mode.set(0)
    music(1)
    if recruited(Species.Etemon) and recruited(Species.Ninjamon):
        load(Species.Etemon162)
        spawn(Species.Etemon162, slot=3)
        return
    if not recruited(Species.Ninjamon):
        load(Species.Ninjamon175)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Aruraumon)
        spawn(Species.Aruraumon, slot=0, autotalk=True)
    else:
        load(Species.Tsukaimon)
        spawn(Species.Tsukaimon, slot=2, autotalk=True)

@slot5.on_talk
def talk():    # section 10
    use_script(11, Screen.digimon_bridge_10)
    engine.music_mode.set(0)
    music(1)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.ModokiBetamon)
        load(Species.Aruraumon)
        spawn(Species.ModokiBetamon, slot=0, autotalk=True)
        spawn(Species.ModokiBetamon, slot=1, autotalk=True)
        spawn(Species.Aruraumon, slot=2, autotalk=True)
    else:
        load(Species.Tsukaimon)
        spawn(Species.Tsukaimon, slot=3, autotalk=True)
        spawn(Species.Tsukaimon, slot=4, autotalk=True)
        spawn(Species.Tsukaimon, slot=5, autotalk=True)

@slot6.on_talk
def talk():    # section 11
    use_script(12, Screen.tropical_jungle_11)
    engine.music_mode.set(0)
    music(2)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Aruraumon)
        spawn(Species.Aruraumon, slot=0, autotalk=True)
        spawn(Species.Aruraumon, slot=1, autotalk=True)
    else:
        load(Species.Tsukaimon)
        spawn(Species.Tsukaimon, slot=2, autotalk=True)
        spawn(Species.Tsukaimon, slot=3, autotalk=True)

@slot7.on_talk
def talk():    # section 12
    use_script(13, Screen.tropical_jungle_12)
    engine.music_mode.set(0)
    music(2)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Muchomon)
        spawn(Species.Muchomon, slot=1, autotalk=True)
        spawn(Species.Muchomon, slot=2, autotalk=True)
    else:
        load(Species.JMojyamon)
        spawn(Species.JMojyamon, slot=4, autotalk=True)
        spawn(Species.JMojyamon, slot=3, autotalk=True)
    if recruited(Species.Piximon):
        return
    raw.store_random(random_roll_screen, 99)
    if random_roll_screen <= 2:
        load(Species.Piximon173)
        spawn(Species.Piximon173, slot=0, autotalk=True)

@lib.section(13)
def sec13():    # section 13
    use_script(14, Screen.tropical_jungle_13)
    engine.music_mode.set(0)
    music(2)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Yanmamon)
        spawn(Species.Yanmamon, slot=0, autotalk=True)
        spawn(Species.Yanmamon, slot=1, autotalk=True)
        spawn(Species.Yanmamon, slot=2, autotalk=True)
    else:
        load(Species.Tsukaimon)
        load(Species.JMojyamon)
        spawn(Species.Tsukaimon, slot=3, autotalk=True)
        spawn(Species.JMojyamon, slot=4, autotalk=True)
        spawn(Species.JMojyamon, slot=5, autotalk=True)

@lib.section(14)
def sec14():    # section 14
    use_script(15, Screen.tropical_jungle_14)
    engine.music_mode.set(0)
    music(2)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.RedVegiemon)
        spawn(Species.RedVegiemon, slot=0, autotalk=True)
        spawn(Species.RedVegiemon, slot=2, autotalk=True)
    else:
        load(Species.Tsukaimon)
        load(Species.JMojyamon)
        spawn(Species.Tsukaimon, slot=3, autotalk=True)
        spawn(Species.JMojyamon, slot=4, autotalk=True)

@lib.section(15)
def sec15():    # section 15
    use_script(16, Screen.mangrove_region_15)
    engine.music_mode.set(0)
    music(2)
    if not recruited(Species.Betamon):
        load(Species.Betamon128)
        spawn(Species.Betamon128, slot=0, autotalk=True)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.ModokiBetamon)
        spawn(Species.ModokiBetamon, slot=1, autotalk=True)
    else:
        load(Species.Tsukaimon)
        load(Species.JMojyamon)
        spawn(Species.JMojyamon, slot=2, autotalk=True)

@lib.section(16)
def sec16():    # section 16
    use_script(17, Screen.mangrove_region_16)
    engine.music_mode.set(0)
    music(2)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Yanmamon)
        spawn(Species.Yanmamon, slot=0, autotalk=True)
        spawn(Species.Yanmamon, slot=1, autotalk=True)
        load(Species.Muchomon)
        spawn(Species.Muchomon, slot=2, autotalk=True)
    else:
        load(Species.JMojyamon)
        spawn(Species.JMojyamon, slot=3, autotalk=True)
        spawn(Species.JMojyamon, slot=4, autotalk=True)
        spawn(Species.JMojyamon, slot=5, autotalk=True)

@lib.section(17)
def sec17():    # section 17
    use_script(18, Screen.amida_forest)
    engine.music_mode.set(0)
    music(12)
    load(Species.Centarumon156)

@lib.section(18)
def sec18():    # section 18
    use_script(19, Screen.path_thru_mt_panorama_18)
    engine.music_mode.set(0)
    music(3)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=0, autotalk=True)
        spawn(Species.Goblimon, slot=1, autotalk=True)
        load(Species.Aruraumon)
        spawn(Species.Aruraumon, slot=2, autotalk=True)
        spawn(Species.Aruraumon, slot=3, autotalk=True)
    else:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=4, autotalk=True)
        spawn(Species.Goblimon, slot=5, autotalk=True)
        load(Species.Gotsumon)
        spawn(Species.Gotsumon, slot=6, autotalk=True)
        spawn(Species.Gotsumon, slot=7, autotalk=True)

@lib.section(19)
def sec19():    # section 19
    use_script(20, Screen.mt_panorama_plains)
    engine.music_mode.set(0)
    music(3)
    raw.store_random(random_roll_screen, 99)
    if random_roll_screen <= 2 and not recruited(Species.Mamemon):
        load(Species.Mamemon137)
        spawn(Species.Mamemon137, slot=0, autotalk=True)
    else:
        load(Species.MudFrigimon)
        spawn(Species.MudFrigimon, slot=1, autotalk=True)
        spawn(Species.MudFrigimon, slot=2, autotalk=True)
        spawn(Species.MudFrigimon, slot=3, autotalk=True)

@lib.section(20)
def sec20():    # section 20
    use_script(21, Screen.path_thru_mt_panorama_20)
    engine.music_mode.set(0)
    music(3)
    load(Species.Gotsumon)
    spawn(Species.Gotsumon, slot=0, autotalk=True)
    spawn(Species.Gotsumon, slot=2, autotalk=True)
    load(Species.Goblimon)
    spawn(Species.Goblimon, slot=1, autotalk=True)
    spawn(Species.Goblimon, slot=3, autotalk=True)

@lib.section(21)
def sec21():    # section 21
    use_script(22, Screen.mt_panorama_spore_area_21)
    engine.music_mode.set(0)
    music(3)

@lib.section(22)
def sec22():    # section 22
    use_script(23, Screen.foot_of_mt_panorama_22)
    engine.music_mode.set(0)
    music(3)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Flarerizamon)
        load(Species.Aruraumon)
        spawn(Species.Flarerizamon, slot=0, autotalk=True)
        spawn(Species.Flarerizamon, slot=1, autotalk=True)
        spawn(Species.Aruraumon, slot=2, autotalk=True)
        spawn(Species.Aruraumon, slot=3, autotalk=True)
    else:
        load(Species.Tsukaimon)
        spawn(Species.Tsukaimon, slot=4, autotalk=True)
        spawn(Species.Tsukaimon, slot=5, autotalk=True)
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=6, autotalk=True)
        spawn(Species.Goblimon, slot=7, autotalk=True)

@lib.section(23)
def sec23():    # section 23
    use_script(24, Screen.foot_of_mt_panorama_23)
    engine.music_mode.set(0)
    music(3)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Flarerizamon)
        load(Species.Aruraumon)
        spawn(Species.Flarerizamon, slot=0, autotalk=True)
        spawn(Species.Flarerizamon, slot=1, autotalk=True)
        spawn(Species.Aruraumon, slot=2, autotalk=True)
        spawn(Species.Aruraumon, slot=3, autotalk=True)
    else:
        load(Species.Tsukaimon)
        spawn(Species.Tsukaimon, slot=4, autotalk=True)
        spawn(Species.Tsukaimon, slot=5, autotalk=True)
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=6, autotalk=True)
        spawn(Species.Goblimon, slot=7, autotalk=True)

@lib.section(24)
def sec24():    # section 24
    use_script(25, Screen.drill_tunnel_24)
    engine.music_mode.set(1)
    music(4)
    load(Species.Goblimon)
    spawn(Species.Goblimon, slot=0, autotalk=True)

@lib.section(25)
def sec25():    # section 25
    use_script(26, Screen.drill_tunnel_2nd_floor_25)
    if not new_ogre_fortress_cleared or recruited(Species.Ogremon):
        engine.music_mode.set(1)
        music(4)
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=0, autotalk=True)
        spawn(Species.Goblimon, slot=1, autotalk=True)
        spawn(Species.Goblimon, slot=2, autotalk=True)
    else:
        engine.music_mode.set(2)
        music(6)
        load(Species.Ogremon154)
        load(Species.Agumon)
        spawn(Species.Ogremon154, slot=3)
        spawn(Species.Agumon, slot=4)
        spawn(Species.Agumon, slot=5)
    if drill_tunnel_progress == 2:
        drill_tunnel_progress.set(1)

@lib.section(26)
def sec26():    # section 26
    use_script(27, Screen.drill_tunnel_3rd_floor)
    engine.music_mode.set(1)
    music(4)
    load(Species.Drimogemon158)
    spawn(Species.Drimogemon158, slot=0)

@lib.section(27)
def sec27():    # section 27
    use_script(28, Screen.residential_area)
    engine.music_mode.set(1)
    music(4)
    load(Species.Drimogemon158)
    spawn(Species.Drimogemon158, slot=0)

@lib.section(28)
def sec28():    # section 28
    use_script(29, Screen.underground_pond)
    engine.music_mode.set(1)
    music(4)
    if drimogemon_job_days >= 5 and drill_tunnel_progress < 3 and drill_tunnel_progress >= 1:
        return
    if underground_pond_dig_work >= 10:
        return
    if underground_pond_dig_work >= 5:
        load(Species.Drimogemon158)
        spawn(Species.Drimogemon158, slot=1)
        return
    load(Species.Drimogemon158)
    spawn(Species.Drimogemon158, slot=0)

@lib.section(29)
def sec29():    # section 29
    use_script(30, Screen.drill_tunnel_2nd_floor_29)
    engine.music_mode.set(1)
    music(4)
    if not recruited(Species.Meramon):
        load(Species.Drimogemon158)
        spawn(Species.Drimogemon158, slot=0)

@lib.section(30)
def sec30():    # section 30
    use_script(5, Screen.lava_cave_30)
    engine.music_mode.set(1)
    music(9)

@lib.section(31)
def sec31():    # section 31
    use_script(31, Screen.lava_cave_31)
    engine.music_mode.set(1)
    music(9)
    if not recruited(Species.Meramon):
        load(Species.Meramon133)
        spawn(Species.Meramon133, slot=0, autotalk=True)

@lib.section(32)
def sec32():    # section 32
    use_script(32, Screen.drill_tunnel_32)
    engine.music_mode.set(1)
    music(4)
    if not recruited(Species.Drimogemon):
        load(Species.Drimogemon158)
        spawn(Species.Drimogemon158, slot=0)

@lib.section(33)
def sec33():    # section 33
    use_script(33, Screen.lava_cave_33)
    load(Species.DemiMeramon)
    spawn(Species.DemiMeramon, slot=0)
    spawn(Species.DemiMeramon, slot=1)

@lib.section(34)
def sec34():    # section 34
    use_script(34, Screen.overdell)
    engine.music_mode.set(1)
    music(5)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.DarkLizardmon)
        spawn(Species.DarkLizardmon, slot=0, autotalk=True)
        spawn(Species.DarkLizardmon, slot=1, autotalk=True)
        spawn(Species.DarkLizardmon, slot=2, autotalk=True)
        spawn(Species.DarkLizardmon, slot=3, autotalk=True)
    else:
        load(Species.DarkLizardmon)
        load(Species.Tsukaimon)
        spawn(Species.DarkLizardmon, slot=4, autotalk=True)
        spawn(Species.DarkLizardmon, slot=5, autotalk=True)
        spawn(Species.Tsukaimon, slot=6, autotalk=True)
        spawn(Species.Tsukaimon, slot=7, autotalk=True)

@lib.section(35)
def sec35():    # section 35
    use_script(35, Screen.overdell_cemetery)
    engine.music_mode.set(1)
    music(5)
    if not recruited(Species.Bakemon):
        load(Species.Bakemon157)
        spawn(Species.Bakemon157, slot=0, autotalk=True)
        load(Species.Tsukaimon)
        spawn(Species.Tsukaimon, slot=1, autotalk=True)
        spawn(Species.Tsukaimon, slot=2, autotalk=True)
        return
    roll = random.roll(1)
    if roll == 0:
        load(Species.Tsukaimon)
        spawn(Species.Tsukaimon, slot=1, autotalk=True)
        spawn(Species.Tsukaimon, slot=2, autotalk=True)
        spawn(Species.Tsukaimon, slot=3, autotalk=True)
    if roll == 1:
        load(Species.Soulmon)
        spawn(Species.Soulmon, slot=4, autotalk=True)
        spawn(Species.Soulmon, slot=5, autotalk=True)
        spawn(Species.Soulmon, slot=6, autotalk=True)

@lib.section(36)
def sec36():    # section 36
    use_script(36, Screen.great_canyon_entrance)
    engine.music_mode.set(0)
    music(6)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=0, autotalk=True)
        spawn(Species.Goblimon, slot=1, autotalk=True)
    else:
        load(Species.Gotsumon)
        spawn(Species.Gotsumon, slot=2, autotalk=True)
        spawn(Species.Gotsumon, slot=3, autotalk=True)

@lib.section(37)
def sec37():    # section 37
    use_script(37, Screen.great_canyon_top_area_37)
    engine.music_mode.set(0)
    music(6)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=0, autotalk=True)
        spawn(Species.Goblimon, slot=1, autotalk=True)
        spawn(Species.Goblimon, slot=2, autotalk=True)
    else:
        load(Species.Weedmon)
        spawn(Species.Weedmon, slot=3, autotalk=True)
        spawn(Species.Weedmon, slot=4, autotalk=True)
        spawn(Species.Weedmon, slot=5, autotalk=True)

@lib.section(38)
def sec38():    # section 38
    use_script(38, Screen.great_canyon_top_area_38)
    engine.music_mode.set(0)
    music(6)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Weedmon)
        load(Species.SandYanmamon)
        spawn(Species.Weedmon, slot=0, autotalk=True)
        spawn(Species.SandYanmamon, slot=1, autotalk=True)
        spawn(Species.SandYanmamon, slot=2, autotalk=True)
    else:
        load(Species.Gotsumon)
        spawn(Species.Gotsumon, slot=3, autotalk=True)
        spawn(Species.Gotsumon, slot=4, autotalk=True)

@lib.section(39)
def sec39():    # section 39
    use_script(39, Screen.great_canyon_bridge)
    engine.music_mode.set(0)
    music(6)
    if ogre_fortress_cleared and canyon_elevator_ridden and not recruited(Species.Shellmon):
        load(Species.Shellmon155)
        spawn(Species.Shellmon155, slot=0)
    load(Species.Goblimon)
    spawn(Species.Goblimon, slot=1, autotalk=True)

@lib.section(40)
def sec40():    # section 40
    use_script(40, Screen.fortress_entrance)
    engine.music_mode.set(0)
    music(6)
    if not recruited(Species.MainCharacter):
        load(Species.Agumon)
        spawn(Species.Agumon, slot=0)

@lib.section(41)
def sec41():    # section 41
    use_script(41, Screen.great_canyon_bot_area_41)
    engine.music_mode.set(0)
    music(6)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Weedmon)
        load(Species.Muchomon)
        spawn(Species.Muchomon, slot=0, autotalk=True)
        spawn(Species.Muchomon, slot=1, autotalk=True)
        spawn(Species.Weedmon, slot=2, autotalk=True)
    else:
        load(Species.Weedmon)
        load(Species.Goblimon)
        spawn(Species.Weedmon, slot=3, autotalk=True)
        spawn(Species.Weedmon, slot=4, autotalk=True)
        spawn(Species.Goblimon, slot=5, autotalk=True)

@lib.section(42)
def sec42():    # section 42
    use_script(42, Screen.great_canyon_bot_area_42)
    engine.music_mode.set(0)
    music(6)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.SandYanmamon)
        load(Species.Weedmon)
        spawn(Species.SandYanmamon, slot=0, autotalk=True)
        spawn(Species.SandYanmamon, slot=1, autotalk=True)
        spawn(Species.Weedmon, slot=2, autotalk=True)
    else:
        load(Species.Gotsumon)
        load(Species.Gururumon)
        spawn(Species.Gotsumon, slot=3, autotalk=True)
        spawn(Species.Gotsumon, slot=4, autotalk=True)
        spawn(Species.Gururumon, slot=5, autotalk=True)

@lib.section(43)
def sec43():    # section 43
    use_script(43, Screen.great_canyon_top_area_43)
    if canyon_bandits_active:
        engine.music_mode.set(2)
        music(6)
        return
    engine.music_mode.set(0)
    music(6)
    load(Species.Goblimon)
    spawn(Species.Goblimon, slot=0, autotalk=True)
    spawn(Species.Goblimon, slot=1, autotalk=True)
    spawn(Species.Goblimon, slot=2, autotalk=True)

@lib.section(44)
def sec44():    # section 44
    use_script(44, Screen.great_canyon_top_area_44)
    engine.music_mode.set(0)
    music(6)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Gotsumon)
        load(Species.Weedmon)
        spawn(Species.Gotsumon, slot=0, autotalk=True)
        spawn(Species.Weedmon, slot=1, autotalk=True)
    else:
        load(Species.Gururumon)
        spawn(Species.Gururumon, slot=2, autotalk=True)
        spawn(Species.Gururumon, slot=3, autotalk=True)

@lib.section(45)
def sec45():    # section 45
    use_script(45, Screen.ogre_fortress_45)
    engine.music_mode.set(1)
    music(8)
    if not ogre_fortress_cleared:
        load(Species.Gabumon139)
        spawn(Species.Gabumon139, slot=0, autotalk=True)
        spawn(Species.Gabumon139, slot=1, autotalk=True)
        spawn(Species.Gabumon139, slot=2, autotalk=True)

@lib.section(46)
def sec46():    # section 46
    use_script(46, Screen.ogre_fortress_46)
    engine.music_mode.set(1)
    music(8)
    if not ogre_fortress_cleared:
        load(Species.Gabumon139)
        load(Species.Agumon)
        spawn(Species.Gabumon139, slot=0, autotalk=True)
        spawn(Species.Gabumon139, slot=1, autotalk=True)
        spawn(Species.Agumon, slot=2, autotalk=True)

@lib.section(47)
def sec47():    # section 47
    use_script(47, Screen.ogre_fortress_47)
    engine.music_mode.set(1)
    music(8)
    if back_dimension_portal == 3:
        load(Species.Machinedramon)
        load(Species.Analogman)
        spawn(Species.Machinedramon, slot=3, autotalk=True)
        spawn(Species.Analogman, slot=4, autotalk=True)
        return
    if not ogre_fortress_cleared:
        load(Species.Agumon)
        spawn(Species.Agumon, slot=0, autotalk=True)
        spawn(Species.Agumon, slot=1, autotalk=True)
        spawn(Species.Agumon, slot=2, autotalk=True)

@lib.section(48)
def sec48():    # section 48
    use_script(48, Screen.ogre_fortress_48)
    engine.music_mode.set(1)
    music(8)
    if not ogre_fortress_cleared:
        engine.music_mode.set(2)
        music(6)
        load(Species.Agumon)
        load(Species.Ogremon154)
        spawn(Species.Agumon, slot=0, autotalk=True)
        spawn(Species.Agumon, slot=1, autotalk=True)
        spawn(Species.Ogremon154, slot=2, autotalk=True)
        spawn(Species.Agumon, slot=3, autotalk=True)
        spawn(Species.Agumon, slot=4, autotalk=True)
    if new_ogre_fortress_cleared and not key_chain_found.ogre_fortress:
        load(Species.Nanimon171)
        spawn(Species.Nanimon171, slot=6)

@lib.section(49)
def sec49():    # section 49
    use_script(49, Screen.monochrome_shop)
    engine.music_mode.set(1)
    music(7)
    if not recruited(Species.Monochromon):
        load(Species.Monochromon165)
        spawn(Species.Monochromon165, slot=0)

@lib.section(50)
def sec50():    # section 50
    use_script(5, Screen.grey_lords_mansion_50)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(0)
def step0():    # section 51
    use_script(50, Screen.grey_lords_mansion_51)
    engine.music_mode.set(1)
    music(10)
    load(Species.Golemon)
    spawn(Species.Golemon, slot=0, autotalk=True)
    spawn(Species.Golemon, slot=1, autotalk=True)

@lib.on_step(1)
def step1():    # section 52
    use_script(51, Screen.grey_lords_mansion_52)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(2)
def step2():    # section 53
    use_script(52, Screen.grey_lords_mansion_53)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(3)
def step3():    # section 54
    use_script(53, Screen.grey_lords_mansion_54)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(4)
def step4():    # section 55
    use_script(54, Screen.grey_lords_mansion_55)
    engine.music_mode.set(1)
    music(10)
    if recruited(Species.SkullGreymon):
        load(Species.Myotismon177)
        spawn(Species.Myotismon177, slot=0)
        return
    if myotismon_freed and not myotismon_missing:
        load(Species.Myotismon177)
        spawn(Species.Myotismon177, slot=0)

@lib.on_step(5)
def step5():    # section 56
    use_script(55, Screen.grey_lords_mansion_56)
    engine.music_mode.set(1)
    music(10)
    load(Species.Soulmon)
    spawn(Species.Soulmon, slot=0, autotalk=True)
    spawn(Species.Soulmon, slot=1, autotalk=True)
    spawn(Species.Soulmon, slot=2, autotalk=True)

@lib.on_step(6)
def step6():    # section 57
    use_script(56, Screen.grey_lords_mansion_57)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(7)
def step7():    # section 58
    use_script(57, Screen.grey_lords_mansion_58)
    engine.music_mode.set(1)
    music(10)
    load(Species.Tsukaimon)
    spawn(Species.Tsukaimon, slot=0, autotalk=True)

@lib.on_step(8)
def step8():    # section 59
    use_script(58, Screen.grey_lords_mansion_59)
    engine.music_mode.set(1)
    music(10)
    load(Species.Tsukaimon)
    spawn(Species.Tsukaimon, slot=0, autotalk=True)

@lib.on_step(9)
def step9():    # section 60
    use_script(59, Screen.grey_lords_mansion_60)
    engine.music_mode.set(1)
    music(10)
    unrecruit(Species.Tekkamon)

@lib.on_step(10)
def step10():    # section 61
    use_script(5, Screen.grey_lords_mansion_61)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(11)
def step11():    # section 62
    use_script(60, Screen.grey_lords_mansion_62)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(12)
def step12():    # section 63
    use_script(61, Screen.grey_lords_mansion_63)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(13)
def step13():    # section 64
    use_script(62, Screen.grey_lords_mansion_64)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(14)
def step14():    # section 65
    use_script(5, Screen.grey_lords_mansion_65)
    engine.music_mode.set(1)
    music(10)

@lib.on_step(15)
def step15():    # section 66
    use_script(63, Screen.mansion_basement)
    engine.music_mode.set(1)
    music(10)
    if back_dimension_portal == 2:
        load(Species.Machinedramon)
        load(Species.Analogman)
        spawn(Species.Machinedramon, slot=1)
        spawn(Species.Analogman, slot=2)
        return
    if not myotismon_freed:
        load(Species.Myotismon177)
        spawn(Species.Myotismon177, slot=0)

@lib.on_step(16)
def step16():    # section 67
    use_script(64, Screen.underground_lab_67)
    engine.music_mode.set(1)
    music(10)
    if not myotismon_joined_city:
        load(Species.Myotismon177)
        load(Species.Bakemon157)
        spawn(Species.Myotismon177, slot=0)
        spawn(Species.Bakemon157, slot=1)

@lib.on_step(17)
def step17():    # section 68
    use_script(65, Screen.underground_lab_68)
    engine.music_mode.set(1)
    music(10)
    load(Species.DarkLizardmon)
    spawn(Species.DarkLizardmon, slot=1, autotalk=True)
    spawn(Species.DarkLizardmon, slot=2, autotalk=True)
    spawn(Species.DarkLizardmon, slot=3, autotalk=True)
    spawn(Species.DarkLizardmon, slot=4, autotalk=True)
    spawn(Species.DarkLizardmon, slot=5, autotalk=True)
    if not underground_lab_tekkamon_beaten:
        load(Species.Tekkamon)
        spawn(Species.Tekkamon, slot=0, autotalk=True)

@lib.on_step(18)
def step18():    # section 69
    use_script(66, Screen.gear_savanna_69)
    engine.music_mode.set(0)
    music(11)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.ShimaUnimon)
        spawn(Species.ShimaUnimon, slot=0, autotalk=True)
        spawn(Species.ShimaUnimon, slot=1, autotalk=True)
    else:
        load(Species.Tsukaimon)
        load(Species.NiseDrimogemon)
        spawn(Species.Tsukaimon, slot=2, autotalk=True)
        spawn(Species.NiseDrimogemon, slot=3, autotalk=True)

@lib.on_step(19)
def step19():    # section 70
    use_script(67, Screen.gear_savanna_70)
    engine.music_mode.set(0)
    music(11)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Psychemon)
        spawn(Species.Psychemon, slot=0, autotalk=True)
        spawn(Species.Psychemon, slot=1, autotalk=True)
        load(Species.ShimaUnimon)
        spawn(Species.ShimaUnimon, slot=2, autotalk=True)
    else:
        load(Species.NiseDrimogemon)
        spawn(Species.NiseDrimogemon, slot=3, autotalk=True)
        spawn(Species.NiseDrimogemon, slot=4, autotalk=True)
        load(Species.Shamamon)
        spawn(Species.Shamamon, slot=5, autotalk=True)

@lib.on_step(20)
def step20():    # section 71
    use_script(68, Screen.gear_savanna_71)
    engine.music_mode.set(0)
    music(11)
    if not recruited(Species.Elecmon):
        load(Species.Elecmon140)
        spawn(Species.Elecmon140, slot=0)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Shamamon)
        load(Species.Akatorimon)
        spawn(Species.Akatorimon, slot=1, autotalk=True)
        spawn(Species.Akatorimon, slot=2, autotalk=True)
        spawn(Species.Shamamon, slot=3, autotalk=True)
    else:
        load(Species.Psychemon)
        load(Species.Shamamon)
        spawn(Species.Psychemon, slot=4, autotalk=True)
        spawn(Species.Psychemon, slot=5, autotalk=True)
        spawn(Species.Shamamon, slot=6, autotalk=True)

@lib.on_step(21)
def step21():    # section 72
    use_script(69, Screen.gear_savanna_72)
    engine.music_mode.set(0)
    music(11)
    if not recruited(Species.Patamon):
        load(Species.Patamon151)
        spawn(Species.Patamon151, slot=0, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.ShimaUnimon)
        load(Species.Shamamon)
        spawn(Species.ShimaUnimon, slot=1, autotalk=True)
        spawn(Species.Shamamon, slot=2, autotalk=True)
    else:
        load(Species.Shamamon)
        spawn(Species.Shamamon, slot=3, autotalk=True)
        spawn(Species.Shamamon, slot=4, autotalk=True)

@lib.on_step(22)
def step22():    # section 73
    use_script(70, Screen.gear_savanna_73)
    engine.music_mode.set(0)
    music(11)
    if not recruited(Species.Biyomon):
        gear_savanna.chase_stage.set(0)
        load(Species.Biyomon163)
        spawn(Species.Biyomon163, slot=0, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.ShimaUnimon)
        load(Species.Akatorimon)
        spawn(Species.ShimaUnimon, slot=1, autotalk=True)
        spawn(Species.ShimaUnimon, slot=2, autotalk=True)
        spawn(Species.Akatorimon, slot=3, autotalk=True)
    else:
        load(Species.Shamamon)
        load(Species.Tsukaimon)
        spawn(Species.Shamamon, slot=4, autotalk=True)
        spawn(Species.Shamamon, slot=5, autotalk=True)
        spawn(Species.Tsukaimon, slot=6, autotalk=True)

@lib.on_step(23)
def step23():    # section 74
    use_script(71, Screen.gear_savanna_74)
    engine.music_mode.set(0)
    music(11)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Psychemon)
        load(Species.Akatorimon)
        spawn(Species.Psychemon, slot=0, autotalk=True)
        spawn(Species.Psychemon, slot=1, autotalk=True)
        spawn(Species.Akatorimon, slot=2, autotalk=True)
    else:
        load(Species.Tsukaimon)
        load(Species.Shamamon)
        spawn(Species.Tsukaimon, slot=3, autotalk=True)
        spawn(Species.Tsukaimon, slot=4, autotalk=True)
        spawn(Species.Shamamon, slot=5, autotalk=True)

@lib.on_step(24)
def step24():    # section 75
    use_script(72, Screen.gear_savanna_75)
    engine.music_mode.set(0)
    music(11)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Psychemon)
        spawn(Species.Psychemon, slot=2, autotalk=True)
        spawn(Species.Psychemon, slot=3, autotalk=True)
    else:
        load(Species.Shamamon)
        spawn(Species.Shamamon, slot=4, autotalk=True)
        spawn(Species.Shamamon, slot=5, autotalk=True)

@lib.on_step(25)
def step25():    # section 76
    use_script(73, Screen.gear_savanna_76)
    engine.music_mode.set(0)
    music(11)
    if not leomon_rescue_seen:
        load(Species.Goblimon125)
        load(Species.Patamon151)
        load(Species.Leomon166)
        return
    load(Species.Shamamon)
    spawn(Species.Shamamon, slot=3, autotalk=True)
    spawn(Species.Shamamon, slot=4, autotalk=True)

@lib.on_step(26)
def step26():    # section 77
    use_script(74, Screen.gear_savanna_77)
    engine.music_mode.set(0)
    music(11)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.ShimaUnimon)
        load(Species.Shamamon)
        spawn(Species.ShimaUnimon, slot=0, autotalk=True)
        spawn(Species.Shamamon, slot=1, autotalk=True)
        spawn(Species.Shamamon, slot=2, autotalk=True)
    else:
        load(Species.NiseDrimogemon)
        load(Species.Shamamon)
        spawn(Species.NiseDrimogemon, slot=3, autotalk=True)
        spawn(Species.Shamamon, slot=4, autotalk=True)
        spawn(Species.Shamamon, slot=5, autotalk=True)

@lib.on_step(27)
def step27():    # section 78
    use_script(75, Screen.gear_savanna_78)
    engine.music_mode.set(0)
    music(11)
    if not recruited(Species.Leomon) and leomon_rescue_seen:
        load(Species.Leomon166)
        spawn(Species.Leomon166, slot=0, autotalk=True)

@lib.on_step(28)
def step28():    # section 79
    use_script(76, Screen.ancient_dino_region)
    engine.music_mode.set(0)
    music(14)
    load(Species.Tyrannomon132)
    if not dino_region_guard_beaten:
        spawn(Species.Tyrannomon132, slot=0, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Vermilimon)
        spawn(Species.Vermilimon, slot=1, autotalk=True)
        spawn(Species.Vermilimon, slot=2, autotalk=True)
    else:
        load(Species.Yanmamon)
        spawn(Species.Yanmamon, slot=3, autotalk=True)
        spawn(Species.Yanmamon, slot=4, autotalk=True)

@lib.on_use(0)
def use0():    # section 80
    use_script(77, Screen.ancient_glacial_region_80)
    engine.music_mode.set(0)
    music(14)
    load(Species.Vermilimon)
    load(Species.Yanmamon)
    if clock.hour >= 7 and clock.hour < 19:
        spawn(Species.Vermilimon, slot=0, autotalk=True)
        spawn(Species.Yanmamon, slot=1, autotalk=True)
        spawn(Species.Vermilimon, slot=2, autotalk=True)
    else:
        spawn(Species.Yanmamon, slot=3, autotalk=True)
        spawn(Species.Vermilimon, slot=4, autotalk=True)
        spawn(Species.Vermilimon, slot=5, autotalk=True)

@lib.on_use(1)
def use1():    # section 81
    use_script(78, Screen.ancient_glacial_region_81)
    engine.music_mode.set(0)
    music(14)
    load(Species.Monochromon165)
    load(Species.Saberdramon)
    load(Species.Brachiomon)
    spawn(Species.Monochromon165, slot=0)
    spawn(Species.Saberdramon, slot=1)
    spawn(Species.Brachiomon, slot=2)
    spawn(Species.Brachiomon, slot=3)

@lib.on_use(2)
def use2():    # section 82
    use_script(79, Screen.ancient_glacial_region_82)
    engine.music_mode.set(0)
    music(14)
    load(Species.Tyrannomon132)
    load(Species.MasterTyrannomon)
    if not glacial_tyrannomon_let_through:
        spawn(Species.Tyrannomon132, slot=0)
    if glacial_tyrannomon_let_through and not recruited(Species.Tyrannomon):
        spawn(Species.Tyrannomon132, slot=1)
    if recruited(Species.Tyrannomon):
        spawn(Species.MasterTyrannomon, slot=3)

@lib.on_use(3)
def use3():    # section 83
    use_script(80, Screen.ancient_speedy_region_83)
    engine.music_mode.set(0)
    music(13)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Gotsumon)
        load(Species.Saberdramon)
        spawn(Species.Gotsumon, slot=0, autotalk=True)
        spawn(Species.Gotsumon, slot=1, autotalk=True)
        spawn(Species.Saberdramon, slot=2, autotalk=True)
    else:
        load(Species.DarkLizardmon)
        load(Species.Gotsumon)
        spawn(Species.DarkLizardmon, slot=3, autotalk=True)
        spawn(Species.DarkLizardmon, slot=4, autotalk=True)
        spawn(Species.Gotsumon, slot=5, autotalk=True)

@lib.on_use(4)
def use4():    # section 84
    use_script(5, Screen.ancient_speedy_region_84)
    engine.music_mode.set(0)
    music(13)

@lib.on_use(5)
def use5():    # section 85
    use_script(81, Screen.ancient_speedy_region_85)
    engine.music_mode.set(0)
    music(13)
    load(Species.Saberdramon)
    spawn(Species.Saberdramon, slot=0, autotalk=True)

@lib.on_use(6)
def use6():    # section 86
    use_script(82, Screen.ancient_speedy_region_86)
    engine.music_mode.set(0)
    music(13)
    if not meteormon_checked:
        load(Species.Meteormon)
        spawn(Species.Meteormon, slot=0)
    if meteormon_checked and not key_chain_found.speedy_region and recruited(Species.Tyrannomon):
        load(Species.Nanimon171)
        spawn(Species.Nanimon171, slot=1)

@lib.on_use(7)
def use7():    # section 87
    use_script(83, Screen.ancient_speedy_region_87)
    engine.music_mode.set(0)
    music(13)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Saberdramon)
        spawn(Species.Saberdramon, slot=0, autotalk=True)
        spawn(Species.Saberdramon, slot=1, autotalk=True)
    else:
        load(Species.DarkLizardmon)
        spawn(Species.DarkLizardmon, slot=2, autotalk=True)
        spawn(Species.DarkLizardmon, slot=3, autotalk=True)

@lib.on_use(8)
def use8():    # section 88
    use_script(84, Screen.freezeland_88)
    engine.music_mode.set(0)
    music(15)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.SnowAgumon)
        load(Species.SnowGoblimon)
        spawn(Species.SnowAgumon, slot=0, autotalk=True)
        spawn(Species.SnowGoblimon, slot=1, autotalk=True)
    else:
        load(Species.IceDevimon)
        spawn(Species.IceDevimon, slot=2, autotalk=True)
        spawn(Species.IceDevimon, slot=3, autotalk=True)

@lib.on_use(9)
def use9():    # section 89
    use_script(85, Screen.freezeland_89)
    engine.music_mode.set(0)
    music(15)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Hyogamon)
        spawn(Species.Hyogamon, slot=0, autotalk=True)
        spawn(Species.Hyogamon, slot=1, autotalk=True)
    else:
        load(Species.IceDevimon)
        spawn(Species.IceDevimon, slot=2, autotalk=True)
        spawn(Species.IceDevimon, slot=3, autotalk=True)

@lib.on_use(10)
def use10():    # section 90
    use_script(86, Screen.freezeland_90)
    engine.music_mode.set(0)
    music(15)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.SnowAgumon)
        spawn(Species.SnowAgumon, slot=0, autotalk=True)
        spawn(Species.SnowAgumon, slot=1, autotalk=True)
    else:
        load(Species.SnowGoblimon)
        spawn(Species.SnowGoblimon, slot=2, autotalk=True)
        spawn(Species.SnowGoblimon, slot=3, autotalk=True)

@lib.on_use(11)
def use11():    # section 91
    use_script(87, Screen.freezeland_91)
    engine.music_mode.set(0)
    music(15)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Hyogamon)
        load(Species.SnowGoblimon)
        spawn(Species.SnowGoblimon, slot=0, autotalk=True)
        spawn(Species.SnowGoblimon, slot=1, autotalk=True)
        spawn(Species.Hyogamon, slot=2, autotalk=True)
    else:
        load(Species.IceDevimon)
        spawn(Species.IceDevimon, slot=3, autotalk=True)
        spawn(Species.IceDevimon, slot=4, autotalk=True)
        spawn(Species.IceDevimon, slot=5, autotalk=True)

@lib.on_use(12)
def use12():    # section 92
    use_script(88, Screen.freezeland_92)
    engine.music_mode.set(0)
    music(15)

@lib.on_use(13)
def use13():    # section 93
    use_script(89, Screen.freezeland_93)
    engine.music_mode.set(0)
    music(15)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Hyogamon)
        spawn(Species.Hyogamon, slot=0, autotalk=True)
        spawn(Species.Hyogamon, slot=1, autotalk=True)
        spawn(Species.Hyogamon, slot=2, autotalk=True)
    else:
        load(Species.IceDevimon)
        load(Species.Hyogamon)
        spawn(Species.IceDevimon, slot=3, autotalk=True)
        spawn(Species.IceDevimon, slot=4, autotalk=True)
        spawn(Species.Hyogamon, slot=5, autotalk=True)

@lib.on_use(14)
def use14():    # section 94
    use_script(90, Screen.freezeland_94)
    engine.music_mode.set(0)
    music(15)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.SnowGoblimon)
        spawn(Species.SnowGoblimon, slot=0, autotalk=True)
        spawn(Species.SnowGoblimon, slot=1, autotalk=True)
    else:
        load(Species.IceDevimon)
        spawn(Species.IceDevimon, slot=2, autotalk=True)
        spawn(Species.IceDevimon, slot=3, autotalk=True)

@lib.on_use(15)
def use15():    # section 95
    use_script(91, Screen.freezeland_95)
    engine.music_mode.set(0)
    music(15)
    if not garurumon_duel_promised:
        load(Species.Garurumon144)
        spawn(Species.Garurumon144, slot=0)
        return
    if garurumon_duel_promised and clock.hour >= 15 and clock.hour < 17 and not recruited(Species.Garurumon) and garurumon_promise_days >= 1:
        load(Species.Garurumon144)
        spawn(Species.Garurumon144, slot=5)
        return
    if garurumon_duel_promised and date_hour >= 17 and not recruited(Species.Garurumon) and garurumon_promise_days >= 1:
        load(Species.Garurumon144)
        spawn(Species.Garurumon144, slot=0)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.SnowAgumon)
        spawn(Species.SnowAgumon, slot=1, autotalk=True)
        spawn(Species.SnowAgumon, slot=2, autotalk=True)
    else:
        load(Species.Hyogamon)
        spawn(Species.Hyogamon, slot=3, autotalk=True)
        spawn(Species.Hyogamon, slot=4, autotalk=True)

@lib.on_use(16)
def use16():    # section 96
    use_script(92, Screen.freezeland_96)
    engine.music_mode.set(0)
    music(15)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.SnowAgumon)
        spawn(Species.SnowAgumon, slot=0, autotalk=True)
        spawn(Species.SnowAgumon, slot=1, autotalk=True)
    else:
        load(Species.SnowGoblimon)
        spawn(Species.SnowGoblimon, slot=2, autotalk=True)
        spawn(Species.SnowGoblimon, slot=3, autotalk=True)

@lib.on_use(17)
def use17():    # section 97
    use_script(93, Screen.ice_sanctuary_97)
    engine.music_mode.set(1)
    music(17)

@lib.on_use(18)
def use18():    # section 98
    use_script(94, Screen.ice_sanctuary_98)
    engine.music_mode.set(1)
    music(18)
    load(Species.Icemon)
    load(Species.BlueMeramon)
    spawn(Species.Icemon, slot=0, autotalk=True)
    spawn(Species.Icemon, slot=1, autotalk=True)
    spawn(Species.BlueMeramon, slot=2, autotalk=True)

@lib.on_use(19)
def use19():    # section 99
    use_script(95, Screen.ice_sanctuary_99)
    engine.music_mode.set(1)
    music(18)

@lib.on_use(20)
def use20():    # section 100
    use_script(96, Screen.ice_sanctuary_100)
    engine.music_mode.set(1)
    music(18)
    load(Species.Hyogamon)
    load(Species.Gururumon)
    spawn(Species.Hyogamon, slot=0, autotalk=True)
    spawn(Species.Hyogamon, slot=1, autotalk=True)
    spawn(Species.Gururumon, slot=2, autotalk=True)

@lib.on_use(21)
def use21():    # section 101
    use_script(97, Screen.ice_sanctuary_101)
    engine.music_mode.set(1)
    music(18)
    load(Species.BlueMeramon)
    load(Species.Icemon)
    spawn(Species.BlueMeramon, slot=0, autotalk=True)
    spawn(Species.BlueMeramon, slot=1, autotalk=True)
    spawn(Species.Icemon, slot=2, autotalk=True)
    spawn(Species.Icemon, slot=3, autotalk=True)

@lib.on_use(22)
def use22():    # section 102
    use_script(98, Screen.ice_sanctuary_102)
    engine.music_mode.set(1)
    music(18)
    load(Species.Icemon)
    load(Species.Hyogamon)
    spawn(Species.Icemon, slot=0, autotalk=True)
    spawn(Species.Hyogamon, slot=1, autotalk=True)
    spawn(Species.Hyogamon, slot=2, autotalk=True)

@lib.on_use(23)
def use23():    # section 103
    use_script(99, Screen.ice_sanctuary_103)
    engine.music_mode.set(1)
    music(18)
    load(Species.Gururumon)
    spawn(Species.Gururumon, slot=0, autotalk=True)
    spawn(Species.Gururumon, slot=1, autotalk=True)

@lib.on_use(24)
def use24():    # section 104
    use_script(100, Screen.ice_sanctuary_104)
    engine.music_mode.set(1)
    music(18)
    load(Species.Machinedramon)
    load(Species.Analogman)
    spawn(Species.Machinedramon, slot=0, autotalk=True)
    spawn(Species.Analogman, slot=1, autotalk=True)

@lib.on_use(25)
def use25():    # section 105
    use_script(101, Screen.beetle_land_105)
    engine.music_mode.set(0)
    music(25)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Tentomon)
        load(Species.Dokunemon)
        spawn(Species.Tentomon, slot=0, autotalk=True)
        spawn(Species.Tentomon, slot=1, autotalk=True)
        spawn(Species.Tentomon, slot=2, autotalk=True)
        spawn(Species.Dokunemon, slot=3, autotalk=True)
    else:
        load(Species.Tentomon)
        load(Species.Dokunemon)
        spawn(Species.Dokunemon, slot=4, autotalk=True)
        spawn(Species.Dokunemon, slot=5, autotalk=True)
        spawn(Species.Tentomon, slot=6, autotalk=True)
        spawn(Species.Tentomon, slot=7, autotalk=True)

@lib.on_use(26)
def use26():    # section 106
    use_script(102, Screen.beetle_land_106)
    engine.music_mode.set(0)
    music(25)
    load(Species.Tentomon)
    spawn(Species.Tentomon, slot=0)

@lib.on_use(27)
def use27():    # section 107
    use_script(103, Screen.beetle_land_107)
    engine.music_mode.set(0)
    music(25)
    if not recruited(Species.Kabuterimon):
        load(Species.Kabuterimon141)
        spawn(Species.Kabuterimon141, slot=0)
    load(Species.Kabuterimon141)
    spawn(Species.Kabuterimon141, slot=1)
    spawn(Species.Kabuterimon141, slot=2)

@lib.on_use(28)
def use28():    # section 108
    use_script(104, Screen.beetle_land_108)
    engine.music_mode.set(0)
    music(25)
    if not recruited(Species.Kuwagamon):
        load(Species.Kuwagamon169)
        spawn(Species.Kuwagamon169, slot=0)
    load(Species.Kuwagamon169)
    spawn(Species.Kuwagamon169, slot=1)
    spawn(Species.Kuwagamon169, slot=2)

@lib.on_use(29)
def use29():    # section 109
    use_script(105, Screen.native_forest_109)
    engine.music_mode.set(0)
    music(1)
    if not recruited(Species.Agumon):
        load(Species.Agumon)
        spawn(Species.Agumon, slot=2, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.ModokiBetamon)
        spawn(Species.ModokiBetamon, slot=3, autotalk=True)
        spawn(Species.ModokiBetamon, slot=4, autotalk=True)
    else:
        load(Species.Dokunemon)
        spawn(Species.Dokunemon, slot=0, autotalk=True)
        spawn(Species.Dokunemon, slot=1, autotalk=True)

@lib.section(110)
def sec110():    # section 110
    use_script(106, Screen.native_forest_110)
    engine.music_mode.set(0)
    music(1)
    if debug_mode:
        return
    load(Species.Sukamon)
    spawn(Species.Sukamon, slot=0)
    spawn(Species.Sukamon, slot=1)

@lib.section(111)
def sec111():    # section 111
    use_script(107, Screen.native_forest_111)
    engine.music_mode.set(0)
    music(1)
    if debug_mode:
        return
    load(Species.Sukamon)
    spawn(Species.Sukamon, slot=0)
    spawn(Species.Sukamon, slot=1)

@lib.section(112)
def sec112():    # section 112
    use_script(108, Screen.green_gym)
    engine.music_mode.set(0)
    music(1)
    load(Species.Koromon)
    spawn(Species.Koromon, slot=0)
    if recruited(Species.Kabuterimon):
        load(Species.Kabuterimon141)
        spawn(Species.Kabuterimon141, slot=1)
    if recruited(Species.Kuwagamon):
        load(Species.Kuwagamon169)
        spawn(Species.Kuwagamon169, slot=2)

@lib.section(113)
def sec113():    # section 113
    use_script(109, Screen.leomon_ancestors_cave_113)
    engine.music_mode.set(1)
    music(4)
    if recruited(Species.Leomon) and not key_chain_found.leomon_cave:
        load(Species.Nanimon171)
        spawn(Species.Nanimon171, slot=0)

@lib.section(114)
def sec114():    # section 114
    use_script(110, Screen.leomon_ancestors_cave_114)
    engine.music_mode.set(1)
    music(4)
    load(Species.Drimogemon158)
    spawn(Species.Drimogemon158, slot=0)

@lib.section(115)
def sec115():    # section 115
    use_script(111, Screen.misty_trees_115)
    engine.music_mode.set(0)
    music(20)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Fugamon)
        load(Species.MoriShellmon)
        spawn(Species.Fugamon, slot=0, autotalk=True)
        spawn(Species.Fugamon, slot=1, autotalk=True)
        spawn(Species.MoriShellmon, slot=2, autotalk=True)
    else:
        load(Species.DarkLizardmon)
        load(Species.Tsukaimon)
        spawn(Species.DarkLizardmon, slot=3, autotalk=True)
        spawn(Species.DarkLizardmon, slot=4, autotalk=True)
        spawn(Species.Tsukaimon, slot=5, autotalk=True)

@lib.section(116)
def sec116():    # section 116
    use_script(112, Screen.misty_trees_116)
    engine.music_mode.set(0)
    music(20)
    if not misty_trees_fog_spell_cast and not cherrymon_met:
        load(Species.MoriShellmon)
        spawn(Species.MoriShellmon, slot=0, autotalk=True)
        spawn(Species.MoriShellmon, slot=1, autotalk=True)
        spawn(Species.MoriShellmon, slot=2, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Fugamon)
        spawn(Species.Fugamon, slot=3, autotalk=True)
        spawn(Species.Fugamon, slot=4, autotalk=True)
    else:
        load(Species.DarkLizardmon)
        spawn(Species.DarkLizardmon, slot=5, autotalk=True)
        spawn(Species.DarkLizardmon, slot=6, autotalk=True)

@lib.section(117)
def sec117():    # section 117
    use_script(113, Screen.misty_trees_117)
    engine.music_mode.set(0)
    music(20)
    raw.store_date(date_year)
    misty_trees_dawn_visitor_spawned.clear()
    if date_hour >= 4 and date_hour <= 6 and not recruited(Species.Kokatorimon):
        load(Species.Kokatorimon168)
        spawn(Species.Kokatorimon168, slot=0, autotalk=True)
        misty_trees_dawn_visitor_spawned.set()
        return
    if not misty_trees_fog_spell_cast and not cherrymon_met:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=1, autotalk=True)
        spawn(Species.Goblimon, slot=2, autotalk=True)
        spawn(Species.Goblimon, slot=3, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.MoriShellmon)
        spawn(Species.MoriShellmon, slot=4, autotalk=True)
        spawn(Species.MoriShellmon, slot=5, autotalk=True)
    else:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=6, autotalk=True)
        spawn(Species.Goblimon, slot=7, autotalk=True)

@lib.section(118)
def sec118():    # section 118
    use_script(114, Screen.misty_trees_118)
    engine.music_mode.set(0)
    music(20)
    if not misty_trees_fog_spell_cast and not cherrymon_met:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=0, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Fugamon)
        load(Species.MoriShellmon)
        spawn(Species.Fugamon, slot=1, autotalk=True)
        spawn(Species.MoriShellmon, slot=2, autotalk=True)
    else:
        load(Species.Saberdramon)
        spawn(Species.Saberdramon, slot=3, autotalk=True)
        spawn(Species.Saberdramon, slot=4, autotalk=True)

@lib.section(119)
def sec119():    # section 119
    use_script(115, Screen.misty_trees_119)
    engine.music_mode.set(0)
    music(20)
    load(Species.Cherrymon)
    spawn(Species.Cherrymon, slot=0)

@lib.section(120)
def sec120():    # section 120
    use_script(116, Screen.misty_trees_120)
    engine.music_mode.set(0)
    music(20)
    if not recruited(Species.Gabumon):
        load(Species.Gabumon139)
        spawn(Species.Gabumon139, slot=0, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Goblimon)
        spawn(Species.Goblimon, slot=1, autotalk=True)
        spawn(Species.Goblimon, slot=2, autotalk=True)
    else:
        load(Species.Tsukaimon)
        load(Species.DarkLizardmon)
        spawn(Species.Tsukaimon, slot=3, autotalk=True)
        spawn(Species.DarkLizardmon, slot=4, autotalk=True)

@lib.section(121)
def sec121():    # section 121
    use_script(117, Screen.misty_trees_121)
    engine.music_mode.set(0)
    music(20)
    if not misty_trees_fog_spell_cast and not cherrymon_met:
        load(Species.Fugamon)
        spawn(Species.Fugamon, slot=0, autotalk=True)
        spawn(Species.Fugamon, slot=1, autotalk=True)
        spawn(Species.Fugamon, slot=2, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Goblimon)
        load(Species.Fugamon)
        spawn(Species.Goblimon, slot=3, autotalk=True)
        spawn(Species.Goblimon, slot=4, autotalk=True)
        spawn(Species.Fugamon, slot=5, autotalk=True)
    else:
        load(Species.Tsukaimon)
        spawn(Species.Tsukaimon, slot=6, autotalk=True)
        spawn(Species.Tsukaimon, slot=7, autotalk=True)

@lib.section(122)
def sec122():    # section 122
    use_script(118, Screen.lava_cave_122)

@lib.section(123)
def sec123():    # section 123
    use_script(119, Screen.lava_cave_123)
    load(Species.DemiMeramon)
    spawn(Species.DemiMeramon, slot=0)

@lib.section(124)
def sec124():    # section 124
    use_script(120, Screen.lava_cave_124)

@lib.section(125)
def sec125():    # section 125
    use_script(121, Screen.lava_cave_125)
    load(Species.DemiMeramon)
    spawn(Species.DemiMeramon, slot=0)

@lib.section(126)
def sec126():    # section 126
    use_script(5, Screen.drill_tunnel_126)
    engine.music_mode.set(1)
    music(4)

@lib.section(127)
def sec127():    # section 127
    use_script(122, Screen.great_canyon_127)
    engine.music_mode.set(0)
    music(6)
    load(Species.Goblimon)
    load(Species.Shellmon155)
    if ogre_fortress_elevator_ridden and shellmon_plea_heard and not recruited(Species.Shellmon):
        spawn(Species.Shellmon155, slot=0)
    spawn(Species.Goblimon, slot=1, autotalk=True)

@lib.section(128)
def sec128():    # section 128
    use_script(123, Screen.great_canyon_128)
    engine.music_mode.set(0)
    music(6)
    if canyon_bandits_active:
        return
    load(Species.Goblimon)
    spawn(Species.Goblimon, slot=0, autotalk=True)
    spawn(Species.Goblimon, slot=1, autotalk=True)
    spawn(Species.Goblimon, slot=2, autotalk=True)

@lib.section(129)
def sec129():    # section 129
    use_script(124, Screen.great_canyon_129)
    engine.music_mode.set(0)
    music(6)
    load(Species.Birdramon143)

@lib.section(130)
def sec130():    # section 130
    use_script(125, Screen.ogre_fortress_130)
    engine.music_mode.set(1)
    music(8)

@lib.section(131)
def sec131():    # section 131
    use_script(126, Screen.gear_savanna_131)
    engine.music_mode.set(0)
    music(11)
    load(Species.MarketManager)
    spawn(Species.MarketManager, slot=0)
    spawn(Species.MarketManager, slot=1)

@lib.section(132)
def sec132():    # section 132
    use_script(127, Screen.freezeland_132)
    engine.music_mode.set(0)
    music(15)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Hyogamon)
        spawn(Species.Hyogamon, slot=0, autotalk=True)
        spawn(Species.Hyogamon, slot=1, autotalk=True)
    else:
        load(Species.IceDevimon)
        spawn(Species.IceDevimon, slot=2, autotalk=True)
        spawn(Species.IceDevimon, slot=3, autotalk=True)

@lib.section(133)
def sec133():    # section 133
    use_script(128, Screen.freezeland_133)
    engine.music_mode.set(0)
    music(15)
    load(Species.Mojyamon170)
    if not mojyamon_left.set2:
        spawn(Species.Mojyamon170, slot=0)
    if not mojyamon_left.set3:
        spawn(Species.Mojyamon170, slot=1)

@lib.section(134)
def sec134():    # section 134
    use_script(129, Screen.freezeland_134)
    engine.music_mode.set(0)
    music(15)
    if not recruited(Species.Penguinmon):
        load(Species.Penguinmon)
        spawn(Species.Penguinmon, slot=0)
    if not mojyamon_left.set1:
        load(Species.Mojyamon170)
        spawn(Species.Mojyamon170, slot=1)

@lib.section(135)
def sec135():    # section 135
    use_script(130, Screen.freezeland_135)
    engine.music_mode.set(0)
    music(15)
    if ogre_fortress_cleared and not recruited(Species.Whamon):
        load(Species.Whamon146)
        spawn(Species.Whamon146, slot=1)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.SnowGoblimon)
        spawn(Species.SnowGoblimon, slot=0, autotalk=True)
    else:
        load(Species.IceDevimon)
        spawn(Species.IceDevimon, slot=2, autotalk=True)

@lib.section(136)
def sec136():    # section 136
    use_script(131, Screen.freezeland_136)
    engine.music_mode.set(1)
    music(16)
    if curling_opponent == 1:
        load(Species.MetalGreymonVirus149)
        spawn(Species.MetalGreymonVirus149, slot=1)
        return
    if curling_match_pending == 1:
        load(Species.Penguinmon)
        spawn(Species.Penguinmon, slot=0)

@lib.section(137)
def sec137():    # section 137
    use_script(132, Screen.freezeland_137)
    engine.music_mode.set(4)
    music(15)
    if not recruited(Species.Frigimon):
        load(Species.Frigimon145)
        spawn(Species.Frigimon145, slot=0)

@lib.section(138)
def sec138():    # section 138
    use_script(133, Screen.geko_swamp_138)
    engine.music_mode.set(0)
    music(19)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Yanmamon)
        spawn(Species.Yanmamon, slot=0, autotalk=True)
        spawn(Species.Yanmamon, slot=1, autotalk=True)
        spawn(Species.Yanmamon, slot=2, autotalk=True)
    else:
        load(Species.Gekomon)
        spawn(Species.Gekomon, slot=3, autotalk=True)
        spawn(Species.Gekomon, slot=4, autotalk=True)
        spawn(Species.Gekomon, slot=5, autotalk=True)

@lib.section(139)
def sec139():    # section 139
    use_script(134, Screen.geko_swamp_139)
    engine.music_mode.set(0)
    music(19)
    roll = random.roll(2)
    if roll <= 0 and not recruited(Species.Otamamon):
        load(Species.Otamamon)
        spawn(Species.Otamamon, slot=4)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Yanmamon)
        spawn(Species.Yanmamon, slot=0, autotalk=True)
        spawn(Species.Yanmamon, slot=1, autotalk=True)
    else:
        load(Species.Gekomon)
        spawn(Species.Gekomon, slot=2, autotalk=True)
        spawn(Species.Gekomon, slot=3, autotalk=True)

@lib.section(140)
def sec140():    # section 140
    use_script(5, Screen.volume_villa_140)
    engine.music_mode.set(0)
    music(19)

@lib.section(141)
def sec141():    # section 141
    use_script(135, Screen.volume_villa_141)
    engine.music_mode.set(0)
    music(19)
    load(Species.ShogunGekomon)
    load(Species.Gekomon)
    spawn(Species.ShogunGekomon, slot=0)
    spawn(Species.Gekomon, slot=1)
    spawn(Species.Gekomon, slot=2)
    spawn(Species.Gekomon, slot=3)

@lib.section(142)
def sec142():    # section 142
    use_script(136, Screen.secret_beach_cave_142)
    engine.music_mode.set(7)
    music(26)
    load(Species.Whamon146)
    spawn(Species.Whamon146, slot=0)

@lib.section(143)
def sec143():    # section 143
    use_script(137, Screen.secret_beach_cave_143)
    engine.music_mode.set(8)
    music(26)
    if not new_ogre_fortress_cleared:
        load(Species.Ogremon154)
        load(Species.Gabumon139)
        load(Species.WaruSeadramon)
        spawn(Species.Ogremon154, slot=0)
        spawn(Species.Gabumon139, slot=1)
        spawn(Species.Gabumon139, slot=2)

@lib.section(144)
def sec144():    # section 144
    use_script(138, Screen.toy_town)
    if toy_tale_heard:
        engine.music_mode.set(6)
        music(21)
    else:
        engine.music_mode.set(5)
        music(21)
    if toy_tale_heard:
        load(Species.ClearAgumon)
        load(Species.ToyAgumon)
        load(Species.Tankmon)
        spawn(Species.ClearAgumon, slot=0)
        spawn(Species.ToyAgumon, slot=1)
        spawn(Species.Tankmon, slot=2)

@lib.section(145)
def sec145():    # section 145
    use_script(139, Screen.costume_house)
    if toy_tale_heard:
        engine.music_mode.set(6)
        music(21)
    else:
        engine.music_mode.set(5)
        music(21)
    if toy_tale_heard or partner.species == Species.Monzaemon:
        return
    load(Species.Monzaemon138)
    spawn(Species.Monzaemon138, slot=0)

@lib.section(146)
def sec146():    # section 146
    use_script(140, Screen.robot_house)
    if toy_tale_heard:
        engine.music_mode.set(6)
        music(21)
    else:
        engine.music_mode.set(5)
        music(21)
    load(Species.Tinmon)
    spawn(Species.Tinmon, slot=0)
    spawn(Species.Tinmon, slot=2)
    spawn(Species.Tinmon, slot=3)

@lib.section(147)
def sec147():    # section 147
    use_script(141, Screen.toy_mansion_147)
    if toy_tale_heard:
        engine.music_mode.set(6)
        music(21)
    else:
        engine.music_mode.set(5)
        music(21)

@lib.section(148)
def sec148():    # section 148
    use_script(142, Screen.toy_mansion_148)
    if toy_tale_heard:
        engine.music_mode.set(6)
        music(21)
    else:
        engine.music_mode.set(5)
        music(21)
    load(Species.ToyAgumon)
    spawn(Species.ToyAgumon, slot=0, autotalk=True)
    spawn(Species.ToyAgumon, slot=1, autotalk=True)
    spawn(Species.ToyAgumon, slot=2, autotalk=True)

@lib.section(149)
def sec149():    # section 149
    use_script(143, Screen.toy_mansion_149)
    if toy_tale_heard:
        engine.music_mode.set(6)
        music(21)
    else:
        engine.music_mode.set(5)
        music(21)
    load(Species.Tankmon)
    spawn(Species.Tankmon, slot=0, autotalk=True)
    spawn(Species.Tankmon, slot=1, autotalk=True)

@lib.section(150)
def sec150():    # section 150
    use_script(144, Screen.toy_mansion_150)
    if toy_tale_heard:
        engine.music_mode.set(6)
        music(21)
    else:
        engine.music_mode.set(5)
        music(21)
    load(Species.ClearAgumon)
    spawn(Species.ClearAgumon, slot=0, autotalk=True)
    spawn(Species.ClearAgumon, slot=1, autotalk=True)
    spawn(Species.ClearAgumon, slot=2, autotalk=True)

@lib.section(151)
def sec151():    # section 151
    use_script(145, Screen.toy_mansion_151)
    if toy_tale_heard:
        engine.music_mode.set(6)
        music(21)
    else:
        engine.music_mode.set(5)
        music(21)
    load(Species.WaruMonzaemon)
    load(Species.Hagurumon)
    if toy_tale_heard and not key_chain_found.toy_mansion:
        load(Species.Nanimon171)
        spawn(Species.Nanimon171, slot=1)

@lib.section(152)
def sec152():    # section 152
    use_script(146, Screen.factorial_town_152)
    engine.music_mode.set(0)
    music(22)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Guardromon)
        spawn(Species.Guardromon, slot=0, autotalk=True)
        spawn(Species.Guardromon, slot=1, autotalk=True)
    else:
        load(Species.PlatinumSukamon)
        spawn(Species.PlatinumSukamon, slot=2, autotalk=True)
        spawn(Species.PlatinumSukamon, slot=3, autotalk=True)
    load(Species.Whamon146)
    spawn(Species.Whamon146, slot=4)

@lib.section(153)
def sec153():    # section 153
    use_script(147, Screen.factorial_town_153)
    engine.music_mode.set(0)
    music(22)
    roll = random.roll(99)
    if roll <= 2 and not recruited(Species.MetalMamemon):
        load(Species.MetalGreymonVirus149)
        spawn(Species.MetalGreymonVirus149, slot=4, autotalk=True)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Guardromon)
        spawn(Species.Guardromon, slot=0, autotalk=True)
        spawn(Species.Guardromon, slot=1, autotalk=True)
    else:
        load(Species.Geremon)
        spawn(Species.Geremon, slot=2, autotalk=True)
        spawn(Species.Geremon, slot=3, autotalk=True)

@lib.section(154)
def sec154():    # section 154
    use_script(148, Screen.factorial_town_154)
    engine.music_mode.set(0)
    music(22)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Guardromon)
        load(Species.PlatinumSukamon)
        spawn(Species.Guardromon, slot=0, autotalk=True)
        spawn(Species.PlatinumSukamon, slot=1, autotalk=True)
        spawn(Species.PlatinumSukamon, slot=2, autotalk=True)
    else:
        load(Species.Geremon)
        load(Species.Guardromon)
        spawn(Species.Geremon, slot=3, autotalk=True)
        spawn(Species.Guardromon, slot=4, autotalk=True)
        spawn(Species.Guardromon, slot=5, autotalk=True)

@lib.section(155)
def sec155():    # section 155
    use_script(149, Screen.factorial_town_155)
    engine.music_mode.set(0)
    music(22)
    if clock.hour == 11 and clock.minute >= 55:
        return
    if date_hour == 12 and date_minute <= 5:
        return
    if date_hour == 23 and date_minute >= 55:
        return
    if date_hour == 0 and date_minute <= 5:
        return
    if not factory_guards_passed:
        load(Species.Guardromon)
        spawn(Species.Guardromon, slot=6)
        spawn(Species.Guardromon, slot=7)
        return
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Geremon)
        spawn(Species.Geremon, slot=0, autotalk=True)
        spawn(Species.Geremon, slot=1, autotalk=True)
        spawn(Species.Geremon, slot=2, autotalk=True)
    else:
        load(Species.PlatinumSukamon)
        spawn(Species.PlatinumSukamon, slot=3, autotalk=True)
        spawn(Species.PlatinumSukamon, slot=4, autotalk=True)
        spawn(Species.PlatinumSukamon, slot=5, autotalk=True)

@lib.section(156)
def sec156():    # section 156
    use_script(150, Screen.factorial_town_156)
    engine.music_mode.set(0)
    music(22)

@lib.section(157)
def sec157():    # section 157
    use_script(151, Screen.factorial_town_157)
    engine.music_mode.set(0)
    music(22)
    load(Species.Andromon160)
    spawn(Species.Andromon160, slot=0)

@lib.section(158)
def sec158():    # section 158
    use_script(152, Screen.factorial_town_158)
    engine.music_mode.set(0)
    music(22)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Guardromon)
        load(Species.Geremon)
        spawn(Species.Geremon, slot=0, autotalk=True)
        spawn(Species.Geremon, slot=1, autotalk=True)
        spawn(Species.Guardromon, slot=2, autotalk=True)
    else:
        load(Species.Guardromon)
        spawn(Species.Guardromon, slot=3, autotalk=True)
        spawn(Species.Guardromon, slot=4, autotalk=True)
        spawn(Species.Guardromon, slot=5, autotalk=True)

@lib.section(159)
def sec159():    # section 159
    use_script(153, Screen.factorial_town_159)
    engine.music_mode.set(0)
    music(22)
    if not recruited(Species.Giromon):
        load(Species.Giromon161)
        spawn(Species.Giromon161, slot=0)
        return

@lib.section(160)
def sec160():    # section 160
    use_script(154, Screen.factorial_town_160)
    engine.music_mode.set(0)
    music(22)
    load(Species.Giromon161)
    spawn(Species.Giromon161, slot=0)

@lib.section(161)
def sec161():    # section 161
    use_script(155, Screen.factorial_town_161)
    engine.music_mode.set(0)
    music(22)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Guardromon)
        load(Species.PlatinumSukamon)
        spawn(Species.Guardromon, slot=0, autotalk=True)
        spawn(Species.PlatinumSukamon, slot=1, autotalk=True)
        spawn(Species.Guardromon, slot=2, autotalk=True)
    else:
        load(Species.Geremon)
        spawn(Species.Geremon, slot=3, autotalk=True)
        spawn(Species.Geremon, slot=4, autotalk=True)
        spawn(Species.Geremon, slot=5, autotalk=True)

@lib.section(162)
def sec162():    # section 162
    use_script(156, Screen.factorial_town_162)
    engine.music_mode.set(0)
    music(22)
    load(Species.Guardromon)
    spawn(Species.Guardromon, slot=0)
    spawn(Species.Guardromon, slot=1, autotalk=True)
    spawn(Species.Guardromon, slot=2, autotalk=True)

@lib.section(163)
def sec163():    # section 163
    use_script(157, Screen.sewer_163)
    engine.music_mode.set(1)
    music(23)

@lib.section(164)
def sec164():    # section 164
    use_script(158, Screen.trash_mountain_164)
    engine.music_mode.set(0)
    music(24)
    if clock.hour >= 7 and clock.hour < 19:
        load(Species.Psychemon)
        load(Species.Geremon)
        spawn(Species.Psychemon, slot=0, autotalk=True)
        spawn(Species.Geremon, slot=1, autotalk=True)
        spawn(Species.Geremon, slot=2, autotalk=True)
    else:
        load(Species.Psychemon)
        load(Species.Geremon)
        spawn(Species.Geremon, slot=3, autotalk=True)
        spawn(Species.Psychemon, slot=4, autotalk=True)
        spawn(Species.Psychemon, slot=5, autotalk=True)

@lib.section(165)
def sec165():    # section 165
    use_script(159, Screen.trash_mountain_165)
    engine.music_mode.set(0)
    music(24)
    load(Species.Sukamon)
    load(Species.KingSukamon)
    spawn(Species.KingSukamon, slot=0)
    spawn(Species.Sukamon, slot=1)
    spawn(Species.Sukamon, slot=2)
    spawn(Species.Sukamon, slot=3)

@lib.section(166)
def sec166():    # section 166
    use_script(160, Screen.mt_infinity_166)
    engine.music_mode.set(1)
    music(27)
    load(Species.Vermilimon)
    load(Species.Golemon)
    spawn(Species.Vermilimon, slot=0, autotalk=True)
    spawn(Species.Vermilimon, slot=1, autotalk=True)
    spawn(Species.Golemon, slot=2, autotalk=True)
    spawn(Species.Vermilimon, slot=3, autotalk=True)
    spawn(Species.Golemon, slot=4, autotalk=True)

@lib.section(167)
def sec167():    # section 167
    use_script(161, Screen.mt_infinity_167)
    engine.music_mode.set(1)
    music(27)
    load(Species.Piddomon)
    load(Species.Gururumon)
    spawn(Species.Piddomon, slot=0, autotalk=True)
    spawn(Species.Piddomon, slot=1, autotalk=True)
    spawn(Species.Gururumon, slot=2, autotalk=True)
    spawn(Species.Piddomon, slot=3, autotalk=True)
    spawn(Species.Gururumon, slot=4, autotalk=True)

@lib.section(168)
def sec168():    # section 168
    use_script(162, Screen.file_city_168)
    engine.music_mode.set(0)
    music(28)
    return L228()

@lib.section(169)
def sec169():    # section 169
    use_script(162, Screen.file_city_169)
    engine.music_mode.set(0)
    music(28)
    return L229()

@lib.section(170)
def sec170():    # section 170
    use_script(162, Screen.file_city_170)
    engine.music_mode.set(0)
    music(28)
    return L230()

@lib.section(171)
def sec171():    # section 171
    use_script(162, Screen.file_city_171)
    engine.music_mode.set(0)
    music(28)
    return L228()

@lib.section(172)
def sec172():    # section 172
    use_script(162, Screen.file_city_172)
    engine.music_mode.set(0)
    music(28)
    return L229()

@lib.section(173)
def sec173():    # section 173
    use_script(162, Screen.file_city_173)
    engine.music_mode.set(0)
    music(28)
    return L230()

@lib.section(174)
def sec174():    # section 174
    use_script(162, Screen.file_city_174)
    engine.music_mode.set(0)
    music(28)
    return L228()

@lib.section(175)
def sec175():    # section 175
    use_script(162, Screen.file_city_175)
    engine.music_mode.set(0)
    music(28)
    return L229()

@lib.section(176)
def sec176():    # section 176
    use_script(162, Screen.file_city_176)
    engine.music_mode.set(0)
    music(28)
    return L230()

@lib.section(177)
def sec177():    # section 177
    use_script(162, Screen.file_city_177)
    engine.music_mode.set(0)
    music(28)
    return L228()

@lib.section(178)
def sec178():    # section 178
    use_script(162, Screen.file_city_178)
    engine.music_mode.set(0)
    music(28)
    return L229()

@lib.section(179)
def sec179():    # section 179
    use_script(162, Screen.file_city_179)
    engine.music_mode.set(0)
    music(28)
    return L230()

@lib.section(180)
def sec180():    # section 180
    use_script(163, Screen.file_city_180)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(1)
    return L247()

@lib.section(181)
def sec181():    # section 181
    use_script(163, Screen.file_city_181)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(2)
    return L247()

@lib.section(182)
def sec182():    # section 182
    use_script(163, Screen.file_city_182)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(3)
    return L247()

@lib.section(183)
def sec183():    # section 183
    use_script(163, Screen.file_city_183)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(4)
    return L247()

@lib.section(184)
def sec184():    # section 184
    use_script(163, Screen.file_city_184)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(5)
    return L247()

@lib.section(185)
def sec185():    # section 185
    use_script(163, Screen.file_city_185)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(6)
    return L247()

@lib.section(186)
def sec186():    # section 186
    use_script(163, Screen.file_city_186)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(7)
    return L247()

@lib.section(187)
def sec187():    # section 187
    use_script(163, Screen.file_city_187)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(8)
    return L247()

@lib.section(188)
def sec188():    # section 188
    use_script(163, Screen.file_city_188)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(9)
    return L247()

@lib.section(189)
def sec189():    # section 189
    use_script(163, Screen.file_city_189)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(10)
    return L247()

@lib.section(190)
def sec190():    # section 190
    use_script(163, Screen.file_city_190)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(11)
    return L247()

@lib.section(191)
def sec191():    # section 191
    use_script(163, Screen.file_city_191)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(12)
    return L247()

@lib.section(192)
def sec192():    # section 192
    use_script(163, Screen.file_city_192)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(13)
    if not factorial_town_reopened:
        return L247()
    trigger(329).set()
    return L247()

@lib.section(193)
def sec193():    # section 193
    use_script(163, Screen.file_city_193)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(14)
    return L247()

@lib.section(194)
def sec194():    # section 194
    use_script(163, Screen.file_city_194)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(15)
    return L247()

@lib.section(195)
def sec195():    # section 195
    use_script(163, Screen.file_city_195)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(16)
    return L247()

@lib.section(196)
def sec196():    # section 196
    use_script(163, Screen.file_city_196)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(17)
    return L247()

@lib.section(197)
def sec197():    # section 197
    use_script(163, Screen.file_city_197)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(18)
    return L247()

@lib.section(198)
def sec198():    # section 198
    use_script(163, Screen.file_city_198)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(19)
    return L247()

@lib.section(199)
def sec199():    # section 199
    use_script(163, Screen.file_city_199)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(20)
    return L247()

@lib.section(200)
def sec200():    # section 200
    use_script(163, Screen.file_city_200)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(21)
    return L247()

@lib.section(201)
def sec201():    # section 201
    use_script(163, Screen.file_city_201)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(22)
    return L247()

@lib.section(202)
def sec202():    # section 202
    use_script(163, Screen.file_city_202)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(23)
    return L247()

@lib.section(203)
def sec203():    # section 203
    use_script(163, Screen.file_city_203)
    engine.music_mode.set(0)
    music(28)
    city_layout.set(24)
    return L247()

@lib.section(204)
def sec204():    # section 204
    use_script(164, Screen.file_city_204)
    engine.music_mode.set(0)
    music(28)
    if debug_test_npcs:
        load(Species.Jijimon)
        load(Species.Tokomon)
        spawn(Species.Tokomon, slot=5)
        spawn(Species.Jijimon, slot=3)
        return
    if not debug_mode:
        load(Species.Jijimon)
        load(Species.Tokomon)
        spawn(Species.Jijimon, slot=0)
        spawn(Species.Tokomon, slot=1)
        spawn(Species.Jijimon, slot=2)
        spawn(Species.Jijimon, slot=3)
        return
    load(Species.Yuramon)
    load(Species.Tanemon)
    spawn(Species.Yuramon, slot=4)
    spawn(Species.Tanemon, slot=6)

@lib.section(205)
def sec205():    # section 205
    use_script(165, Screen.jijimons_house_205)
    engine.music_mode.set(0)
    music(28)
    load(Species.Jijimon)
    spawn(Species.Jijimon, slot=0)
    if recruited(Species.Angemon):
        load(Species.Angemon142)
        spawn(Species.Angemon142, slot=1)
    load(Species.Tokomon)
    spawn(Species.Tokomon, slot=2)

@lib.section(206)
def sec206():    # section 206
    use_script(166, Screen.jijimons_house_206)
    engine.music_mode.set(0)
    music(28)
    load(Species.Botamon)
    spawn(Species.Botamon, slot=0)
    if recruited(Species.Monzaemon):
        load(Species.Monzaemon138)
        spawn(Species.Monzaemon138, slot=1)
    if airdramon_ambush_fought and not engine.game_beaten:
        load(Species.Airdramon131)
        spawn(Species.Airdramon131, slot=2)

@lib.section(207)
def sec207():    # section 207
    use_script(167, Screen.birdra_transport)
    engine.music_mode.set(0)
    music(28)
    load(Species.Birdramon143)
    spawn(Species.Birdramon143, slot=0)
    if recruited(Species.Leomon):
        load(Species.Leomon166)
        spawn(Species.Leomon166, slot=1)

@lib.section(208)
def sec208():    # section 208
    use_script(168, Screen.arena_lobby_208)
    engine.music_mode.set(0)
    music(28)
    load(Species.Greymon178)
    spawn(Species.Greymon178, slot=0)

@lib.section(209)
def sec209():    # section 209
    use_script(169, Screen.treasure_hunt)
    engine.music_mode.set(0)
    music(28)
    load(Species.Drimogemon158)
    spawn(Species.Drimogemon158, slot=0)
    if recruited(Species.Gabumon):
        load(Species.Gabumon139)
        spawn(Species.Gabumon139, slot=1)

@lib.section(210)
def sec210():    # section 210
    use_script(170, Screen.mt_infinity_210)
    engine.music_mode.set(1)
    music(27)
    load(Species.Piddomon)
    load(Species.Golemon)
    spawn(Species.Golemon, slot=0, autotalk=True)
    spawn(Species.Piddomon, slot=1, autotalk=True)
    spawn(Species.Piddomon, slot=3, autotalk=True)
    spawn(Species.Piddomon, slot=4, autotalk=True)

@lib.section(211)
def sec211():    # section 211
    use_script(171, Screen.item_keeper)
    engine.music_mode.set(0)
    music(28)
    load(Species.Agumon)
    load(Species.Poyomon)
    spawn(Species.Agumon, slot=0)
    spawn(Species.Poyomon, slot=1)
    if recruited(Species.Nanimon):
        load(Species.Nanimon171)
        spawn(Species.Nanimon171, slot=2)

@lib.section(212)
def sec212():    # section 212
    use_script(172, Screen.mt_infinity_212)
    engine.music_mode.set(1)
    music(27)
    load(Species.Vermilimon)
    load(Species.Gururumon)
    spawn(Species.Vermilimon, slot=0, autotalk=True)
    spawn(Species.Gururumon, slot=1, autotalk=True)
    spawn(Species.Vermilimon, slot=2, autotalk=True)
    spawn(Species.Gururumon, slot=4, autotalk=True)

@lib.section(213)
def sec213():    # section 213
    use_script(173, Screen.centar_clinic)
    engine.music_mode.set(0)
    music(28)
    load(Species.Centarumon156)
    spawn(Species.Centarumon156, slot=0)
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Coelamon):
            load(Species.Coelamon167)
            spawn(Species.Coelamon167, slot=1)

@lib.section(214)
def sec214():    # section 214
    use_script(174, Screen.restaurant_214)
    engine.music_mode.set(0)
    music(28)
    if recruited(Species.Meramon) and not restaurant_chef_met.meramon:
        load(Species.Meramon133)
        spawn(Species.Meramon133, slot=0)
        restaurant_chef.set(0)
        return
    if recruited(Species.Tyrannomon) and not restaurant_chef_met.tyrannomon:
        load(Species.Tyrannomon132)
        spawn(Species.Tyrannomon132, slot=1)
        restaurant_chef.set(1)
        return
    if recruited(Species.Garurumon) and not restaurant_chef_met.garurumon:
        load(Species.Garurumon144)
        spawn(Species.Garurumon144, slot=2)
        restaurant_chef.set(2)
        return
    if recruited(Species.Frigimon) and not restaurant_chef_met.frigimon:
        load(Species.Frigimon145)
        spawn(Species.Frigimon145, slot=3)
        restaurant_chef.set(3)
        return
    roll = random.roll(99)
    if recruited(Species.Vademon) and roll <= 19:
        load(Species.Vademon150)
        spawn(Species.Vademon150, slot=4)
        restaurant_chef.set(4)
        return
    roll = random.roll(99)
    if recruited(Species.Digitamamon) and roll <= 9:
        load(Species.Digitamamon174)
        spawn(Species.Digitamamon174, slot=5)
        restaurant_chef.set(5)
        return
    if restaurant_chef_met.meramon and clock.hour >= 12 and clock.hour < 18:
        load(Species.Meramon133)
        spawn(Species.Meramon133, slot=0)
        restaurant_chef.set(0)
        return
    if restaurant_chef_met.tyrannomon and date_hour >= 6 and date_hour < 12:
        load(Species.Tyrannomon132)
        spawn(Species.Tyrannomon132, slot=1)
        restaurant_chef.set(1)
        return
    if restaurant_chef_met.garurumon and date_hour >= 0 and date_hour < 6:
        load(Species.Garurumon144)
        spawn(Species.Garurumon144, slot=2)
        restaurant_chef.set(2)
        return
    if restaurant_chef_met.frigimon and date_hour >= 18:
        load(Species.Frigimon145)
        spawn(Species.Frigimon145, slot=3)
        restaurant_chef.set(3)
        return
    if recruited(Species.Meramon):
        load(Species.Meramon133)
        spawn(Species.Meramon133, slot=0)
        restaurant_chef.set(0)
        return
    if recruited(Species.Tyrannomon):
        load(Species.Tyrannomon132)
        spawn(Species.Tyrannomon132, slot=1)
        restaurant_chef.set(1)
        return
    if recruited(Species.Garurumon):
        load(Species.Garurumon144)
        spawn(Species.Garurumon144, slot=2)
        restaurant_chef.set(2)
        return
    if recruited(Species.Frigimon):
        load(Species.Frigimon145)
        spawn(Species.Frigimon145, slot=3)
        restaurant_chef.set(3)
        return

@lib.section(215)
def sec215():    # section 215
    use_script(175, Screen.restaurant_215)
    engine.music_mode.set(0)
    music(28)
    load(Species.Giromon161)
    spawn(Species.Giromon161, slot=6)
    if recruited(Species.Meramon) and not restaurant_chef_met.meramon:
        load(Species.Meramon133)
        spawn(Species.Meramon133, slot=0)
        restaurant_chef.set(0)
        return
    if recruited(Species.Tyrannomon) and not restaurant_chef_met.tyrannomon:
        load(Species.Tyrannomon132)
        spawn(Species.Tyrannomon132, slot=1)
        restaurant_chef.set(1)
        return
    if recruited(Species.Garurumon) and not restaurant_chef_met.garurumon:
        load(Species.Garurumon144)
        spawn(Species.Garurumon144, slot=2)
        restaurant_chef.set(2)
        return
    if recruited(Species.Frigimon) and not restaurant_chef_met.frigimon:
        load(Species.Frigimon145)
        spawn(Species.Frigimon145, slot=3)
        restaurant_chef.set(3)
        return
    roll = random.roll(99)
    if recruited(Species.Vademon) and roll <= 19:
        load(Species.Vademon150)
        spawn(Species.Vademon150, slot=4)
        restaurant_chef.set(4)
        return
    roll = random.roll(99)
    if recruited(Species.Digitamamon) and roll <= 9:
        load(Species.Digitamamon174)
        spawn(Species.Digitamamon174, slot=5)
        restaurant_chef.set(5)
        return
    if restaurant_chef_met.meramon and clock.hour >= 12 and clock.hour < 18:
        load(Species.Meramon133)
        spawn(Species.Meramon133, slot=0)
        restaurant_chef.set(0)
        return
    if restaurant_chef_met.tyrannomon and date_hour >= 6 and date_hour < 12:
        load(Species.Tyrannomon132)
        spawn(Species.Tyrannomon132, slot=1)
        restaurant_chef.set(1)
        return
    if restaurant_chef_met.garurumon and date_hour >= 0 and date_hour < 6:
        load(Species.Garurumon144)
        spawn(Species.Garurumon144, slot=2)
        restaurant_chef.set(2)
        return
    if restaurant_chef_met.frigimon and date_hour >= 18:
        load(Species.Frigimon145)
        spawn(Species.Frigimon145, slot=3)
        restaurant_chef.set(3)
        return
    if recruited(Species.Meramon):
        load(Species.Meramon133)
        spawn(Species.Meramon133, slot=0)
        restaurant_chef.set(0)
        return
    if recruited(Species.Tyrannomon):
        load(Species.Tyrannomon132)
        spawn(Species.Tyrannomon132, slot=1)
        restaurant_chef.set(1)
        return
    if recruited(Species.Garurumon):
        load(Species.Garurumon144)
        spawn(Species.Garurumon144, slot=2)
        restaurant_chef.set(2)
        return
    if recruited(Species.Frigimon):
        load(Species.Frigimon145)
        spawn(Species.Frigimon145, slot=3)
        restaurant_chef.set(3)
        return

@lib.section(216)
def sec216():    # section 216
    use_script(176, Screen.item_shop)
    engine.music_mode.set(0)
    music(28)
    load(Species.Punimon)
    spawn(Species.Punimon, slot=5)
    if recruited(Species.Patamon) and not item_shop_keeper_met.patamon:
        load(Species.Patamon151)
        spawn(Species.Patamon151, slot=0)
        item_shop_keeper.set(0)
        return
    if recruited(Species.Biyomon) and not item_shop_keeper_met.biyomon:
        load(Species.Biyomon163)
        spawn(Species.Biyomon163, slot=1)
        item_shop_keeper.set(1)
        return
    if recruited(Species.Unimon) and not item_shop_keeper_met.unimon:
        load(Species.Unimon153)
        spawn(Species.Unimon153, slot=2)
        item_shop_keeper.set(2)
        return
    if recruited(Species.Monochromon) and not item_shop_keeper_met.monochromon:
        load(Species.Monochromon165)
        spawn(Species.Monochromon165, slot=3)
        item_shop_keeper.set(3)
        return
    piximon_in_item_shop.clear()
    roll = random.roll(9)
    if recruited(Species.Piximon) and roll <= 1:
        load(Species.Piximon173)
        spawn(Species.Piximon173, slot=4)
        piximon_in_item_shop.set()
    if item_shop_keeper_met.patamon and clock.hour >= 12 and clock.hour < 18:
        load(Species.Patamon151)
        spawn(Species.Patamon151, slot=0)
        item_shop_keeper.set(0)
        return
    if item_shop_keeper_met.biyomon and date_hour >= 6 and date_hour < 12:
        load(Species.Biyomon163)
        spawn(Species.Biyomon163, slot=1)
        item_shop_keeper.set(1)
        return
    if item_shop_keeper_met.unimon and date_hour >= 0 and date_hour < 6:
        load(Species.Unimon153)
        spawn(Species.Unimon153, slot=2)
        item_shop_keeper.set(2)
        return
    if item_shop_keeper_met.monochromon and date_hour >= 18:
        load(Species.Monochromon165)
        spawn(Species.Monochromon165, slot=3)
        item_shop_keeper.set(3)
        return
    raw.store_date(date_year)
    if recruited(Species.Patamon):
        load(Species.Patamon151)
        spawn(Species.Patamon151, slot=0)
        item_shop_keeper.set(0)
        return
    if recruited(Species.Biyomon):
        load(Species.Biyomon163)
        spawn(Species.Biyomon163, slot=1)
        item_shop_keeper.set(1)
        return
    if recruited(Species.Unimon):
        load(Species.Unimon153)
        spawn(Species.Unimon153, slot=2)
        item_shop_keeper.set(2)
        return
    if recruited(Species.Monochromon):
        load(Species.Monochromon165)
        spawn(Species.Monochromon165, slot=3)
        item_shop_keeper.set(3)
        return

@lib.section(217)
def sec217():    # section 217
    use_script(177, Screen.secret_item_shop)
    engine.music_mode.set(0)
    music(28)
    if recruited(Species.Ninjamon):
        load(Species.Ninjamon175)
        spawn(Species.Ninjamon175, slot=4)
    if recruited(Species.Numemon) and not secret_shop_keeper_met.numemon:
        load(Species.Numemon135)
        spawn(Species.Numemon135, slot=0)
        secret_shop_keeper.set(0)
        return
    if recruited(Species.Mojyamon) and not secret_shop_keeper_met.mojyamon:
        load(Species.Mojyamon170)
        spawn(Species.Mojyamon170, slot=1)
        secret_shop_keeper.set(1)
        return
    if recruited(Species.Mamemon) and not secret_shop_keeper_met.mamemon:
        load(Species.Mamemon137)
        spawn(Species.Mamemon137, slot=2)
        secret_shop_keeper.set(2)
        return
    if recruited(Species.Devimon) and not secret_shop_keeper_met.devimon:
        load(Species.Devimon130)
        spawn(Species.Devimon130, slot=3)
        secret_shop_keeper.set(3)
        return
    if secret_shop_keeper_met.numemon and clock.hour >= 0 and clock.hour < 6:
        load(Species.Numemon135)
        spawn(Species.Numemon135, slot=0)
        secret_shop_keeper.set(0)
        return
    if secret_shop_keeper_met.mojyamon and date_hour >= 6 and date_hour < 12:
        load(Species.Mojyamon170)
        spawn(Species.Mojyamon170, slot=1)
        secret_shop_keeper.set(1)
        return
    if secret_shop_keeper_met.mamemon and date_hour >= 12 and date_hour < 18:
        load(Species.Mamemon137)
        spawn(Species.Mamemon137, slot=2)
        secret_shop_keeper.set(2)
        return
    if secret_shop_keeper_met.devimon and date_hour >= 18:
        load(Species.Devimon130)
        spawn(Species.Devimon130, slot=3)
        secret_shop_keeper.set(3)
        return
    raw.store_date(date_year)
    if recruited(Species.Numemon):
        load(Species.Numemon135)
        spawn(Species.Numemon135, slot=0)
        secret_shop_keeper.set(0)
        return
    if recruited(Species.Mojyamon):
        load(Species.Mojyamon170)
        spawn(Species.Mojyamon170, slot=1)
        secret_shop_keeper.set(1)
        return
    if recruited(Species.Mamemon):
        load(Species.Mamemon137)
        spawn(Species.Mamemon137, slot=2)
        secret_shop_keeper.set(2)
        return
    if recruited(Species.Devimon):
        load(Species.Devimon130)
        spawn(Species.Devimon130, slot=3)
        secret_shop_keeper.set(3)
        return

@lib.section(218)
def sec218():    # section 218
    use_script(178, Screen.jijimons_house)
    engine.music_mode.set(0)
    music(28)
    load(Species.Jijimon)
    load(Species.Tokomon)
    load(Species.Botamon)
    spawn(Species.Jijimon, slot=0)
    spawn(Species.Tokomon, slot=1)
    spawn(Species.Botamon, slot=2)

@lib.section(219)
def sec219():    # section 219
    use_script(179, Screen.mt_infinity_219)
    engine.music_mode.set(1)
    music(27)
    load(Species.Vermilimon)
    load(Species.Golemon)
    spawn(Species.Vermilimon, slot=0, autotalk=True)
    spawn(Species.Golemon, slot=1, autotalk=True)
    spawn(Species.Golemon, slot=2, autotalk=True)

@lib.section(220)
def sec220():    # section 220
    use_script(180, Screen.sewer_220)
    engine.music_mode.set(1)
    music(23)
    if factory_shut_down and not recruited(Species.Numemon):
        load(Species.Numemon135)
        spawn(Species.Numemon135, slot=1)
        return
    if not recruited(Species.Numemon):
        load(Species.Numemon135)
        spawn(Species.Numemon135, slot=0)
    if island_history_read and not key_chain_found.sewer:
        load(Species.Nanimon171)
        spawn(Species.Nanimon171, slot=2)

@lib.section(221)
def sec221():    # section 221
    use_script(181, Screen.underground_lab_221)
    engine.music_mode.set(1)
    music(10)
    if not lab_skullgreymon_beaten:
        load(Species.SkullGreymon148)
        spawn(Species.SkullGreymon148, slot=0, autotalk=True)

@lib.section(222)
def sec222():    # section 222
    use_script(182, Screen.mt_infinity_222)
    engine.music_mode.set(1)
    music(27)
    if not mt_infinity_metalgreymon_beaten:
        load(Species.MetalGreymonVirus136)
        spawn(Species.MetalGreymonVirus136, slot=0, autotalk=True)

@lib.section(223)
def sec223():    # section 223
    use_script(168, Screen.arena_lobby_223)
    engine.music_mode.set(0)
    music(28)
    load(Species.Greymon178)
    spawn(Species.Greymon178, slot=0)
    if engine.game_beaten:
        load(Species.Airdramon131)
        load(Species.MetalGreymonVirus179)
        spawn(Species.Airdramon131, slot=1)
        spawn(Species.MetalGreymonVirus179, slot=2)

@lib.section(224)
def sec224():    # section 224
    use_script(183, Screen.grey_lords_mansion_224)
    engine.music_mode.set(1)
    music(10)
    load(Species.Myotismon177)
    spawn(Species.Myotismon177, slot=0)

@lib.section(225)
def sec225():    # section 225
    use_script(184, Screen.mt_infinity_225)
    engine.music_mode.set(10)
    music(27)
    if not engine.game_beaten:
        load(Species.Analogman)
        spawn(Species.Analogman, slot=1)
        load(Species.Machinedramon)
        return
    if not recruited(Species.Digitamamon) and engine.game_beaten:
        load(Species.Digitamamon174)
        spawn(Species.Digitamamon174, slot=3)

@lib.section(226)
def sec226():    # section 226
    use_script(185, Screen.back_dimension_226)
    engine.music_mode.set(1)
    music(27)
    load(Species.Piddomon)
    load(Species.IceDevimon)
    spawn(Species.Piddomon, slot=0, autotalk=True)
    spawn(Species.Piddomon, slot=1, autotalk=True)
    spawn(Species.IceDevimon, slot=2, autotalk=True)
    spawn(Species.IceDevimon, slot=3, autotalk=True)

@lib.section(227)
def sec227():    # section 227
    use_script(186, Screen.back_dimension_227)
    engine.music_mode.set(1)
    music(27)
    load(Species.Tekkamon)
    load(Species.BlueMeramon)
    spawn(Species.Tekkamon, slot=0, autotalk=True)
    spawn(Species.Tekkamon, slot=1, autotalk=True)
    spawn(Species.BlueMeramon, slot=2, autotalk=True)
    spawn(Species.BlueMeramon, slot=3, autotalk=True)

@lib.section(228)
def sec228():    # section 228
    use_script(187, Screen.back_dimension_228)
    engine.music_mode.set(1)
    music(27)
    load(Species.Tankmon)
    load(Species.Golemon)
    spawn(Species.Tankmon, slot=0, autotalk=True)
    spawn(Species.Tankmon, slot=1, autotalk=True)
    spawn(Species.Golemon, slot=2, autotalk=True)
    spawn(Species.Golemon, slot=3, autotalk=True)

@lib.section(229)
def sec229():    # section 229
    use_script(180, Screen.mt_infinity_229)
    engine.music_mode.set(1)
    music(23)

@lib.section(230)
def sec230():    # section 230
    use_script(180, Screen.mt_infinity_230)
    engine.music_mode.set(1)
    music(23)

@lib.section(231)
def sec231():    # section 231
    use_script(180, Screen.mt_infinity_231)
    engine.music_mode.set(1)
    music(23)

@lib.section(232)
def sec232():    # section 232
    use_script(188, Screen.grey_lords_mansion_232)
    engine.music_mode.set(1)
    music(10)

@lib.section(233)
def sec233():    # section 233
    use_script(189, Screen.mt_panorama_spore_area_233)
    engine.music_mode.set(0)
    music(3)
    if not recruited(Species.Unimon) and centar_clinic_intro_seen:
        load(Species.Unimon153)
        spawn(Species.Unimon153, slot=0)

@lib.section(234)
def sec234():    # section 234
    use_script(190, Screen.mt_panorama_spore_area_234)
    engine.music_mode.set(0)
    music(3)
    load(Species.Vademon150)

@lib.section(235)
def sec235():    # section 235
    use_script(191, Screen.digimon_curling)
    engine.music_mode.set(0)
    music(28)
    if curling_opponent == 1:
        load(Species.MetalGreymonVirus149)
        spawn(Species.MetalGreymonVirus149, slot=1)
        return
    if curling_opponent == 0:
        load(Species.Penguinmon176)
        spawn(Species.Penguinmon176, slot=0)
        return
    roll = random.roll(7)
    if recruited(Species.MetalMamemon) and roll <= 0:
        curling_opponent.set(1)
        load(Species.MetalGreymonVirus149)
        spawn(Species.MetalGreymonVirus149, slot=1)
        return
    if recruited(Species.Penguinmon):
        curling_opponent.set(0)
        load(Species.Penguinmon176)
        spawn(Species.Penguinmon176, slot=0)

@lib.section(236)
def sec236():    # section 236
    use_script(192, Screen.file_city_236)
    engine.music_mode.set(0)
    music(28)
    load(Species.Jijimon)
    load(Species.Greymon129)
    load(Species.Airdramon131)
    spawn(Species.Jijimon, slot=0)
    spawn(Species.Greymon129, slot=1)
    spawn(Species.Airdramon131, slot=2)

@lib.section(237)
def sec237():    # section 237
    use_script(192, Screen.file_city_237)
    engine.music_mode.set(0)
    music(28)
    load(Species.Jijimon)
    load(Species.Greymon129)
    load(Species.Airdramon131)
    spawn(Species.Jijimon, slot=0)
    spawn(Species.Greymon129, slot=1)
    spawn(Species.Airdramon131, slot=2)

@lib.section(238)
def sec238():    # section 238
    use_script(193, Screen.file_city_238)
    engine.music_mode.set(0)
    music(28)
    if debug_test_npcs:
        load(Species.Jijimon)
        load(Species.Tokomon)
        load(Species.Poyomon)
        spawn(Species.Tokomon, slot=5)
        spawn(Species.Jijimon, slot=3)
        spawn(Species.Poyomon, slot=7)
        return

@lib.section(239)
def sec239():    # section 239
    use_script(180, 239)
    engine.music_mode.set(1)
    music(23)

@lib.section(240)
def sec240():    # section 240
    use_script(180, 240)
    engine.music_mode.set(1)
    music(23)

@lib.section(241)
def sec241():    # section 241
    use_script(180, 241)
    engine.music_mode.set(1)
    music(23)

@lib.section(242)
def sec242():    # section 242
    use_script(180, 242)
    engine.music_mode.set(1)
    music(23)

@lib.section(243)
def sec243():    # section 243
    use_script(180, 243)
    engine.music_mode.set(1)
    music(23)

@lib.section(244)
def sec244():    # section 244
    use_script(180, 244)
    engine.music_mode.set(1)
    music(23)

@lib.section(245)
def sec245():    # section 245
    use_script(180, 245)
    engine.music_mode.set(1)
    music(23)

@lib.section(246)
def sec246():    # section 246
    use_script(180, 246)
    engine.music_mode.set(1)
    music(23)

@lib.section(247)
def sec247():    # section 247
    use_script(194, 247)
    engine.music_mode.set(1)
    music(27)
    if not mt_infinity_devimon_beaten:
        load(Species.Devimon130)
        spawn(Species.Devimon130, slot=5, autotalk=True)
        return
    load(Species.Vermilimon)
    load(Species.Piddomon)
    spawn(Species.Vermilimon, slot=0, autotalk=True)
    spawn(Species.Piddomon, slot=1, autotalk=True)
    spawn(Species.Piddomon, slot=2, autotalk=True)
    spawn(Species.Vermilimon, slot=3, autotalk=True)
    spawn(Species.Piddomon, slot=4, autotalk=True)

@lib.section(248)
def sec248():    # section 248
    use_script(195, 248)
    engine.music_mode.set(1)
    music(27)
    load(Species.Golemon)
    spawn(Species.Golemon, slot=0, autotalk=True)
    spawn(Species.Golemon, slot=1, autotalk=True)
    spawn(Species.Golemon, slot=2, autotalk=True)

@lib.section(249)
def sec249():    # section 249
    use_script(196, 249)
    engine.music_mode.set(1)
    music(27)
    load(Species.Gururumon)
    load(Species.Vermilimon)
    spawn(Species.Gururumon, slot=0, autotalk=True)
    spawn(Species.Gururumon, slot=1, autotalk=True)
    spawn(Species.Vermilimon, slot=2, autotalk=True)
    spawn(Species.Vermilimon, slot=3, autotalk=True)

@lib.section(250)
def sec250():    # section 250
    use_script(180, 250)
    engine.music_mode.set(1)
    music(23)

@lib.section(251)
def sec251():    # section 251
    use_script(180, 251)
    engine.music_mode.set(1)
    music(23)

@lib.section(252)
def sec252():    # section 252
    use_script(180, 252)
    engine.music_mode.set(1)
    music(23)

@lib.section(253)
def sec253():    # section 253
    use_script(197, 253)
    engine.music_mode.set(1)
    music(27)
    load(Species.Piddomon)
    load(Species.Golemon)
    spawn(Species.Piddomon, slot=0, autotalk=True)
    spawn(Species.Golemon, slot=1, autotalk=True)
    spawn(Species.Piddomon, slot=2, autotalk=True)

@lib.on_enter
def enter():    # section 254
    use_script(198, 254)
    engine.music_mode.set(1)
    music(27)
    if not recruited(Species.Megadramon):
        load(Species.Megadramon172)
        spawn(Species.Megadramon172, slot=6, autotalk=True)
        return
    load(Species.Gururumon)
    load(Species.Piddomon)
    spawn(Species.Piddomon, slot=0, autotalk=True)
    spawn(Species.Gururumon, slot=1, autotalk=True)
    spawn(Species.Piddomon, slot=2, autotalk=True)
    spawn(Species.Gururumon, slot=3, autotalk=True)
    spawn(Species.Piddomon, slot=4, autotalk=True)
    spawn(Species.Gururumon, slot=5, autotalk=True)

@lib.section(1220)
def sec1220():    # section 1220
    dws(r"""goto L359;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L363;""")
    dws(r"""goto L364;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L367;""")
    dws(r"""goto L368;""")
    dws(r"""goto L369;""")
    dws(r"""goto L370;""")
    dws(r"""goto L371;""")
    dws(r"""goto L372;""")

@lib.section(1221)
def sec1221():    # section 1221
    dws(r"""goto L373;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L374;""")
    dws(r"""goto L375;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L376;""")
    dws(r"""goto L377;""")
    dws(r"""goto L378;""")
    dws(r"""goto L379;""")
    dws(r"""goto L371;""")
    dws(r"""goto L380;""")

@lib.section(1222)
def sec1222():    # section 1222
    dws(r"""goto L381;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L382;""")
    dws(r"""goto L383;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L384;""")
    dws(r"""goto L385;""")
    dws(r"""goto L386;""")
    dws(r"""goto L387;""")
    dws(r"""goto L371;""")
    dws(r"""goto L388;""")

@lib.section(1223)
def sec1223():    # section 1223
    dws(r"""goto L389;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L390;""")
    dws(r"""goto L391;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L392;""")
    dws(r"""goto L393;""")
    dws(r"""goto L394;""")
    dws(r"""goto L395;""")
    dws(r"""goto L371;""")
    dws(r"""goto L396;""")

@lib.section(1224)
def sec1224():    # section 1224
    dws(r"""goto L397;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L398;""")
    dws(r"""goto L399;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L400;""")
    dws(r"""goto L401;""")
    dws(r"""goto L402;""")
    dws(r"""goto L403;""")
    dws(r"""goto L371;""")
    dws(r"""goto L404;""")

@lib.section(1225)
def sec1225():    # section 1225
    dws(r"""goto L405;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L406;""")
    dws(r"""goto L407;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L408;""")
    dws(r"""goto L409;""")
    dws(r"""goto L410;""")
    dws(r"""goto L411;""")
    dws(r"""goto L371;""")
    dws(r"""goto L412;""")

@lib.section(1226)
def sec1226():    # section 1226
    dws(r"""goto L413;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L414;""")
    dws(r"""goto L415;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L416;""")
    dws(r"""goto L417;""")
    dws(r"""goto L418;""")
    dws(r"""goto L419;""")
    dws(r"""goto L371;""")
    dws(r"""goto L420;""")

@lib.section(1227)
def sec1227():    # section 1227
    dws(r"""goto L421;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L422;""")
    dws(r"""goto L423;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L424;""")
    dws(r"""goto L425;""")
    dws(r"""goto L426;""")
    dws(r"""goto L427;""")
    dws(r"""goto L371;""")
    dws(r"""goto L428;""")

@lib.section(1228)
def sec1228():    # section 1228
    dws(r"""goto L429;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L430;""")
    dws(r"""goto L431;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L432;""")
    dws(r"""goto L433;""")
    dws(r"""goto L434;""")
    dws(r"""goto L435;""")
    dws(r"""goto L371;""")
    dws(r"""goto L436;""")

@lib.section(1229)
def sec1229():    # section 1229
    dws(r"""goto L437;""")
    dws(r"""goto L360;""")
    dws(r"""goto L361;""")
    dws(r"""goto L362;""")
    dws(r"""goto L438;""")
    dws(r"""goto L439;""")
    dws(r"""goto L365;""")
    dws(r"""goto L366;""")
    dws(r"""goto L440;""")
    dws(r"""goto L441;""")
    dws(r"""goto L442;""")
    dws(r"""goto L443;""")
    dws(r"""goto L371;""")
    dws(r"""goto L444;""")

@lib.section(1230)
def sec1230():    # section 1230
    dws(r"""
        goto l7;
        goto l1;
        goto l2;
        goto l3;
        goto l8;
        goto l9;
        goto l4;
        goto l5;
        goto l10;
        goto l11;
        goto l12;
        goto l13;
        goto l6;
        goto l14;
        show_textbox(text("s000.sec1230.u0"));
        shared L359:
        show_textbox(text("s000.sec1230.u1"));
        shared L360:
        l1:
        show_textbox(text("s000.sec1230.u2"));
        shared L361:
        l2:
        show_textbox(text("s000.sec1230.u3"));
        shared L362:
        l3:
        show_textbox(text("s000.sec1230.u4"));
        shared L363:
        show_textbox(text("s000.sec1230.u5"));
        shared L364:
        show_textbox(text("s000.sec1230.u6"));
        shared L365:
        l4:
        show_textbox(text("s000.sec1230.u7"));
        shared L366:
        l5:
        show_textbox(text("s000.sec1230.u8"));
        shared L367:
        show_textbox(text("s000.sec1230.u9"));
        shared L368:
        show_textbox(text("s000.sec1230.u10"));
        shared L369:
        show_textbox(text("s000.sec1230.u11"));
        shared L370:
        show_textbox(text("s000.sec1230.u12"));
        shared L371:
        l6:
        show_textbox(text("s000.sec1230.u13"));
        shared L372:
        show_textbox(text("s000.sec1230.u14"));
        shared L373:
        show_textbox(text("s000.sec1230.u15"));
        shared L374:
        show_textbox(text("s000.sec1230.u16"));
        shared L375:
        show_textbox(text("s000.sec1230.u17"));
        shared L376:
        show_textbox(text("s000.sec1230.u18"));
        shared L377:
        show_textbox(text("s000.sec1230.u19"));
        shared L378:
        show_textbox(text("s000.sec1230.u20"));
        shared L379:
        show_textbox(text("s000.sec1230.u21"));
        shared L380:
        show_textbox(text("s000.sec1230.u22"));
        shared L381:
        show_textbox(text("s000.sec1230.u23"));
        shared L382:
        show_textbox(text("s000.sec1230.u24"));
        shared L383:
        show_textbox(text("s000.sec1230.u25"));
        shared L384:
        show_textbox(text("s000.sec1230.u26"));
        shared L385:
        show_textbox(text("s000.sec1230.u27"));
        shared L386:
        show_textbox(text("s000.sec1230.u28"));
        shared L387:
        show_textbox(text("s000.sec1230.u29"));
        shared L388:
        show_textbox(text("s000.sec1230.u30"));
        shared L389:
        show_textbox(text("s000.sec1230.u31"));
        shared L390:
        show_textbox(text("s000.sec1230.u32"));
        shared L391:
        show_textbox(text("s000.sec1230.u33"));
        shared L392:
        show_textbox(text("s000.sec1230.u34"));
        shared L393:
        show_textbox(text("s000.sec1230.u35"));
        shared L394:
        show_textbox(text("s000.sec1230.u36"));
        shared L395:
        show_textbox(text("s000.sec1230.u37"));
        shared L396:
        show_textbox(text("s000.sec1230.u38"));
        shared L397:
        show_textbox(text("s000.sec1230.u39"));
        shared L398:
        show_textbox(text("s000.sec1230.u40"));
        shared L399:
        show_textbox(text("s000.sec1230.u41"));
        shared L400:
        show_textbox(text("s000.sec1230.u42"));
        shared L401:
        show_textbox(text("s000.sec1230.u43"));
        shared L402:
        show_textbox(text("s000.sec1230.u44"));
        shared L403:
        show_textbox(text("s000.sec1230.u45"));
        shared L404:
        show_textbox(text("s000.sec1230.u46"));
        shared L405:
        show_textbox(text("s000.sec1230.u47"));
        shared L406:
        show_textbox(text("s000.sec1230.u48"));
        shared L407:
        show_textbox(text("s000.sec1230.u49"));
        shared L408:
        show_textbox(text("s000.sec1230.u50"));
        shared L409:
        show_textbox(text("s000.sec1230.u51"));
        shared L410:
        show_textbox(text("s000.sec1230.u52"));
        shared L411:
        show_textbox(text("s000.sec1230.u53"));
        shared L412:
        show_textbox(text("s000.sec1230.u54"));
        shared L413:
        show_textbox(text("s000.sec1230.u55"));
        shared L414:
        show_textbox(text("s000.sec1230.u56"));
        shared L415:
        show_textbox(text("s000.sec1230.u57"));
        shared L416:
        show_textbox(text("s000.sec1230.u58"));
        shared L417:
        show_textbox(text("s000.sec1230.u59"));
        shared L418:
        show_textbox(text("s000.sec1230.u60"));
        shared L419:
        show_textbox(text("s000.sec1230.u61"));
        shared L420:
        show_textbox(text("s000.sec1230.u62"));
        shared L421:
        show_textbox(text("s000.sec1230.u63"));
        shared L422:
        show_textbox(text("s000.sec1230.u64"));
        shared L423:
        show_textbox(text("s000.sec1230.u65"));
        shared L424:
        show_textbox(text("s000.sec1230.u66"));
        shared L425:
        show_textbox(text("s000.sec1230.u67"));
        shared L426:
        show_textbox(text("s000.sec1230.u68"));
        shared L427:
        show_textbox(text("s000.sec1230.u69"));
        shared L428:
        show_textbox(text("s000.sec1230.u70"));
        shared L429:
        show_textbox(text("s000.sec1230.u71"));
        shared L430:
        show_textbox(text("s000.sec1230.u72"));
        shared L431:
        show_textbox(text("s000.sec1230.u73"));
        shared L432:
        show_textbox(text("s000.sec1230.u74"));
        shared L433:
        show_textbox(text("s000.sec1230.u75"));
        shared L434:
        show_textbox(text("s000.sec1230.u76"));
        shared L435:
        show_textbox(text("s000.sec1230.u77"));
        shared L436:
        show_textbox(text("s000.sec1230.u78"));
        shared L437:
        show_textbox(text("s000.sec1230.u79"));
        shared L438:
        show_textbox(text("s000.sec1230.u80"));
        shared L439:
        show_textbox(text("s000.sec1230.u81"));
        shared L440:
        show_textbox(text("s000.sec1230.u82"));
        shared L441:
        show_textbox(text("s000.sec1230.u83"));
        shared L442:
        show_textbox(text("s000.sec1230.u84"));
        shared L443:
        show_textbox(text("s000.sec1230.u85"));
        shared L444:
        show_textbox(text("s000.sec1230.u86"));
        l7:
        show_textbox(text("s000.sec1230.u87"));
        l8:
        show_textbox(text("s000.sec1230.u88"));
        l9:
        show_textbox(text("s000.sec1230.u89"));
        l10:
        show_textbox(text("s000.sec1230.u90"));
        l11:
        show_textbox(text("s000.sec1230.u91"));
        l12:
        show_textbox(text("s000.sec1230.u92"));
        l13:
        show_textbox(text("s000.sec1230.u93"));
        l14:
        show_textbox(text("s000.sec1230.u94"));
        end_section();
    """)

@lib.section(1235)
def sec1235():    # section 1235
    dws(r"""
        goto l1;
        goto l2;
        goto l3;
        goto l4;
        goto l5;
        goto l6;
        goto l7;
        goto l8;
        goto l9;
        l1:
        show_textbox(text("s000.sec1235.u0"));
        l2:
        show_textbox(text("s000.sec1235.u1"));
        l3:
        show_textbox(text("s000.sec1235.u2"));
        l4:
        show_textbox(text("s000.sec1235.u3"));
        l5:
        show_textbox(text("s000.sec1235.u4"));
        l6:
        show_textbox(text("s000.sec1235.u5"));
        l7:
        show_textbox(text("s000.sec1235.u6"));
        l8:
        show_textbox(text("s000.sec1235.u7"));
        l9:
        show_textbox(text("s000.sec1235.u8"));
        end_section();
    """)

@lib.section(1236)
def sec1236():    # section 1236
    dws(r"""
        goto l1;
        goto l2;
        goto l3;
        goto l4;
        goto l5;
        goto l6;
        goto l7;
        goto l8;
        goto l9;
        goto l10;
        goto l11;
        goto l12;
        l1:
        show_textbox(text("s000.sec1236.u0"));
        l2:
        show_textbox(text("s000.sec1236.u1"));
        l3:
        show_textbox(text("s000.sec1236.u2"));
        l4:
        show_textbox(text("s000.sec1236.u3"));
        l5:
        show_textbox(text("s000.sec1236.u4"));
        l6:
        show_textbox(text("s000.sec1236.u5"));
        l7:
        show_textbox(text("s000.sec1236.u6"));
        l8:
        show_textbox(text("s000.sec1236.u7"));
        l9:
        show_textbox(text("s000.sec1236.u8"));
        l10:
        show_textbox(text("s000.sec1236.u9"));
        l11:
        show_textbox(text("s000.sec1236.u10"));
        l12:
        show_textbox(text("s000.sec1236.u11"));
        end_section();
    """)

@lib.section(1237)
def sec1237():    # section 1237
    dws(r"""
        goto l1;
        goto l2;
        goto l3;
        goto l4;
        goto l5;
        goto l6;
        l1:
        show_textbox(text("s000.sec1237.u0"));
        l2:
        show_textbox(text("s000.sec1237.u1"));
        l3:
        show_textbox(text("s000.sec1237.u2"));
        l4:
        show_textbox(text("s000.sec1237.u3"));
        l5:
        show_textbox(text("s000.sec1237.u4"));
        l6:
        show_textbox(text("s000.sec1237.u5"));
        end_section();
    """)

@lib.section(1238)
def sec1238():    # section 1238
    dws(r"""
        goto l1;
        goto l2;
        goto l3;
        goto l4;
        goto l5;
        goto l6;
        goto l7;
        goto l8;
        goto l9;
        goto l10;
        goto l11;
        goto l12;
        goto l13;
        goto l14;
        goto l15;
        goto l16;
        goto l17;
        goto l18;
        goto l19;
        goto l20;
        goto l21;
        goto l22;
        goto l23;
        goto l24;
        goto l25;
        goto l26;
        goto l27;
        goto l28;
        goto l29;
        goto l30;
        goto l31;
        goto l32;
        goto l33;
        l1:
        show_textbox(text("s000.sec1238.u0"));
        l2:
        show_textbox(text("s000.sec1238.u1"));
        l3:
        show_textbox(text("s000.sec1238.u2"));
        l4:
        show_textbox(text("s000.sec1238.u3"));
        l5:
        show_textbox(text("s000.sec1238.u4"));
        l6:
        show_textbox(text("s000.sec1238.u5"));
        l7:
        show_textbox(text("s000.sec1238.u6"));
        l8:
        show_textbox(text("s000.sec1238.u7"));
        l9:
        show_textbox(text("s000.sec1238.u8"));
        l10:
        show_textbox(text("s000.sec1238.u9"));
        l11:
        show_textbox(text("s000.sec1238.u10"));
        l12:
        show_textbox(text("s000.sec1238.u11"));
        l13:
        show_textbox(text("s000.sec1238.u12"));
        l14:
        show_textbox(text("s000.sec1238.u13"));
        l15:
        show_textbox(text("s000.sec1238.u14"));
        l16:
        show_textbox(text("s000.sec1238.u15"));
        l17:
        show_textbox(text("s000.sec1238.u16"));
        l18:
        show_textbox(text("s000.sec1238.u17"));
        l19:
        show_textbox(text("s000.sec1238.u18"));
        l20:
        show_textbox(text("s000.sec1238.u19"));
        l21:
        show_textbox(text("s000.sec1238.u20"));
        l22:
        show_textbox(text("s000.sec1238.u21"));
        l23:
        show_textbox(text("s000.sec1238.u22"));
        l24:
        show_textbox(text("s000.sec1238.u23"));
        l25:
        show_textbox(text("s000.sec1238.u24"));
        l26:
        show_textbox(text("s000.sec1238.u25"));
        l27:
        show_textbox(text("s000.sec1238.u26"));
        l28:
        show_textbox(text("s000.sec1238.u27"));
        l29:
        show_textbox(text("s000.sec1238.u28"));
        l30:
        show_textbox(text("s000.sec1238.u29"));
        l31:
        show_textbox(text("s000.sec1238.u30"));
        l32:
        show_textbox(text("s000.sec1238.u31"));
        l33:
        show_textbox(text("s000.sec1238.u32"));
        end_section();
    """)

@lib.section(1240)
def sec1240():    # section 1240
    dws(r"""
        goto l1;
        goto l2;
        goto l3;
        goto l4;
        goto l5;
        goto l6;
        goto l7;
        goto l8;
        l1:
        show_textbox(text("s000.sec1240.u0"));
        l2:
        show_textbox(text("s000.sec1240.u1"));
        l3:
        show_textbox(text("s000.sec1240.u2"));
        l4:
        show_textbox(text("s000.sec1240.u3"));
        l5:
        show_textbox(text("s000.sec1240.u4"));
        l6:
        show_textbox(text("s000.sec1240.u5"));
        l7:
        show_textbox(text("s000.sec1240.u6"));
        l8:
        show_textbox(text("s000.sec1240.u7"));
        end_section();
    """)

@lib.section(1241)
def sec1241():    # section 1241
    sound(0, 6)
    tamer.say(t1241.u0)

@lib.section(1242)
def sec1242():    # section 1242
    sound(0, 6)
    tamer.say(t1242.u0)

@lib.section(1243)
def sec1243():    # section 1243
    dws(r"""
        goto l1;
        goto l2;
        goto l3;
        goto l4;
        goto l5;
        goto l6;
        l1:
        show_textbox(text("s000.sec1243.u0"));
        l2:
        show_textbox(text("s000.sec1243.u1"));
        l3:
        show_textbox(text("s000.sec1243.u2"));
        l4:
        show_textbox(text("s000.sec1243.u3"));
        l5:
        show_textbox(text("s000.sec1243.u4"));
        l6:
        show_textbox(text("s000.sec1243.u5"));
        end_section();
    """)

@lib.section(1244)
def sec1244():    # section 1244
    raw.play_sound(0, 7)
    raw.delay(10)
    raw.set_dialog_owner(tamer)
    if pstat(254) == 0:
        raw.show_textbox(t1244.u0)
    else:
        raw.show_textbox(t1244.u1)

@lib.section(1245)
def sec1245():    # section 1245
    sound(0, 9)
    if not recruited(Species.Agumon):
        warp(Screen.file_city_204, entry=0)
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_170, entry=0)
            if recruited(Species.Palmon):
                warp(Screen.file_city_169, entry=0)
            warp(Screen.file_city_168, entry=0)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=0)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=0)
        warp(Screen.file_city_171, entry=0)
    if not recruited(Species.Birdramon):
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_176, entry=0)
        if recruited(Species.Palmon):
            warp(Screen.file_city_175, entry=0)
        warp(Screen.file_city_174, entry=0)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=0)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=0)
    warp(Screen.file_city_177, entry=0)

@lib.section(1246)
def sec1246():    # section 1246
    engine.no_escape.clear()
    partner_death_started.set()
    if partner.lives == 0 and partner.hp == 0:
        raw.section_on_exit(73)
        raw.call_digimon_routine(DigimonRoutine.sickness_death)
        narrator.arrived()
        return
    if partner.lives == 0 and partner.hp != 0:
        raw.section_on_exit(73)
        raw.call_digimon_routine(DigimonRoutine.sickness_death)
        narrator.arrived()
        return
    if partner.lifetime <= 0:
        raw.section_on_exit(71)
        raw.call_digimon_routine(DigimonRoutine.dying_a)
        narrator.arrived()
        return
    raw.section_on_exit(72)
    raw.call_digimon_routine(DigimonRoutine.battle_death)
    narrator.arrived()

@lib.section(1250)
def sec1250():    # section 1250
    raw.call_digimon_routine(DigimonRoutine.toilet)
    narrator.arrived()
    sound(0, 10)

@lib.section(1251)
def sec1251():    # section 1251
    slot0.say(t1251.u0)
    return sec1253()

@lib.section(1253)
def sec1253():    # section 1253
    raw.teleport(engine.object)

@lib.section(1252)
def sec1252():    # section 1252
    jump_to_script(7, 82)

def L228():    # shared code (the disc's label L228)
    top_map_residents_placed.set(0)
    load(Species.Tanemon)
    spawn(Species.Tanemon, slot=6)
    top_map_residents_placed.add(1)
    return L231()

def L229():    # shared code (the disc's label L229)
    top_map_residents_placed.set(0)
    load(Species.Palmon164)
    spawn(Species.Palmon164, slot=6)
    top_map_residents_placed.add(1)
    return L231()

def L230():    # shared code (the disc's label L230)
    top_map_residents_placed.set(0)
    load(Species.Vegiemon147)
    spawn(Species.Vegiemon147, slot=6)
    top_map_residents_placed.add(1)
    return L231()

def L231():    # shared code (the disc's label L231)
    if recruited(Species.Whamon):
        load(Species.Whamon146)
        spawn(Species.Whamon146, slot=7)
        top_map_residents_placed.add(1)
    if greymon_challenge_ready and not recruited(Species.Greymon):
        return
    if mt_infinity_entrance_found and not trigger(355):
        return
    if not city_resident_met.kokatorimon and recruited(Species.Kokatorimon):
        load(Species.Kokatorimon168)
        spawn(Species.Kokatorimon168, slot=3)
        top_map_residents_placed.add(1)
    if top_map_residents_placed == 3:
        return
    if clock.hour >= 7 and clock.hour < 19:
        roll = random.roll(3)
        if recruited(Species.Andromon) and roll <= 0 and top_map_residents_placed <= 2:
            load(Species.Andromon160)
            spawn(Species.Andromon160, slot=2)
            top_map_residents_placed.add(1)
        if top_map_residents_placed == 3:
            return
        load(Species.Yuramon)
        spawn(Species.Yuramon, slot=0)
        return
    if top_map_residents_placed > 2:
        return
    if recruited(Species.Kokatorimon) and city_resident_met.kokatorimon and date_hour >= 4 and date_hour < 8:
        load(Species.Kokatorimon168)
        spawn(Species.Kokatorimon168, slot=3)
        top_map_residents_placed.add(1)
    if top_map_residents_placed == 3:
        return
    if recruited(Species.Sukamon):
        load(Species.Sukamon159)
        spawn(Species.Sukamon159, slot=1)
    return

def L247():    # shared code (the disc's label L247)
    dws(r"""
        p38 = 0;
        p39 = 0;
        unless (is_recruited(species(4))) goto l2;
        unless (is_recruited(species(31)) || is_recruited(species(45)) || is_recruited(species(33)) || is_recruited(species(47))) goto l1;
        goto l2;
        l1:
        p38 += 1;
        load_digimon(species(128));
        set_digimon(species(128), 2, 0);
        l2:
        unless (!trigger(77) && is_recruited(species(37))) goto l3;
        p38 += 1;
        load_digimon(species(157));
        set_digimon(species(157), 0, 0);
        l3:
        unless (!trigger(78) && is_recruited(species(35))) goto l4;
        p38 += 1;
        load_digimon(species(155));
        set_digimon(species(155), 1, 0);
        l4:
        unless (p38 == 3) goto l5;
        end_section();
        l5:
        unless (!trigger(79) && is_recruited(species(32))) goto l6;
        p38 += 1;
        load_digimon(species(152));
        set_digimon(species(152), 3, 0);
        l6:
        unless (p38 == 3) goto l7;
        end_section();
        l7:
        store_date(p105);
        unless (p107 >= 7 && p107 < 19) goto l8;
        goto l10;
        l8:
        unless (!trigger(80) && is_recruited(species(18))) goto l9;
        p38 += 1;
        load_digimon(species(140));
        set_digimon(species(140), 5, 0);
        l9:
        unless (p38 == 3) goto l10;
        end_section();
        l10:
        store_date(p105);
        unless (p107 >= 7 && p107 < 19) goto l11;
        goto l12;
        goto l12;
        l11:
        goto l21;
        l12:
        p38 += 1;
        load_digimon(species("Tsunomon"));
        set_digimon(species("Tsunomon"), 4, 0);
        unless (p38 == 3) goto l13;
        end_section();
        l13:
        unless (is_recruited(species(4))) goto l14;
        unless (is_recruited(species(31)) || is_recruited(species(45)) || is_recruited(species(33)) || is_recruited(species(47))) goto l14;
        p38 += 1;
        load_digimon(species(128));
        set_digimon(species(128), 2, 0);
        unless (p38 == 3) goto l14;
        end_section();
        l14:
        store_random(p110, 1);
        unless (p110 == 0 && is_recruited(species(35)) && trigger(78)) goto l15;
        goto l17;
        l15:
        unless (is_recruited(species(34))) goto l16;
        p38 += 1;
        load_digimon(species(154));
        set_digimon(species(154), 7, 0);
        l16:
        unless (p38 == 3) goto l17;
        end_section();
        l17:
        unless (is_recruited(species(35)) && trigger(78)) goto l18;
        p38 += 1;
        load_digimon(species(155));
        set_digimon(species(155), 1, 0);
        l18:
        unless (p38 == 3) goto l19;
        end_section();
        l19:
        p39 += 1;
        unless (p39 < 2) goto l20;
        goto l21;
        l20:
        end_section();
        l21:
        store_date(p105);
        unless (p107 >= 7 && p107 < 19) goto l22;
        goto l24;
        l22:
        unless (is_recruited(species(37)) && trigger(77)) goto l23;
        p38 += 1;
        load_digimon(species(157));
        set_digimon(species(157), 0, 0);
        l23:
        unless (p38 == 3) goto l24;
        end_section();
        l24:
        unless (is_recruited(species(18))) goto l25;
        p38 += 1;
        load_digimon(species(140));
        set_digimon(species(140), 5, 0);
        l25:
        unless (p38 == 3) goto l26;
        end_section();
        l26:
        store_random(p110, 1);
        unless (p110 == 0 && is_recruited(species(54))) goto l27;
        goto l29;
        l27:
        unless (is_recruited(species(32)) && trigger(79)) goto l28;
        p38 += 1;
        load_digimon(species(152));
        set_digimon(species(152), 3, 0);
        l28:
        unless (p38 == 3) goto l29;
        end_section();
        l29:
        unless (is_recruited(species(54))) goto l30;
        p38 += 1;
        load_digimon(species(172));
        set_digimon(species(172), 6, 0);
        l30:
        unless (p38 == 3) goto l31;
        end_section();
        l31:
        p39 += 1;
        unless (p39 < 2) goto l32;
        goto l12;
        l32:
        end_section();
    """)

# the section table, in the order of the original header
sections(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 1220, 1221, 1222, 1223, 1224, 1225, 1226, 1227, 1228, 1229, 1230, 1235, 1236, 1237, 1238, 1240, 1241, 1242, 1243, 1244, 1245, 1246, 1250, 1251, 1253, 1252)
