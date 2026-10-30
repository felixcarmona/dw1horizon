# Record-original deltas

`models.json` pins all 37 outputs (33 MMD, four TIM), their player-disc sources,
and plain MD3 patches by SHA-256. The 29 native models use their DW1 MMD and
the original DW1 animation donor's MMD as copy sources. Decoding them uses only
the standard library. No game model or texture is a committed build input.

Four records have cross-game meshes: WereGarurumon (62) and Brachiomon (126)
come from Card Battle; Hagurumon (122) and Tinmon (123) come from World 2.
A DW1-only delta for those would contain imported game data. `imports.json`
freezes their additional batch entries, final spec SHA-256s and two size
operations. `tools/recordimports.py` reuses derive's importers against the
same player-supplied discs as the other 175 imports. It does not change their
recipes or deltas. Seven of the eight cross-game patches contain no ADD bytes;
Hagurumon's model retains its later edits as a delta.

`tools/derive/steps/record_originals.py` generates OUT/record-originals before
the species step, for the selected records only. Base discs that carry none
do not need the extra source games. The provider checks the existing SHA-1 pins and routes selected
records there before making DIGI.DAT. Slot aliases stay in each species record
and are applied as before. There is no fallback to a private batch binary, and
the everything recipe has no private model input folders.

```sh
python3 tools/models/edit.py get 67
python3 tools/models/edit.py put 67 build/imported-model-edit/edit/67-Yanmamon.MMD
python3 tools/models/edit.py --from build/everything --originals check --species-pins
python3 tools/audit_recordoriginals.py --from build/everything --out /tmp/record-original-audit.json
```

The cross-game records use `--from`, `--games` or `--source-disc` exactly like
imported imports. Native records only read extracted/. `put` keeps unchanged deltas,
encodes edits in plain mode, and updates both the SHA-256 manifest and the
record-original provider's SHA-1 pins.

The literal audit examines each ADD run separately against extracted CHDAT,
with a 16-byte matching floor, and separately checks the exact delta sources.
It reports overlap lengths and byte diversity: single-byte coincidences do not
establish provenance. The recorded audit has zero literal matches of 16 bytes
or longer against either the exact sources or all 179 CHDAT files. Pure copy
patches have zero ADD bytes.

`verification.json` records the 37-file oracle comparison, native strict derive,
actual Pyodide replay, and the larger 882-file corpus audit (DW1 CHDAT plus the
three source-game extractions). That larger audit has zero matches against the
pinned sources, zero against DW1 CHDAT, and only Hagurumon's edit has short
matches elsewhere: at most 25 bytes in an unrelated Card Battle packed file,
with eight distinct byte values. This bounds exact overlap; it is not an
assertion about the authorship of arbitrary short numerical sequences.
Neither verification report is rewritten by a later animation edit.

Native everything and USA + JP Rev 1 `make-release` were compared with an
untouched-main `a218f425` snapshot: all 2,318 disc-file SHA-1s and both release
output SHA-1s match. The release bundle contains the 37 deltas and no private
model/texture binaries or model build folders. `verification.json` records the
image, per-file-list and release output hashes. Both release proofs use four
independent workers with shared map passes serialized.
