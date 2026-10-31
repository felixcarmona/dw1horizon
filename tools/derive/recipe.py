"""A recipe (recipes/NAME.json): one disc's settings, the single source of what the bash once spelled out
(tools/derive/README.md, "Design"). Today one recipe, the everything disc (everything.json):

  environment   the build's settings as build-full.sh reads them (TEXT, LANGS, SPECIES, SPECIES_PROVIDER, ...; null: unset)
  story         mod: the story mod's folder; sources: EXTRA_STORY, pinned in the order they are compiled (the order
                changes bytes); dev_sources: DEV=1's additions (the playtest hook)
  maps          the story mod's map recipes in order (steps/maps.py, steps/retouch.py)

A story mod's maps are made into the maps folder beside the build's (maps_out: build/NAME-maps for build/NAME), and the
story reads them from there: env() gives the variables the story mod's build.sh hands build-full.sh (EXTRA_STORY,
SCREEN_CONTENT, DWS_MAPS, EXTRA_FILES), and environment() the whole environment of a player's build (derive build
--recipe: the patcher), the recipe's settings over what the machine has, nothing else of the machine's.
"""
import glob
import json
import os

from .runner import ROOT

DIR = os.path.join(ROOT, 'tools', 'derive', 'recipes')
# what a step or a script reads from the environment that a recipe does not set: off on a player's build
# (a developer's shell may have them)
NOT_THE_RECIPES = ('EXTRA_SPECIES', 'TEXT_ZONES', 'ES_ZONES', 'COLD', 'SPECIES_RAM_MB', 'EVL_SHARD_SCRATCH_SIZE',
                   'SHARD_SCRATCH_WARN', 'SOUND_STAGING_MAX', 'STORY_LANG', 'BALANCE_CONTENT', 'DWS_LOWERED',
                   'SPECIES_PORTRAITS', 'SPECIES_CONTENT', 'MAIN_STORY', 'SCNASM_PACK_ASCII', 'DWS_RELAYOUT')


def path(name):
    return name if name.endswith('.json') or os.sep in name else os.path.join(DIR, f'{name}.json')


def load(name):
    with open(path(name)) as f:
        return json.load(f)


def maps_out(out):
    """The story mod's maps folder of the build folder out (build/NAME -> build/NAME-maps, build.sh's $O)."""
    return os.path.abspath(out).rstrip(os.sep) + '-maps'


def retouched(rec, out):
    """EXTRA_FILES (build.sh RETOUCH): every file of the retouch recipes' folder, DEST in the folder of the disc's map
    of the same name, SRC as build.sh wrote it (relative to the repository)."""
    m = os.path.relpath(maps_out(out), ROOT)
    names = sorted(os.path.basename(w) for e in rec['maps']['steps'] if e['step'] == 'retouch'
                   for w in e.get('writes', []) if w.startswith('retouch/'))
    out = []
    for n in names:
        found = glob.glob(os.path.join(ROOT, 'extracted', 'MAP', '*', n.rsplit('.', 1)[0] + '.MAP'))
        if len(found) != 1:
            raise SystemExit(f'recipe: {n}: {len(found)} maps of that name on the disc')
        d = os.path.relpath(os.path.dirname(found[0]), os.path.join(ROOT, 'extracted')).replace(os.sep, '/')
        out.append(f'{d}/{n}={m}/retouch/{n}')
    return out


def env(rec, out, dev=False):
    """{variable: value}: what the story mod's build.sh hands tools/build-full.sh."""
    if 'story' not in rec:
        return {}
    m = os.path.relpath(maps_out(out), ROOT)
    story = rec['story']['sources'] + (rec['story'].get('dev_sources', []) if dev else [])
    return {'EXTRA_STORY': ' '.join(story), 'SCREEN_CONTENT': f'{m}/screens', 'DWS_MAPS': os.path.join(ROOT, m, 'retouch'),
            'EXTRA_FILES': ' '.join(retouched(rec, out))}


def environment(rec, out, base=None):
    """The environment of a player's build of the recipe into out: base (os.environ) without NOT_THE_RECIPES, the
    recipe's settings (null: unset), env(), and what build-full.sh exports before its derive step (DWS_RELAYOUT=1;
    SCNASM_PACK_ASCII by PACK_ASCII, else on for every TEXT but us)."""
    e = {k: v for k, v in (os.environ if base is None else base).items() if k not in NOT_THE_RECIPES}
    for k, v in rec.get('environment', {}).items():
        if v is None:
            e.pop(k, None)
        else:
            e[k] = str(v)
    e.update(env(rec, out, dev=e.get('DEV') == '1'))
    e['DWS_RELAYOUT'] = '1'
    pack = e.get('PACK_ASCII') or ('0' if e.get('TEXT', 'us') == 'us' else '1')
    if pack == '1':
        e['SCNASM_PACK_ASCII'] = '1'
    return e
