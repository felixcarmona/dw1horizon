# Disliked-habitat mood blink

The original field HUD's `renderStatusBars` chooses texture U 64 for happiness
>= 0 and 97 below zero. For `PLAYTIME_FRAMES % 10 < 5`, a disliked map
(`MAP_TILE_DATA.partnerAreaResponse == 2`) adds 11: the blue sad expression
at U 75 or the worse angry expression at U 108. The other five ticks show the
normal expression. These are play ticks, independent of the game clock.

This rule survives in v0.0.6. Commit `20988072` introduced the B5a care HUD
(`Render-the-B5a-field-care-HUD-from-live-partner-data.patch`), whose mood
selection reads only the happiness sign. The old renderer retained habitat
handling when the new HUD was disabled. Commit `3085c184`
(`Make-the-care-HUD-and-status-panels-permanent.patch`), shipped in v0.0.7,
removed that remaining renderer, making the lost blink unavoidable.

`Restore-the-native-disliked-habitat-mood-blink.patch` restores exactly the
original disliked-map phase. `tools/field_hud_art.py` encodes normal/worse
colour pairs in the two existing mood tiles. Two previously empty CLUT rows,
(272,511) and (256,511), select the native expressions. Occupied cells fail
closed. Gauge fills, housing, neutral/liked-map rendering, needs and gameplay
rules stay unchanged. No tile, upload allocation or GPU draw packet is added.

The SDK's inline `getClut`, shared five-tick quotient and reuse of the normal
warning palette keep the renderer's linked size at 964 bytes. Main BSS end and
aligned heap are unchanged in matched before/after builds: `0x801CE9A0`,
185680 B, in the prepared current series; `0x801CEA90`, 185440 B, in the
existing multilingual runtime fixture. The runtime archive check passes all
255 setups in that fixture; screen 207 retains 720 B. This is not a fresh
all-language release build.

## Verification

- `python3 tools/dev/playtest/field_hud_host.py build/decomp-int`: existing
  589828 exhaustive value/flag/baseline cases, every 16-bit counter value for
  need-warning timing, and every counter value × three habitat responses ×
  both happiness signs. The unmodified renderer fails the habitat assertion.
- `python3 -m unittest tools.test_field_hud_art tools.test_care_badge tools.test_care_bubble_art`:
  15 tests, including native face pixels in both phases and unchanged housing.
- `python3 -m unittest tools.test_patcher_tabledata`: 24 tests.
- `python3 tools/patch_series.py check --apply`: the full series applies.
- `tools/selftest.sh`: 137 passed, 2 failed, 6 skipped. The local prepared
  executable has unsynchronized balance tables; the portrait suite also lacks
  `cv2`. These failures were not repaired as part of this HUD fix.

The emulator capture boots a locally reassembled multilingual fixture with
PCSX-Redux in original 2 MB mode. The field code change is confined to the renderer; its English mood atlas is
regenerated and the version label changes. The existing language bank remains
matched to its executable. Agumon (species 3) has region 0 both in its species JSON and
live `RAISE_DATA`. Screen 92, Freezeland, naturally sets response 2; the test
never writes the habitat response. Care values and partner placement are test
fixtures. The game clock is paused; the original play counter continues.

```sh
python3 tools/dev/playtest/habitat_mood.py build/habitat-fixed.cue \
  --exe build/proof-exe/SLUS_010.32 --out build/habitat-visible
```

The 75 consecutive refresh captures show sad/happy/sad/happy/sad/happy.
Each complete expression lasts 15 refreshes, exactly five logic ticks at
20 Hz. `result.json` records the species, actual habitat response, play counter
and independently observed face colours. Presented frames lag RAM at phase
crossings because of GPU buffering. The PNGs, MP4 and player-disc artifacts
remain under ignored `build/`. Original hardware and a fresh full multilingual
release build were not tested.
