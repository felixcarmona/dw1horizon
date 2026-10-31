# Sound formats and authoring tools

`tools/sound.py` inspects and edits SEQ music and VAB sample banks from the
player's disc. This page describes the original USA formats and limits; source
locations refer to the unmodified decompilation unless stated. The integrated
mod uses indexed banks and dynamic SPU allocation, described below.

For a shipped change, keep our MIDI/WAV and generator inputs as source and build
through [derive](../derive.md). Exported original audio belongs under ignored
`build/`. Do not commit a rebuilt bank or a sample from the player's game.

## 1. The files

| File | Size | Chunks | Layout | RAM header buffer | Bank (SPU slot) | Who loads it |
|---|---|---|---|---|---|---|
| `SS.VHB` | 0xDF5C | 1 | single chunk, not padded | `VHB_HEADER_SS` 0x1000 | 0 (`0x01010`) | boot (`initializeMusic`) |
| `SL.VHB` | 0xD90C | 1 | single chunk | `VHB_HEADER_SL` 0x1000 | 1 (`0x0E800`) | boot |
| `FAALL.VHB` | 0x283800 | 33 | stride **39 sectors** (0x13800) | `VHB_HEADER_FAALL` 0x2000 | 2 (`0x1B800`) | `loadMusicFont(font)`: sector `(font−1)·39` |
| `VLALL.VHB` | 0x78000 | 16 | stride **15 sectors** (0x7800) | `VHB_HEADER_VLALL` 0x1000 | 3 (`0x2A000`) | `loadPartnerSounds`, `loadVLALL`: sector `DIGIMON_VLALL_SOUND_ID[type]·15` |
| `VBALL.VHB` | 0xF8800 | 71 | stride **7 sectors** (0x3800) | `VHB_HEADER_VBALL_0..3` 0x1000 each | 4–7 (`0x31800`, `0x34000`, `0x36800`, `0x39000`) | `loadDigimonSounds`, `readVBALLSection`: sector `DIGIMON_VBALL_SOUND_ID[type]·7` |
| `ESALL.VHB` | 0x387000 | 22 | each chunk at the next sector | `VHB_HEADER_ESALL_SB` 0x1800 | 8 (`0x3B800`) | `loadMapSounds(id)`: `MAP_SOUND_PARA[id]` |
| `SB.VHB` | 0x3CACC | 1 | single chunk | same as ESALL | 8 | battles (`loadSB`, `VSLoadSounds`) |

Strides and table entries are in sectors of 2048 bytes. The padding between
chunks is zeros. The files are read through `FILE_OFFSET_TABLE` (sector and
size in the executable), so a file that changes size moves every file after it:
same size → `build-disc.py --file`, any other size → `--relayout` (mod
executable).

### 1.1 Chunk

```
chunk + 0x00  u32 vhOffset   0x0C (0x10 in FAALL)          VhbFileHeader, include/dw/sound.h
        0x04  u32 vbOffset   end of the VAB header = start of the body
        0x08  u32 end        end of the body          (FAALL: u32 seqOffset = end of the body)
       (0x0C  u32 end        FAALL only: end of the SEQ block)
vhOffset      VAB header (VH): 0xA20 + 0x200·ps bytes
vbOffset      VAB body (VB): the ADPCM samples, back to back
seqOffset     SEQ block (FAALL)
```

`readVHBFile`/`readVHBFileSectors` (`sound.c:379-466`) and their asynchronous
twins (`sound_async.c:128-196`) read the chunk into `GENERAL_BUFFER`
(0x80010000), `memcpy` the VH (`vbOffset − vhOffset` bytes, **unchecked**) to
the bank's header buffer, `SsVabOpenHeadSticky(header, bank,
VHB_SOUNDBUFFER_START[bank])` and `SsVabTransBody` the body to that SPU
address. `loadMusicFont` (`732-745`) also copies the SEQ block
(`u32[2]..u32[3]`, **unchecked**) to `SEQ_BUFFER` (0x5800 bytes).

### 1.2 VAB header (standard Psy-Q)

Offsets from the start of the VH (add 0x0C, or 0x10 in FAALL, for the chunk):

| Offset | Size | Field |
|---|---|---|
| 0x000 | 0x20 | `VabHdr`: `char form[4]` = `pBAV`, `u32 ver` = 7, `u32 id` = 0, `u32 fsize` (VH + VB), `u16 res0` = 0xEEEE, `u16 ps` (programs), `u16 ts` (tones), `u16 vs` (samples), `u8 mvol` = 127, `u8 pan` = 64, `u8 attr1, attr2`, `u32 res1` = 0xFFFFFFFF |
| 0x020 | 128 × 0x10 | `ProgAtr`: `u8 tones, mvol, prior, mode, mpan, res0; u16 attr; u32 res1, res2` |
| 0x820 | ps × 16 × 0x20 | `VagAtr` (tones), 16 per program: `u8 prior, mode, vol, pan, center, shift, min, max, vibW, vibT, porW, porT, pbmin, pbmax, res1, res2; u16 adsr1, adsr2; i16 prog, vag; i16 res[4]` |
| 0x820 + 0x200·ps | 256 × u16 | sample sizes in units of 8 bytes; entry 0 unused, entries 1..vs used |

Every bank in the game has programs 0..ps−1 contiguous, which is what
`startSound` (`tones + prog·16`) assumes. A tone answers keys `min..max`;
the sample plays at 44.1 kHz at key **`center − shift/128`**: libsnd's
`SsPitchFromNote` computes `note − (center − 60)` plus `(fine + shift) >> 3`
sixteenths of a semitone (its pitch table has 16 steps per semitone), so a
positive `shift` *raises* the pitch and only multiples of 8 matter. A negative
`shift` indexes before the pitch table when `note − center + 60` is a multiple
of 12, so `sound.py` writes `shift` in 0..120. `adsr1/adsr2` are the SPU
envelope registers; `vag` is
the sample number (1-based). One quirk: 13 VBALL chunks (16–24, 26, 45, 57,
62) declare `vs = 4` with size 0 for sample 4 and a stray size at entry 20; the
data are in the body after sample 3, so sample 4 (address = sum of the earlier
sizes) plays them. `sound.py` keeps that as is.

### 1.3 Samples (SPU ADPCM)

16-byte blocks of 28 samples: byte 0 = filter·16 + shift, byte 1 = flags,
14 bytes of 4-bit nibbles (low first); filters (0,0) (60,0) (115,−52) (98,−55)
(122,−60) / 64. Every sample of the game has the same shape: a block of zeros
(flags 0), then data; **one-shots**: first data block flags 4, last data block
flags 1, then a silent block `00 07 77 77…`; **loops**: first block flags 2,
loop start 6, last block 3.

### 1.4 SEQ block and SEQ format (FAALL)

The SEQ block of a font is `u32 offset[n]` (n = `offset[0] / 4`, the number
of tracks) followed by n SEQs, each padded to 4 bytes with **0xCD** (the
filler of the original tools). One SEQ:

```
0x00  "pQES"
0x04  u32 version      BE, 1
0x08  u16 resolution   BE, ticks per quarter (480 in all 74)
0x0A  u24 tempo        BE, µs per quarter (initial)
0x0D  u8 u8 rhythm     01 04 in all 74
0x0F  events: VLQ delta, status, data; running status
```

It is a MIDI track with three differences: meta events have **no length
byte** (`FF 51 t t t` tempo, `FF 2F 00` end); note-off is a note-on with
velocity 0 (no `8x` in the game); loop points are NRPN controllers: `CC99 = 20`
loop start (followed by `CC6` = count, 127 = forever) and `CC99 = 30` loop
end. The 74 sequences use only `9x`, `Bx` (CC 6, 7, 10, 99), `Cx`, `Ex`, two
tempo changes, running status always (reset after a meta), shortest VLQs.
`seqOpen` (`sound.c:469-480`) opens track `CURRENT_SEQ_TRACK` (0 if it is
≥ n) with `SsSeqOpen(buf + offset[track], 2)`; `seqPlay` sets volume 0x50 and
plays forever, except fonts 0x1D (track ≠ 1) and 0x1E–0x20 (track ≠ 2), which
play once (`SsSetTableSize(SEQ_TABLE, 1, 1)`: one sequence at a time).

## 2. Music: from a BGM id to the SPU

1. A screen's section in `MAPHEAD.SCN` runs `1E SET_PSTAT p245 mode` and
   `5D SET_BGM font` (`script_interp.c:1492`; `sound.py list FAALL` shows the
   screens of each font, e.g. 54 screens use 0x1C File City).
2. `playBGM(font)` (`script_interp.c:2508-2523`; 0xFF = stop) →
   `handleMusicOverride` (`1508-1560`) by `PSTAT_245`: mode 0 → track 0 from
   6:00 to 20:59, 1 at night; 1 → track 0; 2..10 → fixed (font, track)
   pairs (6,2) (0xB,2) (0xF,2) (0x15,0) (0x15,1) (0x1A,0) (0x1A,1) (0x1B,0)
   (0x1B,1). `updateBGM` re-runs it so the day/night switch is live.
   Patch 0278 keeps an already open, infinitely looping sequence when the
   resolved font and variant match `CURRENT_SEQ_FONT/TRACK`; it still updates
   `ACTIVE_BGM_FONT/TRACK`. One-shot fonts 0x1D–0x20 retain their replay behavior,
   including after the sequence ends. A closed sequence always restarts.
   At normal entry's first `0xFB`, `modHeaderKeepsMusic` peeks at a plain
   optional `1E 00 F5 mode` followed by `SET_BGM`. It resolves the override,
   restores `PSTAT_245`, and stops before `loadMap` when font or variant differs.
   An immediate `FE` or font 0xFF also stops before loading. Headers that branch
   first stay deferred until their executed `SET_BGM`; absent a request, entry
   finishes by stopping. `STOP_BGM` and explicit script `0xFB` still reset.
   `updateBGM`, `forceUpdateBGM`, the jukebox, and asynchronous battle music
   retain their existing paths.
3. `playMusic(font, track)` (`sound.c:747-771`): rejects font ≤ 0 or > 0x21;
   if the font changed, `loadMusicFont` reads **39 sectors at
   `(font−1)·39`** of `FAALL.VHB` into `GENERAL_BUFFER`, uploads the VAB to
   bank 2 (SPU 0x1B800) and copies the SEQ block to `SEQ_BUFFER`; then
   `seqOpen` + `seqPlay`. State: `CURRENT_SEQ_FONT` 0x80134D96,
   `CURRENT_SEQ_TRACK` 0x80134D98, `SEQ_ACCESS_NUM` 0x80134D94.
4. Battles (`btl.c:349-365`) play font 0x21: track 3 against Machinedramon
   (0x73), 0 in scripted battles, otherwise
   `ENEMY_MUSIC_MAPPING[type − 0x43]` (48 bytes at 0x8012BAE4, values 0–2) for types 0x43..0x6F and 1 for the rest. Arena/tournament overlays use
   fonts 0x1D–0x20.
5. The jukebox (`script_menu.c:1572`) lists 63 (font, track) pairs from
   `MAIN_D_801303B8` with names from `BGM_TRACK_NAMES`; `sound.py list` prints
   them per font.

`python3 tools/dev/playtest/music_continuity_host.py build/decomp-dev` checks
`playBGM` against the actual `seqPlay` loop policy, plus normal map entry,
explicit resets and day/night updates. Room crossings still need an emulator
trace: the sequence must advance through `loadMap` without `SsSeqPlay`.

## 3. Sound effects

`playSound(bank, val)` (`sound.c:635-642`): banks 0, 1, 8 → program
`val / 16`, key `60 + val % 16`; banks 3–7 → program 0, key `val`.
`startSound` (`596-621`) keys **every** tone of that program whose `max`
equals the key (layered sounds) on a free voice 10–23 (`getNextFreeChannel`,
round robin over 14; the SEQ player takes its voices from libsnd's pool) at
full volume. So an effect id is `program·16 + (max − 60)` and each program
holds up to 16 ids. Callers: the script opcode `5A PLAY_SOUND bank, id`, C code
(menus: `(0,0)/(0,1)` open/close box, `(0,3)` confirm, `(0,4)` cancel,
`(0,12)` feed...), and model animations (`anim.c:335-346`, instruction 0x4000:
bank in the high byte, 4 = the entity's own `vabId`, only when on screen).

- **Bank 0 `SS`, bank 1 `SL`**: loaded once at boot (`initializeMusic`,
  `sound.c:511-544`, which also sets the STUDIO_B reverb on all 24 voices).
- **Bank 8, map effects**: `loadMapSounds(MAP_ENTRIES[screen].flags & 0x1F)`
  (`map.c:4212`, also `partner.c:765/797` and `loadMapSounds2(19)` at
  `partner.c:644`) reads `ESALL.VHB` from sector `MAP_SOUND_PARA[id].sectorId / 2`
  for `sectorCount / 2` sectors (the table counts half-sectors; 22 entries at
  0x80127FF4). `sound.py list ESALL` prints each region with its screens.
- **Bank 8 in battle**: `SB.VHB` replaces the region (`loadSB`), and the
  region is reloaded after the battle (`ACTIVE_MAP_SOUND_ID = −1`).

## 4. Voices

- **VBALL** (7-sector chunks, banks 4–7): `DIGIMON_VBALL_SOUND_ID[180]`
  (0x80127F40) maps every Digimon type to a chunk 0..0x46 (71 chunks; chunk 0
  is a 12-tone generic voice for the tamer, NPCs and WereGarurumon; most
  Digimon have 3 tones on keys 53–55). Bank 4 = partner
  (`loadPartnerSounds`, `partner_impl.c:436`), 5–7 = up to three enemies in
  battle (`btl.c:400-401`), 5 = opponent in the arena (`std_main.c:1681`),
  4/5 in VS mode. The entity's `stats.current.vabId` says which bank its
  animations play.
- **VLALL** (15-sector chunks, bank 3): the partner's long voice,
  `DIGIMON_VLALL_SOUND_ID[66]` (0x80127EFC, partners only; type ≥ 66 or 0 →
  chunk 15), loaded with the partner and on evolution (`evl.c:101`) and
  rebirth (`dooa.c:1029`).

## 5. SPU RAM (512 KB)

| Range | Size | Use | Largest original body | Free in the worst case |
|---|---|---|---|---|
| `0x00000–0x0100F` | 4 KB | SPU capture buffers, libspu silence | — | — |
| `0x01010–0x0E7FF` | 0xD7F0 | bank 0 `SS` | 0xD130 | 1.7 KB |
| `0x0E800–0x1B7FF` | 0xD000 | bank 1 `SL` | 0xCAE0 | 1.3 KB |
| `0x1B800–0x29FFF` | 0xE800 | bank 2 music font | 0xC850 (font 3) | 7.9 KB |
| `0x2A000–0x317FF` | 0x7800 | bank 3 `VLALL` | 0x6850 | 3.9 KB |
| `0x31800–0x3B7FF` | 4 × 0x2800 | banks 4–7 `VBALL` | 0x2700 | 0.25 KB |
| `0x3B800–0x7B7BF` | 0x3FFC0 | bank 8 `ESALL`/`SB` | 0x3CE20 (region 4) | 12.5 KB |
| `0x7B7C0–0x7FFFF` | 0x4840 | STUDIO_B reverb work area | — | — |

libsnd does not check a body against the next bank's address
(`SsVabOpenHeadSticky`): an oversized body silently overwrites the next bank.
Measured per screen in `docs/data/memory-budget.csv`.

## 6. `tools/sound.py`

```bash
tools/sound.py list [FAALL ...]                 # every chunk: programs, samples, body vs slot, tracks, users
tools/sound.py info FAALL 27                    # font 0x1C: every program/tone (key range, root, ADSR), sample, track
tools/sound.py export FAALL 27 -o build/snd     # FAALL_27_s01..09.wav, FAALL_27_t0_File-City.mid, FAALL_27.json
tools/sound.py export VBALL 3 -o build/snd      # Agumon's voice (sound ids 53-55)
tools/sound.py render 0x1c 0 -o build/fc.wav --secs 30     # listen to a track offline (approximate SPU)
tools/sound.py import-midi 0x1c 0 song.mid -o build/x.FAALL.VHB [--loop] [--prog-map 0=6,1=2]
tools/sound.py import-wav FAALL 27 lead.wav --vag 7 -o build/x.FAALL.VHB [--root A4] [--rate 22050] [--loop 1000:5000]
tools/sound.py import-wav ESALL 10 boom.wav --program 1 --keys 60 -o build/x.ESALL.VHB   # new effect, id 16
tools/sound.py check build/x.FAALL.VHB          # every limit of § 7
tools/sound.py index FAALL -o build/x.FAALL.VHB # indexed layout for the integrated executable (§ 8)
tools/sound.py add-font song.mid --instruments 0x1c -o build/x.FAALL.VHB [--vhb IN] [--loop]   # new font 34+ (§ 8)
tools/sound.py set-bgm 218 0x22 -o build/x.MAPHEAD.SCN   # a screen plays a font
tools/sound.py spu-budget [--vhb-dir DIR]       # SPU allocation per screen with the integrated executable (§ 8)
tools/sound.py roundtrip                        # selftest
```

FILE is a path (its name must contain the kind: `FAALL.VHB`, `x.FAALL.VHB`,
`FAALL-mod.VHB`) or a bare kind for the original in `extracted/`.

- **WAV export**: mono 16-bit at 44.1 kHz, which is the sample's pitch at the
  tone's `center` key; a `smpl` chunk carries the root key, the fine tune and
  the loop. The leading silent block is dropped (import adds it back), so
  exporting and importing an unchanged sample gives the same bytes (4 of 9
  File City samples; the others differ in a few blocks at ≥ 108 dB SNR).
  The root written to `smpl` is the tone's `center − shift/128` (unity note
  plus pitch fraction).
- **WAV import**: any PCM WAV (8/16/24/32-bit, float, mono or stereo mixed
  down); `--rate` resamples (smaller samples, lower quality; better generate
  the WAV at the rate you want); the root (the key at which the WAV plays at
  its own pitch) comes from `--root` or the `smpl` chunk and becomes
  `center − shift/128 = root − 12·log2(rate/44100)` (`center` rounded up,
  `shift` 0..120 in steps of 8) on the first tone that uses the sample; the
  other tones that share it keep their pitch relative to that one (`SS`
  plays sample 1 at seven pitches for ids 0, 1, 5, 6, 7, 19, 20). Without
  either, a **single-key tone** (every effect and voice: `min = max`) gets its
  own key as the root, so `playSound` plays the WAV unchanged (effect id 3 is
  key 63, Agumon's voice id 55 is key 55); other tones get C4 = 60. The loop
  comes from `--loop` or `smpl`. `--vag N` replaces sample N;
  `--program P [--keys LO-HI]` appends a sample as a new tone of program P (or a
  new program P = ps), with key range = root by default, and prints the effect
  id it gets. The importer refuses anything that breaks § 7.
- **MIDI → SEQ**: format 0 or 1, tracks merged in time order; note-off becomes
  velocity 0; aftertouch, sysex and other metas are dropped; the first tempo
  at tick 0 goes to the header; `--loop` adds the loop markers around the
  notes (start at the first note, end at the last event); `--prog-map`
  renumbers program changes. Programs refer to the **font's own programs**
  (`info` lists them with key ranges): the importer warns about programs the
  font does not have and about more than 14 simultaneous notes. A MIDI made by
  `export` comes back byte for byte.
- **render**: a pure-Python approximation of the SPU (pitch from
  center/shift and pitch bend range, the ADSR registers stepped as the SPU
  does, loops, volumes and pans; no reverb, no voice limit) at 22.05 kHz.
  Levels and timbre are approximate.

## 7. Limits

The original executable's; § 8 lists what the `soundlimits` mod changes.

| What | Limit | Where | Original executable |
|---|---|---|---|
| Music fonts | 33 (1..0x21) | `playMusic` check, FAALL stride `(font−1)·39` | **full**: no new font; replace one |
| Tracks per font | any (`offset[0]/4`) | `seqOpen` | but only tracks 0/1 (day/night) and the 9 override pairs are reachable from scripts; battle/arena code picks its own; the jukebox table (`MAIN_D_801303B8`, 64 pairs, data) can point to a new one |
| Music chunk | 39 sectors = 0x13800 (VH + VB + SEQ) | stride | 0x7E8 free in the fullest (font 0xB) |
| SEQ block of a font | 0x5800 | `SEQ_BUFFER`, unchecked `memcpy` | font 0xB uses 0x55F8 |
| VAB header | 0xA20 + 0x200·ps ≤ buffer: ps ≤ 2 (SS, SL, VLALL, VBALL, 0x1000), ≤ 6 (ESALL/SB, 0x1800), ≤ 10 (FAALL, 0x2000) | `VHB_HEADER_*`, unchecked; overflow hits the next buffer | |
| Body | the bank's SPU slot (§ 5) | sticky address, unchecked | full by design: ~27 KB free in all slots together |
| Samples per VAB | 254 (u16 size table, 256 entries) | libsnd | |
| Effect ids | 16 per program (`prog·16 + max − 60`): SS/SL ≤ 32, ESALL/SB ≤ 96 | `playSound` | SS has 29 tones in 2 programs |
| Voice ids | keys of program 0 in a VBALL/VLALL chunk (16 tones) | `playSound` banks 3–7 | |
| Voices per Digimon | VBALL chunk ≤ 7 sectors (0x3800) **and** body ≤ 0x2800; VLALL ≤ 15 sectors and body ≤ 0x7800 | strides, slots | 0x4D4 / 0x384 bytes of stride slack at worst; a new voice set reuses an id or replaces one |
| Voice tables | `DIGIMON_VBALL_SOUND_ID[180]`, `DIGIMON_VLALL_SOUND_ID[66]` (u8 chunk ids) | `sound.c:57,126` | data: any type can point to any existing chunk (patch the bytes) |
| Map effect regions | 22 (`MAP_SOUND_PARA`), index = `MAP_ENTRIES.flags & 0x1F` (32 values, 22–31 read past the table) | `sound.c` | data: a region can grow only if the following ones move (patch the table) and `ESALL.VHB` changes size |
| SPU voices | 24; effects take 10–23 round robin, the sequencer allocates its own | `getNextFreeChannel` | dense SEQs (> ~14 notes) steal from effects |
| File sizes | fixed sectors in `FILE_OFFSET_TABLE` | executable | same size → `build-disc.py --file`; growing → `--relayout` (mod executable) |
| Staged size | a chunk (SS/SL/SB: the whole file) is read in whole sectors into `GENERAL_BUFFER` (0x80010000) before its upload: ≤ 124 sectors (0x3E000, `SOUND_STAGING_MAX`, mod executables since patch 0096) | `loadVHBFile`, `readVHBFile*` | the largest is an ESALL chunk of exactly 124 sectors; past it the staging reaches the save extensions (`SAVE_EXT_ADDR`). `sound.py` refuses a bigger chunk (`SOUND_STAGING_MAX` in the environment overrides; `build-full.sh` passes the executable's) |

**Staging overwrites the map's `.TFS` header.** `GENERAL_BUFFER` is also where memreclaim keeps the
background's header (0x80010000), so every bank or music font
staged in the world overwrites it. Nothing may read it afterwards: the time of day reads its palettes
from the resident copy `MOD_TFS_CLUTS` (patch 0159; reading them from the header after a staged load
turns the background into noise at the next hour change). Code that
stages into `GENERAL_BUFFER` on a map and then needs anything else from the header calls
`readMapTFS(CURRENT_SCREEN)`, as the evolution, death and battle exits do.

## 8. Integrated sound build

The patch series replaces fixed chunk strides with an index, expands sequence
storage and allocates SPU banks per load. These changes are part of the integrated
executable; a separate historical sound worktree is unnecessary.

`tools/derive/steps/sound.py` makes the indexed VBALL, VLALL and ESALL banks, and
builds FAALL with our committed song and instruments from `content/sound/house-theme/`.
The story step selects the added music in the appropriate MAPHEAD setups.
`tools/build-full.sh` checks staging and SPU budgets using the final resources.

The bindings in `story/core/audio.json` select the house theme only for Jijimon's
house (screen 218, font 34). Tropical Jungle, including the toilet screen
(13, TROP02), keeps the original font 2 and its day/night variants. Toilet use
itself does not select music.

For additional sound work, update the generator inputs and matching story setup
through these steps rather than manually assembling a release disc.

```sh
python3 tools/sound.py roundtrip
python3 tools/sound.py check build/wtif/sound/FAALL.VHB
python3 tools/sound.py spu-budget --vhb-dir build/wtif/sound \
  --maphead build/wtif/with-new-screens/MAPHEAD.SCN
```

The staging limit comes from the selected executable facts (`SOUND_STAGING_MAX`).
A larger file can also require disc relayout, handled by the integrated builder.
Passing file checks alone is insufficient: test music transitions, battle voices,
evolution, tournaments and VS on the original 2 MB setup where affected.

The offline renderer is an approximation of the SPU. A successful preview does
not prove reverb, envelopes, channel contention or runtime allocation correct;
listen to the actual game and check the active SPU budget as well.
