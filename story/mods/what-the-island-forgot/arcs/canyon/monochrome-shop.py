# The Monochrome Shop (49) after Monochromon has gone to File City: his cousin Tuskmon keeps it open. Before the recruit
# nothing changes (MAPHEAD loads Monochromon only while he is not recruited, Tuskmon only once he is, so they never meet).
#
# Talked to across the counter (use trigger 1, as Monochromon was; the base's use code returns at once after the
# recruit) or face to face: a normal shop, and a deal of the day. The deal is one item of DEAL_ITEMS, all worth 2000
# bits, offered at 2500. Haggling: a draw (60 %, then 40 %); a win takes 350 off (2150, then 1800, two at most), a loss
# annoys him and closes the deal until the next day. The lowest price stays far above the 1000 an item sells for.
#
# Saved: the deal's day (clock.day + 1: 0 is "never"), its item id and its step (0-2 the haggles won = the price,
# 3 closed, 4 bought). The original engine compares a saved number with constants only, so today is compared with the
# deal's day by counting both down in scratch pstats (93, 88, 89: outside the compiler's own 94-99; no yield inside the loop).
# The script has 16 KB for the game's 3 KB and this: the talk, the purchase and the haggle are each compiled once (a def
# that ends with dws("return;") is a shared block), not inlined at every call.
from dw import *
from dw.base.monochrome_shop import shop_, monochromon

tuskmon = shop_.npc(Species.Tuskmon, at=(-341, 292), behaves_like=monochromon, still=True,
                    when=recruited(Species.Monochromon))
tuskmon_met = flag()
deal_day = counter()
deal_item = counter()
deal_step = counter()

ITEM = 93            # scratch: the deal's item id, for {item 93}
TODAY = 88           # scratch: 1 when the deal is today's
LEFT = 89            # scratch: the countdown, then a yes/no


def deal_is_today():
    pstat(TODAY).set(0)
    pstat(LEFT).set(clock.day)
    pstat(LEFT).add(1)
    pstat(ITEM).set(deal_day)
    while pstat(ITEM) >= 1:
        if pstat(LEFT) == 0:
            break
        pstat(LEFT).sub(1)
        pstat(ITEM).sub(1)
    if pstat(LEFT) == 0 and pstat(ITEM) == 0:
        pstat(TODAY).set(1)


def new_deal():
    deal_day.set(clock.day)
    deal_day.add(1)
    deal_step.set(0)
    roll = random.roll(3)
    if roll == 0:
        deal_item.set(6)        # Large MP
    elif roll == 1:
        deal_item.set(9)        # Omnipotent
    elif roll == 2:
        deal_item.set(37)       # Health shoe
    else:
        deal_item.set(66)       # Digicatfish


def buy():
    pstat(LEFT).set(0)          # 1: the tamer can pay the current price
    if deal_step == 0 and bits >= 2500:
        pstat(LEFT).set(1)
    if deal_step == 1 and bits >= 2150:
        pstat(LEFT).set(1)
    if deal_step == 2 and bits >= 1800:
        pstat(LEFT).set(1)
    if pstat(LEFT) == 0:
        tuskmon.say("You don't have the bits. No bits, no deal.")
    else:
        if deal_item == 6:
            give(Item.LargeMP)
        elif deal_item == 9:
            give(Item.Omnipotent)
        elif deal_item == 37:
            give(Item.HealthShoe)
        else:
            give(Item.Digicatfish)
        if trigger(0):          # GIVE_ITEM sets trigger 0 when the bag has no room: nothing is taken
            tuskmon.say("Your bag is full. Make some room first.")
        else:
            if deal_step == 0:
                take(bits=2500)
            elif deal_step == 1:
                take(bits=2150)
            else:
                take(bits=1800)
            deal_step.set(4)
            narrator.say("Received {item 93}.")
            tuskmon.say("Pleasure doing business. Same time tomorrow.")
    dws("return;")


def haggle():
    pstat(LEFT).set(0)          # 1: the haggle is won (60 % on the first, 40 % on the second)
    if deal_step == 0:
        if random.chance(60):
            pstat(LEFT).set(1)
    elif random.chance(40):
        pstat(LEFT).set(1)
    if pstat(LEFT) == 0:
        pstat(247).set(10)      # the mood bubble of Monochromon's customers, over Tuskmon (script id 10: slot 5)
        pstat(248).set(3)       # 3: the angry face of the five (0 laughing ... 4 furious)
        call(Routine.monochromon_mood_bubble)
        wait(1000)
        deal_step.set(3)
        tuskmon.say("Hmph! Now you insult me. No deal today. Come back tomorrow.")
        pstat(248).set(5)       # 5 takes the bubble away (it stays up until told, as the customers' scenes do)
        call(Routine.monochromon_mood_bubble)
    elif deal_step == 0:
        deal_step.set(1)
        tuskmon.say("Grr... Fine. 2150 bits. Happy now?")
    else:
        deal_step.set(2)
        tuskmon.say("You drive a hard bargain. 1800 bits, and that's my last word.")
    dws("return;")


def deal():
    deal_is_today()
    if pstat(TODAY) == 0:
        new_deal()
    pstat(ITEM).set(deal_item)
    if deal_step == 4:
        tuskmon.say("Today's deal is sold. Come back tomorrow.")
    elif deal_step == 3:
        tuskmon.say("No deal for you today. Tomorrow, maybe.")
    else:
        if deal_step == 0:
            tuskmon.say("Today's deal: {item 93}. Not easy to find around here. 2500 bits.")
        elif deal_step == 1:
            tuskmon.say("{item 93} for 2150 bits. Take it or leave it.")
        else:
            tuskmon.say("{item 93} for 1800 bits. Not one bit less.")
        if deal_step == 2:
            if tuskmon.ask(yes="Buy it", no="Leave it"):
                buy()
        else:
            match tuskmon.choose(buy="Buy it", haggle="Haggle", leave="Leave it"):
                case "buy":
                    buy()
                case "haggle":
                    haggle()
                case _:
                    pass
        tuskmon.say("Your loss.")


def conversation():
    if not tuskmon_met:
        tuskmon_met.set()
        tuskmon.say("Looking for Monochromon? My cousin packed up and moved to File City.",
                    "Said the city needs him more. So I run the shop now.")
        tuskmon.say("I don't do smiles, but my prices are fair. Most days.")
    else:
        tuskmon.say("You again. What do you need?")
    match tuskmon.choose(shop="Buy or sell", deal="Deal of the day", leave="Nothing"):
        case "shop":
            tuskmon.say("Good stuff for the canyon road. Take a look.")
            tuskmon.shop(Item.MedRecovery, Item.MPFloppy, Item.Bandage, Item.Meat, Item.GiantMeat, Item.PortPotty,
                         Item.AutoPilot)
        case "deal":
            deal()
        case _:
            tuskmon.say("Then don't block the counter.")
    dws("return;")


@tuskmon.on_talk
def talk():
    conversation()


# The counter, where Monochromon was talked to (the base's use code returns at once after the recruit).
@shop_.on_use(1, when=recruited(Species.Monochromon))
def counter():
    tamer.face(tuskmon)
    conversation()
