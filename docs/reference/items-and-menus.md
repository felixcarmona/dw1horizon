# Items, inventory, shops and menus

What the original code does with items: the inventory, the effect of every item, how the partner accepts or refuses
one, shops, recycling, cards, the merit shop, the item keeper and the other shop-like routines, and the triangle menu
screens. Sources: `decomp/src/main/{item,inventory,game_menu,script_common,script_interp}.c`,
`decomp/src/shop/script_menu.c` and the `dooa/doo2/dget/eab` overlays; `file.c:line` citations are into `decomp/src/`.
RAM addresses are those of the original USA executable. The `ITEM_PARA` record layout is in
[executable.md](executable.md#item_para-128--32-bytes-item); names and prices are in `../data/items.csv`.

## Summary

- The inventory is three 30-byte arrays (`type`, `amount`, `name`) plus `size`
  (10/20/30 slots, raised by the script with op `0x23`). One item per stack, cap 99,
  and a full stack blocks picking up more of that type.
- Each item has a handler in `ITEM_FUNCTIONS[128]` (`item.c:1931`); the numbers for
  each effect (HP, stats, energy, weight, sickness) are in the item table below. Using
  an item in the field means "giving" it to the partner (who may refuse it); in battle
  it means throwing it at them.
- Normal shops sell whatever the map script's *triggers* `0x180+id` mark, at the price
  in `ITEM_PARA.value` (−10 % with a baby partner), and buy at half price. The card
  shop, recycling (items lost on death), the merit shop, the item keeper (a bank of 128
  counters), the jukebox, Birdramon and Mojyamon live in `src/shop/script_menu.c`,
  which in the USA version is linked inside `SLUS`.
- Cards: 66 entries (`CARD_DATA`), collection in `SCRIPT_STATE.cards` (one nibble per
  card, 0–9). Six new random cards in the shop every day.
- The triangle menu (`game_menu.c`) has 6 options (+ Fish): Items, Digimon
  (Status / Techniques), Player (Player / Chart / Medals / Cards / City), Praise, Scold,
  Sleep, Fish. The original has no in-game options screen (sound and vibration are set in the title menu,
  `main_menu.c`); our build adds one ([../mods/options.md](../mods/options.md)).
- The DOOA/DOO2 overlays are the death and reincarnation cutscene (and the egg choice
  box), DGET the arena tournament calendar screens and EAB the boss appearance effect.
  None of them is an item menu.
- Elsewhere: the evolution that `EVOLUTION_TARGET` starts ([partner.md](partner.md)), disk *buffs* in battle
  ([combat.md](combat.md)), chest contents ([world.md](world.md)). The economy of Monochromon's shop and the
  restaurant lives in the map scripts (the executable only provides the `SHOP_VARIABLE` accumulator and the mood
  bubble).

## City page

City is read-only: prosperity, recruited residents and their points. Missing
residents are grey; Devimon, Airdramon and MetalGreymonVirus stay unnamed and
have empty boxes until recruited. Extended story shows 96 residents (180
points maximum); original story shows 50 (100 points). NEW DIGIMON does not
change this page. Opening it refreshes prosperity using the save's rule.

## Source files

| File | Contents |
|---|---|
| `src/main/item.c` | `ITEM_PARA`, `ITEM_DESCS`, `ITEM_FUNCTIONS`, `EVOLUTION_ITEM_TARGET`, effect handlers (`handleFood`, `handleChips`, `handleEvoItems`, `handleRestore`, `handleStatusItems`, HP/MP healing), inventory (`giveItem`, `removeItem`, `getItemCount`, `initializeInventory`), items on the ground (`DROPPED_ITEMS`, `spawnItem`, `pickupItem`), sprite of the item in hand (`TAMER_ITEM`) |
| `src/main/inventory.c` | the inventory box in the menu: cursor, Use/Move/Sort/Drop, `sortItems`, availability colours |
| `src/main/main.c:4149-4345` | `initializeInventoryModules`, throwing the item in battle (`startThrowingItem`, `tickThrownItem`) and `handleBuffDisks` |
| `src/main/partner.c:418-520` | partner state 5: approach, accept or refuse the item, eat it and run the handler |
| `src/main/partner_impl.c:1401-1462` | `partnerWillRefuseItem` (which items it refuses and why) |
| `src/main/game_menu.c` | triangle menu, Digimon screens (status, techniques) and Player screens (player, evolution chart, medals, cards, City) |
| `src/main/script_common.c` | normal shop (`openShop`), buy/sell lists, amount box, single-card shop, item loss on death (`handleItemLoss`), daily restock (`dailyPStatTrigger`), tables `CARD_DATA`, `CARD_PRICES`, `SHOP_MAPS`, `RECYCLABLE_ITEMS`, `BIRDRA_TRANSPORT_TARGETS`, medals and album (`hasMedal`, `hasDigimonRaised`) |
| `src/main/script_interp.c` | script ops for items/cards/money (`0x23`, `0x28-0x2B`, `0x2F-0x33`, `0x74`), `getCardAmount`/`setCardAmount`, dispatch of the shop routines (`:345-382`) |
| `src/shop/script_menu.c` | recycling, card packs and card shop, merit shop, item keeper, jukebox, Birdramon, Mojyamon trades, name box and new game dialogue. In USA it is in `SLUS` itself (`config/us/main.yaml:131`), although `SHOP_REL.BIN` is still on the disc and `checkShopMap` (`script_common.c:2978`) loads it in the 8 maps of `SHOP_MAPS` |
| `src/dooa/dooa.c` (`DOOA_REL.BIN`, base `0x80080000`) | death and reincarnation cutscene: model dissolving into fragments (`DOOA_tickDissolve`), iris, camera, rebirth (`DOOA_tickRebirth`, `REINCARNATE_BABY_TYPE[4]`) |
| `src/doo2/doo2.c` (`DOO2_REL.BIN`, base `0x80070000`) | DOOA helpers (fragments, CLUT, wireframe model) and the egg choice box (`DOO2_openEggBox`, 4 eggs, script routine `0x1d`) |
| `src/dget/dget.c` (`DGET_REL.BIN`, base `0x80080800`) | arena tournament calendar and registration (`initTournamentSchedule`, `isTournamentEnabled`, `tournamentCheckEligible`); loaded in `ARENA_MAPS` 208/223 (`checkArenaMap`) |
| `src/eab/eab.c` (`EAB_REL.BIN`, base `0x80060000`) | boss appearance effect (`EAB_startBuildup`, rings, particles, flash); not a menu |
| `include/dw/item.h`, `script.h:143-200`, `ui.h` | `Item`, `Inventory`, `WorldItem`, `ScriptState` (cards, triggers, pstats), `CardData`, `ItemMenuBox`, `UIBoxData` |

## State in memory

All addresses verified in `config/us/symbols.txt`; internal offsets come from the
structs in `include/dw/`.

| Symbol | RAM | Type / size | Meaning |
|---|---|---|---|
| `INVENTORY` | `0x8013D474` | `Inventory`, 0x5B | `types[30]` at `+0`, `amounts[30]` at `0x8013D492`, `names[30]` at `0x8013D4B0`, `size` (u8) at `0x8013D4CE`. `type 0xFF` = empty slot; `names[i]` is the text row that shows the name (rewritten to `i` when the menu opens, `inventory.c:268`) |
| `TAMER_ITEM` | `0x8013D4D0` | `TamerItem`, 0x10 | item in hand / in flight: `spriteLocation` (SVECTOR), `type` (i32, `0xFF` = none) at `+8`, `time` (frames) at `+12` |
| `DROPPED_ITEMS` | `0x8013D4E0` | 11 × `DroppedItem` (16) | items on the map floor: `spriteLocation`, `type` (`+8`), `tileX`/`tileY` (`+12`/`+14`) |
| `ITEM_PARA` / `ITEM_DESCS` | `0x801269DC` / `0x801279DC` | 128 × 32 / 128 pointers | layout in [executable.md](executable.md#data-tables) |
| `ITEM_FUNCTIONS` | `0x80127C88` | 128 pointers | handler per item (NULL = no effect) |
| `EVOLUTION_ITEM_TARGET` | `0x80127C5C` | 44 u8 | target species of items 71–114 |
| `ITEM_CLUT_DATA` | `0x80127BDC` | 128 u8 | palette of each item's sprite |
| `HEALING_VALUES` | `0x8013435C` | 4 i16 | 500, 1500, 5000, 9999 (HP/MP recovery) |
| `INITIAL_INVENTORY_TYPES` / `_AMOUNTS` | `0x80125F44` / `0x80125F24` | 30 u8 each | kit loaded by `initializeInventory` when the exe starts (`item.c:2641`) |
| `DEFAULT_INVENTORY_TYPES` / `_AMOUNTS` | `0x80131618` / `0x801315F8` | 30 u8 each | new game kit (`main_menu.c:3871-3878`) |
| `ITEM_SORT_ORDER` | `0x8012A9C4` | 3 × 6 u8 | category order for Battle / Raising / Basic |
| `INVENTORY_ACTION` | `0x80134E04` | i32 | box state machine (1 open, 5 use, 7 drop, 8 sort, 11–13 sorted, 14 confirm drop) |
| `INVENTORY_POINTER` | `0x80134E10` | u8 | slot under the cursor (`ITEM_MOVE_SOURCE` `0x80134E11`, `ITEM_MENU_SELECTED` `0x80134E13`, `SORT_SELECTED` `0x80134E14`, `DROP_ITEM_SELECTED_OPTION` `0x80134E15`) |
| `EVOLUTION_TARGET` / `HAS_USED_EVOITEM` | `0x80134E50` / `0x80134E52` | i16 / u8 | what `handleEvoItems` leaves for the evolution sequence |
| `MONEY` | `0x80134EB8` | i32 | bits, cap 999 999 |
| `MERIT` | `0x80134FC4` | i16 | merit points, cap 9 999 |
| `SCRIPT_STATE` | `0x801BDED8` | `ScriptState`, 0x29C | `smth[212]` + `cards[33]` (`0x801BDFAC`) + `triggers[100]` (`0x801BDFCD`) + `pstats[256]` (`0x801BE031`) + stack. `SCRIPT_STATE_PTR` (`0x80134FB8`) points here (`script_interp.c:2119`); the first 0x17C bytes (smth, cards, triggers and 35 pstats) go into the save game (`main_menu.c:3977`). |
| `SCRIPT_STATE.smth[0..5]` | `0x801BDED8` | 6 u8 | stock of the day's card shop (card id or `0xFF` = sold) `[inferred]` |
| `SCRIPT_STATE.smth[6..83]` | `0x801BDEDE` | 78 u8 | recycling stock, indexed by `RECYCLABLE_ITEMS` (cap 99) |
| `SCRIPT_STATE.smth[84..211]` | `0x801BDF2C` | 128 u8 | item keeper ("Keeping"): stored amount of each item, cap 99 |
| `SCRIPT_STATE.cards` | `0x801BDFAC` | 33 u8 | card `c` in byte `c/2`, low nibble if `c` even, high if odd (`script_interp.c:2402-2434`) |
| `SCRIPT_STATE.triggers` | `0x801BDFCD` | 100 u8 (800 bits) | bit `t` = byte `t/8`, mask `1<<(t%8)` (`script_interp.c:2578`). `0x180+id` = item on sale; `0x16C+m` = medal `m`; `0x200+id` = Digimon raised (album) |
| `CARD_DATA` / `CARD_PRICES` | `0x8012FFD8` / `0x8012FFC4` | 66 × `{u8 digimonId, u8 rarity, i16 merit}` / 5 i32 | cards; price by rarity 5000, 1500, 500, 100, 50 |
| `SHOP_MAPS` / `SHOPKEEP_DIGIMON_TYPES` | `0x8012FE68` / `0x8012FE5C` | 8 i16 / 11 u8 | maps where `SHOP_REL` is loaded (131, 133, 134, 141, 207, 211, 215, 218) and shopkeeper species |
| `RECYCLABLE_ITEMS` | `0x8012FE78` | 78 u8 | items that can end up in recycling (11, 12, 23–31, 33, 35, 36, 46, 50, 56–61, 67, 70–76, 78–124; 84 appears twice) |
| `MOJYAMON_ITEMS_GIVE` / `_GET` | `0x80130438` / `0x80130444` | 9 (+3) u8 | Mojyamon trades |
| `BIRDRA_TRANSPORT_TARGETS` | `0x8013024C` | 6 × `{u8 map, u8 exit, u16 trigger, u32 cost}` | Birdramon destinations |
| `ITEM_MENU_LEFT` / `ITEM_MENU_RIGHT` | `0x80134F68` / `0x80134F6C` | `ItemMenuBox *` | shop lists (`buf` = `{id, amount|flags}` pairs), allocated with `allocateArray` |
| `SHOP_ITEM_TYPE` / `SHOP_ITEM_PRICE` / `SHOP_AMOUNT` / `MAX_SHOP_AMOUNT` | `0x80134F78` / `0x80134F7C` / `0x80134F81` / `0x80134F80` | u8 / i32 / u8 / u8 | transaction in progress |
| `SHOP_VARIABLE` | `0x8013500C` | i32 | shop accumulator (card merit, baby discount, Birdramon cost, and the one scripts use with sub-ops `0x1e/0x1f/0x38`) |
| `ITEM_MENU_TYPE` / `SCRIPT_STATE_2` | `0x80135011` / `0x80134FFA` | u8 / u16 | list type (0 buy, 1 sell, 2 recycling, 3 buy card, 4 sell card, 5 discard, 6 card→merit, 7 merit→item) and shop routine state |
| `MENU_OPTIONS` / `MENU_OPTION_COUNT` | `0x80123E88` / `0x80134D28` | 8 × 12 / u8 | triangle options; `MENU_OPTIONS[0].unknown` is the cursor |
| `TRIANGLE_MENU_STATE`, `MENU_STATE`, `MENU_SUB_STATE`, `DIGIMON_MENU_STATE`, `PLAYER_MENU_STATE` | `0x80134D30`, `0x80134D34`, `0x80134D35`, `0x80134D36`, `0x80134D37` | u8 | menu state; Digimon tab (0 status, 1 techniques) and Player tab (0–3) |
| `SELECTED_MEDAL` / `MEDAL_SELECTOR_INDEX` / `SELECTED_CARD` / `CHART_SELECTED_DIGIMON` | `0x80134D3C` / `0x80134D3D` / `0x80134D3E` / `0x80134D40` | u8 / u8 / u8 / i16 | medal, card and chart cursors |
| `EQUIPPED_MOVES` / `MOVE_SELECT_BOX_X` / `_Y` | `0x80134234` / `0x80134D3A` / `0x80134D38` | 4 u8 / i16 / i16 | equipped techniques (ids from `MOVE_NAMES`) and techset cursor |
| `HAS_FISHING_ROD` / `IS_IN_MENU` | `0x80134D2C` / `0x80134EF0` | u8 / i32 | Fish option (0 hidden, 1 grey, 2 active) and "time is stopped by a menu" |
| `UI_BOX_DATA` / `TEXTBOX_DATA` | `0x8013D390` / `0x801BE80C` | 6 × `UIBoxData` / `TextBoxTable` | menu boxes (0 inventory, 1 description, 2 options, 3 submenu) and shop text boxes |

## Items

Columns: `cat` = `sortingValue` (0 recovery, 1 status, 2 food, 3 disk,
4 chip/evolution, 5 tool/key); `use` = `itemColor` (F field, B battle, FB both,
– never); price = `value` (sell = price/2 if `droppable`). "where": "shops" = can be
sold in any normal shop whose script sets its trigger (which shop sells what is in
the scripts); "kit ×n" = amount in the new game. "Energy" is `energyLevel`
(capped by `RAISE_DATA.energyCap`), "weight" `weight` (1–99), "life" `remainingLifetime`.
All food subtracts 1 from `poopLevel`; if it is the species' favourite, energy ×1.4 and
happiness +2 (`item.c:2894`). Stat caps are 9999 HP/MP and 999 for the rest.

| id | name | cat | use | price | effect (code) | where |
|---|---|---|---|---|---|---|
| 0 | sm.recovery | 0 | FB | 100 | +500 HP (`handleHPHealingItem`, only if HP>0) | shops (trigger) |
| 1 | med.recovery | 0 | FB | 500 | +1500 HP | shops; Mojyamon gives/asks |
| 2 | lrg.recovery | 0 | FB | 1000 | +5000 HP | shops; starting kit ×40 |
| 3 | sup.recovery | 0 | FB | 2500 | HP to max (+9999) | shops; merit 20 |
| 4 | MP Floppy | 0 | FB | 300 | +500 MP (`handleMPHealingItem`) | shops |
| 5 | Medium MP | 0 | FB | 800 | +1500 MP | shops |
| 6 | Large MP | 0 | FB | 2000 | +5000 MP | shops |
| 7 | Double flop | 0 | FB | 1500 | +1500 HP and +1500 MP (`handleDoubleFloppy`) | shops |
| 8 | Various | 1 | B | 300 | `BTL_healStatusEffect(1)` (cures status effects) | shops |
| 9 | Omnipotent | 1 | FB | 2000 | in battle `BTL_healStatusEffect(0)`; +1500 HP and +1500 MP (not "full") | shops; kit ×45 |
| 10 | Protection | 1 | B | 1200 | `fighter[0].flags \|= PROTECTED` (immune to status effects for that fight) | shops |
| 11 | Restore | 1 | B | 4000 | revives (removes the death countdown), +maxHP/2 (`handleRestore`) | shops; Mojyamon |
| 12 | Sup.restore | 1 | FB | 9500 | revives, cures status effects in battle, HP to max | merit 100; kit ×50 |
| 13 | Bandage | 1 | F | 200 | always cures injury; sickness with 20 % (`handleMedicineHealing(3,2)`) | shops |
| 14 | Medicine | 1 | F | 1000 | always cures injury and sickness (`(3,10)`) | shops; Mojyamon |
| 15 | Off. Disk | 3 | B | 500 | ATK +20 in combat, cap initial ATK ×1.3 (`handleBuffDisks`, `main.c:4231`) | shops |
| 16 | Def. Disk | 3 | B | 500 | DEF +20, same cap | shops |
| 17 | Hispeed dsk | 3 | B | 500 | SPD +20, same cap | shops; Mojyamon asks |
| 18 | Omni Disk | 3 | B | 3000 | ATK, DEF and SPD +20 with no cap, unlike the other six disks (`main.c:4292-4312`) | shops |
| 19 | S.Off.disk | 3 | B | 4000 | ATK +50, cap ×1.3 | shops; Mojyamon gives |
| 20 | S.Def.disk | 3 | B | 4000 | DEF +50 | shops; Mojyamon gives |
| 21 | S.speed.disk | 3 | B | 4000 | SPD +50 | shops; Mojyamon gives |
| 22 | Auto Pilot | 5 | F | 300 | if the script is paused: jumps to section `0x4DD` of script 0 (return to town) (`handleChips` case `0x16`) | shops; Mojyamon gives |
| 23 | Off. Chip | 4 | F | 9999 | base ATK +50 | merit 800 |
| 24 | Def. Chip | 4 | F | 9999 | base DEF +50 | merit 800 |
| 25 | Brain Chip | 4 | F | 9999 | base BRN +50 | merit 800 |
| 26 | Quick Chip | 4 | F | 9999 | base SPD +50 | merit 800 |
| 27 | HP Chip | 4 | F | 9999 | max HP +500 | merit 800 |
| 28 | MP Chip | 4 | F | 9999 | max MP +500 | merit 800 |
| 29 | DV Chip A | 4 | F | 5000 | ATK +100, BRN +100, life −24, 10 % chance of losing a tamer level (`addTamerLevel(10,-1)`) | shops |
| 30 | DV Chip D | 4 | F | 5000 | DEF +100, SPD +100, life −24, 10 % −1 level | shops |
| 31 | DV Chip E | 4 | F | 5000 | max HP +1000, max MP +1000, life −24, 10 % −1 level (the description says ATK+SPD; the code `item.c:2284` does not) | shops |
| 32 | Port. potty | 5 | F | 300 | if it needs to go (`condition&8`): `poopLevel = poopTimer`, removes the condition and the poop weight (`handlePortaPotty`); consumed either way | shops |
| 33 | Trn. manual | 5 | F | 9999 | passive: training result ×1.1 (`trn_reward.c:712`, `trn2_hud.c:230`); the partner refuses it if given | shops |
| 34 | Rest pillow | 5 | F | 1000 | passive: sleep recovery ×1.2 (`partner_impl.c:1321`); refused | shops |
| 35 | Enemy repel | 5 | F | 5000 | passive: encounter roll +20 → fewer enemies join (`btl.c:293-306`); refused | shops |
| 36 | Enemy bell | 5 | F | 5000 | passive: roll −50 → more enemies; overrides the repel; refused | shops |
| 37 | Health shoe | 5 | F | 2000 | passive: while walking, every 20 frames +5 HP and +5 MP to the partner (`partner.c:938-957`); refused | shops |
| 38 | Meat | 2 | F | 50 | energy +12, weight +1 (`handleFood`) | shops |
| 39 | Giant Meat | 2 | F | 500 | energy +24, weight +2 | shops; Mojyamon asks |
| 40 | Sirloin | 2 | F | 1500 | energy +35, tiredness −5, happiness +3, weight +3 | shops |
| 41 | Supercarrot | 2 | F | 500 | energy +10, training bonus flag `0x29` value 12 for 6×1200 frames, weight −2 | shops; Mojyamon asks |
| 42 | Hawk radish | 2 | F | 500 | energy +15, bonus flag `0x16` value 12, 6×1200 frames, weight +3 | shops |
| 43 | Spiny green | 2 | F | 1000 | energy +9, tiredness −50, weight +1 | shops |
| 44 | Digimushrm | 2 | F | 100 | energy +12, weight +1 | Mojyamon asks |
| 45 | Ice mushrm | 2 | F | 1000 | energy +19, discipline +50, weight +2 | |
| 46 | Deluxmushrm | 2 | F | 5000 | energy +38, ATK/DEF/SPD/BRN +10, max HP/MP +100, weight +4 | recyclable |
| 47 | Digipine | 2 | F | 1000 | energy +22, bonus flag `0x3F` value 15, 6×1200 frames, weight +2 | |
| 48 | Blue apple | 2 | F | 1000 | energy +30, happiness +50, weight +3 | |
| 49 | Red Berry | 2 | F | 1000 | energy +25, tiredness −20, happiness +20, discipline +20, weight +2 | |
| 50 | Gold Acorn | 2 | F | 8000 | energy +40, weight +4 (worth it for its sell price: 4000) | recyclable |
| 51 | Big Berry | 2 | F | 1000 | energy +100, weight +10 | |
| 52 | Sweet Nut | 2 | F | 1000 | energy +20, HP to max, weight +2 | |
| 53 | Super veggy | 2 | F | 1000 | energy +16, MP to max, weight +2 | |
| 54 | Pricklypear | 2 | F | 1000 | energy +33, weight −5 | |
| 55 | Orange bana | 2 | F | 1000 | energy +24, +1000 HP and +1000 MP (not "full"), weight +2 | |
| 56 | Power fruit | 2 | F | 5000 | energy +20, ATK +20, weight +2 | recyclable |
| 57 | Power Ice | 2 | F | 5000 | energy +20, DEF +20, weight +2 | recyclable |
| 58 | Speed Leaf | 2 | F | 5000 | energy +20, SPD +20, weight +2 | recyclable |
| 59 | Sage Fruit | 2 | F | 5000 | energy +20, BRN +20, weight +2 | recyclable |
| 60 | Muscle Yam | 2 | F | 5000 | energy +20, max HP +200, weight +2 | recyclable |
| 61 | Calm berry | 2 | F | 5000 | energy +20, max MP +200, weight +2 | recyclable |
| 62 | Digianchovy | 2 | F | 50 | energy +8, weight +1 | fishing; Mojyamon asks |
| 63 | Digisnapper | 2 | F | 100 | energy +12, weight +1 | fishing |
| 64 | DigiTrout | 2 | F | 300 | energy +22, weight +2 | fishing |
| 65 | Black trout | 2 | F | 1000 | energy +27, +1 to all four stats, max HP/MP +10, weight −2 | fishing; Mojyamon asks |
| 66 | Digicatfish | 2 | F | 2000 | energy +49, weight +5 | fishing |
| 67 | Digiseabass | 2 | F | 8000 | energy +35, HP and MP to max, life +3, 20 % chance of sickness, weight +4 | fishing; recyclable |
| 68 | Moldy Meat | 2 | F | 50 | energy +30, always causes sickness (100 %), weight +2 | |
| 69 | Happymushrm | 2 | F | 1000 | energy +15, happiness +30, tiredness −30, 30 % chance of sickness, weight +1 | Mojyamon asks |
| 70 | Chain melon | 2 | F | 5000 | energy +50, happiness +50, tiredness −50, life +20, 5 % chance of sickness, weight +3 | recyclable |
| 71 | Grey Claws | 4 | F | 5000 | evolves into Greymon (5) | recyclable |
| 72 | Fireball | 4 | F | 5000 | Meramon (9) | |
| 73 | Flamingwing | 4 | F | 5000 | Birdramon (21) | |
| 74 | Iron Hoof | 4 | F | 5000 | Centarumon (36) | |
| 75 | Mono Stone | 4 | F | 5000 | Monochromon (47) | |
| 76 | Steel drill | 4 | F | 5000 | Drimogemon (38) | |
| 77 | White Fang | 4 | F | 5000 | Tyrannomon (8) | |
| 78 | Black Wing | 4 | F | 5000 | Devimon (6) | |
| 79 | Spike Club | 4 | F | 5000 | Ogremon (34) | |
| 80 | Flamingmane | 4 | F | 5000 | Leomon (48) | |
| 81 | White Wing | 4 | F | 5000 | Angemon (20) | |
| 82 | Torn tatter | 4 | F | 5000 | Bakemon (37) | |
| 83 | Electo ring | 4 | F | 5000 | target 0 ("main character", Kaminarimon does not exist): never evolves `[inferred]` | |
| 84 | Rainbowhorn | 4 | F | 5000 | Airdramon (7) | merit 500 |
| 85 | Rooster | 4 | F | 5000 | Kokatorimon (50) | |
| 86 | Unihorn | 4 | F | 5000 | Unimon (33) | |
| 87 | Horn helmet | 4 | F | 5000 | Kabuterimon (19) | |
| 88 | Scissor jaw | 4 | F | 5000 | Kuwagamon (51) | |
| 89 | Fertilizer | 4 | F | 5000 | Vegiemon (25) | |
| 90 | Koga laws | 4 | F | 5000 | Ninjamon (58) | |
| 91 | Waterbottle | 4 | F | 5000 | Seadramon (10) | merit 500 |
| 92 | North Star | 4 | F | 5000 | Whamon (24) | |
| 93 | Red Shell | 4 | F | 5000 | Shellmon (35) | merit 500 |
| 94 | Hard Scale | 4 | F | 5000 | Coelamon (49) | merit 500 |
| 95 | Bluecrystal | 4 | F | 5000 | Garurumon (22) | |
| 96 | Ice crystal | 4 | F | 5000 | Frigimon (23) | merit 500 |
| 97 | Hair grower | 4 | F | 5000 | Mojyamon (52) | Mojyamon gives |
| 98 | Sunglasses | 4 | F | 5000 | Nanimon (53) | |
| 99 | Metal part | 4 | F | 9999 | MetalGreymon (12) | |
| 100 | Fatal Bone | 4 | F | 9999 | SkullGreymon (26) | |
| 101 | Cyber part | 4 | F | 9999 | Andromon (40) | |
| 102 | Mega Hand | 4 | F | 9999 | Megadramon (54) | |
| 103 | Silver ball | 4 | F | 9999 | Mamemon (13) | |
| 104 | Metal armor | 4 | F | 9999 | MetalMamemon (27) | |
| 105 | Chainsaw | 4 | F | 9999 | Giromon (41) | |
| 106 | Small spear | 4 | F | 9999 | Piximon (55) | |
| 107 | X Bandage | 4 | F | 9999 | Monzaemon (14) | |
| 108 | Ray Gun | 4 | F | 9999 | Vademon (28) | |
| 109 | Gold banana | 4 | F | 9999 | Etemon (42) | |
| 110 | Mysty Egg | 4 | F | 9999 | Digitamamon (56) | |
| 111 | Red Ruby | 4 | F | 9999 | Phoenixmon (59) | |
| 112 | Beetlepearl | 4 | F | 9999 | H-Kabuterimon (60) | |
| 113 | Coral charm | 4 | F | 9999 | MegaSeadramon (61) | |
| 114 | Moon mirror | 4 | F | 9999 | WereGarurumon (62) | |
| 115 | Blue Flute | 5 | F | 9999 | no handler; the partner refuses it (not consumed); read by scripts | cannot be dropped |
| 116 | old fishrod | 5 | F | 100 | no handler, refused; enables Fish (`fish.c:59`) | cannot be dropped |
| 117 | Amazing rod | 5 | F | 3000 | no handler, refused; better rod | merit 300; cannot be dropped |
| 118 | Leomonstone | 5 | F | 100 | no handler, refused; scripts | cannot be dropped |
| 119 | Mansion key | 5 | F | 100 | no handler, refused; scripts | cannot be dropped |
| 120 | Gear | 5 | F | 100 | no handler, refused; scripts | cannot be dropped |
| 121 | Rain Plant | 5 | FB | 1000 | +1000 MP (`handleFood` case `0x79`, no energy or weight) | recyclable |
| 122 | Steak | 0 | F | 1000 | energy +32, +1000 HP, 20 % chance of sickness (`0x7A`) | recyclable |
| 123 | Frig Key | 5 | – | 100 | no handler; `itemColor 0xFF`: "Use" is never enabled | cannot be dropped |
| 124 | AS Decoder | 5 | – | 500 | same | cannot be dropped |
| 125 | Giga Hand | 4 | F | 0 | Gigadramon (64); accepted only at level 4 (`partner_impl.c:1426`) | no price; kit ×50 |
| 126 | Noble Mane | 4 | F | 0 | Panjyamon (63); only at level 3 | kit ×50 |
| 127 | Metalbanana | 4 | F | 0 | MetalEtemon (65); only at level 4 | kit ×80 |

Evolution items 71–114 (`handleEvoItems`, `item.c:2179`): the target is
`EVOLUTION_ITEM_TARGET[id-71]` and its level must be exactly the partner's
+1; `partnerWillRefuseItem` (`partner_impl.c:1421-1433`) refuses the item
(and it is not consumed) if the target is at the same level, two above or one below.
If accepted, the handler sets `EVOLUTION_TARGET`, `HAS_USED_EVOITEM=1`, puts the
tamer in state 6 and the partner in 13 (evolution sequence: raising); the item is
consumed (`partner.c:497`). "Merit N" = bought in the merit shop for N points;
"shops (trigger)" = any shop whose script sets trigger `0x180+id`.

## How it works

### Inventory

- When the exe starts, `initializeInventory` (`item.c:2641`) loads the test kit
  `INITIAL_INVENTORY_*` with `size=30`; "New game" replaces it with
  `DEFAULT_INVENTORY_*` (`main_menu.c:3871-3878`): 29 stacks (lrg.recovery ×40,
  Omnipotent ×45, Sup.restore ×50, S.Off ×30, S.Def ×40, S.speed ×30, Digiseabass ×30,
  Chain melon ×30, Medicine ×30, Rainbowhorn ×30, Koga laws ×30, Hard Scale ×50,
  Bluecrystal ×30, Silver ball ×40, Metal armor ×30, Giga Hand ×50, Noble Mane ×50,
  Metalbanana ×80, Hair grower ×50, Fatal Bone ×50, Small spear ×98, Ray Gun, Mysty Egg,
  Red Ruby, Beetlepearl, Coral charm, Mansion key, Port. potty and Auto Pilot ×50), 50 000
  bits and `size=30`. Loading a game copies `savegame->inventory`
  (`main_menu.c:3955`). The intro script then trims this (see Notes).
- `giveItem(type, n)` (`item.c:2551`): if a stack already exists, adds to it (cap 99) and
  returns 1, but if the stack is at 99 it returns 0 without looking for free slots;
  otherwise, first `0xFF` slot within `size`; with no slot it returns 0. `removeItem`
  (`:2605`) subtracts and empties the slot if it reaches 0. `getItemCount` (`:2538`)
  only looks at the first `size` slots.
- `size` is changed by the script with `SCRIPT_OP_SET_INVENTORY_SIZE` (`0x23`,
  `script_interp.c:740`). The box shows 10 slots (2 columns × 5) or 18 with scrolling
  (`inventory.c:460-470`).
- Picking up from the ground: `tamerTickTakeItem` (`tamer.c:1370`) probes with
  `giveItem(type,0)` (fails only with the stack at 99 or no free slot) and then
  `pickupItem` (`item.c:2628`) adds 1 and clears `DROPPED_ITEMS[i]`. Chests do the same
  with `TAKE_CHEST_ITEM` (`tamer.c:1505-1532`). `spawnItem` (`:2426`) and script op
  `0x74` create up to 11 items on the ground (world object `0x195`).
- Menu: Use (`itemColor` 0/2 in the field, 1/2 in battle; `inventory.c:829-862`), Move
  (swaps the slot's three bytes), Sort (Battle: recovery, status, disks, food, tools,
  chips; Raising: food, tools, recovery, status, chips, disks; Basic: food, recovery,
  status, disks, tools, chips; by id within each group, `sortItems` `:897`), Drop (only
  `droppable`, only in the field, with confirmation: destroys **the whole stack** and
  leaves nothing on the ground, `:384`).
- Scripts: `GIVE_ITEM` (`0x28`, sets trigger 0 if it does not fit), `REMOVE_ITEM` (`0x29`),
  `ADD/REDUCE_MONEY` (`0x2A/0x2B`, caps 0 and 999 999), amount comparison
  (`script_value.c:351`), sub-ops `0x0c/0x0d` remove 1/99 of the item in `pstat 0xFE`.

### Using an item

- Field: `startFeedingItem` (`game_menu.c:2019`) puts the type in `TAMER_ITEM`, tamer
  state 6, partner state 5. The partner walks up (`ITEM_TAKE_DISTANCE`), and on frame 8
  of the animation decides with `partnerWillRefuseItem` (`partner_impl.c:1401`):
  it always refuses 115–120/123–124 and 33–37; evolution items at the wrong level;
  non-food items (id < 38) with probability `110 − (discipline + 10..19)` % (and sets
  `ITEM_SCOLD_FLAG`: scolding then gives discipline +8 and the next one is accepted);
  and 2 out of 10 times its favourite food if it is not hungry. Refused → animation 13,
  the item goes back to the inventory. Accepted → animation 8, at the end
  `ITEM_FUNCTIONS[type]`, `removeOneSelectedItem` (1 unit) and `partnerHandleFoodFeed`
  (`partner.c:486-500`): eating when not hungry costs happiness −3 and discipline −2
  (`partner_impl.c:1622`); the rest is raising.
- Care menu (our build, patches 0150–0155 and 0158, `mod_feed.c`): on the map, X in front of the partner lists, in the inventory's
  layout and most urgent first (the cursor on it), Sleep when it is sleepy and the items for the needs it has,
  nothing else (cures when injured or sick, Port. potty when it needs to go, food only when hungry with its
  favourite first in gold, field HP/MP items when short of the maximum); a second description line warns of a cure
  that may not work or marks the favourite food. It gives the chosen item through
  `startFeedingItem` as above (refusals included) or puts it to sleep as the triangle menu does. Nothing to offer:
  X does nothing. With a fair scolding pending (`ITEM_SCOLD_FLAG` 1, patches 0152–0153) Scold heads the list (the
  triangle menu's Scold), and a refusal of the item the menu gave opens the menu again with Scold under the cursor.
  While X would open it, the dialogue box's X button is drawn beside the condition bubbles (patch 0158, `bubble.c`; alone where the
  bubbles would be when there is none).
- Battle: `startThrowingItem` (`main.c:4175`) removes 1 unit immediately, the item flies
  for 24 frames (`ITEM_THROW_HEIGHT`) and on landing runs the handler (`:4217`). Healing
  handlers do nothing at HP 0 except Restore/Sup.restore (`item.c:2304`), which revive.
- Handlers write directly to `PARTNER_ENTITY.digimonEntity.stats` and `PARTNER_PARA`
  with `addWithLimit` (`item.c:2918`); disks go through `BTL_buffStats`.

### Normal shops and recycling

- Entering a map in `SHOP_MAPS` loads `SHOP_REL` (`checkShopMap`); script routine 8
  opens `openShop` or, with `TRIGGER_3` set, `openRecycleShop`
  (`script_interp.c:355-357`). The lists are stored in `ITEM_MENU_LEFT/RIGHT` as
  `{id, amount|0x80 buyable}` pairs.
- Stock: `shopFillBuyItemList` (`script_common.c:660`) walks the 128 items and offers
  those with trigger `0x180+id`; it is only marked buyable if `value ≤ MONEY` and it
  fits (free slot or stack < 99). Those triggers are set by the map script, not the exe.
- Buy price `ITEM_PARA.value`; with a baby partner (`BABY_IDS`) the unit price is
  `value×90/100` and the accumulated difference goes to `SHOP_VARIABLE` (`:1478-1484`).
  Max amount = min(99 − the ones you have, `MONEY/price`) (`:1916-1966`). Selling: only
  `droppable`, at `value>>1` (`:1944`), any amount; `MONEY` caps at 999 999.
- Recycling: on death, `handleItemLoss` (`:1283`) loses 30 % of the occupied stacks
  (whole, at random); those in `RECYCLABLE_ITEMS` add their amount to `smth[6+idx]`
  (cap 99) and can be bought back at full price; buying subtracts from the stock
  (`:1489`). Only items with stock > 0 appear (`script_menu.c:1311`).
- "Discard" (routine 0, `openDiscardItem` `:1767`) is the same sell list used by
  scripts: it leaves the chosen item in `pstat 0xFE` and clears `TRIGGER_3`.

### Cards and the merit shop

- `CARD_DATA[66]`: rarity (`spriteId`) 0 (ids 1–5, merit 100), 1 (6–25, 30), 2 (26–50,
  10), 3 (51–60, 5), 4 (61–64, 1); 0 and 65 are sentinels (rarity 5). Collection in
  `SCRIPT_STATE.cards`, 0–9 per card; ops `GIVE_CARD`/`TAKE_CARD` (`0x2F/0x30`).
- Routine 14: without `TRIGGER_3` and without `TRIGGER_4`, a 3-card pack (`rollCardPack`):
  rarity by `randomLimit(100)` → 0: 1 %, 1: 4 %, 2: 15 %, 3: 30 %, 4: 50 %, and a
  uniform card within the rarity (`rollCard` `script_menu.c:1340`). With `TRIGGER_4`,
  `openBuyCardMenu`: the day's 6 cards (`smth[0..5]`, `dailyPStatTrigger`
  `script_common.c:1355`: ids 1–64 without repeats, never 4, on day change in
  `clock.c:135/186`; a new game starts with 58–63, `main_menu.c:3868`), at `CARD_PRICES[rarity]` =
  5000/1500/500/100/50, at most 9 copies; the one bought becomes `0xFF`. With `TRIGGER_3`,
  selling at half price (`:1971`).
- Routine 1, `openMeritShop` (`script_menu.c:714`): exchanges cards for their merit
  (`MERIT` cap 9999, `:770-779`) and sells the items with `meritValue ≠ 0` (`:1405`):
  sup.recovery 20, Sup.restore 100, the six chips 800, Rainbowhorn/Waterbottle/Red
  Shell/Hard Scale/Ice crystal 500, Amazing rod 300.

### Item keeper, Mojyamon, Birdramon, jukebox

- Routine 11, `tickItemKeeper` (`script_menu.c:818`): bank of 128 counters
  (`smth[84+id]`, cap 99) against the inventory; left "Keeping", right "In hand";
  ✕ (`CONFIRM_BUTTON`, bit `0x40` in USA) moves 1, ○ (`ALT_BUTTON`, `0x20`) 10, □ (`0x80`)
  the whole stack (`keeperMoveOne/Ten/Stack` `:1987-2160`), respecting slots and the 99
  caps on both sides.
- Routine 2, `openMojyamonShop` (`:977`): three pages (`pstat 249`) of three trades
  `MOJYAMON_ITEMS_GIVE→GET`: Digimushrm→med.recovery, Supercarrot→Omnipotent,
  Happymushrm→Hair grower, Giant Meat→Auto Pilot, Black trout→Restore, Hispeed dsk→Medicine,
  Omnipotent→S.Off.disk, med.recovery→S.Def.disk, Digianchovy→S.speed.disk; each one
  once (triggers 5–13; all nine set 14, `:1727`).
- Routine 10, `tickBirdraTransport` (`:913`): 6 destinations `{map, exit, trigger, cost}`
  = (38, 1000), (70, 1000), (79, 1500), (93, 2000), (119, 2500), (105, 2500); only
  those whose trigger is set; charges `SHOP_VARIABLE` and jumps to section `0x4E3` of script 0.
- Routine 9, `openJukebox` (`:873`): 63 tracks; `0x3E` only with `TRIGGER_50`
  (game finished); the table `MAIN_D_801303B8` gives (bank, variant) for each track.
- Monochromon and the restaurant (maps 131 and 215 of `SHOP_MAPS`): the exe provides
  the mood bubble (`createMonochromonMoodBubble`, `pstat 0xF7/0xF8`, mood 0–4) and
  sub-ops `0x1e` (set `SHOP_VARIABLE` to 0), `0x1f` (add `pstat 0xF3:0xF4`) and `0x38`
  (dump it into those pstats) (`script_interp.c:1710-1718`); customers and income are in
  the map script. Patch 0279 adds a top-right plate during the screen-49 shop shift:
  `<profit> B  <customer>/20`, plus a blue bar full at 2560 B and a white tick at 1792 B.
  Patch 0280 lowers the recruit target and bar maximum from 3072 B to 2560 B.
  Routine `0x1e` on screen 49 explicitly arms its world object; leaving the screen removes it.
  The count reads p123 (capped at 20), including the extra step for a customer who storms off.
  Other uses of `SHOP_VARIABLE` do not arm it. Prices, odds and payouts stay in the scripts.

### Triangle menu and Digimon screens

- `addGameMenu` (`game_menu.c:1132`): options 1 Items, 2 Digimon, 3 Player,
  4 Praise (`partnerSetState(15)`), 5 Scold (`partnerSetState(4)`), 6 Sleep (only with
  `PARTNER_PARA.condition & 1`), 7 Fish (if `getFishingAvailability`, grey with no rod or
  no bait). Opening it stops the clock (`IS_IN_MENU`, `startGameTime` on close).
- Digimon › Status (`renderDigimonStatsView` `:2189`): name, species, age, weight,
  current and max HP/MP, ATK/DEF/SPD/BRN with bars (scale 9999 / 999), specialties
  and type (`DIGIMON_DATA`), sleep cycle (`RAISE_DATA.sleepCycle`), lives, status
  (`PARTNER_PARA.condition`), happiness and discipline bars (−100..100 / 0..100) and
  virus bar (`virusBar × 3 px`).
- Digimon › Techniques (`:2328`, `equipMove` `:2089`): 3 equipped slots
  (`EQUIPPED_MOVES`, stored as animation index `+0x2E` in `stats.base.moves`);
  8×7 techset grid (`moveId = col + row×8` with the rows reordered, skipping
  `0x30`); only learned moves (`hasMove`) that are among the species' 16 moves can be
  equipped; `0x2C↔0x30` and `0x37↔0x39` count as the same technique.

### Player menu

- Player (`renderPlayerInfoView` `:2551`): name, tamer level and title
  (`TAMER_LEVEL_TITLES`), Digimon raised (`raisedCount`), bits, play time, four
  key item icons (triggers `0x2D–0x30`) and number of medals (out of 18).
- Chart (`:1710-1838`, `renderEvoChartView` `:2902`): 61 boxes in 9 columns (our build lists every partner species instead, by level tabs and pages)
  (`EVO_CHART_BOXES`); the detail only opens for a raised Digimon (`hasDigimonRaised`
  = trigger `0x200+id`, `script_common.c:2934`).
- Medals (`:1840`): 15 in 5×3, `hasMedal` = trigger `0x16C+m`; names: Grade Cup,
  Version Cup, Type Cup, Special Cup, 100 Times, Technique Master, Digimon Master, Max
  Abilities, Perfect Curling, 100 Fish, (game finished), Town Flourishing, Card
  Complete, Bits Maxed, 10 Years.
- Cards (`:1869`, `renderCardsView` `:3253`): 6×11 slots, sprite if
  `getCardAmount > 0`; ✕ opens the card (`CARD.ALL`, TIM `id×14`) with its amount.

## Useful writes

Raw memory writes for setting up a state from a debugger or emulator ([../developing.md](../developing.md)); integers
little-endian. Do the inventory writes with the menu closed: sprites and amounts are re-read every frame, but the name
text is only drawn when the box opens (`drawInventoryText`, `game_menu.c:1967`). Triggers and `smth` live in
`SCRIPT_STATE` and are saved with the game.

| Goal | Write |
|---|---|
| put an item in slot *i* (0–29) | type at `0x8013D474 + i`, amount at `0x8013D492 + i`, name row (= *i*) at `0x8013D4B0 + i` |
| 30 inventory slots (scrolling box) | `size` at `0x8013D4CE` = 30 |
| bits / merit to the cap | `MONEY` `0x80134EB8` = 999 999 (u32); `MERIT` `0x80134FC4` = 9 999 (i16) |
| card collection | `SCRIPT_STATE.cards` from `0x801BDFAC`, one nibble per card (0–9); leave the sentinel cards 0 and 65 at 0 |
| item keeper | stored amount of item `id` at `0x801BDF2C + id` |
| everything for sale in a normal shop | triggers 0x180..0x1FF = 16 bytes from `0x801BDFFD` set to `0xFF`; on the shop map, before talking (the list is built when the shop opens) |
| the day's card shop | 6 card ids (1..64) at `0x801BDED8` |
| medals | triggers 0x16C..0x17A: byte 45 bits 4–7, byte 46, byte 47 bits 0–2 of `triggers`; OR them in, the same bytes hold other triggers |
| album (Digimon raised) | triggers `0x200 + id` from `0x801BE00D` |

## Notes

- A new game starts from `DEFAULT_INVENTORY_*` (30 slots, 50 000 bits, a kit that includes Giga Hand, Noble Mane and
  Metalbanana), yet the real game starts with 10 slots and few items: the intro script is expected to trim it with
  `0x23` (`SET_INVENTORY_SIZE`) and `0x29`. If only `size` changed, slots 10–29 would stay occupied and reappear when the
  inventory grows.
- `SHOP_REL.BIN` is loaded by `checkShopMap` on the shop maps even though the USA executable already contains its
  code.
- Which trigger each shop sets for `0x180+id` (and whether talking to the shopkeeper rewrites it) is in the map
  scripts.
- `Electo ring` points to species 0 (`EVOLUTION_ITEM_TARGET[12]`): depending on that entry's level it is refused or
  consumed with no effect.
- The training bonus flags of Supercarrot, Hawk radish and Digipine (`0x29`, `0x16`, `0x3F`) are read by the training
  code ([minigames.md](minigames.md#training-trn-and-trn2)).
- The jukebox table `MAIN_D_801303B8` gives (bank, variant) per track ([engine.md](engine.md#sound)); the 11
  shopkeeper species are in `SHOPKEEP_DIGIMON_TYPES`.
