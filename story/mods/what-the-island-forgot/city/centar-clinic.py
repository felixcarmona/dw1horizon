# The Clinic (213): Piddomon (Mt. Infinity) helps Centarumon at the second bed and Aruraumon (Native Forest) sells
# herbs and medicine by the stools, clear of the door (arrival at (1078, 786)).
from dw import *
from dw.base.centar_clinic import clinic, coelamon

piddomon = clinic.npc(Species.Piddomon, at=(-750, -550), behaves_like=coelamon, when=recruited(Species.Piddomon))
aruraumon = clinic.npc(Species.Aruraumon, at=(50, 1150), behaves_like=coelamon, when=recruited(Species.Aruraumon))


@piddomon.on_talk
def talk():
    say("My wing never healed well enough to fly up the mountain again.",
        "So I help Centarumon here. A healer who was hurt understands the hurt ones.")


@aruraumon.on_talk
def talk():
    say("Leaves for the cuts, roots for the fever. Everything grown in the forest by me!")
    shop(Item.Bandage, Item.Medicine, Item.SmRecovery, Item.MPFloppy)
