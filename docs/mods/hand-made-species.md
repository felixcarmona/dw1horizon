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

## Nyokimon size review (2026-11-16)

World-space rendered triangle bounds over every tick (height × width; root travel does not change extents). These are mesh measurements, not `model.height`, which is camera metadata. The table uses the current main device models, and the player extraction for natives.

| Species | JSON height / radius | Idle H × W range | Walk H × W range | Bubble (46) H × W range |
| --- | --- | --- | --- | --- |
| Botamon (before) | 120 / 95 | 106.0–127.2 × 115.2–144.0 | 36.3–156.0 × 85.3–226.9 | 106.0–204.2 × 144.0–144.0 |
| Koromon (before) | 150 / 100 | 180.0–188.0 × 178.0–178.0 | 133.7–205.0 × 151.3–213.6 | 123.5–284.5 × 124.6–204.7 |
| Punimon (before) | 120 / 95 | 55.7–192.4 × 79.8–175.6 | 87.4–171.4 × 89.8–185.3 | 74.4–167.8 × 79.7–172.8 |
| Tanemon (before) | 230 / 100 | 236.0–297.2 × 275.0–297.2 | 252.7–311.7 × 192.0–297.2 | 236.0–312.7 × 259.1–297.0 |
| Pabumon (before) | 120 / 95 | 106.8–134.4 × 170.6–191.4 | 90.7–159.7 × 155.8–203.9 | 72.0–167.6 × 99.1–214.8 |
| Pichimon (before) | 150 / 95 | 144.6–159.4 × 132.6–141.0 | 134.8–160.7 × 114.8–148.8 | 111.5–218.3 × 96.6–158.7 |
| YukimiBotamon (before) | 120 / 95 | 115.3–120.8 × 147.1–158.6 | 103.5–129.2 × 144.1–160.6 | 107.3–223.6 × 148.0–148.0 |
| Nyokimon (before) | 130 / 90 | 118.5–144.4 × 117.4–130.3 | 109.7–141.2 × 118.3–134.3 | 102.0–228.8 × 125.0–125.0 |
| Motimon (before) | 160 / 100 | 155.9–164.2 × 164.8–172.0 | 150.1–172.2 × 163.6–176.7 | 126.2–227.6 × 122.5–201.2 |
| Bukamon (before) | 200 / 100 | 184.7–193.5 × 141.3–148.9 | 177.8–197.5 × 145.2–155.7 | 143.2–253.0 × 96.6–158.7 |
| Nyaromon (before) | 170 / 100 | 157.2–167.5 × 186.0–211.3 | 153.4–169.4 × 185.3–213.6 | 147.4–204.3 × 171.4–217.8 |
| Yokomon (before) | 240 / 100 | 232.4–235.4 × 186.0–241.6 | 221.2–248.9 × 186.0–257.7 | 232.1–251.2 × 185.8–238.5 |
| Nyokimon (after) | 175 / 100 | 159.8–194.8 × 157.7–176.1 | 147.9–190.6 × 160.0–181.5 | 137.2–309.8 × 169.0–169.0 |

Commit `765f6567` pins the earlier scaled-down models; the actual size operation lives in `authoring/shrink.py` (0.80 for Nyokimon). Nyokimon was subsequently rebound to Botamon in `5b7f2f47`, retaining that factor. `content/models/imports/import-sizes.json` does not exist in this tree; the importer size manifest is `content/modeldelta/import-sizes.json`, and it has no Nyokimon entry because the baby uses its own authored delta builder.

Use 1.08 of the authored mesh instead: a 108-unit body rather than 80, with a 174-unit neutral silhouette (169 wide). Botamon is 106 high and 144 wide; Nyokimon’s sprout accounts for its extra height. Field idle starts at 175 × 168 and stays under 200, in the Bukamon height class and below Yokomon. Regenerate the calm clips against the resized mesh to solve floor contact again; keep the donor battle programs and native field speeds. Radius 100 matches the other in-training-sized silhouettes. All occupied battle slots were measured, including 33–36, 40–44 and Bubble 46; donor squash and rolls explain their changing bounds.

Pack the 176 existing triangle pairs as PS1 quads on the same diagonal: 208 stored primitives still render the identical 384 triangles, including winding, UVs, normals and palette. This recovers 3,520 bytes to pay for the shared field-origin fix without increasing resident data. The field-origin pass is the shared `nyaromon-shadow` implementation invoked by `babies.encode`; no separate Nyokimon shadow algorithm is needed.

Battle slots use the same mesh; these extrema include the donor’s squash, turns and leaps, rather than a change of authored scale.

| Species | Battle idle (33) H × W | Tired idle (34) H × W | Move (35) H × W | Move (36) H × W |
| --- | --- | --- | --- | --- |
| Botamon | 106.0–127.2 × 115.2–144.0 | 84.8–106.0 × 144.0–172.8 | 36.3–156.0 × 85.3–226.9 | 50.7–162.2 × 43.2–219.3 |
| Koromon | 180.0–188.0 × 178.0–178.0 | 116.4–147.8 × 249.2–287.2 | 133.7–205.0 × 151.3–213.6 | 133.7–205.0 × 151.3–213.6 |
| Punimon | 55.7–192.4 × 79.8–175.6 | 98.2–124.0 × 144.0–165.7 | 87.4–171.4 × 89.8–185.3 | 87.4–171.4 × 89.8–185.3 |
| Tanemon | 236.0–297.2 × 275.0–297.2 | 231.4–248.5 × 186.0–275.0 | 252.7–311.7 × 192.0–297.2 | 252.7–311.7 × 192.0–297.2 |
| Pabumon | 53.9–186.2 × 99.9–218.3 | 95.1–120.0 × 179.0–211.8 | 84.9–159.4 × 110.8–230.9 | 84.9–159.4 × 110.8–230.9 |
| Pichimon | 152.0–169.3 × 138.0–138.0 | 114.9–141.4 × 117.6–124.7 | 87.1–163.7 × 117.3–165.6 | 87.1–163.7 × 117.3–165.6 |
| YukimiBotamon | 118.0–141.6 × 118.4–148.0 | 94.4–118.0 × 148.0–177.6 | 40.4–170.9 × 87.7–233.2 | 56.4–174.5 × 44.4–225.4 |
| Nyokimon (before) | 129.0–154.8 × 100.0–125.0 | 103.2–129.0 × 125.0–150.0 | 44.2–185.7 × 74.0–197.0 | 61.5–185.5 × 37.5–190.4 |
| Motimon | 160.0–184.0 × 175.0–175.0 | 136.0–160.0 × 157.2–163.2 | 111.7–181.6 × 148.7–210.0 | 111.7–181.6 × 148.7–210.0 |
| Bukamon | 191.0–219.6 × 138.0–138.0 | 162.3–191.0 × 196.8–202.5 | 121.3–209.1 × 117.3–165.6 | 121.3–209.1 × 117.3–165.6 |
| Nyaromon | 157.2–167.5 × 186.0–211.3 | 149.9–161.0 × 198.0–217.8 | 153.4–169.4 × 185.3–213.6 | 147.4–169.0 × 189.2–223.4 |
| Yokomon | 232.4–235.4 × 186.0–241.6 | 227.0–251.2 × 186.0–186.0 | 221.2–248.9 × 186.0–257.7 | 220.6–248.9 × 186.0–257.7 |
| Nyokimon (after) | 174.0–208.8 × 135.2–169.0 | 139.2–174.0 × 169.0–202.8 | 59.6–250.5 × 100.1–266.3 | 83.0–250.2 × 50.7–257.4 |

Final resident data: 24,510 bytes versus 26,190 on main (−1,680), including centering; texture unchanged. Use `python3 -m tools.models.babies encode 473 ...` for the delta pins, then `python3 -m tools.derive.steps.species pin OUT 473` for the provider pin. Never edit either hash by hand.


## Pichimon size review (2026-11-16)

Use the Nyokimon review's rendered world-space bounds and decision rule above: judge body bulk against native babies, with the neutral silhouette no taller than Bukamon/Yokomon. Pichimon's 92-unit round head was narrower than Botamon's 106-unit body; feelers and tail made its 152-unit neutral height misleading. Apply 1.20 in the same ground-anchored `authoring/shrink.py` pass: head diameter about 110, neutral silhouette 182 × 166, first field idle 185.5 × 167.3. This is above Botamon's bulk, near Koromon, below Bukamon's 191-unit neutral height and Yokomon's 233. JSON height/radius changes from 150/95 to 185/100, matching the shared native-baby radius choice.

Pichimon is absent from `content/modeldelta/import-sizes.json`: its size comes from its authored mesh delta, not the imported-model sizing rules. The requested `content/models/imports/import-sizes.json` path does not exist. Commit `765f6567` actually says “Pin the scaled-down Nyokimon, Nyaromon and Yokomon”; it does not modify Pichimon. The cause here is the small authored mesh, rather than a later import scale pin.

Bounds over every tick, H range × W range in DW1 units (travel changes position, not dimensions):

| Clip | Before | After |
| --- | --- | --- |
| Field idle (0) | 144.6–159.4 × 132.6–141.0 | 173.4–188.6 × 157.9–169.4 |
| Walk (2) | 134.8–160.7 × 114.8–148.8 | 162.1–192.5 × 137.6–178.8 |
| Tired walk (3) | 123.4–148.5 × 143.1–153.5 | 149.1–175.7 × 171.0–185.5 |
| Run (4) | 133.7–152.7 × 96.5–124.2 | 156.4–184.0 × 115.7–149.0 |
| Battle 33 (33) | 152.0–169.3 × 138.0–138.0 | 182.0–204.3 × 166.0–166.0 |
| Battle 34 (34) | 114.9–141.4 × 117.6–124.7 | 136.8–170.1 × 142.5–160.3 |
| Battle 35 (35) | 87.1–163.7 × 117.3–165.6 | 104.2–196.0 × 141.1–199.2 |
| Battle 36 (36) | 87.1–163.7 × 117.3–165.6 | 104.2–196.0 × 141.1–199.2 |
| Battle 37 (37) | 111.0–195.4 × 103.5–151.8 | 134.6–225.1 × 124.5–182.6 |
| Battle 40 (40) | 85.4–188.2 × 138.0–220.9 | 98.7–223.7 × 166.0–250.9 |
| Battle 41 (41) | 77.2–181.9 × 138.0–220.9 | 92.6–215.5 × 166.0–250.9 |
| Battle 42 (42) | 76.0–193.2 × 103.5–193.2 | 91.0–232.8 × 124.5–232.4 |
| Battle 43 (43) | 69.0–212.2 × 107.8–207.0 | 83.0–251.8 × 129.7–249.0 |
| Battle 44 (44) | 62.1–178.8 × 124.2–207.0 | 74.7–213.4 × 149.4–249.0 |
| Battle 46 (46) | 111.5–218.3 × 96.6–158.7 | 134.3–259.4 × 116.2–190.9 |

Donor battle programs, field pace and hop timing stay unchanged. Regenerate calm clips after resizing to solve floor contact again; fin shoulders are measured from the resized fin root edges, so the paddles still pivot at their attachment. Shadow centering is exclusively the shared `nyaromon-shadow` pass in `babies.encode`, using the centroid of distinct referenced points per rigid piece. Duplicate or unused vertex-pool entries and quad splitting do not change this measure. After the shared mesh pass, all eight babies remain within 0.69 units of the entity origin in every field tick (the QA limit stays 1 unit).

To reproduce: run `authoring/pichimon.py`, call `authoring.shrink.shrink(PATH, 2, 1.20)`, run `python3 -m tools.models.field_animations.pichimon_hop SRC.MMD OUT.MMD`, then `python3 -m tools.models.babies encode 471 OUT.MMD Pichimon.TIM`. Use `python3 -m tools.derive.steps.species pin OUT 471` for the provider pin. Both pin layers are generated by their tools.

Resident data is 47,598 versus 47,676 bytes (−78); cold data remains 8,188 bytes and the 18,432-byte texture is unchanged. Reuse the importer's exact triangle-pair packer (19 pairs, saving 380 bytes) and share duplicate normals (216 bytes). A rendered-triangle multiset comparison verifies positions, winding, UVs, CLUTs and normals are identical before/after each storage optimization. No runtime geometry processing or new resident table is added.
