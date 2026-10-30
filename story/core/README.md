# core/

The standard library. Scripts should read like intent, not instructions, so the idioms live here.

| file | what |
|---|---|
| `engine.dws` | names for the engine's own triggers and pstats (`engine.arg` is p254, `engine.result` is p255, `engine.cutscene` is trigger 44...) |
| `scene.dws` | scene helpers: `fade_to_white(frames)`, `fade_from_white(frames)`, `walk_away(who, x, z, looks)` |
| `recruit.dws` | `recruit(species)`, `is_recruited(species)`: the `200+type` flags the C code reads; `join_city(...)`, `join_city_camera(...)`: the end of a departure to the city |
