# Native NPCs as partners

The native NPC partner generators live together under `content/models/partners/`.
Derive's models step is their build registry; it keeps output ordering, disc names
and model bytes independent of the source directory layout.

| Models | Sources and shared helpers |
|---|---|
| KingSukamon, Icemon, Meteormon | `kingsukamon-model.py`, `icemon-model.py`, `meteormon-model.py`; `tools/models/partners/support.py`, `tools/models/partners/golem.py` |
| WaruMonzaemon, Myotismon, ShogunGekomon | each species' `make-model.py`; `tools/models/partners/rig.py`; `tech-origins.py` audits technique effects |
| Machinedramon, Jijimon, Analogman | `machinedramon.py`, `jijimon.py`, `analogman.py`; `tools/models/partners/boss.py` |

MasterTyrannomon and Cherrymon retain their dedicated model folders. Generators
read models and animations from the player's extracted USA disc. Their output
must fit the original 2 MB target's partner buffer. Models with separate partner
files preserve the original NPC model for encounters.

```sh
python3 content/models/partners/icemon-model.py build/Icemon.MMD
python3 content/models/partners/myotismon/make-model.py build/Myotismon.MMD
python3 content/models/partners/jijimon.py build/Jijimon.MMD
python3 -m unittest tools.test_partner_model_generators
```

The characterization test requires the extracted USA disc and checks all eleven
derive model outputs against untouched-main hashes. A producer move also needs
the complete everything-disc and recorded-bundle checks; a matching standalone
model does not prove archive or disc assembly.
