# Tamer looks: bald, hairstyles, hair colours, faces and clothes

The tamer can take off his cap. Besides the original tamer there are twelve other looks: a bald head and eleven
hairstyles (classic, messy, quiff, curtains, buzz, long, mullet, ponytail, pigtails, bun, buns), each in twenty hair
colours. They are chosen on the **Look** page of the pause menu's Player tab: left and right change the hairstyle or the
hair colour, L1 and R1 turn the tamer. The original tamer and the bald head have no hair to colour: their colour row
shows a dash and cannot be chosen. The page's first row, **Tamer**, is a boy or a girl, and the rest follows it: the
face, the hands (the girl's are smaller), and which clothes the other rows offer. The boy's face is the
tamer's own; the girl's has a blush instead of the freckle marks, a finer mouth with lips, a darker eyelid and two
lashes (under the original tamer's cap the eye keeps its eyelid: the cap's shadow already frames it). Two more rows,
**Shirt** and **Shirt colour**, dress every look, the original tamer included: the original hoodie with its backpack,
or another shirt in sixteen colours. The boy's are the T-shirt, striped, printed, long sleeve, hoodie and jacket; the
girl's have a bust: the fitted tee, top, cardigan and blouse, and the striped, printed, long sleeve, hoodie and jacket
cut for her. The original hoodie is the boy's. The original hoodie, trousers, shoes and backpack take the colours too: the first choice of their
colour row is **Original**, their own colours, and the other fifteen dye their cloth and leave the rest (cords, soles,
the backpack's emblem) as it was. His cap does the same: on the original tamer the row under the hairstyle is **Cap colour**
instead of the hair's, and the letters of its band stay. The second row, **Skin**, under the tamer's, is his own skin or one of five
other tones, from pale to dark, on the face, the hands and whatever skin the clothes leave bare. Four more rows do the same for the legs and the feet:
**Trousers** (the original ones, straight, baggy, skinny, tracksuit, shorts, capri, skirt, flared) and **Shoes** (the
original ones, trainers, plain, flats, Mary Janes, ankle boots, boots, cuffed boots,
rain boots, sandals), each with its own colour row and the same sixteen colours. The girl's shoes are a smaller foot: flats, Mary Janes, and
the trainers, plain shoes, ankle boots, boots, cuffed boots, rain boots and sandals in her size; the original shoes are
the boy's. The skirt, the capri and the flared trousers are the girl's, the baggy ones the boy's. Changing between boy
and girl changes a garment the other wears for the next one of its kind that this one does. A
boot's leg goes over a slim or bare shin (skinny, shorts, capri, skirt); wide trousers fall over it and only the foot
shows. The last two rows are **Backpack** and **Backpack colour**: the original backpack, none, or one of five others
(classic, which is the original one in any colour, school bag, mini, hiking, round) in the same sixteen colours. Each
of the five is the original backpack in other proportions, with its cloth, seams and shading, and its own fittings
drawn where the original has its emblem. Every
shirt takes every backpack: the original hoodie with the original backpack is the tamer as he always was, and with
another one or none it is the same hoodie without it. Under a backpack a shirt shows its straps. The page shows six of its twelve rows at a time, around the chosen one, with a scroll
bar beside the boxes. The Player tab shows the button that opens the page in a box beside the name, and the
page shows there the two that leave it: the confirm button saves the look, the cancel button leaves without saving and
the tamer is again as he was when the page opened. The look is kept in the save.

| Look | What it is |
|---|---|
| 0 | the original tamer, with his cap: the disc's own model, and the disc's own texture with the first face |
| 1 | bald |
| 2–12 | the hairstyles, in the order above |

Hair colours 0–19: brown, dark brown, black, chestnut, blond, light blond, ginger, red, burgundy, pink, lavender, purple,
navy, blue, turquoise, green, lime, grey, silver, white. The names are shown, translated like the rest of the menu.
Cloth colours 0–15 (shirts, trousers, shoes and backpacks): white, grey, black, red, burgundy, orange, yellow, lime, green, turquoise, blue, navy, purple,
lavender, pink, brown. `tools/tamer_pack.py list` prints every list.

## Where the looks come from

Nothing of the looks is committed as model data. The build makes them from the player's own tamer
(`CHDAT/MMD0/BOYS.MMD` and his `ALLTIM.TIM` texture):

- `tools/tamer_looks/bald.py` removes the cap and closes the skull, and repaints the texture where the cap was.
- `tools/tamer_looks/styles.py` sculpts each hairstyle over that skull; `wig.py` turns a sculpt into the head's
  polygons: skull polygons the hair covers are dropped, and the hair is made of shaded triangles textured with
  a small strand tile (`hairtex.py`: one lock per band, a sheen ring, darker ends) drawn in its own palette row, the
  one the cap used.
- `tools/tamer_looks/face.py` draws the second face on a copy of the bald head's texture and of the original tamer's, the frames the eye and
  mouth animations copy over the face included.
- `tools/tamer_looks/shirts.py` models each shirt over the tamer's own torso and arms (trunk, upper arms and forearms:
  objects 0, 2, 3, 5 and 6 of the model), and draws its cloth where the hoodie's was in the texture.
- `tools/tamer_pack.py` packs every look into `TAMER.DAT` (derive step `tamer`), a new file in the root of the disc.

`TAMER.DAT`, in 2048-byte sectors:

| Part | Content |
|---|---|
| sector 0 | `"TLK1"`, u16 looks in the file, u16 texture sector, u16 cold sector, u16 cold sectors, u16 colours, u16 faces; at 0x10 per look `u16 first sector, u16 length in 4-byte words`; at 0x80 per colour `r, g, b`; at 0xC0 the brightness of each of the hair texture's sixteen tones (128 = the colour itself); at 0xD0 u16 shirts, u16 cloth colours; at 0xD4 `u16 sector, u16 words` of the original tamer's model without his clothes; at 0xD8 the sector of his texture with the first face; at 0xDA u16 trousers, u16 shoes, u16 backpacks; at 0x400 per shirt `u16 first sector, u16 geometry sectors`, at 0x140 the same per pair of trousers, at 0x480 per pair of shoes and at 0x240 per backpack (its only sector, and 0); at 0x260 who wears what, per kind of garment `u32 the boy's choices, u32 the girl's`, a bit each; at 0x300 per cloth colour twelve bytes: `r, g, b` of its shade, of the cloth, of its light and of its second colour |
| texture | the bald head's texture (one `ALLTIM` entry, 9 sectors), shared by every look: one per face, one after the other; then the original tamer's texture with each face but the first, and with the first |
| cold | the animations that leave the models, the same bytes for every look |
| models | one model per look, without the eleven objects clothes replace; then the original tamer's, the same way |
| clothes | per shirt, per pair of trousers and per pair of shoes one head sector, then its geometry; after the shirts that are chosen, the original hoodie without its backpack twice (with straps for another backpack, and bare); per backpack one sector |

## Memory

The tamer's buffer (`TAMER_MMD_MAX`, 0xE000 bytes) does not grow and the heap is untouched. A look's model is larger
than the original, so it gives up twenty-four animations (`COLD_SLOTS` in `tamer_pack.py`): the thirteen only scenes
start (slots 13 and 15–26: the engine itself never asks for them), the gym's (slot 9), which is read while the
gym's overlay loads (`modTamerColdPrefetch`), so nothing waits when it starts, the two praising gestures (38, 39),
read when the praise starts, and the eight of fishing (27–34), each read when it starts. Their table entries become cold entries, as the partners' (`COLD_ANIM_FLAG`),
and every model with the largest shirt, trousers and shoes has to fit in `TAMER_MMD_MAX - 0x1000` bytes. No mesh is simplified for that;
when a look needs more room, more animations become cold. The last 0x1000 bytes of the buffer
(`TAMER_COLD_MAX`) hold the cold animation in use:

- with 2 MB of RAM, the game reads it from the disc when it starts (one or two sectors: a short wait);
- with more RAM, the whole cold part is read once with the model, at 0x80210000, and nothing waits.

The original tamer (look 0) in his original clothes keeps every animation in memory, as always; with another shirt he is
a model of `TAMER.DAT` like the rest.

## In the engine

- For the original tamer with another face, the same loader reads his texture with that face from `TAMER.DAT` and
  then the disc's model.
- `modLoadTamerLook` (`mod_species.c`) loads the texture of the chosen face and the model of the chosen look in `loadMMD`'s place for
  the tamer, and `loadColdAnimation` serves the tamer's cold entries.
- The hair colour is a palette row. `lookHairPalette` writes it into the look's texture before it is uploaded: each
  channel of tone `i` is `colour * level[i] / 128`, so one model and one texture serve every colour. Hair polygons
  come first in the head, which keeps the fringe in front of the forehead.
- `modTamerRelook` (`model.c`) loads the look again and links the tamer's bones to the new model, for a change while
  he is on screen.
- The Look page (`lookPage*` in `game_menu.c`), the loader (`lookTamerLoad`) and the relink (`lookTamerRelook`) are
  not in the main executable: they are linked at the tail of the EVL overlay (`look_ui` in `overlay.ld`), in memory the
  field leaves free. `modLookOverlay` reads that overlay when its marker word (`lookPageMagic`) is not there, so the page
  and the looks cost no heap. A colour change sends the sixteen words of the palette row to video memory; a hairstyle or face change reads the disc.
- Once a model has been drawn, the first header of each run of equal polygons holds the run's length, so the hair is
  found by position (the head's leading triangles in the hair's palette row, seven words each), never by walking header lengths.
- The game draws one face of a polygon. The menu's close-up shows the hair from angles the field never does (under the
  fringe, between a lock and the cheek), so there `lookPageHairInside` sorts the hair a second time with two corners
  swapped: the far faces are drawn and no gap shows what is behind the head. With no depth buffer those faces, sorted
  among the model's own, painted the inside of a lock over the head or the other lock at back and side angles; they
  go to the far half of the portrait's ordering table (buckets 256-511), behind every face of the model and still in
  front of the panel.
- A shirt is five objects of the model. Every model in `TAMER.DAT` comes without them; `lookTamerLoad` reads the
  chosen shirt's geometry right behind the model and points the five entries of the object table at it before the
  model is linked. The shirt's head sector (geometry size, the five entries, a palette recipe, the rectangles of the
  texture it draws on and their pixels) is read first: the pixels go over the texture in memory, and
  `lookShirtPalette` makes the cloth's palette row from the recipe and the chosen colour (per tone: kept, a fixed colour, the second
  colour, or a place on the cloth's ramp from its shade through the colour to its light, or from black to the shade;
  the shade and the light are colours of their own, a little off the cloth's hue, as on the tamer's own clothes). Shirt 0 is the tamer's own five objects with a
  recipe that keeps every tone. A shirt colour change sends that palette row; a shirt change reads the disc.
- Trousers (the two thighs and shins, `tools/tamer_looks/legs.py`) and shoes (the two feet, `shoes.py`) are garments
  of the same kind, read one after the other behind the shirt, each with its own palette row (the legs' and the
  feet's) and its own rectangles of the texture. Trousers are tubes of cloth, or of skin under shorts and skirts;
  shoes are the tamer's own feet, scaled for the small kinds, with another drawing.
- The cloth is painted like the tamer's own: shirts and trousers take their folds from the player's disc (the
  original sleeves' and trousers' pixels, as tones of the new palette row) under a shading of the body's form, and
  bare skin is drawn in three tones of his face, chosen per polygon by where it looks while he stands.
- The seat is part of the torso, so of the shirt, and its palette row is shared with the original hoodie: under other
  trousers `lookTamerLoad` rewrites the torso's last sixteen polygons (every shirt ends with the seat) to the
  legs' palette row and to one texel of plain cloth, which the trousers' head sector names. Last, because with no
  depth buffer the polygons that share a bucket of the ordering table are drawn last to first: the seat lies inside
  the shirt, a few units behind its hem, and first in the torso it was drawn over the hem as flat patches of the
  trousers' colour.
- A boot's leg cannot be part of the foot, which turns at the ankle. It is eleven corners and ten polygons stored in
  the shoes' head sector, and it rides on the shin: slim trousers (a flag in their head sector) keep eleven unused
  corners at the start of each shin and room for ten polygons right before the shin's own, and the loader copies the
  leg there. Other trousers keep no room and the boot shows only its foot.
- A backpack (`backpacks.py`) is a garment with no objects of its own: one sector with its drawing (the backpack's own
  square of the texture), the recipe of its palette row, and at 0x400 up to sixteen corners, sixteen normals and 400
  bytes of polygons. Every shirt but the original keeps that room in its torso (sixteen unused corners and normals at
  the start, the bytes right before its polygons: a flag in its head sector), and the loader copies the backpack
  there. Those shirts also carry one more drawing after their own, the trunk with a backpack's straps, which is
  drawn unless the backpack is none. The original hoodie has its backpack in its mesh and in its drawing, so with
  another backpack or none the loader reads one of two shirts that are not chosen from: the same hoodie with the
  backpack taken out and its back closed, with the straps or without them. The original backpack on another shirt is
  the tamer's own, a little narrower so that it sits on every back. The other styles are that same mesh with its
  corners moved (`STYLES`: how tall, wide and deep) and the original drawing with the emblem painted over.
- Small hands are not a garment: after the model is in memory the loader moves the corners of the two hand objects
  to three quarters of their distance from the wrist. The original tamer with small hands is read as the original
  tamer with another face is.
- Save record `0x000F` holds `MOD_TAMER_STATE`: the look, the hair colour, the face, each garment and its colour, then the hands ([save format](../reference/save-format.md)); a new game and
  an older save start with the original tamer. Without `TAMER.DAT` on the disc every look is the original tamer.
- A new game asks for the look among Jijimon's questions (`lookPageQuiz`, the states from 0x30 of
  `newGameStateMachine`; lines 0x3a to 0x3c of the quiz's text, `story/new-game-quiz.dws`). After his seven questions
  he asks boy or girl, as a list like theirs: a boy is the original tamer, a girl starts from a look made for her
  (`lookPageGirl`). After the name he asks what the tamer looks like and the Look page opens on the black screen, with
  no window: the tamer on the left, every row on the right (the Tamer row too: on this page it starts the other tamer
  as that answer would have), the turn and Save hints, and a line saying the look can be changed later in the menu. The tamer is loaded for the page and unloaded after it (the game
  loads him after the opening's movie, as chosen); his object is removed meanwhile, so he neither ticks nor draws
  himself. The page is one state of the questions, a frame of it per frame of the scene: it has no loop of its own.
  It reads both of the title's overlays first, in the language chosen since the title read them.
- The page's code is in the tail of EVL, and EVL's first sector lies over MENU's last one. An open menu that reads EVL
  (`lookMenuOverlay`) reads MENU again after it; the new game reads them in that order.

## Adding a shirt

Add its row to `STYLES` in `tools/tamer_looks/shirts.py` (at the end: the number is saved), raise `TAMER_SHIRT_COUNT`
in `include/dw/species.h`, give it a name (`lookPageClothes` in `game_menu.c`, `LAB_STR_SHIRT_*`), and run
`tools/tamer_pack.py build` to see that every look still fits with it. The shirt may draw only in its rectangles of the
texture (`RECTS`): the trousers and the shoes use the rest. Its torso must end with the seat's polygons.

Trousers, shoes and backpacks are added the same way: a row in `STYLES` of `legs.py`, `shoes.py` or `backpacks.py`,
`TAMER_TROUSERS_COUNT`, `TAMER_SHOES_COUNT` or `TAMER_PACK_COUNT`, a name in `lookPageClothes` (`LAB_STR_TROUSERS_*`,
`LAB_STR_SHOES_*`, `LAB_STR_BACKPACK_*`). A backpack must fit in the room shirts keep (`PACK_CORNERS`, `PACK_BYTES`).

## Adding a hairstyle

Write its function in `tools/tamer_looks/styles.py`, add it to `STYLES` and to `ORDER` in `__init__.py` (at the end:
the number is saved), raise `TAMER_LOOK_COUNT` in `include/dw/species.h`, and run `tools/tamer_pack.py build` to see
that it fits.
