# Script bytecode and scnasm

This is a low-level reference for the bytecode emitted by the story compiler.
For writing quests, dialogue and events, use the [Python story language](story-language.md).
[DWS](dws.md) is its intermediate language and escape hatch. Generated
`.scn.txt` assembly is an inspection format, not the story source.

`tools/dws/backend.py` prepares sections and placements; `tools/dws/bytecode/__init__.py`
assembles the resulting scripts. The [derive builder](../derive.md) builds the
story variants and records their outputs for the native and player builds.

## Containers and sections

`SCN/DG.SCN` contains the screen scripts. Its first 2048-byte sector holds
little-endian u32 byte offsets: one per entry, followed by the end offset.
The original USA container has 222 entries (0–221). Entries occupy whole
2048-byte sectors; the table has room for 511 entries. New scripts are appended.
Entry 0 is a redundant MAPHEAD copy: the interpreter uses its resident MAPHEAD
buffer for script id 0.

`SCN/MAPHEAD.SCN` is a single script loaded at boot. Its screen setup sections
select scripts and populate maps. The mod also stores setup for new screens in
`SCRN.DAT`; see [maps](maps.md) and [screen formats](../reference/file-formats.md).

Each script starts with a section table. Section ids and offsets are u16;
jumps refer to offsets inside that script. Disassembly replaces offsets with
labels and retains section order, padding and unused slot tails so an unedited
file can be assembled exactly. These tails are not story source.

## If DG.SCN grows

`scnasm.build_container` first tries the existing slots. If needed it shrinks
entry 0, then drops unused tails and compacts the slots. If the result still
exceeds the original container size, `--grow` permits a larger file; otherwise
assembly fails. `--compact` requests compaction directly.

The compiler enables growth for targets whose discs can be relaid out;
`tools/build-full.sh` sets `DWS_RELAYOUT=1` and builds with `--relayout`.
DG.SCN is found by ISO name, but moving later files requires rewriting the
executable's absolute file table. The disc builder handles this automatically;
see [disc layout](../reference/disc.md).

Each nonzero script entry is limited to **0x4000 bytes** by the assembler,
including on a target with a larger runtime buffer. MAPHEAD is limited to
**25,000 bytes** on the original executable and **0x8000 bytes** on the mod
targets; the compiler checks the selected target's limit. Container growth does
not enlarge these RAM buffers. Builds must fit the original PlayStation's 2 MB.

## Opcode reference

`tools/dws/bytecode/__init__.py` defines instruction names, typed operands and byte lengths.
The interpreter and engine calls are described in [the interpreter reference](../reference/scripts.md).
Use `python3 tools/dws.py show FILE.py` to inspect what a story source emits.

The text form has `.section ID LABEL`, labels, one instruction per line and
quoted text rows. Offsets are recalculated during assembly. `IF` clauses are
folded left to right; DWS performs condition lowering for the writer. Section
and jump-table layout can also be read directly by engine code, so equivalent
control flow alone is insufficient when changing a table.

### Wide opcodes

The mod executable adds 16-bit id operations and wide registers, including
opcodes 0x80–0x93. They require a compatible executable. The compiler selects
these operations from the target and operand types; see [compiler targets](dws.md)
and [id carriers](../reference/ids.md). Unsupported opcodes end execution on the
original interpreter.

## Text control codes

Script text uses two-byte glyph units and control codes. The mod can also store
packable ASCII characters as one byte (`--pack-ascii` / `SCNASM_PACK_ASCII=1`);
the interpreter expands them as needed. Assembly keeps the next instruction
aligned. Font coverage, widths and wrapping depend on the selected target:
see [fonts](font.md) and [translation](translating.md).

These escapes are also accepted in story text. An id in a name escape is a
**pstat containing the id**, not a literal item or species id.

| Escape | Bytes | What it draws |
|---|---|---|
| `{color N}` | `01 N` | color N of `FONT_CLUT` (1 white, 2 blue, 3 red, 4 pink, 5 green, 6 light blue, 7 yellow, 10 orange); names usually go `{color 6}...{color 1}` |
| `{player}` / `{partner}` | `05 00` / `06 00` | name of the player / of the partner |
| `{pstat N}` | `04 N` | value of pstat N (3 digits) |
| `{digimon N}` `{move N}` `{item N}` | `07/08/09 N` | name of the Digimon / move / item whose id is **in pstat N** |
| `{bgm N}` `{cup N}` | `11/12 N` | name of the music track / tournament in pstat N |
| `{money}` `{merit}` `{shopvar}` | `0A 00`, `0B 00`, `10 00` | bits, merit, `SHOP_VARIABLE` |
| `{cupswon}` `{wins}` `{losses}` | `13/14/15 00` | tournament counters |
| `{tab N}` `{tab11 N}` `{half N}` | `0C/0E/0F N` | tabs and half space |
| `{pos16 N}`…`{pos1c N}` | `16`–`1C N` | fixed menu columns (USA only) |
| `{sjis XXXX}` | `XX XX` | Shift-JIS character with no glyph in the font |
| `{raw xx yy ...}` | raw | any other unit (e.g. `03 a b c`, or `00 00`) |

## Free triggers and pstats

`python3 tools/dws/bytecode/__init__.py libres extracted/SCN/DG.SCN extracted/SCN/MAPHEAD.SCN`
reports original-script usage alongside known engine uses. This is a diagnostic,
not a reservation system: it cannot account for another mod's state. Use named
flags, quests and counters with `mod.toml` reservations and committed `save.lock`
files; see [story state](story-language.md) and [save compatibility](../reference/save-format.md).

## Round-trip check

With an extracted USA disc:

```sh
python3 tools/dws/bytecode/__init__.py check extracted/SCN/DG.SCN extracted/SCN/MAPHEAD.SCN
```

This disassembles, reassembles and compares the bytes, including unused tails.
It verifies format preservation, not the behaviour of an edited story. Story
checks belong to the compiler and [development tests](../developing.md).

## Testing compiled scripts

Scripts and file offsets are cached in RAM. A save state can retain an old script
or a different disc layout. Boot the rebuilt disc and continue from a memory-card
save for testing; entering a screen that uses another script reloads the active script.
Load NPC models during screen setup: loading multiple new models inside a talk
can hang the interpreter. Use the story compiler's NPC placement and heap checks.
