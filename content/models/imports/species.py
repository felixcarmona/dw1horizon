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
Every final model and texture is checked against the derive species pins.
"""
import importlib.util, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '../../..'))
OVERLAYS = {   # field_overlay: (id, generator module, model name)
    'taomon-equipment': ('315', 'tools.models.field_animations.imported_equipment', '315-taomon-equipment'),
    'roachmon-equipment': ('332', 'tools.models.field_animations.imported_equipment', '332-roachmon-equipment'),
    'megagargomon-equipment': ('335', 'tools.models.field_animations.imported_equipment', '335-megagargomon-equipment'),
    'solarmon-steady-hover': ('251', 'tools.models.field_animations.gliding', '251-solarmon-steady-hover'),
    'thundermon-rolling-boots': ('252', 'tools.models.field_animations.thundermon', '252-thundermon-rolling-boots'),
    'tuskmon-heavy-field': ('253', 'tools.models.field_animations.tuskmon', '253-tuskmon-heavy-field'),
    'shadramon-supported-field': ('250', 'tools.models.field_animations.shadramon', '250-shadramon-supported-field'),
    'marineangemon-steady-run': ('248', 'tools.models.field_animations.gliding', '248-marineangemon-steady-run'),
    'quetzalmon-steady-flight': ('249', 'tools.models.field_animations.gliding', '249-quetzalmon-steady-flight'),
    'kokuwamon-rolling-boots': ('247', 'tools.models.field_animations.kokuwamon', '247-kokuwamon-rolling-boots'),
    'infermon-tripod-field': ('246', 'tools.models.field_animations.infermon', '246-infermon-tripod-field'),
    'piedmon-native-float': ('245', 'tools.models.field_animations.piedmon', '245-piedmon-native-float'),
    'superstarmon-supported-field': ('244', 'tools.models.field_animations.super_starmon', '244-superstarmon-supported-field'),
    'starmon-boxer-field': ('243', 'tools.models.field_animations.starmon', '243-starmon-boxer-field'),
    'sorcermon-supported-field': ('242', 'tools.models.field_animations.sorcermon', '242-sorcermon-supported-field'),
    'wizardmon-supported-field': ('241', 'tools.models.field_animations.wizardmon', '241-wizardmon-supported-field'),
    'gesomon-steady-run': ('240', 'tools.models.field_animations.gliding', '240-gesomon-steady-run'),
    'gizamon-paired-bound': ('239', 'tools.models.field_animations.gizamon', '239-gizamon-paired-bound'),
    'dolphmon-native-swim': ('238', 'tools.models.field_animations.dolphmon', '238-dolphmon-native-swim'),
    'diaboromon-supported-field': ('237', 'tools.models.field_animations.diaboromon', '237-diaboromon-supported-field'),
    'candlemon-pedestal-field': ('235', 'tools.models.field_animations.candlemon', '235-candlemon-pedestal-field'),
    'gatomon-supported-field': ('234', 'tools.models.field_animations.gatomon', '234-gatomon-supported-field'),
    'bombernanimon-boxer-field': ('232', 'tools.models.field_animations.bomber_nanimon', '232-bombernanimon-boxer-field'),
    'shellnumemon-slug-field': ('231', 'tools.models.field_animations.shell_numemon', '231-shellnumemon-slug-field'),
    'rosemon-field': ('230', 'tools.models.field_animations.rosemon', '230-rosemon-field'),
    'phantomon-native-glide': ('229', 'tools.models.field_animations.phantomon', '229-phantomon-native-glide'),
    'apemon-knuckle-field': ('227', 'tools.models.field_animations.apemon', '227-apemon-knuckle-field'),
    'silphymon-field': ('226', 'tools.models.field_animations.silphymon', '226-silphymon-field'),
    'shurimon-field': ('225', 'tools.models.field_animations.shurimon', '225-shurimon-field'),
    'metalgreymon-vaccine-field': ('224', 'tools.models.field_animations.metal_greymon', '224-metalgreymon-vaccine-field'),
    'blackgatomon-field': ('222', 'tools.models.field_animations.black_gatomon', '222-blackgatomon-field'),
    'salamon-field': ('221', 'tools.models.field_animations.salamon', '221-salamon-field'),
    'vikemon-field': ('220', 'tools.models.field_animations.vikemon', '220-vikemon-field'),
    'zudomon-field': ('219', 'tools.models.field_animations.zudomon', '219-zudomon-field'),
    'ikkakumon-field': ('218', 'tools.models.field_animations.ikkakumon', '218-ikkakumon-field'),
    'gomamon-field': ('217', 'tools.models.field_animations.gomamon', '217-gomamon-field'),
    'devidramon-field': ('216', 'tools.models.field_animations.devidramon', '216-devidramon-field'),
    'magnadramon-glide': ('215', 'tools.models.field_animations.gliding', '215-magnadramon-glide'),
    'shakkoumon-glide': ('214', 'tools.models.field_animations.gliding', '214-shakkoumon-glide'),
    'aeroveedramon-field': ('213', 'tools.models.field_animations.aero_veedramon', '213-aeroveedramon-field'),
    'venommyotismon-field': ('212', 'tools.models.field_animations.venom_myotismon', '212-venommyotismon-field'),
    'metalseadramon-glide': ('211', 'tools.models.field_animations.gliding', '211-metalseadramon-glide'),
    'grankuwagamon-field': ('210', 'tools.models.field_animations.gran_kuwagamon', '210-grankuwagamon-field'),
    'lillymon-native-flight': ('209', 'tools.models.field_animations.lillymon', '209-lillymon-native-flight'),
    'togemon-field': ('208', 'tools.models.field_animations.togemon', '208-togemon-field'),
    'seraphimon-field': ('207', 'tools.models.field_animations.seraphimon', '207-seraphimon-field'),
    'magnaangemon-field': ('206', 'tools.models.field_animations.magna_angemon', '206-magnaangemon-field'),
    'megakabuterimon-field': ('205', 'tools.models.field_animations.mega_kabuterimon', '205-megakabuterimon-field'),
    'veedramon-field': ('203', 'tools.models.field_animations.gaits', '203-veedramon-field'),
    'monmon-upperbody': ('352', 'tools.models.field_animations.monmon', '352-monmon-upperbody'),
    'wargreymon-field': ('373', 'tools.models.field_animations.war_greymon', '373-wargreymon-field'),
    'blackwargreymon-field': ('404', 'tools.models.field_animations.gaits', '404-blackwargreymon-field'),
    'omnimon-field': ('461', 'tools.models.field_animations.gaits', '461-omnimon-field'),
    'renamon-field': ('354', 'tools.models.field_animations.gaits', '354-renamon-field'),
    'beelzemon-field': ('403', 'tools.models.field_animations.gaits', '403-beelzemon-field'),
    'magnamon-field': ('197', 'tools.models.field_animations.gaits', '197-magnamon-field'),
    'puppetmon-field': ('181', 'tools.models.field_animations.articulation', '181-puppetmon-field'),
    'kotemon-field': ('351', 'tools.models.field_animations.imported_equipment', '351-kotemon-field'),
    'bastemon-field': ('432', 'tools.models.field_animations.gaits', '432-bastemon-field'),
    'veemon-field': ('180', 'tools.models.field_animations.gaits', '180-veemon-field'),
    'exveemon-field': ('194', 'tools.models.field_animations.gaits', '194-exveemon-field'),
    'flamedramon-field': ('195', 'tools.models.field_animations.gaits', '195-flamedramon-field'),
    'stingmon-field': ('187', 'tools.models.field_animations.secondary_motion', '187-stingmon-field'),
    'angewomon-field': ('190', 'tools.models.field_animations.secondary_motion', '190-angewomon-field'),
    'paildramon-field': ('199', 'tools.models.field_animations.secondary_motion', '199-paildramon-field'),
    'ankylomon-field': ('189', 'tools.models.field_animations.weight_shift', '189-ankylomon-field'),
    'lighdramon-field': ('201', 'tools.models.field_animations.weight_shift', '201-lighdramon-field'),
    'metalgarurumon-field': ('191', 'tools.models.field_animations.secondary_motion', '191-metalgarurumon-field'),
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
    s['_path'] = os.path.join(ROOT, 'content/species', name)
    model, proof = generator.build(species_tools.species_model(s)[0], s['model']['skeleton'])
    if t == '224':
        from tools.models.field_animations import metal_greymon_care
        model, care = metal_greymon_care.build(model, s['model']['skeleton'])
        care['field'] = proof
        proof = care
    model_path, report = overlay_paths(out, t, e)
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, 'wb') as f:
        f.write(model)
    with open(report, 'w') as f:
        json.dump(proof, f, indent=2)
    return model_path, proof


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
        s['model']['file'] = model_path
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
