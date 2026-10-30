# Japanese map normalization remainder

The 165 bytes left after source-copy refinement of the Japanese mappings do not
need to ship. This investigation covers both Japanese pressings: the three source
maps are identical between them. The release accepts Rev 1; this does not make the
first pressing an accepted base.

| Map | Residual bytes | Meaning | Resolution |
| --- | ---: | --- | --- |
| GIAS00 (Gear Savanna, screen 69) | 61 | Enemy HP/MP, current HP/MP, combat stats and fleeing coordinates | Keep the player's enemy list until content generation replaces it |
| FRZL03 (Freezeland, screen 90) | 32 | Enemy HP/MP and current HP/MP | Same |
| MAYO00 (Native Forest, screen 109) | 68 | Enemy stats and Bits rewards | Same |
| MAYO00 | 4 | Two hidden sprite sorting coordinates | Keep the player's values |

The literal runs sometimes cut across 16-bit fields. They must not be replaced
individually with arbitrary bytes from other fields or regions. The mapping
producer instead retains the complete Japanese enemy list and checks that
`content.build_map` generates the identical complete map from either enemy list.
The generator supplies all enemy fields, including fleeing coordinates and
current HP/MP. The story compiler starts with this generated list; maps outside
story output pass through the balance step. These source enemy differences are
therefore discarded before reaching the final disc.

The final values are live to the game, not unused padding. `loadMapDigimon` in
`decomp/src/main/overworld.c` reads them into the enemy stats and fleeing vector.
The three screens have the enemy-loading flag set. Restoring Japanese stats in
the final output would change combat; this implementation does not do that.

MAYO00's other two fields are sprite definitions 26 and 27, their Y words at file
offsets 199020 and 199038. Japan has Y=10000; USA has Y=6000.
`calcMapObjectOrder` treats 10000 as a sentinel selecting order 4094. The only
instances using these sprites are 28 and 29, both with flag 1 (hidden).
`renderMapOverlays` skips that flag. Native Forest script 105
(`story/base/zones/native-forest/s105-109/script.py`) only hides those instances
again at prosperity 25; it never shows them. MAPHEAD section 109 selects script
105. The shared day/night visibility rule targets screen 183, not 109, and the
training handlers target their training screens. No extended-story override
selects these sprites on screen 109. Thus their different calculated order does
not affect rendering in the current game. The mapping producer checks that each
sprite still has exactly its one hidden instance before retaining Japan's Y.
Future script changes that show these objects must reconsider the sorting values.

Keeping those unused Japanese fields intentionally changes four data bytes of
MAYO00 on the Japanese output, plus that sector's EDC/ECC. Every other file stays
identical. The normalization data is removed without changing runtime code, allocations,
models or gameplay. Original 2 MB hardware
requirements are unaffected.

## Verified map outputs

The reference uses the older fully normalized mappings. Sign localization from
the Japanese disc, followed by the content map generator, produces these final
file SHA-1s in both Python 3.10.22 without NumPy/Pillow and Pyodide:

| Map | Untouched reference | Candidate |
| --- | --- | --- |
| GIAS00 | `20a3a769ba73e46e3e46182227dcfa0c113e4bfc` | identical |
| FRZL03 | `eabfadbf23e4cb5aa85303bfc24309e41287aaf6` | identical |
| MAYO00 | `9be4682b36f215ce4560c207aff31df82d5dde33` | `472160a038e2a9ffd32b22c92ce06e43afdccfff` |

The complete 2,318-file/license inventory differs only in MAYO00, at the two Y
words above (four bytes). Streaming the independent reference image with its one
changed sector rebuilt by the production Form1 encoder gives:

- Reference: `06ddeb33dea3488b99f8c153740887bb2e07d24e`.
- Candidate: `28b9cccc3916b69e9266ff2bc992e7bddd2dc3d1` (900,526,704 bytes).

This is a fresh three-map producer proof and independent file/sector proof,
not a claim of a complete four-disc derive or final package publication gate.
Japanese derive inputs and release references must be regenerated with these
mappings. Reusing an older MAYO00 hole would conceal the intended four-byte
change. European title artwork is handled separately; USA output is unchanged.
