# Hagurumon movement sound routing

The Robot House scene plays `sound(8, 8)` immediately before moving Hagurumon
(`story/base/zones/robot-house/s140-146/script.py`). Robot House uses ESALL
region 9. Effect 8 uses program 0, key 68, sample 9 (4,480 ADPCM bytes).
The original HAGU movement program contains texture events but no sound event;
the scene supplies the effect separately.

This cannot be copied directly into the partner's movement animation. Animation
bank 8 plays the current map's effects, which change on arrival and become SB
in battle. Bank 4 instead resolves to the entity's own loaded VBALL bank.
Hagurumon uses VBALL chunk 37, with notes 53–55; it has no gear sample. That
chunk is shared with Giromon, Tekkamon and Solarmon.

The sound is deferred until the build supports a private species sound bank:

1. Clone VBALL chunk 37 to a new indexed chunk, preserving its three existing
   notes. Add the source ESALL sample and tone without changing the shared bank.
2. Convert the effect's program/key routing to a free program-0 voice key,
   preserving its pitch and envelope. For key 56, the source key moves from
   68 to 56, so the tone's root must move down twelve semitones too.
3. Assign the private bank to Hagurumon. Extend the current 71-chunk species
   validation and its tone audit to read the generated bank. The existing
   `copy-effect` command only copies effects within one file and uses effect
   key routing; it does not perform this cross-file voice conversion.
4. Add bank-4 events to walk, condition walk and run. Check cadence and tails
   with sound in Robot House, File City, another region and a battle. Check
   indexed bank staging, SPU allocation and original-2-MB heap limits.

No movement event or voice assignment is changed here: a global map-bank call
would produce unrelated sounds outside Toy Town. The build must derive the
sample from the player's disc; no original audio is stored in the repository.

Inspection commands:

```sh
python3 tools/sound.py list ESALL
python3 tools/sound.py info ESALL 9
python3 tools/sound.py info VBALL 37
```
