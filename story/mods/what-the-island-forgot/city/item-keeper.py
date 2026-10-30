# The Item Bank (211): Weedmon, from the Great Canyon, tends a little garden behind the vault.
from dw import *
from dw.base.item_keeper import keeper as bank, poyomon

weedmon = bank.npc(Species.Weedmon, at=(-300, -700), behaves_like=poyomon, when=recruited(Species.Weedmon))


@weedmon.on_talk
def talk():
    say("The vault keeps your things safe. I keep the seeds safe.", "Everything grows here, even in the shade of a safe.")
