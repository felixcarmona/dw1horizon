# The Item Bank (211): Floramon, from the Native Forest, tends the seed it was guarding, in a little garden behind the vault.
from dw import *
from dw.base.item_keeper import keeper as bank, poyomon

floramon = bank.npc(Species.Floramon, at=(-300, -700), behaves_like=poyomon, when=recruited(Species.Floramon))


@floramon.on_talk
def talk():
    say("The vault keeps your things safe. I keep the seeds safe.", "Yours is growing. Everything grows here, even in the shade of a safe.")
