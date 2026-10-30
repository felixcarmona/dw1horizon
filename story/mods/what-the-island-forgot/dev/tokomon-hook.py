# Playtest hook (DEV=1 builds only): Tokomon in Jijimon's house sends the player to the Engine Room (screen 300), or
# recruits everyone the mod houses (the Works and the existing buildings) so the whole city can be seen without playing
# every fight.
from dw import *
from dw.base.jijimons_house import tokomon

toko = take_over(tokomon)


@toko.on_talk
def talk():
    if ask(yes="Engine Room", no="Recruit all"):
        warp(300, entry=0)
    recruit(Species.Golemon)
    recruit(Species.MoriShellmon)
    recruit(Species.Saberdramon)
    recruit(Species.NiseDrimogemon)
    recruit(Species.ModokiBetamon)
    recruit(Species.JMojyamon)
    recruit(Species.Guardromon)
    recruit(Species.Tankmon)
    recruit(Species.SandYanmamon)
    recruit(Species.Tentomon)
    recruit(Species.Yanmamon)
    recruit(Species.Geremon)
    recruit(Species.Goblimon)
    recruit(Species.Tekkamon)
    recruit(Species.BlueMeramon)
    recruit(Species.Flarerizamon)
    recruit(Species.SnowAgumon)
    recruit(Species.MudFrigimon)
    recruit(Species.SnowGoblimon)
    recruit(Species.Gotsumon)
    recruit(Species.ShimaUnimon)
    recruit(Species.ClearAgumon)
    recruit(Species.Psychemon)
    recruit(Species.Shamamon)
    recruit(Species.Tsukaimon)
    recruit(Species.Fugamon)
    recruit(Species.Hyogamon)
    recruit(Species.Muchomon)
    recruit(Species.Piddomon)
    recruit(Species.Aruraumon)
    recruit(Species.Soulmon)
    recruit(Species.ToyAgumon)
    recruit(Species.Icemon)
    recruit(Species.PlatinumSukamon)
    recruit(Species.Akatorimon)
    recruit(Species.Weedmon)
    recruit(Species.RedVegiemon)
    say("Everyone has moved in!")
