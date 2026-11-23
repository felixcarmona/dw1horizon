# Boosted techniques

Every raisable species that can learn an attacking technique has one regular technique it is better at: its
**boosted technique**. In that species' hands the technique hits harder and costs less MP. It is not given: the
partner still has to learn it like any other.

## What it does

- Power: `power + power / 8 + 30`. Weak techniques gain the most (Sonic Jab 52 becomes 88), strong ones the least
  (DG Dimension 722 becomes 842), and a boosted technique never overtakes a stronger one boosted the same way.
- MP cost: a quarter less (the stored cost, rounded).
- Only the partner gets it, and both fighters in VS. Wild Digimon, tournament opponents and bosses of the same species
  do not.
- The speed gauge is not touched: the technique is ready as fast as before.
- Finishers and Counter are never boosted.

The technique menu shows the boosted technique's power in red with a small up arrow and its MP cost in blue
with a small down arrow, in the equipped list and in the technique's panel, and its cell in the grid carries a small up arrow on its corner.

## Where it lives

- `content/species/*.json`: `"boosted_technique": "<technique>"`, one of the species' `techniques` (and of its
  `off.techniques` when it has a NEW DIGIMON off list). `tools/species.py` (`boosted_technique`) checks it.
- Species parameters: the last byte of each `DigimonPara` row (`boostedTech`, the technique + 1; padding in the
  original game), in the executable's table for the original species and in the `DIGI.DAT` record for the rest.
- Engine: `modBoost` in `src/main/mod_species.c`; the battle, the tournament and VS call it where damage and MP cost
  are computed (`MOD_BOOST_POWER`, `MOD_BOOST_COST` test for the partner). No table of its own: the main executable's
  size is the heap's.

## How the techniques were chosen

One per species, automatically, with three aims:

1. **Canon first.** Each species' learnable attacking techniques were ranked by how well they match one of its
   secondary attacks in the Digimon Reference Book (by form and element: a punch, a kick, a breath of fire, a blade of
   wind, a beam...), never its finisher. Species with no usable attack follow their first specialty.
2. **Balanced.** No technique is the boosted one of more than eight species; when a technique is full, the species takes
   its next best match. An evolution avoids repeating its pre-evolution's technique when it has another fit.
3. **Usable.** A technique the species cannot learn in battle is not chosen, one it learns rarely is avoided, Ultimates
   and Megas avoid techniques under 200 and 250 power, and DG Dimension only goes to Megas.
