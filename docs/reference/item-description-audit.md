# Item description audit

All 128 item descriptions were compared in English, Spanish, Brazilian Portuguese,
French, German, Italian, Japanese and Catalan. Descriptions summarize an item's
main use; they do not list every food energy, weight or favourite-food modifier.
Effect values remain unchanged.

The source is `content/items/*.json`, with `content/tables/partner-rules.json`
for recovery amounts, `care-rules.json` for medicine dice, and
`evolution-rules.json` for the three later evolution items. Items without a JSON
`effect` also require checking their runtime handler in `src/main/item.c`,
`main.c` and the care, training, fishing and encounter code in the patched decomp.
An absent `effect` does not mean that an item does nothing.

| IDs | Checked against |
| --- | --- |
| 0–7 | HP/MP recovery handlers and `healingValues`: 500, 1500, 5000, full; Double Floppy has no JSON effect row and restores neither |
| 8–14 | Battle cures/protection, revival and JSON recovery/cure values; Bandage always heals injury and has a 2/10 sickness cure chance; Medicine uses 3/3 and 10/10 |
| 15–21 | Battle buff handlers; Omni Disk affects offense, defense and speed, without raising brains or maximum HP/MP |
| 22–31 | Auto Pilot dispatch; permanent chip gains and Devil Chips' six game hours of lifetime loss |
| 32–37 | Portable toilet effect; carried training/rest/encounter modifiers; walking HP/MP recovery |
| 38–70 | Every food's JSON energy, happiness, weight, tiredness, discipline, lifetime, recovery, stat gain, training boost and sickness fields |
| 71–114 | Every `evolution_target` and the corresponding species; Electo Ring's zero target supplies no usable evolution |
| 115–120 | Story and fishing uses: flute, rods, tablet, mansion key and Gear |
| 121–124 | Rain Plant's MP restoration and story use, Steak's food/healing/sickness effects, fridge key and decoder |
| 125–127 | `evolutionItemRules`: Gigadramon, IceLeomon and MetalEtemon, with the handler's partner-level checks |

Corrections and clarifications:

- 7: remove the promised 1500 HP/MP recovery: the runtime uses `itemFx(7)`,
  but the current JSON has no effect row. This audit does not add one.

- 9, 11–13: distinguish battle ailments from injury/sickness, name the recovery
  amount, and replace Bandage's vague sickness hint with its cure probability.
- 18: name the three affected combat stats instead of promising every stat.
- 29–31: state the six-hour lifetime cost rather than hiding it behind “But...”.
- 41, 42, 47: state the six-hour training boost duration. These do not promise
  every stat for Supercarrot or Hawk Radish: their JSON boost flags differ.
- 44: describe the same fullness as Meat and Digisnapper (all have energy 12).
- 55, 60, 61: distinguish restoration from permanent maximum gains and give the
  amounts; already precise translations retain their wording.
- 67–70, 122: expose sickness or its risk, and the lifetime gain for Digiseabass
  and Chain Melon. Moldy Meat's 100/100 sickness chance is certain. Other chances
  are 20%, 30%, 5% and 20% respectively.
- 83: remove the false Thundermon evolution claim. The current data supplies
  target zero, not Thundermon; this audit does not change that effect.

The audit changes 164 descriptions across the eight languages. Every other description was retained after review. Both runtime fonts must fit
244 pixels and the encoded description plus terminators must fit its 64-byte
textbox row. Validate with `python3 -m tools.localize.check` and the existing
`tools.test_languages` tests.
