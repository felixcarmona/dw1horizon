# Making a new species by hand (no source game has it)

How the eight babies 470-477 (Pabumon, Pichimon, YukimiBotamon, Nyokimon, Motimon, Bukamon, Nyaromon, Yokomon) were
made, written as a recipe for the next ones. The engine side (records, deltas, pins, re-porting) is in
[imported-species.md](../reference/imported-species.md) and `tools/models/babies/__init__.py`; this page is the
method that produced the models.

## 1. Check that no donor game has it

Search the cross-game catalogue first (`tools/crossgame.py`, the DCB/DW2/DW2003 name tables): an import from a
source game is always cheaper. None of the three source games has a Fresh or In-Training model (their models start at
Rookie), so every baby has to be drawn.

## 2. Choose a DW1 donor with the same rig needs

The new species keeps a DW1 Digimon's skeleton and every animation program byte for byte; only the mesh, UVs and
the texture page are new. Pick the donor by what the target needs to move, not by colour:

| target | donor | why |
|---|---|---|
| Pabumon | Punimon 15 | one-bone squash-and-stretch blob: reads as a bouncing slime |
| Pichimon, Motimon, Bukamon | Koromon 2 | body bone inside the body (grounded hop), two 2-segment ear chains for feelers or flippers |
| YukimiBotamon | Botamon 1 | the same character family |
| Nyokimon | Botamon 1 | seed body on the plain baby rig; Yuramon (43) was dropped: its hop and tuft junk objects made the clips unusable. Tsunomon (16) and Tokomon (30) also fit (hops taller than the body) |
| Nyaromon | Tokomon 30 | ears plus four feet |
| Yokomon | Tanemon 44 | bulb, stem, two leaf bones (petals) and four feet (roots) |

Before building, render the donor's slots (`tools/animstudio.py`) to see which bones swing and how far: geometry on a
bone that rotates 50-100 degrees around a distant pivot detaches. Parts that must not flap (Nyaromon's ears,
Nyokimon's sprout) go rigid on the body or head bone; the unused objects collapse to one point with one degenerate
primitive whose UV points at a texel of its own CLUT row.

## 3. References

- The official encyclopedia art (`https://digimon.net/cimages/digimon/<name>.jpg`, the Japanese romanisation).
- Many more from Wikimon: other official art, card art, and above all the 3D renders of modern games (DSTS stats
  renders, New Century, Re:Digitize) that show the back, the side and the top that a front drawing hides.

Keep references local and git-ignored (`build/`); never commit them.

## 4. Draw it with a script

One script per species (`tools/models/babies/authoring/<name>.py`, NumPy/OpenCV, developer only) builds the mesh from
profiles and lathes in ground space, writes it into the bones' local spaces, paints the whole 256x128 4 bpp page and
saves `<Name>.MMD` + `<Name>.TIM`. Lessons that cost iterations:

- Choose each CLUT row's 16 colours yourself; the generic quantiser greys out small details (blue eyes on a grey face).
- Repaint every eye and mouth frame that the texture animations copy (`tex_anims()`): open, half, closed, happy, hurt,
  eating. The face is usually mirrored around u = 0; give it its own UVs if the art is asymmetric.
- Paint the face rectangle's background with exactly the body's colours at its borders, or it shows as a pale box.
- Check winding (cull render = unculled render) and per-vertex normals; a column wound backwards is a hole the game culls.
- Budget: under 48 KB per MMD and about 400 primitives (DW1 babies are 15-42 KB, at most 234 primitives).

## 5. Review loop

- Judge with a renderer that lights like the game: per-vertex lighting from the TMD normals, interpolated
  (`authoring/gouraud.py`). `animstudio.py` shades each triangle flat and makes every model look faceted.
- Always compare against the reference side by side (front, 3/4, side, and the game's high camera at the size the
  partner has on screen, 25-60 px).
- Render several animation slots and ticks (idle 0, walk 2, happy 5, eat 8, asleep 9) for parts that detach, sink
  into the floor or float.
- A separate critic pass, given the references and the renders, ranks what still differs (silhouette from every angle,
  proportions, colours, every expression frame, appendages, animation problems); the fixes follow its list.
- Sizes: a Fresh must read smaller than its In-Training and an In-Training smaller than a Rookie. Measured rest
  heights (world units): DW1 Fresh 106-133, In-Training 180-245, Rookies 200-311. A uniform scale about the ground
  point (`authoring/shrink.py`) fixes a model that came out too big without touching its animations.

## 6. Into the game

Port with `python3 -m tools.models.babies encode-dir DIR` (plain MD3 deltas against the player's donor files, pinned
in `content/modeldelta/babies.json`), add the species file (`content/species/<id>-<name>.json`: `effects_like` = the
donor, partner rows from a native of the same stage, evolution links), build, and test in the emulator with the
Cheats menu: field, care, battle, evolution. Record the result as video.

## 7. Menu icon

Every species needs `content/icons/<id>.txt`: a 16x16 icon drawn by hand in four frames (`idle`, `idle2`, `atk`,
`hurt`), at most 15 colours plus transparency, near-black 1-pixel outline, three tones per colour with light from the
upper left, facing left, standing on the bottom row; a baby fills the box like the native babies do, not like a
Rookie. The in-game model is the colour authority. Without an icon the menus fall back to a render of the model, which
reads badly.

## 8. Place it in the evolution tree

The topology is `content/tables/evolution-tree.json` (`children` by name, `routes` by id; `tools/evo_tree.py --write`
writes the species files, `tools/test_evo_tree.py` and `tools/evo_check.py` guard it). Rules: canon line first, then
family and a shared specialty; the disc's own routes stay and keep winning their canonical state; parent order names the
primary parent (`requirements.digimon`). A canon In-Training among the hand-made babies replaces a native stand-in as
the primary parent, and the stand-in link goes when the child stays reachable with NEW DIGIMON on (with it off, no
import is raised).

Decisions (2026-11-03, the eight eggs):

| Rookie | parents before | parents now | why |
|---|---|---|---|
| Gomamon | Tsunomon, Bukamon | Bukamon | canon Bukamon line |
| Salamon | Tokomon, Nyaromon | Nyaromon | canon Nyaromon line |
| Kokuwamon | Tsunomon, Motimon | Motimon | machine family, shares Mech |
| Syakomon, Crabmon | Tsunomon | Bukamon | aquatic family, share Ice and Battle |
| Gizamon | Tsunomon, Bukamon | Bukamon, Tsunomon | aquatic family first |
| Floramon | Tanemon, Motimon, Yokomon | Yokomon, Tanemon | Yokomon's plant line; Motimon shares no specialty |
| Mushroomon | Tanemon | Tanemon, Yokomon | Yokomon's plant line, shares Nature |
| Hagurumon | Tokomon | Tokomon, Motimon | machine family, shares Mech |
| Bearmon | Tsunomon, Bukamon | Tsunomon, Nyaromon | beast family, shares Battle; Bukamon is aquatic |
| Hawkmon | Tokomon, Nyaromon, Yokomon | Tokomon, Yokomon | bird family |
| Dokunemon | Tanemon, Yokomon | Tanemon | insect, no Yokomon canon |

So Motimon raises Tentomon, Kokuwamon, Wormmon, Hagurumon; Bukamon Gomamon, Otamamon, Gizamon, Syakomon, Crabmon;
Nyaromon Salamon, Tsukaimon, DemiDevimon, Bearmon; Yokomon Biyomon, Floramon, Hawkmon, Mushroomon. Tentomon ← Tanemon
and Biyomon ← Tokomon stay the primary routes (disc routes). Tsunomon keeps seven Rookies, Tokomon ten.

2026-11-04: Vemmon (331, imported as a Champion under the wrong name Snatchmon) takes its canon level, Rookie. Its canon
In-Training, Bowmon, is not in the game, so it joins Motimon's machine line (shares Mech): Motimon raises five Rookies.
Its four Champions are canon Tyrannomon and stand-ins for its other canon forms: Hookmon for Snatchmon (a grabbing
hook), Tankmon for Destromon (an armoured war machine), BomberNanimon for Damemon (the comic no-good line); all share
Battle. Hagurumon and Kokuwamon keep four Champions each; Assaultmon and Knightmon keep three Champion parents.
