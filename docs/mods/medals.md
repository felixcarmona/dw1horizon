# Medals

The original game has fifteen medals. Horizon keeps them as the **classic** medals, which ask only for what the original
game had, and adds four **Horizon** medals that ask for everything the mod adds on top. The rules are data:
`content/tables/medals.json` (keys in its `_comment`), encoded by `tools/balance.py` into `MOD_MEDALS`.

| Id | Medal | Earned by |
|---|---|---|
| 0-3 | Grade, Version, Type, Special Cups | winning every cup of the group |
| 4 | 100 Wins | 100 tournament wins |
| 5 | Technique Master | every technique learned |
| 6 | Classic Master | raising the 61 original Digimon |
| 7 | Classic Peak | HP and MP 9999, the other four stats 999, on one Digimon |
| 8 | Perfect Curling | a perfect curling score |
| 9 | 100 Fish | 100 fish caught |
| 10 | Game Clear | beating the last boss |
| 11 | Classic City | the 50 residents of the original game all recruited |
| 12 | Classic Collection | every card of the original game (card ids below 66) |
| 13 | Bits Maxed | 999999 bits |
| 14 | 10th Anniversary | year 10 |
| 15 | Horizon Master | raising every Digimon of the partner list (NEW DIGIMON on) |
| 16 | Limit Breaker | HP and MP 15000, the other four stats 1500, on one Digimon |
| 17 | Horizon City | every resident recruited (EXTENDED STORY on) |
| 18 | Full Collection | every card (NEW CARDS on) |

- A classic medal does not change with the options: Classic Collection counts only the original cards even with NEW CARDS on.
- Horizon Master, Horizon City and Full Collection wait for their option. While it is off the medal is not shown in the
  Medals view, is not counted on the Player page and cannot be earned. A medal already earned is kept.
- Classic City is checked every tick from the recruit flags. Jijimon's scene at 100 prosperity still raises the tamer
  level and brings Tsunomon, and no longer gives the medal.

## The Medals view

Five medals a row, three rows on screen, scrolling by rows; the classic medals first. The panel under the grid shows the
selected medal's name, two lines of description and its state: earned, a count such as `37 / 61`, or not earned yet.

Each medal is a drawn picture: `content/medals/NN.txt` holds its fifteen colours, a 24x24 grid (`small`, the list) and a
48x48 grid (`large`, the selected medal). A medal not earned yet is the same picture in dark metal; that palette is
computed by `tools/species.py medal_block`, which packs the art into `DIGI.DAT`. The view loads the small pictures over
the old coin stamps in video memory when it opens and the large one when the cursor moves, so the art costs no memory.
The spinning coin of the original view is gone, and with it its 2 KB mesh buffer. The cursor stays on the medal last
looked at; when an option was switched off and that medal is no longer listed, it returns to the first.

## Telling the original from what Horizon adds

The Digimon chart, the City page and the card album draw a small gold corner, top right, on the box of every entry
the original game did not have: a species past the original 61, a resident past the original 50, a card id from 66
up. The classic medals count the boxes without the corner.
