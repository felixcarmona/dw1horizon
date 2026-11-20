# Tamer looks: bald, hairstyles, hair colours and faces

The tamer can take off his cap. Besides the original tamer there are twelve other looks: a bald head and eleven
hairstyles (classic, messy, quiff, curtains, buzz, long, mullet, ponytail, pigtails, bun, buns), each in twenty hair
colours. They are chosen on the **Look** page of the pause menu's Player tab: left and right change the hairstyle or the
hair colour, L1 and R1 turn the tamer. The original tamer and the bald head have no hair to colour: their colour row
shows a dash and cannot be chosen. A third row, **Face**, chooses between two faces for every look but the original
tamer, whose row shows a dash: the first is the tamer's own, the second has a blush instead of the freckle marks, a
finer mouth with lips, a darker eyelid and two lashes. The Player tab shows the button that opens the page beside the name, and the
page shows there the two that leave it: the confirm button saves the look, the cancel button leaves without saving and
the tamer is again as he was when the page opened. The look is kept in the save.

| Look | What it is |
|---|---|
| 0 | the original tamer, with his cap: the disc's own model and texture, loaded exactly as before |
| 1 | bald |
| 2–12 | the hairstyles, in the order above |

Hair colours 0–19: brown, dark brown, black, chestnut, blond, light blond, ginger, red, burgundy, pink, lavender, purple,
navy, blue, turquoise, green, lime, grey, silver, white. The names are shown, translated like the rest of the menu.
`tools/tamer_pack.py list` prints both lists.

## Where the looks come from

Nothing of the looks is committed as model data. The build makes them from the player's own tamer
(`CHDAT/MMD0/BOYS.MMD` and his `ALLTIM.TIM` texture):

- `tools/tamer_looks/bald.py` removes the cap and closes the skull, and repaints the texture where the cap was.
- `tools/tamer_looks/styles.py` sculpts each hairstyle over that skull; `wig.py` turns a sculpt into the head's
  polygons: skull polygons the hair covers are dropped, and the hair is made of shaded triangles textured with
  a small strand tile (`hairtex.py`: one lock per band, a sheen ring, darker ends) drawn in its own palette row, the
  one the cap used.
- `tools/tamer_looks/face.py` draws the second face on a copy of the bald head's texture, the frames the eye and
  mouth animations copy over the face included.
- `tools/tamer_pack.py` packs every look into `TAMER.DAT` (derive step `tamer`), a new file in the root of the disc.

`TAMER.DAT`, in 2048-byte sectors:

| Part | Content |
|---|---|
| sector 0 | `"TLK1"`, u16 looks in the file, u16 texture sector, u16 cold sector, u16 cold sectors, u16 colours, u16 faces; at 0x10 per look `u16 first sector, u16 sectors`; at 0x80 per colour `r, g, b`; at 0xC0 the brightness of each of the hair texture's sixteen tones (128 = the colour itself) |
| texture | the bald head's texture (one `ALLTIM` entry, 9 sectors), shared by every look: one per face, one after the other |
| cold | the animations that leave the models, the same bytes for every look |
| models | one model per look |

## Memory

The tamer's buffer (`TAMER_MMD_MAX`, 0xE000 bytes) does not grow and the heap is untouched. A look's model is larger
than the original, so it gives up sixteen animations (`COLD_SLOTS` in `tamer_pack.py`): the thirteen only scenes
start (slots 13 and 15–26: the engine itself never asks for them), the gym's (slot 9), which is read while the
gym's overlay loads (`modTamerColdPrefetch`), so nothing waits when it starts, and the two praising gestures (38, 39),
read when the praise starts. Their table entries become cold entries, as the partners' (`COLD_ANIM_FLAG`),
and every model has to fit in `TAMER_MMD_MAX - 0x1000` bytes. No mesh is simplified for that; when a look needs more
room (clothes, shoes), more animations become cold: fishing (27–34; 4.3 KB) is the next
candidate, at the price of a short read when each starts on a 2 MB console. The last 0x1000 bytes of the buffer
(`TAMER_COLD_MAX`) hold the cold animation in use:

- with 2 MB of RAM, the game reads it from the disc when it starts (one or two sectors: a short wait);
- with more RAM, the whole cold part is read once with the model, at 0x80210000, and nothing waits.

The original tamer (look 0) keeps every animation in memory, as always.

## In the engine

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
  swapped: the far faces are drawn and no gap shows what is behind the head.
- Save record `0x000F` holds the look, the colour and the face ([save format](../reference/save-format.md)); a new game and
  an older save start with the original tamer. Without `TAMER.DAT` on the disc every look is the original tamer.

## Adding a hairstyle

Write its function in `tools/tamer_looks/styles.py`, add it to `STYLES` and to `ORDER` in `__init__.py` (at the end:
the number is saved), raise `TAMER_LOOK_COUNT` in `include/dw/species.h`, and run `tools/tamer_pack.py build` to see
that it fits.
