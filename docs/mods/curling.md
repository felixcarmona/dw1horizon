# Curling: matches and cups

The rink of Freezeland has its own menu, opened by Penguinmon once he lives in the city. It lives in the curling
overlay (`src/kar/kar.c`, patch `Curling-doubles-three-and-four-teams-cups-and-the-ri.patch`); the story side is
`story/base/zones/libraries/s206/script.py`, and the rivals and their skill are `content/tables/curling.json`.

## Modes

- **Singles**: a quick match, and the five cups.
- **Doubles** and **free-for-all** (three or four teams): quick matches only.

A quick match costs any fish and draws its rivals from the recruits of the city. The original match against
Penguinmon is unchanged.

## Cups

Rookie, Amateur, Expert, Elite and Legend, each closed until the one before it is won. A cup is the player and seven
rows of the rivals table (windows starting at rows 1, 4, 7, 10 and 14, weakest first), and all seven must live in the
city: the list shows the seven faces of the cup under the cursor, the missing ones dark.

- A cup asks for its own fish at every entry (Digianchovy, Digisnapper, DigiTrout, Digicatfish, Digiseabass).
- Three rounds on a drawn bracket. The places come from the cup's seed; the ties the player is not in are drawn from
  the same seed, each player weighted by `(place in the window + 2)^2`, so the better thrower goes through more
  often but not always.
- A level cup match is played again, with no new fish. A quick match still goes to the nearest stone.
- Prizes: each cup draws one item of its own set. The first Legend Cup gives the Curling Legend medal (flag 379,
  medal 15 of the [medals](medals.md)) and one chip of each kind; the chips that do not fit in the bag stay with Penguinmon
  (`curling_chips_kept`), who hands them over at the next talk. No prize is Bits.

Saved state: the cups won (variable 7) and the chips kept (variable 8). A cup is played in one go, round after round,
so its cup, round and seed (132 to 134) are not saved.

## Collisions

Two free stones that touch (centres closer than 150) exchange the part of their speed that runs along the line between
their centres and keep the rest (`KAR_exchangeAlongCentres`, patch
`Curling-collisions-stones-exchange-their-speed-along.patch`): a square hit stops the thrown stone and sends the other
on with all its speed, as before; a hit on the side sends the other stone away from the contact and the thrown one
carries on, turned; a grazing touch barely moves either. Stones moving apart are left alone, and both stones wait at
the contact positions for the rest of that tick.

The original shared the speed by the angle alone and moved both stones by guessed amounts. A stone hit on its side
left along the thrower's line while the thrown stone stopped dead, and a grazing touch could leave the pair inside
each other: the collision pass repeats its last step while anything touches, so that pair hung the game. The repeat
is now capped at eight. A stone standing on a peg collides as in the original.

## Cup names

Each cup's name is drawn as art in every language, over the cup list and over the bracket: fat hand-drawn letters
in the cup's colour and nothing else, the screen showing through around them. The art is the repository's own: one
sheet of five names per language in `content/localized/curling/<lang>.png` (256 x 200, a name in each 40-line band,
at most 128 colours a band, magenta where nothing is drawn), drawn by the image generator from `prompt-en.txt` and,
for the other languages, from the English sheet (`jobs.py`); `tools/curling_banners.py --make` cuts the names out of
the generator's sheets and fits them to that size.

The derive step `curling` packs them into `KARCUP.DAT`, a new file in `ETCDAT`: for each language, in the
game's order, 26 sectors with five rows of 128 colours and the five 256 x 40 pictures (magenta packed as the transparent colour). The menu reads its language's
section through the world's scratch area into the video memory the rink leaves free (576, 256). A disc without the
file shows the menu with the cup's name as text.
