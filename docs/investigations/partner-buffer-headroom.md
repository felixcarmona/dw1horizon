# Partner model buffer headroom

Measured from `integ5` (`41eb85c1`) and the supplied developer disc, 2026-11-16.
The working branch is `heap-96-check`, already at that commit. The sandbox makes
the parent repository's Git metadata read-only, so creating another branch failed.
No commits, pushes or PRs were made.

## Capacity and the original peak

Both **303 KingEtemon and 304 Divermon are 100,256 bytes**. This includes the MMD
header, mesh, animation offset table and **all** resident animation programs.
Playing a different slot does not allocate or append another resident program.

The linked array is `[0x80176b4c, 0x8018f34c)`: 100,352 usable bytes,
word aligned. Direct CD reads use that exact base; sector alignment applies to
the disc offset and read length, not to rounding the destination address upward.
`PARTNER_POSITION_DATA` starts immediately at the end. There is no trailing guard
subtracting from capacity. Both peak reads round to **49 sectors / 100,352 bytes**:
the original payload margin is **96 bytes**, but read margin is **zero**. Those
96 bytes are overwritten by the sector read. `loadMMD` and `loadMMDAsync` reject
oversized partners; with a sector-multiple capacity, any permitted size rounds
within the array. `applyMMD` copies the exact payload length.

There is one `PARTNER_MODEL` descriptor and one fixed array across field, menus,
care, training and battle. Loading another partner replaces its bytes. NPCs, even
the same species, use separate heap models; the tamer has a separate 57,344-byte
array. Cold slots share one separate 8,192-byte buffer: each new read waits for
a pending write, invalidates the prior clip key and replaces it. Non-partner
entities cannot start cold entries. Expanded RAM optionally caches the partner
cold bank at `0x80200000`, disjoint from the resident array and Chinese resources.
The maximum cold read across the archive is 8,192 bytes, including its initial
sector offset and terminal rounding. Textures upload through separate staging
space to VRAM; neither textures nor language text append to the MMD.

KingEtemon: header 8, mesh 35,128, table 252, resident programs 64,868 bytes.
Divermon: header 8, mesh 34,076, table 240, resident programs 65,932 bytes.

Resident slot alias groups (decimal; one program per bracket):

- KingEtemon: [0], [1,14,15,16,17,18], [2], [3,27], [4], [19,24], [33],
  [34], [35], [36], [37], [40,41], [42], [43], [44], [46], [47], [48], [49],
  [50], [51,61], [52,54], [53], [55], [56,57,58], [59], [60], [62].
- Divermon: [0], [1,14,15,16,17,18,34], [2], [3], [4], [19], [33], [35],
  [36], [37], [40], [41], [42], [43], [44], [46,47,49,50,52],
  [48,51,54,56,57,58], [53], [55], [59].
- KingEtemon's cold slots are 5,7,8,9,10,11,12,13,21,22,23,25;
Divermon also has cold slots 24 and 27. Aliases of resident
  programs stay resident, even when their slot is in the requested cold set.

The linked `.bss.PARTNER_MODEL_BUFFER` occupies `0x80176b4c..0x8018f34b`,
exactly 0x18800 (100,352) bytes. It is word aligned, as the CD destination needs;
there is no additional sector-address alignment adjustment, leading reservation
or trailing guard. `PARTNER_POSITION_DATA` starts immediately at `0x8018f34c`.
The 96 bytes are **payload padding**, not spare space after the transfer:
`ceil(100256/2048)*2048 = 100352`, leaving **zero CD-write headroom**.

Engine evidence: `model.c:readDigimonModel/loadMMD` reads whole sectors directly
into the fixed array; `loadMMDAsync` reads at a word-aligned evolution staging
address, and `applyMMD` copies exactly `modelSize` bytes. `isPartnerModelFit` and
all three load/apply checks compare size with `PARTNER_MMD_MAX`. Since that
capacity is a sector multiple, their size check also bounds rounded reads.
TMD mapping fixes pointers within the mesh; it does not append data.

## Sharing, states and languages

The array belongs exclusively to the current partner. Field, battle intro,
combat, training and menus reuse that same instance. NPCs, including another
instance of the same species, use their own model allocations from `malloc3`.
The tamer uses its separate 57,344-byte buffer. Partner textures upload to VRAM;
they do not occupy the MMD array. The header and all resident slot tables are
already counted above.

Cold clips use a separate 8,192-byte buffer at `0x8013a798`, shared serially by
this partner's clips. The loader finishes an outstanding write before replacing
it, and only the partner may request cold entries. Full-sector reads include the
clip's offset within the first sector; the archive audit checks this expression
for every cold entry. The maximum remains 8,192 bytes, with no overflow.
8 MB mode optionally caches the cold bank at `0x80200000` (64 KB); this does not
change resident MMD capacity. Loading/applying a model invalidates the caches.

Evolution temporarily keeps the old partner and the new model in separate
regions: texture at `0x80020000`, staged MMD at `0x80024800`. At the original peak,
the rounded staging read ends at `0x8003d000`, below the evolution overlay at
`0x80060000` and reincarnation shard scratch at `0x80044800`. Applying it replaces
the fixed partner array. This temporary copy costs load-area space, not heap or
additional partner-buffer space.

All nine native language link maps declare the same 100,352-byte partner buffer,
8,192-byte cold buffer and 187,296-byte heap. Models and their slot tables are
language independent. Screen changes do not grow the partner; the all-screen
archive-aware check passes **320 setups**, with screen 207 tightest at **3,488
bytes** remaining. This check includes the simultaneously resident NPC models. For separate-file
native replacements it conservatively retains their larger extracted-model costs;
the final archive bytes are used directly.
Simplified Chinese has an **existing 8 MB requirement** for its language module
and fonts above `0x80400000`; the other eight languages retain 2 MB support.
There is no new expanded-RAM dependency.

## Cheapest change

Lossless re-encoding and pool compaction recover nothing from the two peak
imports. Reserve a complete sector without taking bytes from the screen heap:
re-fit only their field/intro locomotion and aliases, plus Sorcermon's. The
existing encoder decodes every candidate and accepts it only when frame count,
loop, events and per-channel error meet the bound. Try tolerances independently
against the source; never accumulate approximation. Keep all mesh bytes exact.

The comprehensive audit also includes original species carried by archive
records, omitted by the older import-only `motionstorage.audit_archive`.
Three more of these exceed 48 sectors and receive the same final storage pass
(without cold splitting). WereGarurumon's change is lossless. Myotismon and
Cherrymon also re-fit resident combat programs, preserving all timing/events.
Their measured maximum channel bounds are 3 and 1; imported bounds are 3, 2 and 1.
Meteormon and Machinedramon are two more partners loaded from separate files:
Meteormon compacts losslessly; Machinedramon fits at tolerance 5. The other
68 separate-file partners already fit 48 sectors. Five angular units are
0.439453125 degrees; translation/scale channels use their
own native units. No faces, tables, techniques or effects are removed.

| Species | Before | After | Tolerance |
|---|---:|---:|---:|
| 303 KingEtemon | 100256 | 98062 | 3 |
| 304 Divermon | 100256 | 96468 | 2 |
| 242 Sorcermon | 98924 | 97900 | 1 |
| 62 WereGarurumon | 100100 | 94320 | 0 |
| 66 Myotismon | 99822 | 97758 | 3 |
| 121 Cherrymon | 99050 | 97788 | 1 |
| 113 Meteormon | 98552 | 97258 | 0 |
| 115 Machinedramon | 99988 | 97956 | 5 |

Across all **291 partners** (221 archive-backed and 70 separate-file),
the measured resulting peak is **333 Raijinmon: 98,266 bytes**.
Payload margin: **2,086 bytes**. Whole-sector read: **98,304 bytes**.
Actual spare capacity after the read: **2,048 bytes**. The fixed array, main
executable, heap and cold-buffer sizes do not grow. The build pass fails if a
reviewed oversized model cannot meet its bounded tolerance.

## Reproduction and artifacts

`build/heap-proof/` holds before/final budget JSON (including every slot group and
cold-read offset/length), nine-language link measurements, archive checks,
all-screen heap report, decoded-motion checks, emulator states and screenshots.
The private test image changes only DIGI.DAT data in a frozen disc snapshot;
ISO extents and engine file tables stay fixed and sector EDC/ECC is regenerated.
Full native recompilation is unnecessary: the executable is unchanged.

```
python3 tools/dev/memory/partner_budget.py DIGI.DAT budget.json
PARTNER_HEADROOM_FIXTURES=build/heap-proof python3 -m unittest tools.test_partner_headroom
python3 -m unittest tools.test_mesh_stability tools.test_motionstorage
python3 tools/dev/playtest/partner_buffer.py DISC.cue --exe EXE --out OUT --port PORT
# Repeat the last command with --ram8 and a separate port/output.
```

Runtime results are recorded separately in each emulator output's `result.json`.
The harness checks a 2,048-byte canary inside the reserved last sector, rounded
CD read lengths, actual scripted walking, every cold clip/replacement, a wild
battle and return, and the engine evolution state machine into/out of both
original peak species. Fixture writes select species, stats and evolution
targets; they do not replace the model loaders or the battle/evolution loops.

## Emulator result

PCSX-Redux interpreter, English, explicit 2 MB and 8 MB RAM settings:
KingEtemon and Divermon each completed a scripted field walk, a wild battle
including intro and return, every effective cold slot, cancellation/restart,
and `Agumon -> target -> Agumon` evolution through EVL's real loader/apply path.
The new peak, Raijinmon, also completed field/cold-slot/battle checks at 2 MB.
The last 2,048 bytes of the partner allocation were filled with `0xA5` and checked
at every boundary: **37 checks passed**. Instrumented direct reads were exactly
98,304 bytes. No checked corruption, game crash or stalled evolution occurred.

Evidence: `build/heap-proof/emulator-summary.json`, `proof2/`, `proof8/`,
`final8/` (KingEtemon's completed 8 MB sequence), and `raijinmon2/`.
The initial helper fixtures were corrected: a looping idle is verified by
playback/cancellation rather than waiting for the toilet state to finish;
shared-host care timeouts were extended; enemies receive enough fixture HP to
remain alive for the 600-refresh battle sample. These were harness assertions,
not buffer-canary failures. The earlier re-laid-out test image was replaced by
a frozen snapshot to preserve engine file-table extents.

The complete imported-model provider was re-run for all three changed imports;
its final outputs exactly match the emulator-tested files and updated pins.
Eight private real-model decoder regressions pass (all meshes exact; program
lengths/loops/events preserved and channel errors bounded). Existing model,
capacity and species tests pass, as does the actual host-C cold-loader oracle.
The runtime tests exercise the changed peak models; other recompressions and
all language layouts receive offline checks, not an exhaustive emulator tour.

The completed review image is `build/heap-proof/final.cue` / `final.bin`.
A direct readback of its archive and 70 separate model files confirms all 291
partners fit 48 sectors (`final-disc-budget.json`). Packaging preserves LBAs,
updates the two shortened native file sizes and regenerates EDC/ECC. The two
native lookup-table size changes do not overlap any language patch.
The final peak model bytes are the same ones exercised in the emulator.
Image SHA-256 and packaging checks are in `build/heap-proof/package.json`.
