# Text sources

How the game's text is keyed, how a text source fills those keys from a disc identified by checksum, and how a build
picks and fits one. The translator's workflow, the key forms and the style rules are in
[../mods/translating.md](../mods/translating.md); the run-time language switch is in
[../mods/language.md](../mods/language.md); the glyphs in [../mods/font.md](../mods/font.md). This page adds the
mechanics underneath.

## Keys and sources

Every piece of text has a key: the story's dialogue by utterance (`s002.sec6.u0`) and menu option
(`s002.sec6.m0.o1`), MAPHEAD's shared dialogue by section (`m1230.u3`), the executable's and overlays' strings by the
decompilation's text keys (`main.MOVE_NAMES.12`, `main.STR_YES`). A **text source** is a folder `text/<source>/` that
fills those keys:

| Source | Origin | Committed |
|---|---|---|
| `us` | the US disc | no, extracted from your own disc |
| `jp`, `jp-rev1` | the two Japanese releases | no, extracted |
| `es-fan` | a Spanish fan translation disc, if you have one | no, extracted |
| `ours` | our own English, translated from the Japanese | yes, `text/ours/` |
| any other name (`es`, `ca`...) | a language of ours, the layout of `text/ours/` | yes |

Nothing of any disc is committed. What is committed: the tools, the disc registry (`tools/discs.py`: checksums only),
the script numbering map between the US and Japanese discs (`docs/data/script-map-us-jp.csv`, numbers only) and the
glyph table of the Spanish disc's redrawn font (`docs/data/es-fan-glyphs.csv`, a description of its codes).

## Identifying a disc

`python3 tools/discs.py identify DISC.cue` names the release. An image (`.bin`/`.cue`, `.iso` at 2352 or 2048 bytes per
sector, or an extracted folder) is first matched by size and whole-image SHA-1. If that fails, the SHA-1s of a set of
key files (the executable, the script files) are compared with every registered disc: all of them matching accepts
another rip of a known disc; a partial match is refused and the closest disc is named.

## Extracting

```bash
python3 tools/dws.py extract-text DISC.cue                 # -> text/<source>/
python3 tools/dws.py extract-text ES.iso --base JP.cue     # es-fan needs the Japanese disc it was made from
```

Output in `text/<source>/`:

| File | Content |
|---|---|
| `dialogue.json` | utterances and menu options of `DG.SCN` and `MAPHEAD.SCN` by US key: a string, a list of rows (one page) or a list of pages. Text the US story has no place for is kept as `x.<source>.<own key>` and never loaded into a build |
| `names.json` | the executable's and overlays' strings by key |
| `report.csv` | one row per key: `aligned`, `us-only` (no counterpart in the source), `src-only`, `missing`/`absent` (executable text that disc does not have), and both sides' page counts |

### Aligning the dialogue

The Japanese discs number their 225 scripts differently; the US numbering (the one of `story/base`) is the reference,
and `script-map-us-jp.csv` maps one to the other. Within a script, sections match by id. Within a section, utterances
match by aligning the section's instruction stream with its text removed (operands that name labels or scripts are
masked; one utterance or one menu is one element) against the US section. With this, the Japanese releases cover all but
two of the 3 927 US utterances and all but two of the 799 menu options; a few dozen utterances have a different page
count. Rev 1 of the Japanese disc carries the same fixes as the US disc (swapped lines, two prize names), so it is the
preferred Japanese reading. Script 0 is a dead copy of MAPHEAD the game never reads.

### Decoding

- `jp`, `jp-rev1`: Shift-JIS, kept as is (full width).
- `es-fan`: its disc redraws the Japanese font, so codes first go through `es-fan-glyphs.csv` (`tools/dws/text/esglyphs.py`:
  accents, punctuation, pad buttons and a few hundred two- and three-letter name tiles), the rest through Shift-JIS folded
  to ASCII. That disc keeps the string tables in place but repoints the strings, so tables are read through their
  pointers and named strings through the code and data that reference them in the Japanese executable, hence `--base`.
- Control codes become the compiler's escapes (`{player}`, `{color 6}`, `{item 3}`).

`python3 tools/dws.py text-extract` also writes `text/us/dialogue.json` from an extracted `SCN/` folder; `extract-text` on
the US disc writes the same keys and values from the image.

## The executable's strings

Keys come from the decompilation's text layer, `decomp/text/<dir>/<file>.yaml` (about 1 170 keys):

| Form | Example | Meaning |
|---|---|---|
| `<dir>.<SYMBOL>` | `btl.BTL_STR_DROPPED`, `main.STR_YES` | a named string |
| `<dir>.<BLOCK>.<i>` | `main.MOVE_NAMES.12`, `main.ITEM_NAMES.38`, `main.ITEM_DESCS.38`, `main.DIGIMON_NAMES.1` | row i of a table |
| `<dir>.<BLOCK>` | | a single entry |

Only the keys and addresses come from the decompilation (`decomp/config/<version>/symbols*.txt`); the text itself is read
from your disc (`tools/localize/executable/extract.py`). A string the decompilation merged into an identical one, or left without a
symbol, is found by its bytes. Every release covers well over 1 100 of the keys; the rest are `absent` (strings of other
releases, such as the trial disc or the European curling texts).

The mod's own strings are keys too (patch 0090): the lab menu (`main.LAB_STR_*`), the item keeper's labels
(`shop.STR_IN_HAND`, `shop.STR_KEEPING`) and the arena calendar's title (`dget.DGET_STR_TOURNAMENT`).

### Into the executable

`tools/localize/executable/bank.py exe-bank <source>` writes `text-bank.json` for the build. `decomp/tools/gen_text.py`, as patched
by 0090, reads it, replaces each entry's text by key and encodes the extra glyphs as their `F0xx` codes. The bank keeps
the US text, and lists it in `build/<name>/text-exe-kept.txt`, where:

- the entry is a species name: names always come from `content/species` ([../mods/species.md](../mods/species.md));
- an item name is longer than its 19-byte record;
- a message's format codes (`#C1`, `%d`...) differ from the US executable's (`tools/localize/executable/us-format-codes.json`): the
  Japanese battle messages use other codes.

For a multilingual disc the executable is built once per selected language with a
shared layout and strings padded to accommodate the selected translations; see
[../mods/language.md](../mods/language.md).

## Building with a source

`TEXT=<source> tools/build-full.sh NAME` (default `us`); the story build takes `--text-source`. Banks load in order,
later wins (`tools/dws/textbank.py`, `load_defaults`):

| `TEXT` | Loaded |
|---|---|
| `us` | the US bank only (byte for byte the build without `TEXT`) |
| `ours` | `text/ours/` |
| a disc source (`jp`, `jp-rev1`, `es-fan`) | `text/ours/` as fallback, then the source |
| a language of ours (`es`...) | `text/ours/`, then `text/<lang>/` |

then, for all of them, the mods' own banks. A key the source lacks stays in the fallback's English and is listed in
`build/<name>/text-fallback.txt` (`story-build --strict` fails instead). A value that still contains Japanese script
(lines a translation left untranslated) is not used and is listed. `TEXT_ZONES=zone[,zone...]` loads only those zones of a
source split by zone (`ours`), the rest staying US: a quick test build. `names.json` is always loaded whole.

### Fitting to the font

A source's text is fitted to the target executable's font (`TextBank.fit`):

- glyphs the target has are kept (the extra punctuation and accents, [../mods/font.md](../mods/font.md));
- characters without a glyph are replaced (`…` becomes `...` for an older executable, `〜` becomes `~`) or dropped, and
  the build lists them;
- a page whose rows are too wide becomes a plain string that the compiler wraps.

### The MAPHEAD limit

`MAPHEAD.SCN` is loaded into a fixed resident buffer: 32 768 bytes in the mod executables (patch 0091, see
[memory.md](memory.md)), 25 000 in the original. The US MAPHEAD is about 24 700 bytes. When a disc source's MAPHEAD text
does not fit, the keys that grew most stay in the fallback English until it fits, and are listed; under `TEXT=ours` an
overflow is an error. `DG.SCN` has no total limit (the build moves the files after it), but each script must stay within
16 384 bytes. Lines the game shows one box at a time (MAPHEAD's table entries) must not take more pages than the US text:
that is a build error naming the key ([../mods/translating.md](../mods/translating.md)).

`TEXT=jp` is an extraction source only: the US executable has no kana or kanji glyphs.

## Review

```bash
python3 tools/dws.py text review                   # every key -> build/text-review/index.html and review.csv
python3 tools/dws.py text review file-city names   # one zone of story/base/zones, and the executable's strings
```

One row per key: zone, screen, speaker, status (aligned, pages differ, us-only, missing in ours, mod text), then the
Japanese (Rev 1 when present), US, Spanish and ours. It is generated from your local banks and holds disc text, so it
stays under `build/`.

## Files

| File | Role |
|---|---|
| `tools/discs.py` | disc registry and `identify` |
| `tools/dws/text/extract.py` | `extract-text`: reading the image, alignment, dialogue, report |
| `tools/localize/executable/extract.py` | the executable's strings by the decompilation's keys |
| `tools/dws/text/esglyphs.py` | the Spanish disc's glyph table |
| `tools/localize/executable/bank.py` | `text-bank.json` for the executable |
| `tools/dws/text/review.py` | `text review` |
| `tools/dws/textbank.py` | the story build's banks, source order and fitting |
| `mods/patches/0090-*.patch` | `gen_text.py` with a bank and the `F0xx` glyphs; the mod's strings keyed |
