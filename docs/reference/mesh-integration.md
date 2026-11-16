# Final mesh integration

The existing `hard-kyubimon` commit is preserved. The working tree adds
`hard-megagargomon`, `hard-malomyotismon`, `hard-omnimon`, `hard-raidenmon`
and `heap-96-check` from their `integ5` bases. Each cleanup hook remains active;
partner recompression runs after geometry and pose repairs.

The repository tools regenerated all 25 cleanup input hashes (unchanged),
183 import pins and 38 record-original pins. All 221 provider pins verify;
fresh source/delta/provider checks pass for the eight changed imports.
Alternate-release pins remain unchanged.

Validation runs passed: 177 related tests (31 optional fixture skips before
final fixtures were prepared), 96 supporting tests (one optional skip),
54 packaging/technique-summary tests, 100 related tests after the QA fix
(seven optional skips), all 32 final-model tests without skips, and the
headroom regression across eight freshly recompressed real models.
The QA fix retains a reference motion probe when cleanup removes an invisible
piece but keeps its bone; a synthetic regression covers the previous crash.

The final archive plus standalone models measures all 291 partners.
Raijinmon peaks at **98,266 B** resident, **98,304 B / 48 sectors** read,
leaving **2,086 B payload margin** and **2,048 B real read margin** within
100,352 B. Cold reads fit 8,192 B. The nine existing language linker maps
all leave **187,296 B** heap; these changes add no executable allocation.
The reviewed MAPHEAD's 255 setup sections fit the final archive, with a
minimum measured margin of 3,488 B on screen 207.

Both timeout models reproduce their reported final geometry and detector
metrics exactly. All 94 reported MaloMyotismon pair depths and all 80 reported
Omnimon pair depths match their sibling RESULT reports to the reported
precision. MaloMyotismon retains 78 crossings, maximum 58.602 units, at
74,500 B resident. Omnimon retains 41, maximum 70.841 units, at 81,502 B.
Their eight battle QA slots are accepted; this does not certify complete
visual clearance or unrestricted residual floors.

Known diagnostic failures remain explicit: the native mesh envelope flags
MaloMyotismon's bent risk and Kyubimon's crossing count. Field QA covers
183 imports and retains 53 review candidates. Battle QA accepts 17 of the
20 checked slots; Kyubimon slots 34, 35 and 36 flag reduced tail motion.
Kyubimon's provider hash is identical to the pre-integration HEAD pin, so
these three flags are inherited from the existing repair. Reviewed rotation
repairs use battle QA's explicit `polished` option; Kyubimon uses its native
pre-repair rig as the baseline because its imported source has another rig.
No integration test failures remain.

Removed 76 JSON/CSV evidence dumps over 100 KB, including compressed dumps.
Reports now name their regeneration tools and keep outputs under `build/`.
The technique CSV is a 33,843-byte operational summary preserving every
patcher and regression input; its 54 consumer tests pass. Native detector
calibration survives in `mesh-glitch-thresholds.json`, and the review tools
use that small input. No JSON/CSV evidence file under `docs/` exceeds 100 KB.

Private validation artifacts and logs are under `build/`. Changes remain
uncommitted; nothing was pushed.
