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

The dirt pile is loaded only while `underground_pond_dig_work < 8`, the same
saved condition that blocks the tunnel entrance. The original renderer keeps
its size in a transient counter initialized to 15, so a cold load could restore
the full pile after excavation. Return visits to an open tunnel now omit the
pile model, including saves made before this fix. The five-day completion path
still clears the pile during entry.
