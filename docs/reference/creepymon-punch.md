# Creepymon Megaton Punch contact

Megaton Punch uses the native line-hit test between the attacker and its effect
origin. The attacker's AI approaches according to the normal melee range class.
A hand point that faces away from the target cannot connect, even when the
attacker starts at the expected distance.

Creepymon's imported shared attack turns its hand behind the body during the
hit window. The former Andromon-hand remap put the endpoint behind Creepymon:
one observed frame had attacker X/Z (-1998, -240), target (-1983, -612), and
endpoint (-1810, 120). The height check passed; the horizontal segment pointed
away from the opponent. Nine isolated attempts caused no damage.

The species record now maps that hand origin to an entity-relative contact
point, [0, 0, -160, -380] before the existing body-size bake. The generated
record contains [0, 0, -134, -319]. It follows the entity's heading rather than
the turning hand. The other effect-origin rows, model, animation programs,
collision radius, range class, power, MP cost and accuracy remain unchanged.
The fixed-size species record and archive do not grow.

Validation uses the original-2-MB emulator and the actual melee AI. The opponent
cannot cast during the isolated comparison, avoiding paralysis and attack
interruptions; its movement and the attacker's spacing remain native. The
rebuilt disc loaded the generated contact row into the native species cache
and produced two damaging attacks at AI-selected start distances of 259 and
305 units, each reducing the opponent's HP by 164 in this fixture. The earlier
live contact-point prototype also connected at 249 and 267 units. An opponent
that moves out of the segment during the windup can still evade the attack.

The final archive/disc validation and reviewed videos are recorded in the
worktree's uncommitted report. The source row is in
[the species record](../../content/species/312-creepymon.json).
