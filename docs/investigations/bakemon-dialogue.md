# Bakemon dialogue in the USA game

Bakemon's partner translation is present in the original USA game's **File
City** conversation. The cemetery recruitment conversation behaves differently.
These two conversations must be tested separately before diagnosing a regression.

The reference is the unmodified SLUS-01032 USA image with SHA-1
`5611645da66183e30d11fb6c11a2784ff47e1fdb`. A memory-card fixture with partner
species 37, retaining valid checksums in both payload copies, reproduces these
results in PCSX-Redux with 2 MB RAM:

| Conversation | Script / section | Result with a Bakemon partner |
|---|---|---|
| Overdell Cemetery recruitment | 35 / 5 | Ghost speech, followed by the tamer's uncertainty and yes/no choices |
| File City resident | 163 / 5 | Ghost speech, the tamer's uncertainty, then a partner reaction and an explanation that the resident is patrolling |

## Where the selection happens

The original File City section stores the partner species in p103 and tests
whether it equals 37. On a match, it turns the tamer toward the partner, plays
partner animation 11, waits, and shows `s163.sec5.u2`. The other partner species
skip this last exchange.

The cemetery's MAPHEAD section 35 selects script 35 and spawns NPC species 157
in slot 0, with talk section 5. Its recruitment flag is 237. Neither this setup
nor the cemetery's talk section selects an alternative dialogue for partner 37.
The extracted USA cemetery text contains the ghost questions and the uncertain
tamer responses; it has no corresponding translated question set.

The shared interpreter reads the partner species in the store-species opcode.
The textbox path (`showTextbox`, `scriptShowSelection`, `tickScriptDialogueBox`
and `drawTextboxStrings`) consumes the selected script's text; it has no
Bakemon-specific species test or message-bank substitution. The runtime cemetery
capture is necessary evidence here: the absence of a check in one script alone
does not establish the behavior of the whole game.

## Horizon comparison

At baseline commit `094c325e`, the File City branch remains in
[`script.py`](../../story/base/zones/file-city/s163-180-181-182/script.py).
Its `partner.species == Species.Bakemon` condition uses the extended engine's
species handling. The named partner remains species 37. Species 157 is the
field NPC variant, with no partner-raising data; it is not a renumbering of the
normal Bakemon partner.

The translated explanation `s163.sec5.u2` is explicitly present in every
language's `dialogue/file-city.json`: authored English (`text/ours`), Spanish,
Brazilian Portuguese, French, German, Italian, Japanese, Catalan and Simplified
Chinese. The cemetery source and all nine cemetery banks retain ghost speech.
No missing native cemetery translation has been established by these checks.

Decoding the nine generated `base/DG.SCN` files also confirms that every File
City version stores the partner species, compares it with 37, plays partner
animation 11 and reaches the explanatory textbox. This checks the compiled
selection as well as the authored sources.

Fresh Horizon boots reproduce the same distinction in English and Spanish on
2 MB: cemetery ghost speech and a translated File City explanation. The Spanish
save's language option is loaded through the normal game code. These runtime
checks establish no loss of the native translation in the tested baseline.

## Reproduction

Use an original-format one-block memory-card save. Set the 32-bit partner ID
at payload offset `0x1b8` to 37 in both copies, then recompute both checksums
as described in [the save format](../reference/save-format.md). Boot the
unmodified USA disc in 2 MB mode; a Horizon savestate is not a native fixture.

With recruitment flag 237 clear, visit screen 35 and talk to NPC slot 0.
Advance all three questions and answer Yes, Yes, No. The ghost questions,
acceptance and uncertain tamer response remain unchanged with this partner.
After recruitment, visit File City screen 180 at night and talk to its Bakemon.
Advance the ghost line and the tamer's initial response: the partner reaction
and patrolling explanation follow.

The original bytecode can be inspected locally with `tools/dws.py decompile
35`, `tools/dws.py decompile 163` and `tools/dws.py decompile maphead`.
Keep extracted original dialogue and script dumps outside committed files.

## Correction to the earlier investigation

Restricting an investigation to the cemetery's 68-instruction recruitment
section was insufficient. It missed a real partner translation branch in File
City and supplied no original-USA runtime comparison. An absent check in that one section
could not rule out selection elsewhere in the game. The earlier method was
incomplete; a claim that partner translation never exists would be too broad.

The broader source audit and original-USA runtime captures still do **not**
demonstrate translated cemetery recruitment questions. Claims that those
questions are translated, including the description on
[Wikimon's Overdell page](https://wikimon.net/Overdell), conflict with the tested
USA behavior. The readable cemetery dialogue added for v0.0.8 is new authored
dialogue rather than restoration of a translated question set recovered from
this disc.

## Horizon v0.0.8

A Bakemon partner now makes the three cemetery recruitment questions and the
acceptance line readable. Both Bakemon records, partner 37 and NPC twin 157,
are recognized. Other partners retain the existing ghost speech. The choices,
Yes/Yes/No solution, animations, departure and recruitment effects are unchanged.

The questions concern moving to the city, guarding it and fear of ghosts. The
acceptance jokes about haunting the city before correcting that to guarding it.
Four new keys, `s035.sec5.u8` through `u11`, are authored in every language bank.
The Python and DWS story views select them with partner-species branches; their
hashes are pinned in `story/base/authored.json`. File City's existing dialogue
is unchanged.

The recruitment regression test compiles both story views, resolves the partner
guards for both Bakemon IDs and unrelated species, and compares every remaining
choice and side effect with the original USA section by control-flow
bisimulation. It also rejects imported species whose low byte matches a Bakemon
ID and checks that all four selected utterances use the intended form.
