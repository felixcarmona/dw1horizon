#!/usr/bin/env python3
"""Build species records from imported models and reviewed field animations.

The imports step regenerates the 175 model/texture pairs from the player's source
discs and verified deltas. BASE contains <id>.MMD and <id>.TIM; it defaults to
build/everything/imported-models. A model marked aliases_applied already contains
its slot_aliases. The registry selects field overlays, generated with the Python
standard library into OUT-models.

  species.py OUT [BASE]

make(out) returns {id: (model file, texture file or None)} for the generated species
records. overlay(out, id) builds one reviewed overlay; derive schedules those
independent units, then calls make(out, generate=False) to read their results.
Additional technique_timing and technique_aliases in models.json align reviewed
attack clips after the field overlays and battle reach pass. Every final model
and texture is checked against the derive species pins.
"""
import importlib.util, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '../../..'))
OVERLAYS = {   # field_overlay: (id, generator module, model name)
    'blackkingnumemon-slug': ('307', 'tools.models.field_animations.black_king_numemon', '307-blackkingnumemon-slug'),
    'wormmon-native-crawl': ('183', 'tools.models.field_animations.native_binding', '183-wormmon-native-crawl'),
    'stingmon-wing-followthrough': ('187', 'tools.models.field_animations.followthrough', '187-stingmon-wing-followthrough'),
    'gizamon-active-gait': ('239', 'tools.models.field_animations.followthrough', '239-gizamon-active-gait'),
    'suijinmon-centaur-field': ('408', 'tools.models.field_animations.suijinmon', '408-suijinmon-centaur-field'),
    'saberleomon-pace': ('258', 'tools.models.field_animations.pace', '258-saberleomon-pace'),
    'marinedevimon-field': ('279', 'tools.models.field_animations.marine_devimon', '279-marinedevimon-field'),
    'bulbmon-field': ('313', 'tools.models.field_animations.bulbmon', '313-bulbmon-field'),
    'kurisarimon-celebration': ('431', 'tools.models.field_animations.celebrations', '431-kurisarimon-celebration'),
    'zanbamon-celebration': ('430', 'tools.models.field_animations.celebrations', '430-zanbamon-celebration'),
    'raijinmon-celebration': ('333', 'tools.models.field_animations.celebrations', '333-raijinmon-celebration'),
    'arukenimon-celebration': ('311', 'tools.models.field_animations.celebrations', '311-arukenimon-celebration'),
    'clockmon-celebration': ('290', 'tools.models.field_animations.celebrations', '290-clockmon-celebration'),
    'redotamamon-celebration': ('233', 'tools.models.field_animations.celebrations', '233-redotamamon-celebration'),
    'imperialdramon-celebration': ('192', 'tools.models.field_animations.celebrations', '192-imperialdramon-celebration'),
    'ladydevimon-flight': ('223', 'tools.models.field_animations.ladydevimon_flight', '223-ladydevimon-flight'),
    'ladydevimon-chibi': ('223', 'tools.models.field_animations.chibi', '223-ladydevimon-chibi'),
    'slashangemon-chibi': ('300', 'tools.models.field_animations.chibi', '300-slashangemon-chibi'),
    'gallantmon-chibi': ('318', 'tools.models.field_animations.celebrations', '318-gallantmon-chibi'),
    'malomyotismon-chibi': ('406', 'tools.models.field_animations.chibi', '406-malomyotismon-chibi'),
    'neocrimson-chibi': ('402', 'tools.models.field_animations.chibi', '402-neocrimson-chibi'),
    'mummymon-chibi': ('334', 'tools.models.field_animations.chibi', '334-mummymon-chibi'),
    'snatchmon-chibi': ('331', 'tools.models.field_animations.snatchmon_polish', '331-snatchmon-chibi'),
    'gargoylemon-chibi': ('327', 'tools.models.field_animations.gargoylemon_gait', '327-gargoylemon-chibi'),
    'wargrowlmon-chibi': ('326', 'tools.models.field_animations.chibi', '326-wargrowlmon-chibi'),
    'musyamon-chibi': ('325', 'tools.models.field_animations.chibi', '325-musyamon-chibi'),
    'maildramon-native': ('324', 'tools.models.field_animations.native_binding', '324-maildramon-native'),
    'kyukimon-chibi': ('322', 'tools.models.field_animations.kyukimon_gait', '322-kyukimon-chibi'),
    'knightmon-chibi': ('321', 'tools.models.field_animations.celebrations', '321-knightmon-chibi'),
    'growlmon-chibi': ('320', 'tools.models.field_animations.chibi', '320-growlmon-chibi'),
    'pharaohmon-chibi': ('319', 'tools.models.field_animations.pharaohmon_gait', '319-pharaohmon-chibi'),
    'fujinmon-chibi': ('317', 'tools.models.field_animations.celebrations', '317-fujinmon-chibi'),
    'sakuyamon-chibi': ('316', 'tools.models.field_animations.chibi', '316-sakuyamon-chibi'),
    'skullsatamon-native': ('314', 'tools.models.field_animations.native_binding', '314-skullsatamon-native'),
    'creepymon-chibi': ('312', 'tools.models.field_animations.creepymon_gait', '312-creepymon-chibi'),
    'assaultmon-native': ('310', 'tools.models.field_animations.native_binding', '310-assaultmon-native'),
    'antylamon-chibi': ('309', 'tools.models.field_animations.antylamon_polish', '309-antylamon-chibi'),
    'dinohyumon-chibi': ('308', 'tools.models.field_animations.dinohyumon_gait', '308-dinohyumon-chibi'),
    'grapleomon-chibi': ('306', 'tools.models.field_animations.chibi', '306-grapleomon-chibi'),
    'kingetemon-chibi': ('303', 'tools.models.field_animations.chibi', '303-kingetemon-chibi'),
    'hiandromon-native': ('302', 'tools.models.field_animations.native_binding', '302-hiandromon-native'),
    'hookmon-chibi': ('299', 'tools.models.field_animations.hookmon_polish', '299-hookmon-chibi'),
    'marsmon-chibi': ('297', 'tools.models.field_animations.chibi', '297-marsmon-chibi'),
    'boltmon-chibi': ('288', 'tools.models.field_animations.chibi', '288-boltmon-chibi'),
    'skullmeramon-chibi': ('277', 'tools.models.field_animations.chibi', '277-skullmeramon-chibi'),
    'metaltyrannomon-native': ('260', 'tools.models.field_animations.native_binding', '260-metaltyrannomon-native'),
    'metaltyrannomon-chibi': ('260', 'tools.models.field_animations.celebrations', '260-metaltyrannomon-chibi'),
    'floramon-pace': ('273', 'tools.models.field_animations.pace', '273-floramon-pace'),
    'mushroomon-pace': ('263', 'tools.models.field_animations.pace', '263-mushroomon-pace'),
    'tortomon-pace': ('261', 'tools.models.field_animations.pace', '261-tortomon-pace'),
    'armadillomon-pace': ('185', 'tools.models.field_animations.pace', '185-armadillomon-pace'),
    'tapirmon-pace': ('287', 'tools.models.field_animations.pace', '287-tapirmon-pace'),
    'snimon-pace': ('328', 'tools.models.field_animations.pace', '328-snimon-pace'),
    'gryphonmon-celebration': ('293', 'tools.models.field_animations.celebrations', '293-gryphonmon-celebration'),
    'wormmon-pace': ('183', 'tools.models.field_animations.pace', '183-wormmon-pace'),
    'datamon-field': ('294', 'tools.models.field_animations.datamon', '294-datamon-field'),
    'deramon-pace': ('286', 'tools.models.field_animations.pace', '286-deramon-pace'),
    'garbagemon-pace': ('269', 'tools.models.field_animations.pace', '269-garbagemon-pace'),
    'gazimon-field': ('285', 'tools.models.field_animations.gazimon', '285-gazimon-field'),
    'dokugumon-pace': ('298', 'tools.models.field_animations.pace', '298-dokugumon-pace'),
    'kyubimon-native': ('409', 'tools.models.field_animations.native_binding', '409-kyubimon-native'),
    'minotarumon-native': ('330', 'tools.models.field_animations.native_binding', '330-minotarumon-native'),
    'grapleomon-native': ('306', 'tools.models.field_animations.native_binding', '306-grapleomon-native'),
    'vilemon-native': ('295', 'tools.models.field_animations.native_binding', '295-vilemon-native'),
    'armageddemon-pace': ('407', 'tools.models.field_animations.pace', '407-armageddemon-pace'),
    'nefertimon-pace': ('198', 'tools.models.field_animations.pace', '198-nefertimon-pace'),
    'tylomon-native-range': ('254', 'tools.models.field_animations.celebrations', '254-tylomon-native-range'),
    'syakomon-native-range': ('283', 'tools.models.field_animations.locomotion', '283-syakomon-native-range'),
    'apocalymon-native-range': ('400', 'tools.models.field_animations.celebrations', '400-apocalymon-native-range'),
    'taomon-equipment': ('315', 'tools.models.field_animations.chibi', '315-taomon-equipment'),
    'roachmon-equipment': ('332', 'tools.models.field_animations.chibi', '332-roachmon-equipment'),
    'megagargomon-equipment': ('335', 'tools.models.field_animations.celebrations', '335-megagargomon-equipment'),
    'solarmon-steady-hover': ('251', 'tools.models.field_animations.celebrations', '251-solarmon-steady-hover'),
    'thundermon-rolling-boots': ('252', 'tools.models.field_animations.thundermon', '252-thundermon-rolling-boots'),
    'tuskmon-heavy-field': ('253', 'tools.models.field_animations.tuskmon', '253-tuskmon-heavy-field'),
    'shadramon-supported-field': ('250', 'tools.models.field_animations.celebrations', '250-shadramon-supported-field'),
    'marineangemon-steady-run': ('248', 'tools.models.field_animations.gliding', '248-marineangemon-steady-run'),
    'quetzalmon-flight': ('249', 'tools.models.field_animations.quetzalmon_flight', '249-quetzalmon-flight'),
    'kokuwamon-rolling-boots': ('247', 'tools.models.field_animations.pace', '247-kokuwamon-rolling-boots'),
    'infermon-tripod-field': ('246', 'tools.models.field_animations.pace', '246-infermon-tripod-field'),
    'piedmon-native-float': ('245', 'tools.models.field_animations.piedmon_levitate', '245-piedmon-native-float'),
    'superstarmon-supported-field': ('244', 'tools.models.field_animations.celebrations', '244-superstarmon-supported-field'),
    'starmon-boxer-field': ('243', 'tools.models.field_animations.pace', '243-starmon-boxer-field'),
    'deltamon-native': ('292', 'tools.models.field_animations.native_binding', '292-deltamon-native'),
    'kingetemon-native': ('303', 'tools.models.field_animations.native_binding', '303-kingetemon-native'),
    'chaoslord-native': ('289', 'tools.models.field_animations.native_binding', '289-chaoslord-native'),
    'princemamemon-native': ('270', 'tools.models.field_animations.native_binding', '270-princemamemon-native'),
    'wargrowlmon-native': ('326', 'tools.models.field_animations.native_binding', '326-wargrowlmon-native'),
    'violetelecmon-native': ('256', 'tools.models.field_animations.native_binding', '256-violetelecmon-native'),
    'sorcermon-native': ('242', 'tools.models.field_animations.sorcermon_native', '242-sorcermon-native'),
    'wizardmon-native': ('241', 'tools.models.field_animations.wizardmon_native', '241-wizardmon-native'),
    'gesomon-terrestrial': ('240', 'tools.models.field_animations.gesomon', '240-gesomon-terrestrial'),
    'gizamon-paired-bound': ('239', 'tools.models.field_animations.pace', '239-gizamon-paired-bound'),
    'dolphmon-gaits': ('238', 'tools.models.field_animations.dolphmon_gaits', '238-dolphmon-gaits'),
    'diaboromon-supported-field': ('237', 'tools.models.field_animations.pace', '237-diaboromon-supported-field'),
    'candlemon-pedestal-field': ('235', 'tools.models.field_animations.candlemon', '235-candlemon-pedestal-field'),
    'gatomon-field': ('234', 'tools.models.field_animations.pace', '234-gatomon-field'),
    'bombernanimon-boxer-field': ('232', 'tools.models.field_animations.bomber_nanimon', '232-bombernanimon-boxer-field'),
    'bombernanimon-native': ('232', 'tools.models.field_animations.native_binding', '232-bombernanimon-native'),
    'shellnumemon-slug-field': ('231', 'tools.models.field_animations.locomotion', '231-shellnumemon-slug-field'),
    'rosemon-field': ('230', 'tools.models.field_animations.pace', '230-rosemon-field'),
    'phantomon-native-glide': ('229', 'tools.models.field_animations.phantomon', '229-phantomon-native-glide'),
    'apemon-knuckle-field': ('227', 'tools.models.field_animations.apemon', '227-apemon-knuckle-field'),
    'silphymon-field': ('226', 'tools.models.field_animations.chibi', '226-silphymon-field'),
    'shurimon-field': ('225', 'tools.models.field_animations.chibi', '225-shurimon-field'),
    'blackgatomon-field': ('222', 'tools.models.field_animations.pace', '222-blackgatomon-field'),
    'vikemon-field': ('220', 'tools.models.field_animations.pace', '220-vikemon-field'),
    'zudomon-field': ('219', 'tools.models.field_animations.pace', '219-zudomon-field'),
    'ikkakumon-field': ('218', 'tools.models.field_animations.pace', '218-ikkakumon-field'),
    'gomamon-field': ('217', 'tools.models.field_animations.pace', '217-gomamon-field'),
    'devidramon-field': ('216', 'tools.models.field_animations.pace', '216-devidramon-field'),
    'magnadramon-glide': ('215', 'tools.models.field_animations.magnadramon_flight', '215-magnadramon-glide'),
    'shakkoumon-glide': ('214', 'tools.models.field_animations.celebrations', '214-shakkoumon-glide'),
    'aeroveedramon-field': ('213', 'tools.models.field_animations.celebrations', '213-aeroveedramon-field'),
    'venommyotismon-field': ('212', 'tools.models.field_animations.venom_myotismon', '212-venommyotismon-field'),
    'metalseadramon-swim': ('211', 'tools.models.field_animations.metal_seadramon', '211-metalseadramon-swim'),
    'grankuwagamon-field': ('210', 'tools.models.field_animations.gran_kuwagamon', '210-grankuwagamon-field'),
    'lillymon-native-flight': ('209', 'tools.models.field_animations.lillymon_flight', '209-lillymon-native-flight'),
    'togemon-field': ('208', 'tools.models.field_animations.togemon', '208-togemon-field'),
    'seraphimon-field': ('207', 'tools.models.field_animations.chibi', '207-seraphimon-field'),
    'magnaangemon-field': ('206', 'tools.models.field_animations.celebrations', '206-magnaangemon-field'),
    'megakabuterimon-field': ('205', 'tools.models.field_animations.mega_kabuterimon', '205-megakabuterimon-field'),
    'veedramon-field': ('203', 'tools.models.field_animations.gaits', '203-veedramon-field'),
    'monmon-upperbody': ('352', 'tools.models.field_animations.monmon', '352-monmon-upperbody'),
    'wargreymon-field': ('373', 'tools.models.field_animations.chibi', '373-wargreymon-field'),
    'blackwargreymon-field': ('404', 'tools.models.field_animations.celebrations', '404-blackwargreymon-field'),
    'omnimon-field': ('461', 'tools.models.field_animations.celebrations', '461-omnimon-field'),
    'renamon-field': ('354', 'tools.models.field_animations.chibi', '354-renamon-field'),
    'beelzemon-field': ('403', 'tools.models.field_animations.chibi', '403-beelzemon-field'),
    'magnamon-native': ('197', 'tools.models.field_animations.magnamon', '197-magnamon-native'),
    'magnamon-field': ('197', 'tools.models.field_animations.gaits', '197-magnamon-field'),
    'puppetmon-field': ('181', 'tools.models.field_animations.articulation', '181-puppetmon-field'),
    'kotemon-field': ('351', 'tools.models.field_animations.imported_equipment', '351-kotemon-field'),
    'bastemon-field': ('432', 'tools.models.field_animations.celebrations', '432-bastemon-field'),
    'veemon-field': ('180', 'tools.models.field_animations.gaits', '180-veemon-field'),
    'exveemon-field': ('194', 'tools.models.field_animations.gaits', '194-exveemon-field'),
    'flamedramon-field': ('195', 'tools.models.field_animations.gaits', '195-flamedramon-field'),
    'stingmon-field': ('187', 'tools.models.field_animations.secondary_motion', '187-stingmon-field'),
    'angewomon-field': ('190', 'tools.models.field_animations.celebrations', '190-angewomon-field'),
    'demidevimon-native-flight': ('236', 'tools.models.field_animations.native_binding', '236-demidevimon-native-flight'),
    'paildramon-field': ('199', 'tools.models.field_animations.chibi', '199-paildramon-field'),
    'ankylomon-field': ('189', 'tools.models.field_animations.pace', '189-ankylomon-field'),
    'metalgarurumon-pace': ('191', 'tools.models.field_animations.pace', '191-metalgarurumon-pace'),
}


def records():
    with open(os.path.join(HERE, 'models.json')) as source:
        return json.load(source)


# the folder of the imported base models (<id>.MMD, <id>.TIM) tools/derive's imports step made from the player's discs;
# derive's species and overlays steps and tools/models/edit.py set it, the command line takes it as BASE
BASE_MODELS = None


def _species(t, e, names):
    """(file name, content/species file of id t with the model and texture of its record e)."""
    name = next(f for f in names if f.split('-')[0] == t)
    s = json.load(open(os.path.join(ROOT, 'content/species', name)))
    if BASE_MODELS is None:
        raise SystemExit('no imported base models: set BASE_MODELS (tools/derive\'s imports step makes them in OUT/imported-models)')
    if 'model' in e and e.get('aliases_applied'):
        s['model'].pop('slot_aliases', None)
    s['model']['file'] = os.path.join(BASE_MODELS, f'{t}.MMD')
    s['texture'] = {'file': os.path.join(BASE_MODELS, f'{t}.TIM')}
    return name, s


def _recipe(t, e):
    recipe = OVERLAYS.get(e['field_overlay'])
    if recipe is None or recipe[0] != t:
        raise ValueError(f'Unknown reviewed field overlay for {t}: {e["field_overlay"]}')
    return recipe


def overlay_paths(out, t, e):
    """(model, report) files of the reviewed field overlay of species t (record e) for the species folder OUT."""
    generated = os.path.abspath(out) + '-models'
    name = _recipe(t, e)[2]
    return os.path.join(generated, name + '.MMD'), os.path.join(generated, name + '-report.json')


def overlay(out, t, recs=None, names=None, s=None):
    """Makes the reviewed field overlay of species t into OUT-models (its .MMD and -report.json) -> (model file, proof).
    (tools/derive's overlays step runs one per unit; make() all of them)"""
    recs = recs or records()
    e = recs[t]
    name, own = _species(t, e, names or os.listdir(os.path.join(ROOT, 'content/species')))
    s = own if s is None else s
    recipe = _recipe(t, e)
    tools = os.path.join(ROOT, 'tools')
    if tools not in sys.path: sys.path.insert(0, tools)
    import species as species_tools
    generator = __import__(recipe[1], fromlist=['build'])
    if hasattr(generator, 'BASE_MODELS'):      # a generator that reads another imported species' model (native_binding's `donor_species`)
        generator.BASE_MODELS = BASE_MODELS
    s['_path'] = os.path.join(ROOT, 'content/species', name)
    model, proof = generator.build(species_tools.species_model(s)[0], s['model']['skeleton'])
    model_path, report = overlay_paths(out, t, e)
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, 'wb') as f:
        f.write(model)
    with open(report, 'w') as f:
        json.dump(proof, f, indent=2)
    return model_path, proof


def technique_aliases(s, aliases):
    """Share existing attack clips for additional techniques, after field overlays.

    The imported base already contains its original slot aliases. Applying the
    additions here keeps those slots stable and also covers generated overlays.
    """
    pairs = []
    for target, source in aliases.items():
        moves = s['techniques']
        pairs.append([0x2E + moves.index(target), 0x2E + moves.index(source)])
    own = dict(s, model=dict(s['model'], slot_aliases=pairs))
    import species as species_tools
    model = species_tools.species_model(s)[0]
    return species_tools.apply_slot_aliases(model, own)


def species_file(out, t, recs=None, names=None, generate=False):
    """(file name, species file) of id t as make() writes it into OUT; its overlay (if any) made here (generate) or read
    back from OUT-models (a missing one stops)."""
    recs = recs or records()
    names = names or os.listdir(os.path.join(ROOT, 'content/species'))
    e = recs[t]
    name, s = _species(t, e, names)
    if e.get('field_overlay'):
        if generate:
            model_path, proof = overlay(out, t, recs, names, s)
        else:
            model_path, report = overlay_paths(out, t, e)
            if not os.path.isfile(model_path):
                raise SystemExit(f'{model_path}: no overlay model (tools/derive\'s overlays step makes it)')
            with open(report) as f:
                proof = json.load(f)
        if 'generated_skeleton' in proof:
            s['model']['skeleton'] = proof['generated_skeleton']
        s.update(proof.get('species_patch', {}))
        s['model']['file'] = model_path
        s['model'].pop('slot_aliases', None)
        s.pop('_path', None)
    # Battle reach is applied after all field size passes: their global model
    # scaling would otherwise shorten the native dash again.
    if 'Buster Dive' in (s.get('techniques') or []) and not e.get('native_animation_donor'):
        import species as species_tools
        from tools.models import buster_dive
        from pathlib import Path
        s['_path'] = os.path.join(ROOT, 'content/species', name)
        model, proof = buster_dive.apply(species_tools.species_model(s)[0], s, clip=e.get('buster_dive_clip'))
        if proof is not None:
            generated = Path(os.path.abspath(out) + '-models')
            generated.mkdir(parents=True, exist_ok=True)
            (generated / f'{t}-buster-dive-report.json').write_text(json.dumps(proof, indent=2) + '\n')
            if proof['applied']:
                model_path = generated / f'{t}-buster-dive.MMD'
                model_path.write_bytes(model)
                s['model']['file'] = str(model_path)
                s['model'].pop('slot_aliases', None)
        s.pop('_path', None)
    if e.get('technique_timing'):
        from pathlib import Path
        import species as species_tools
        from tools.models import technique_timing
        generated = Path(os.path.abspath(out) + '-models')
        generated.mkdir(parents=True, exist_ok=True)
        s['_path'] = os.path.join(ROOT, 'content/species', name)
        model, proof = technique_timing.apply(species_tools.species_model(s)[0], s, e['technique_timing'])
        model_path = generated / f'{t}-technique-timing.MMD'
        model_path.write_bytes(model)
        (generated / f'{t}-technique-timing-report.json').write_text(json.dumps(proof, indent=2) + '\n')
        s['model']['file'] = str(model_path)
        s['model'].pop('slot_aliases', None)
        s.pop('_path', None)
    if e.get('technique_aliases'):
        generated = os.path.abspath(out) + '-models'
        os.makedirs(generated, exist_ok=True)
        s['_path'] = os.path.join(ROOT, 'content/species', name)
        model = technique_aliases(s, e['technique_aliases'])
        model_path = os.path.join(generated, f'{t}-techniques.MMD')
        with open(model_path, 'wb') as f:
            f.write(model)
        s['model']['file'] = model_path
        s['model'].pop('slot_aliases', None)
        s.pop('_path', None)
    if e.get('movement_sound') is not None:
        from pathlib import Path
        import species as species_tools
        from tools.models import movement_sounds
        generated = Path(os.path.abspath(out) + '-models')
        generated.mkdir(parents=True, exist_ok=True)
        s['_path'] = os.path.join(ROOT, 'content/species', name)
        cue = e['movement_sound']
        settings = cue if isinstance(cue, dict) else {'note': cue}
        model, proof = movement_sounds.apply(species_tools.species_model(s)[0],
                                             s['model']['skeleton'], int(t), settings['note'],
                                             settings.get('replace_notes', ()))
        model_path = generated / f'{t}-movement-sounds.MMD'
        model_path.write_bytes(model)
        (generated / f'{t}-movement-sounds-report.json').write_text(json.dumps(proof, indent=2) + '\n')
        s['model']['file'] = str(model_path)
        s['model'].pop('slot_aliases', None)
        s.pop('_path', None)
    return name, s


def make(out, generate=True):
    """The species files of OUT (and the overlays' models in OUT-models); {id: (model file, texture file or None)}.
    generate=False: the overlays' models and reports are already in OUT-models (tools/derive's overlays step made them;
    a missing one stops)."""
    recs = records()
    os.makedirs(out, exist_ok=True)
    made = {}
    names = os.listdir(os.path.join(ROOT, 'content/species'))
    for t in recs:
        name, s = species_file(out, t, recs, names, generate)
        with open(os.path.join(out, name), 'w') as f:
            json.dump(s, f, indent=1, ensure_ascii=False)
        made[int(t)] = (s['model'].get('file'), (s.get('texture') or {}).get('file'))
    return made

if __name__ == '__main__':
    out = sys.argv[1]
    BASE_MODELS = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build/everything/imported-models'))
    if not os.path.isfile(os.path.join(BASE_MODELS, '180.MMD')):
        raise SystemExit(f'{BASE_MODELS}: no imported base models (tools/derive\'s imports step makes them)')
    make(out)
    print(f'{out}: {len(os.listdir(out))} species files')
