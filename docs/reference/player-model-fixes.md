# Player model reports

## Gallantmon: helmet eyes

The full-resolution eye repair is already included in v0.0.6. The final provider
uses the repaired model and texture directly, without a field overlay. Its eight
helmet faces sample a dedicated 56 by 32 texture rectangle beginning at (125, 0).
The source palette, model size and animation programs are preserved by
`tools/models/repair_gallantmon.py`.

A culled front, three-quarter and side render of the current pinned model shows
both yellow eyes. The model and texture pins must be checked together:

```sh
python3 tools/models/edit.py --from build/model-fixes-wolf check 318 --species-pins
```

The repair was introduced by commit `2068525a`; this report does not require a
second texture alteration.
