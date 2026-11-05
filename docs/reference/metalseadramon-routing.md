# MetalSeadramon family routing

MetalSeadramon remains a Data Mega with Ice/Mech specialties, its Water/Machine
techniques and Mail Strome finisher. Its battle voice bank 55 and care voice bank
5 already match MegaSeadramon. WaruSeadramon shares the care bank and uses the same
family effects donor.

The frozen raw import used Birdramon as its animation controller, despite the
model and custom attack performances coming from Card Battle MetalSeadramon.
This left bird-flap instructions in transitions and several attacks. The model
delta now takes sound events from native MegaSeadramon: matching techniques use
their native event tracks, and Machine attacks use its ranged attack cry. Event
timing scales to each imported performance. Care and condition clips use the
corresponding native slot. Bird-only transition cues are removed. Mesh, poses,
texture events, animation durations and field movement remain unchanged.

The effects donor is now MegaSeadramon (61). Its two head-origin rows are remapped
to MetalSeadramon's head bone 6, and its carrier row to bone 1. The explicit head
fallback covers Machine techniques without a family origin row. Old Birdramon
origin mappings are removed.

The original import spec remains a pinned reproducibility input; the correction
is an authored delta after that import. To reproduce the audio edit from the
preceding model (SHA-256
`3230a3c7a4ae156b6dfe58880dd0cf3db7e310ae37ae3670b53d702de5e4ad8f`):

```sh
PYTHONPATH=tools python3 -m tools.models.field_animations.sea_serpent_audio BEFORE.MMD AFTER.MMD
```

The helper checks that only sound instructions change and that the original
resident/cold animation budgets still fit. Store with
`tools/models/edit.py put 211 AFTER.MMD` and update the steady-glide source pin.
The final provider pins include that glide. Battle validation must exercise
ordinary techniques and Mail Strome, with damage and a return to the field.
