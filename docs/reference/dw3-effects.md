# Digimon World 2003 technique effects

This page explains how Digimon World 2003 (PAL; Digimon World 3 in the USA) stores and plays a technique: its
name and power, the caster's animation, the camera, the hits, and the visual effects. It also covers what
carrying those effects into this game's effect engine gives today. Everything is read from the player's own
disc with `tools/dw3effect.py`. Nothing from that disc is kept in the repository.

The PAL and USA discs hold the same tables at slightly different places. Every position below is found by
the table's shape, so both discs work with the same tools. The two discs give every imported species the
same technique, power and effect files. One script differs in length: Pharaohmon's Necro Mist is 330 frames
on PAL and 360 on USA.

## Where a technique lives

### Move records

The boot executable (`SLES_039.36` PAL, `SLUS_014.36` USA) holds 443 move records of 18 bytes each
(`<HHBBBBBBBBBIB`). They start at 0x333DC (PAL) and 0x32FE8 (USA).

| Field | Meaning |
|---|---|
| u16 MP | cost |
| u16 power | base power |
| u8 type | the move's kind |
| u8 accuracy | hit chance |
| u8 boosted stat, u8 boost | what the move raises, and by how much |
| u8 effective against | the target kind it works best on |
| u8 hit effect, u8 rate, u8 value | the status it can cause |
| u32, u8 | not decoded |

The names are in `ESSKLNAM.BIN` (PAL), `USSKLNAM.BIN` (USA) or `MSSKLNAM.BIN` (Japan): 444 strings, one per
move plus one spare. Each name is a run of one-byte font codes, in which 0x01 is a space and 0x1A a hyphen.
Two entries are filler bytes (0xE6) and have no name.

### Who uses which move

- **Partners.** 52 records of 88 bytes are kept in the executable (0x2F75C on PAL). The first u16 is the
  battle model number, and u16 number 20 is the partner's signature move.
- **Enemies.** `SDIGIEDT.PRO` holds the enemy rows, 70 bytes each. A row names its battle model and three
  moves: the plain attack, move 1 and move 2.

### The technique script

Every battle model (`AAA/DAT/FIGHT/MODEL/M###XXXX.BIN`) carries its own technique scripts, one per action
slot. Slot 11 is a partner's signature. An enemy's plain attack is slot 5, its move 1 slot 9 and its move 2
slot 10.

A script is a list of signed 16-bit words. A wait is counted in ticks of 1/60 s; sprite animations and the
3D effects' key frames count the same ticks (fight overlay 0x80083A54 and 0x80083C30). The game does not
lock its frame rate to them.

| Op | Words | Does |
|---|---|---|
| 0 | 1 | end (0xFF also ends) |
| 2 | varies | plays a clip of the caster (the clip is the third word when the second is 0) |
| 3 | 3 or 6 | loads or shows a sprite effect: id, x, y, z (not negated) |
| 4 | 3 or 5 | a scene change (background, light and colour), with the scene's own optional sound |
| 5 | 4 or 17 | a camera preset, or a camera keyframe |
| 6 | 3 or 9 | spawns a 3D effect: id, x, -y, -z, turn x, -turn y, -turn z |
| 7 to 10 | 3 | events; op 10 is a sound (below); event 98 is a hit before the last and 99 the last hit |
| 11 | 2 | waits so many ticks |

The field's middle is the origin. The partner stands at z = -5376 and the enemy at +5376. A partner's 3D
effects are spawned turned half a turn (y = ±2048), so that they face the enemy.

BlackWarGreymon and WarGrowlmon also have a slot 12, a cinematic of about 1500 frames. It is not their
signature; slot 11 is.

### 3D effects (MEFT)

The fight overlay `FIGHTSTG.PRO` holds the 3D effect table at file offset 0x1F8A0. Each 12-byte record is
an id, a section count and the file's index (twice). It lists 129 effects, ids 39 to 376. Id 310 is listed
twice, and some effects have no sections of their own.

A `MEFT####.BIN` file is a small battle model: bones with their own key frames, triangles and quads, and one
16-bit 64×256 texture page. Each material is 7 bytes: u (u16), v, the palette column (in halfwords: 0, 16, 32
or 48) and the palette row (254 or 255). A render register picks the blend: 0 is solid, 2 adds light,
4 subtracts it and 6 adds a quarter. These blend meanings are assumed from the look, not proven.

### Sprite effects

Most techniques also use flat sprites. The fight overlay's sprite table gives each sprite id a pack, a
section and a file. Ids 1000 and up come from the shared packs `E000COM*.BIN`, and ids 2000 and up from the
caster's own pack. For example, 2003 is Kotemon's `E383PKEN.BIN` and 2041 is Renamon's `E373RENA.BIN`.
Id 1009 is the shared finisher emblem that fills the screen and 1020 the white wipe behind it; neither is
part of a technique's own look.

A spawn's z picks the space. z = 32767 draws in screen space in front of everything and z = -1 behind;
x and y are then pixels from the screen's middle. Any other z is a field position, projected again every
frame, not tied to a fighter. A sprite's size in pixels does not change with distance.

A sprite block (`tools/dw3sprite.py`) is a header of words and an animation. Bit i of a key's channel mask
replaces header word 3 + i: 0 the frame, 1 a palette row offset, 2 and 3 x and y in pixels, 4 and 5 the
scale x and y (4096 = 1), 6, 7 and 8 the turn about x, y and z. A block with a scale of 0 is not drawn. A
turn about x or y only narrows the sprite, since depth is dropped. A frame is a list of parts, each drawn as
its own primitive (SPRT, or POLY_FT4 when scaled or turned), the last on top. The frame's word b gives the
blend: -1 is solid, 0 to 3 the PlayStation's semi-transparency rates (half, add, subtract, add a quarter).
Colour 0x8000 is solid black; only 0x0000 is transparent.

## Carrying them into this game

`tools/dw3efe.py` turns a technique's 3D effects into one effect chunk of this game (0x5000 bytes). It
reuses the Digimon World 2 converter (`tools/dw2efe.py`):

1. Each spawned 3D effect is placed in the caster's frame. The spawn's position and turn, and the half turn
   of a partner's side, are baked into the effect's root bones. A later spawn starts with hidden frames.
2. A face stored twice with its winding reversed is kept once. The effects carry both because the game draws
   only the side that faces the camera; drawing both would double an additive face's light.
3. Each effect goes to the converter as a cast object at the caster's feet, for its whole length. (Digimon
   World 2 shows a cast object for two seconds; many DW2003 effects run longer.) When the whole effect
   does not fit a chunk, either the longest opening that fits is kept or named parts are left out and the
   whole length is kept (`--leave-out`).
4. The size follows the field: this game's fighters stand 2700 units apart and DW2003's 10 752, so an effect is
   scaled by a quarter and covers the same share of the field. A beam that crosses DW2003's field crosses this
   game's. (Scaling by the species' import size instead left the large species' effects a quarter of the
   way across.)
   Where a part starts on the caster's half follows the caster instead. A spawn's position is a fixed point
   of DW2003's field (Assaultmon's muzzle fire is 3328 units up), and the field's scale put it about twice as
   high and far as the caster here. So the spawn's position and each part's first-frame offset are scaled
   by the caster's model (its height here over its DW2003 model's), and the parts' size and their flight
   from there keep the field's scale. The build passes the species' height (`caster_height`); the fidelity
   check compares the conversion without it. `python -m tools.efecheck --anchors --archive BUILT_EFEDAT`
   checks that every own effect's parts that start on the caster's half start inside the caster's box.
5. Parts are not re-aimed. Digimon World 2's rule of re-aiming a far-flying part at the target and hiding it at
   the hit would cut a DW2003 beam, which keeps drawing through its hit. So the effect plays as on the disc,
   drawn for a target 2700 units away, and the hit comes when the converter's cast ends. A shot that is a
   single flying ball instead overshoots: Pyrosphere's ball flies 3300 units whatever the distance, so it went
   through the target and the hit came after it had gone. Such an entry sets `"aim": true` (`--aim`): the ball
   is aimed at the target, vanishes at its body and the hit lands there (at 2700 on tick 24, at 1200 on tick 9).
6. The launch point comes from the native chunk that the finisher design names as the template.
7. The 3D effects' key frames are sampled every second tick, at this game's 30 frames a second.
8. A technique with no 3D effect is converted from its sprites (`--sprites`). Each sprite block becomes a bone
   whose frames are flat quads facing the side camera, its pose keyed every 30th of a second from the
   block's channels (place, scale, turn about z; a turn about x or y as a narrower scale). The frames'
   rectangles are packed into one 4-bit texture; when the palettes do not fit the chunk's six rows, each
   colour is moved to the nearest colour of a kept palette of the same kind (solid or blended), never
   averaged. Screen-space spawns are placed on the target (in front) or the caster (behind) at 1024 units up,
   their pixels at 40 field units each. The emblem cut-ins 1009 and 1020 are left out.
9. Each species takes its chunk id from a table (`EFFECT_IDS`): 196 to 222 for the 3D effects, 223 to 250 for
   the sprite effects.

### The fidelity check

`python3 tools/dw3efe.py --disc DW3.bin compare M372SGRG 11 --like 63 --mp4 out.mp4` renders the original
and the conversion side by side from the same camera, scaled with the field, at 60 fps: a frame per DW2003
tick, the conversion showing each 20 Hz engine tick for three frames, as the game does. The camera holds both fighters
and the effect. It measures the two frame by frame and exits with an error when the conversion is not
faithful. A pixel counts as drawn when it differs from that side's scenery. A conversion fails when any of
these is true:

- it is empty in more than a quarter of the frames where the original draws;
- it draws less than half or more than twice the original's area;
- its bright area is less than half or more than three times the original's;
- its coverage over time correlates below 0.7 with the original's;
- its drawn box overlaps the original's below 0.5 on average;
- its picture changes less than 65% as often as the original's, capped at the engine's 20 Hz (smoothness).
  An effect that holds each pose two ticks to fit a chunk moves at 10 Hz and scores about 0.5.

The frame measures run on every second frame (30 fps), smoothness on all of them. To fit a chunk the converter
(tools/dw2efe.py `LEVELS`) first coarsens translations, narrows the texture and draws flat parts one-sided,
and holds poses only when nothing else fits; `info['held_ticks']` reports it.

The box and the coverage curve may be one video frame early or late, since this game's effect engine runs at
20 frames a second. The original's sprites are drawn by a separate renderer from the disc's sprite blocks
(each part blended on its own, with its block's channels), not from the converted quads.

The measures see area, light, timing and place, not shape. A thin part can be missing and the check still
passes, so a conversion that leaves parts out names them.

The first comparisons failed this check for three reasons, all now fixed:

- the effect was cut at two seconds;
- it was scaled by the species' size, a quarter of the field's;
- its beams vanished at the hit.

Three further faults were in the previews, not in the chunks:

- the original was drawn with both faces of each pair, which doubled its light;
- the converted preview drew the converter's two-sided parts twice;
- the camera was fixed on the field's middle, so effects that rise high were filmed out of view.

The renderers do not cull back faces, and the game does.

### Sounds

A technique's sounds are op 10 events (event id, duration) and the optional sound of an op 4 scene. The fight
overlay (`FIGHTSTG.PRO`, PAL: 0x8008C454) reads the event's u32 command at 0x800A368C + 4 × event. With bit 31
set the command is one note of the battle bank `MPCOMMON.BIN` (header) and `MVCOMMON.BIN` (samples, after a 4-byte
offset word): program (cmd >> 11) & 127, note cmd & 127. Without it, it starts a short SEP score of that bank.
Events 98 and 99 (the hits) play the move record's impact sound (byte 0x0F of the 18-byte row). Events 28 and 89
are the shared finisher fanfare that goes with the finisher banner, and 91 fades it out; like the banner, they
are not carried.

This game cannot load the DW2003 samples: the battle leaves about 22 KB of sound memory free at worst
(`tools/sound.py spu-budget`). Each source note is played instead as the battle sound (`SB.VHB`, bank 8) that
sounds closest among the 62 the original effects use: both are rendered as the sound chip plays them (pitch,
loop, envelope) and compared by length, loudness shape and spectrum. An entry's `sounds` lists the results as
(60 Hz script tick, sound id); the conversion plays each at its tick, counted like the effects from the first
spawn (earlier ones on its first tick), in place of the generic start and launch sounds. On one engine tick a
repeated sound plays once and at most two sounds start. Thunder Bolt
(Maildramon) keeps only its impact sound, since more would push its chunk to coarser poses.

### Rebuilt as composed effects

Seven conversions passed the fidelity check but read as flat card art in the 3D fight. Most of the surface they
draw is planar sprites that never turn, scale or fade, above the 90th percentile of DW1's own effects (4.3 % and
7.7 %). They are Pincer Crusher (225), Lizard Dance (228), Thunder Bolt (237), Ura Sword (238), Roach Rush (242),
Hot Head (244) and Bear Fist (245). Each is now a DW1 effect of its kind, recoloured to the attack's element
(`compose` in `content/battle/own-effects.json`, docs/mods/signature-effects.md). Its `compose.sounds` maps the
template's sounds to the converted cues above, so the attack keeps its own sounds. The table below still shows
the conversion as it was measured.

## Every imported species

The key is the species id, the same key the finisher design uses. "Ticks" is the script's length in 1/60 s.
"Effect" lists the 3D effect files
(MEFT) and the number of sprite effects the technique draws. "Converted" is the chunk size, the
chunk id, the behaviour the converter chose and the fidelity check's verdict, or the native template chunk
used instead when a conversion still failed after one round of fixes. A technique with a 3D effect is
converted from its 3D effects alone; one with none, from its sprites. "Melee" here
means no part flies to the target on its own: the effect plays as on the disc and the hit comes when it ends.

| Key | Species | Technique (disc) | Power | Hits | Slot | Ticks | Effect | Converted | Finisher design |
|---|---|---|---|---|---|---|---|---|---|
| 295 | Vilemon | Dark Fear | 600 | 1 | 9 | 225 | MEFT0335 + 3 sprites | 5416 B, id 196, melee, faithful | Nightmare Shock (beam, 1 hit) |
| 296 | Grizzlymon | Maul Attack | 300 | 2 | 11 | 305 | 5 sprites | falls back to template chunk 111 (fits a chunk only holding each pose 4 ticks: it moves 30% as often as the effect engine allows) | Maul Attack (dash, 1 hit) |
| 297 | Marsmon | Mugenhadou | 480 | 1 | 11 | 400 | MEFT0097 + 5 sprites | 7652 B, id 197, melee, faithful | Mugen Hadou (beam, 1 hit) |
| 298 | Dokugumon | (unnamed attack) | 80 | 1 | 5 | 240 | MEFT0328 + 3 sprites | 7888 B, id 198, melee, faithful | Poison Cobweb (shot, 1 hit) |
| 299 | Hookmon | Captain Cannon | 200 | 1 | 11 | 372 | MEFT0091 + 5 sprites | 7264 B, id 199, melee, faithful | Captain Cannon (shot, 1 hit) |
| 300 | SlashAngemon | Golden Ripper | 400 | 1 | 11 | 415 | MEFT0100 + 5 sprites | 3608 B, id 200, melee, faithful | Golden Ripper (dash, 1 hit) |
| 302 | HiAndromon | Atomic Ray | 278 | 1 | 9 | 300 | MEFT0361 + 4 sprites | 13052 B, id 201, melee, faithful | Atomic Ray (beam, 1 hit) |
| 303 | KingEtemon | (unnamed attack) | 500 | 1 | 5 | 250 | MEFT0324 + 2 sprites | 4800 B, id 202, melee, faithful | Dark Spirits DX (area, 1 hit) |
| 304 | Divermon | (unnamed attack) | 250 | 1 | 5 | 20 | 1 sprite | 4404 B, id 224, melee, 1 sprites, faithful | Striking Fish (shot, 1 hit) |
| 305 | Ebidramon | (unnamed attack) | 308 | 1 | 5 | 50 | 2 sprites | 9248 B, id 225, melee, 2 sprites, faithful | Pincer Crusher (melee, 1 hit) |
| 306 | GrapLeomon | Cyclone Turbine | 500 | 3 | 11 | 408 | 5 sprites | falls back to template chunk 62 (too large for a chunk: 36 of 72 frames fit, empty in half of the original's; leaving the repeated sprites out still fails) | Cyclone Turbine (dash, 1 hit) |
| 307 | BlackKingNumemon | Dark Pupil | 198 | 1 | 9 | 280 | 3 sprites | falls back to template chunk 62 (fits a chunk only holding each pose 3 ticks: it moves 23% as often as the effect engine allows) | Royal Muck (thrown, 1 hit) |
| 308 | Dinohyumon | Lizard Dance | 200 | 4 | 11 | 231 | 6 sprites | 11916 B, id 228, melee, 4 sprites, faithful | Lizard Dance (dash, 4 hits) |
| 309 | Antylamon | Dark Elemental | 700 | 1 | 9 | 230 | 3 sprites | falls back to template chunk 62 (coverage over time correlates 0.35: its screen-space sprite (2060) drifts; leaving it out empties 54% of the frames) | Bunny Blades (dash, 2 hits) |
| 310 | Assaultmon | Justice Strike | 140 | 3 | 11 | 539 | MEFT0093 + 5 sprites | 11888 B, id 203, melee, faithful | Justice Strike (rain, 5 hits) |
| 311 | Arukenimon | (unnamed attack) | 390 | 1 | 5 | 290 | 3 sprites | falls back to template chunk 73 (draws 40% of the original's area, 37% with the full texture; coverage over time correlates 0.40) | Spirit Needle (shot, 1 hit) |
| 312 | Creepymon | Darkness Chaos | 150 | 1 | 9 | 243 | MEFT0351 + 3 sprites | 12208 B, id 204, melee, faithful | Evil Inferno (area, 1 hit) |
| 313 | Bulbmon | Mad Pump | 580 | 1 | 9 | 269 | MEFT0346 + 2 sprites | 7456 B, id 205, melee, faithful | Bulb Flash (beam, 1 hit) |
| 314 | SkullSatamon | (unnamed attack) | 410 | 1 | 5 | 296 | 3 sprites | falls back to template chunk 96 (empty in 26% of the original's frames, 28% with the full texture) | Nail Bone (beam, 1 hit) |
| 315 | Taomon | Bonhitsusen | 250 | 1 | 11 | 519 | 6 sprites | falls back to template chunk 63 (coverage over time correlates 0.57, also with the full texture: its last burst of growing sprites is missing) | Talisman of Light (shot, 1 hit) |
| 316 | Sakuyamon | KongouKaimandara | 400 | 1 | 11 | 540 | MEFT0087 + 5 sprites | 20216 B, id 206, melee, passes; 5 parts left out | Amethyst Mandala (area, 1 hit) |
| 317 | Fujinmon | Sylph Storm | 100 | 1 | 9 | 229 | MEFT0370 + 3 sprites | 11104 B, id 207, melee, faithful | Divine Wind (area, 1 hit) |
| 318 | Gallantmon | Final Purification | 480 | 1 | 11 | 457 | MEFT0095 + 6 sprites | 11508 B, id 208, melee, faithful | Final Purification (beam, 1 hit) |
| 319 | Pharaohmon | Necro Mist | 133 | 1 | 9 | 330 | 3 sprites | falls back to template chunk 73 (fits a chunk only holding each pose 2 ticks: it moves 36% as often as the effect engine allows) | Pyramid Power (beam, 1 hit) |
| 320 | Growlmon | Plasma Blade | 300 | 3 | 11 | 400 | 7 sprites | falls back to template chunk 62 (fits a chunk only holding each pose 2 ticks: it moves 47% as often as the effect engine allows) | Plasma Blade (dash, 1 hit) |
| 321 | Knightmon | (unnamed attack) | 435 | 1 | 5 | 40 | 1 sprite | 4384 B, id 235, melee, 1 sprites, faithful | Berserk Sword (dash, 1 hit) |
| 322 | Kyukimon | Blade Twister | 140 | 3 | 11 | 419 | 6 sprites | falls back to template chunk 62 (fits a chunk only holding each pose 4 ticks: it moves 29% as often as the effect engine allows) | Blade Twister (dash, 1 hit) |
| 323 | Lynxmon | (unnamed attack) | 480 | 1 | 5 | 250 | MEFT0332 + 3 sprites | 6792 B, id 209, melee, faithful | Blazing Mane (breath, 1 hit) |
| 324 | Maildramon | Thunder Bolt | 200 | 1 | 9 | 293 | 3 sprites | 20464 B, id 237, melee, 3 sprites, faithful | Mail Bomber (shot, 1 hit) |
| 325 | Musyamon | (unnamed attack) | 410 | 1 | 5 | 20 | 2 sprites | 18280 B, id 238, melee, 2 sprites, faithful | Ura Sword (dash, 1 hit) |
| 326 | WarGrowlmon | Atomic Blaster | 300 | 1 | 11 | 388 | MEFT0096 + 4 sprites | 14304 B, id 210, melee, faithful | Atomic Blaster (beam, 1 hit) |
| 327 | Gargoylemon | Dark Matter | 300 | 1 | 9 | 231 | MEFT0352 + 2 sprites | falls back to template chunk 81 (coverage over time correlates 0.69 at 20 Hz; short flashes) | Gargoyle Rush (dash, 1 hit) |
| 328 | Snimon | (unnamed attack) | 390 | 1 | 5 | 20 | 1 sprite | 4396 B, id 239, melee, 1 sprites, faithful | Twin Sickles (thrown, 2 hits) |
| 329 | Ghoulmon | Darkness Chaos | 150 | 1 | 9 | 216 | MEFT0349 + 3 sprites | 12016 B, id 212, melee, faithful | Necro Eye (beam, 1 hit) |
| 330 | Minotarumon | (unnamed attack) | 180 | 1 | 5 | 20 | 1 sprite | 5100 B, id 240, area, 1 sprites, faithful | Darkside Quake (area, 1 hit) |
| 331 | Vemmon | (unnamed attack) | 160 | 1 | 5 | 100 | 3 sprites | falls back to template chunk 100 (fits a chunk only holding each pose 2 ticks: it moves 30% as often as the effect engine allows) | Vemmon Crash (melee, 1 hit) |
| 332 | Roachmon | (unnamed attack) | 320 | 1 | 5 | 10 | 2 sprites | 18220 B, id 242, melee, 2 sprites, faithful | Roach Rush (dash, 1 hit) |
| 333 | Raijinmon | Electro Ball | 310 | 1 | 9 | 232 | MEFT0363 + 2 sprites | 10832 B, id 213, melee, faithful | Raijin Thunder (area, 1 hit) |
| 334 | Mummymon | Dark Fear | 600 | 1 | 9 | 252 | MEFT0335 + 2 sprites | 5428 B, id 214, melee, faithful | Necrophobia (shot, 1 hit) |
| 335 | MegaGargomon | Giant Missile | 400 | 1 | 11 | 467 | MEFT0085 + 7 sprites | 7798 B, id 215, melee, faithful | Giant Missile (shot, 1 hit) |
| 336 | Raidenmon | Gilead Plant | 650 | 1 | 9 | 298 | 4 sprites | falls back to template chunk 112 (fits a chunk only holding each pose 2 ticks: it moves 49% as often as the effect engine allows) | Raiden Strike (beam, 1 hit) |
| 351 | Kotemon | Hot Head | 80 | 1 | 11 | 320 | 6 sprites | 19012 B, id 244, melee, 5 sprites, faithful | Hot Head (dash, 1 hit) |
| 352 | Monmon | Swing Swing | 100 | 1 | 11 | 406 | MEFT0089 + 4 sprites | 7596 B, id 216, melee, faithful | Swing Swing (melee, 2 hits) |
| 353 | Bearmon | Bear Fist | 100 | 1 | 11 | 355 | 4 sprites | 11400 B, id 245, melee, 2 sprites, faithful | Bear Fist (melee, 1 hit) |
| 354 | Renamon | Diamond Storm | 100 | 1 | 11 | 542 | 5 sprites | falls back to template chunk 70 (fits a chunk only holding each pose 4 ticks: it moves 28% as often as the effect engine allows) | Diamond Storm (rain, 6 hits) |
| 403 | Beelzemon | Blast Mode | 800 | 3 | 11 | 471 | 7 sprites | falls back to template chunk 80 (too large for a chunk: 84 of 102 frames fit, empty in 43%; leaving the repeated sprites out still fails) | Corona Blaster (beam, 1 hit) |
| 404 | BlackWarGreymon | Terra Destroyer | 640 | 1 | 11 | 593 | 4 sprites | falls back to template chunk 96 (fits a chunk only holding each pose 3 ticks: it moves 41% as often as the effect engine allows) | Terra Destroyer (shot, 1 hit) |
| 405 | Cannondramon | DynamoCannon | 320 | 1 | 11 | 423 | MEFT0094 + 5 sprites | 18900 B, id 217, melee, faithful | Dynamo Cannon (beam, 1 hit) |
| 406 | MaloMyotismon | Melting Blood | 480 | 1 | 11 | 438 | MEFT0092 + 4 sprites | 8780 B, id 218, melee, faithful | Melting Blood (melee, 1 hit) |
| 407 | Armageddemon | (unnamed attack) | 140 | 1 | 5 | 306 | MEFT0333 + 3 sprites | 12484 B, id 219, melee, faithful | Ultimate Flare (beam, 1 hit) |
| 408 | Suijinmon | Mugen Cannon | 500 | 4 | 5 | 280 | MEFT0364 + 3 sprites | 18256 B, id 220, melee, faithful | Water Spiral (beam, 1 hit) |
| 409 | Kyubimon | Dragon Wheel | 180 | 1 | 11 | 378 | 5 sprites | falls back to template chunk 61 (fits a chunk only holding each pose 4 ticks: it moves 23% as often as the effect engine allows) | Dragon Wheel (dash, 1 hit) |
| 430 | Zanbamon | Cross Slash | 169 | 1 | 5 | 77 | MEFT0039 + 2 sprites | 8572 B, id 221, melee, faithful | Zanba Blade (dash, 1 hit) |
| 431 | Kurisarimon | no technique script | | | | | | | Data Crusher (shot) |
| 432 | Bastemon | (unnamed attack) | 0 | 4 | 5 | 108 | 2 sprites | falls back to template chunk 60 (moves 57% as often as the effect engine allows) | Cat Laser (beam, 1 hit) |
| 433 | Guilmon | Pyrosphere | 100 | 1 | 11 | 445 | MEFT0102 + 5 sprites | 4384 B, id 222, melee, faithful | Pyrosphere (shot, 1 hit) |
Of the 56 imported species, 55 have a technique script; Kurisarimon has none. 27 techniques have a 3D effect.
Each converts into one chunk, for its whole length; 26 pass the fidelity check. The sizes are the builds
the game uses: gameplay-neutral, one enemy and one hit, as the finisher each stands for. All 26 ship (the
[signature attacks](signature-attacks.md)): a source effect that passes wins over a composed one. The largest whole one,
Cannondramon's, is 18 900 bytes of the 20 480 a chunk holds. Sakuyamon's leaves five small parts out (below).
Gargoylemon's Dark Matter fails on timing alone (its coverage curve correlates 0.69): short flashes that this
game's 20 Hz engine cannot place on the original's 30 fps frames. The conversion is kept out, and the species
keeps a template chunk. These 3D conversions leave the technique's sprites out.

The other 28 techniques draw only sprites. Converted from their sprites (step 8 above), 11 pass the fidelity check
and ship, read through the derive path like the 3D ports (the own effect lists each sprite's pack and sections;
Maildramon's pack differs on the USA disc, so its chunk has a USA pin of its own). 17 keep a template chunk
(their finisher's), after one round of fixes: 10 of them fit a chunk only by holding each pose 2-4 ticks, so they
move at 5-10 Hz and fail the smoothness check (drawing between ticks does not help them: a held pose still stands
still for its ticks); GrapLeomon and Beelzemon do not fit
whole; Antylamon, Arukenimon, SkullSatamon and Taomon draw too little or out of time (a screen-space sprite
drifts, a late burst is missing); Bastemon changes too seldom.

## What the conversion does not keep yet

- **Sakuyamon's whole effect.** Kongou Kaimandara is 296 frames of ten parts, and its faces alone (15 KB)
  leave too little of a 20 KB chunk for the rest. The conversion keeps the rune mandala, the lightning fan and
  the two blue arcs for the whole length, drawn from both sides. It leaves out the comets (part 8), the two
  blue flames at the caster (parts 4 and 5) and the two pink flares (parts 2 and 3). Leaving out fewer parts
  only fits with one-sided faces, and then the turning mandala would vanish whenever it shows its back. Its
  texture is stored at an eighth of its size, so the burst looks blocky up close, and its poses change every
  fourth frame.
- **Timing.** This game's effect engine runs at 20 frames a second, so a short flash can come one frame
  early or late. The 3D effects were first sampled as if their key frames were 1/30 s, which played them at
  half speed; they are 1/60 s ticks like the script's.
- **Sprites.** The sprite conversions are flat quads in the plane facing the side camera, not the engine's
  billboards (DW1 has billboard sprite routines that a later version could use). A screen-space sprite's place
  on a fighter and the size of its pixels (40 field units) are estimates, not read from the game. Palette
  cycling past the texture page's last row falls back to the rectangle's own palette. The shared finisher
  emblem (sprites 1009 and 1020) is left out.
- **Hit timing.** Several finisher designs call a technique a beam or a shot (Vilemon, HiAndromon,
  WarGrowlmon, Gallantmon, Bulbmon and others). The conversion does not re-aim their parts, so the damage
  lands when the effect ends, not when a projectile arrives. Pyrosphere (Guilmon) is aimed (`"aim": true`). WarGrowlmon's Atomic
  Blaster is a beam that stops about halfway to the target and the hit comes after it ends: not aimed yet.
  Ten species (Guilmon, WarGrowlmon, Gallantmon and Sakuyamon among them) no longer play their conversion: their
  finisher is written here ([authored finishers](../mods/signature-effects.md#authored-finishers)).
- **Camera.** DW2003 techniques move the camera; this game's effect engine keeps its own camera.
- **Blending.** The 3D effects' blend meanings above are assumed; the sprites' are read from the frame records.

## Names that need an editorial choice

These are the disc's names, and both releases spell them the same way. Most are run together or are
untranslated Japanese, and some are not what the finisher design calls the technique.

| Species | Disc name | Finisher design |
|---|---|---|
| 316 Sakuyamon | KongouKaimandara | Amethyst Mandala |
| 297 Marsmon | Mugenhadou | Mugen Hadou |
| 315 Taomon | Bonhitsusen | Talisman of Light |
| 403 Beelzemon | Blast Mode | Corona Blaster |
| 405 Cannondramon | DynamoCannon | Dynamo Cannon |
| partner model M056DIGI (not an import) | NM Syndromer | |
| partner model M254PLDR (not an import) | DesperadoBlaster | |

The techniques the disc gives each import that differ from the finisher design are in the table above.
Fifteen imports use a plain attack (slot 5) with no name on the disc: Dokugumon, KingEtemon, Divermon,
Ebidramon, Arukenimon, SkullSatamon, Knightmon, Lynxmon, Musyamon, Snimon, Minotarumon, Vemmon, Roachmon,
Armageddemon and Bastemon. Their names have to come from elsewhere.

## Damage comparison after the seven composed replacements

The 2026-11-16 check found no damage regression from PR #508. The old ports emit
one damage event per target (`dw3efe.convert` defaults to `n_hits=1`), not a
sequence of later hits missing from the composed templates. Three valid trials
per species and version, at charge 80, keep the same damage class:

| Species | Old damage (three trials) | New damage (three trials) | Mean change |
|---|---|---|---|
| Maildramon | 1455, 1530, 1635 | 1470, 1530, 1395 | -4.9% |
| Musyamon | 1103, 1035, 1035 | 1024, 1013, 1013 | -3.9% |
| Roachmon | 1216, 1114, 1126 | 1114, 1024, 1148 | -4.9% |
| Ebidramon | 791, 807, 749 | 791, 840, 848 | +5.6% |
| Dinohyumon | 1114, 1171, 1182 | 1148, 1126, 1238 | +1.3% |
| Kotemon | 437, 446, 496 | 437, 506, 483 | +3.4% |
| Bearmon | 1045, 1055, 986 | 1064, 956, 1005 | -2.0% |

The comparison reconstructed the seven old chunks from the first parent of
#508, verified every historical pin, and changed only those chunks in a copy of
the current disc. All sectors outside the effect archive, the executable, models,
save fixture and battle preparation were identical. The new chunks also match
the current compositions byte for byte. Trials use original 2 MB RAM, offense
400, partner HP 4,000, enemy HP 2,500, and isolated enemy AI.

The original harness could write charge 80 too late for a short effect, or lose a
RAM write to a presentation pass's state restoration. The charge bonus is
`charge / 40` from charge 41 onward: 80 doubles damage, while charge 0 or 12 adds
no bonus. On the unchanged new Maildramon effect, explicit charge 80 and 0
produced **1,470 and 735** damage. An uncontrolled new run likewise varied
1,590 / 1,470 / 780. This explains the apparent halving without changing hits
or templates; the ordinary damage roll varies only 90–110%.

For future comparisons, use `tools/dev/playtest/finisher_targets.py` with
`--trials 3 --chargeup 80`. It maintains charge during the active window,
checks charge during observed HP loss, reapplies enemy isolation after battle
initialization, and samples the complete recording. HP drains across several
frames; `hp_updates` are not separate attack hits. Rejected trials with the
wrong charge were replaced and are retained in the evidence.

All seven fresh presence measurements pass the 0.011–0.45 area bounds, and the
existing presence table is fresh. All seven effect definitions, colours, scales,
`compose.sounds` and pins remain unchanged. The resident partner peak remains
100,256 B in its 100,352 B buffer. The related suites ran 63 tests with three
fixture-dependent skips and no failures.

[Machine-readable evidence](../data/finisher-damage.json) includes all accepted
trials, rejected controls, chunk hashes, presence measurements, and the charge
diagnostic. Full recordings and RAM samples remain under `build/trials/`.
