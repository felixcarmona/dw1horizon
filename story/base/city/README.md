# city/

The rules that decide the city's state, as data ([city rules](../../../docs/mods/city-rules.md)). Generated from the original game by
`python3 tools/dws.py city-extract`; do not edit by hand.

| file | what |
|---|---|
| `city.dws` | `city { }`: prosperity, the File City top map (12 screens from 5 recruit flags), the revival screen, the new game's start state, the shop and arena map lists. These are the rules that are C code in the original; the tier-2 engine reads them from a table (MAPHEAD section 1260) that `dws compile --exe story-state` writes |
| `presence/` | who stands on which screen, and when: one file per screen, one rule per NPC, read out of MAPHEAD's setup sections and verified against them |

`python3 tools/dws.py city-compile --c-header ...` turns `city.dws` into the engine's built-in default table (the original rules), and
`python3 tools/dws.py city-verify` proves the declarations equal the original. A mod writes its own `city { }` (`tools/dws/examples/expanded-city-rules.dws`).
