"""Names of animation slots, only where the engine itself gives the meaning.

An animation slot is an index into the animation table of a model; the table has no names on the
disc. What a slot *is* depends on the model, so a name here is tied to the kind of entity that plays it, and each is derived from code in
`decomp/` (the file:line is the evidence). A slot that the engine never uses for a meaning stays a number (the 28-32 of the NPC gestures,
the tamer's 15-26 cutscene poses): the beautifier writes `animate(who, 29)`.

    kind 'tamer'    entity TAMER   (the tamer's own model)
    kind 'partner'  entity PARTNER (a partner Digimon model: the care slots exist on those)
    kind 'npc'      entities 5-12  (any model: only the slots every model has)

`story/core/scene.dws` declares `group anim` with exactly these names (a test checks that), so `animate(tamer, anim.walk)` is the same number.
"""

# name -> (slot, entities it is certain for, evidence)
ANIMS = {
    'idle':          (0, ('tamer', 'partner', 'npc'), 'every entity starts on slot 0 (model.c:2863); the tamer and the partner return to it (partner.c:692, 725)'),
    'walk':          (2, ('tamer', 'partner', 'npc'), 'the walk of the `walk` command: slot 0 + 2 for the tamer, (0 + 1) << 1 for the others (script_interp.c:803-812)'),
    'tamer_run':     (3, ('tamer',), 'the run of the `run` command for the tamer: 1 + 2 (script_interp.c:806); tamer.c:518'),
    'run':           (4, ('partner', 'npc'), 'the run of the `run` command for the others: (1 + 1) << 1 (script_interp.c:809, 812); the partner catching up, partner.c:837-851'),
    'battle_ready':  (1, ('tamer',), 'the tamer waiting in a fight (btl.c:372, battle_setup.c:284, battle_tick.c:288)'),
    'tired_idle':    (1, ('partner',), 'the partner idles on 1 while SLEEPY, TIRED, INJURED or SICK (setPartnerIdle, partner.c:1054-1068)'),
    'offer_item':    (5, ('tamer',), 'the tamer holds out the item to the partner (partner.c:452; the item is handed over at frame 7)'),
    'happy_idle':    (5, ('partner',), 'a partner with no condition and happiness >= 31 (updateConditionAnimation, partner.c:1021)'),
    'sad_idle':      (7, ('partner',), 'the same with happiness < -30 (partner.c:1019)'),
    'eat':           (8, ('partner',), 'the partner eats the item it was given (partner.c:462) or the poop (partner.c:703)'),
    'poop':          (10, ('partner',), 'the partner relieves itself (partner.c:558, 600)'),
    'tamer_victory': (11, ('tamer',), 'the tamer cheers after a won fight (BTL_handleVictorySequence, battle_main.c:905)'),
    'refuse':        (13, ('partner',), 'the partner refuses the item (partnerWillRefuseItem, partner.c:466)'),
    'command':       (14, ('tamer',), 'the tamer gives an order in a fight (battle_tick.c:128-129)'),
    'sick':          (14, ('partner',), 'the warning of an INJURED or SICK partner (updateConditionAnimation, partner.c:1027)'),
    'hungry':        (15, ('partner',), 'the warning of a HUNGRY partner (partner.c:1035)'),
    'needs_toilet':  (16, ('partner',), 'the warning of a partner that has to poop (partner.c:1031)'),
    'sleepy':        (17, ('partner',), 'the warning of a SLEEPY partner (partner.c:1043)'),
    'tired':         (18, ('partner',), 'the warning of a TIRED partner (partner.c:1039)'),
    'unhappy':       (19, ('partner',), 'the warning of an UNHAPPY partner: it disobeys (partner.c:1047)'),
}

# what the engine does with a slot, but not enough to name it: written as a number with this comment
HINTS = {
    ('tamer', 4): 'the tamer after the partner refused an item (partner.c:507)',
    ('tamer', 8): 'the tamer settling the partner to sleep (partner.c:287)',
    ('tamer', 9): 'the tamer during brain training (trn_brain.c:96)',
    ('partner', 9): 'the partner after waking up (partner.c:302)',
    ('partner', 11): 'the partner reaction in the sleep scene (partner.c:295)',
    ('partner', 12): 'the partner after relieving itself (partner.c:611)',
}


def name_of(kind, slot):
    """The `anim.<name>` of a slot played by an entity of that kind, or None."""
    for nm, (n, kinds, _) in ANIMS.items():
        if n == slot and kind in kinds: return nm
    return None


def enum_source():
    """The text of `pub enum anim { ... }` in story/core/scene.dws."""
    out = ['pub group anim {']
    for nm, (n, kinds, why) in ANIMS.items(): out.append(f'    const {nm} = {n};    // {", ".join(kinds)}')
    out.append('}')
    return '\n'.join(out)
