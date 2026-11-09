# Script 29 (readable)

Screens that load it: 28 Underground Pond.

| section | status | lines | instructions |
|---|---|---|---|
| sec254 | readable | 50 | 43 |
| sec52 | readable | 2 | 3 |
| sec51 | readable | 1 | 2 |
| L8 | readable | 115 | 120 |
| sec81 | readable | 7 | 8 |
| sec5 | readable | 1 | 2 |

The dirt pile is loaded while `underground_pond_dig_work < 10`: ten is
excavation completion, whereas eight only opens the tunnel entrance. Hiding
the pile at eight left the fifth pickup's use trigger on empty ground after a
return visit or Continue. The collision patch `clear-dirt-pile-collision.patch`
makes the pile footprint walkable at the renderer's cutoff while preserving
use trigger 81; it does not decide whether the model is loaded.

The renderer's size counter is transient, initialized to 15. Completed saves
omit the model so a cold load cannot restore the rubble (the earlier reappearing
rubble report). Unfinished saves, including older odd work counters, keep their
pickup. No saved fields or `save.lock` allocations change. The five-day wait
still clears the pile during entry. Both EXTENDED STORY choices compile this
base handler; there is no mod override for script 29.
