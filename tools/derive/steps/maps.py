"""The story mod's new screens (story/mods/what-the-island-forgot/build.sh): the maps and backgrounds of the
69 screens of maps/*.py, made from the player's own maps with our art, into build/NAME-maps/screens as the bash.

The recipes and their order are the recipe file's (recipes/everything.json "maps"; `step` says which are this step's
and which retouch's, `writes` what each makes). Each recipe runs in this process (ctx.run): mapbase.py and the retouch
recipes call tools/dwmap.py's functions (import_png, bg_main), no command. DWS checks lowered placements against the generated maps after every declared output exists.
The recipe selects the sources whose arrival-distance failures stop the build; additional coverage is reported.

Units: each recipe is one (units(ctx)); a recipe that writes several screens (galleries.py, twnb-gate.py) is one per
screen; no recipe reads another's output. derive build --jobs N runs them side by side in N processes (runner.run_units;
one process, in order, is the reference, and always so with --strict or --record). The same bytes either way. The spawn
audit is a check, not a unit: it runs first, here.

Disc paths: a new screen's .TFS is MAP/NEW/<FILE>.TFS on the disc as the recipe makes it; its .MAP is not: the story
step edits it in place (dws/backend.py keeps the recipe's as <FILE>.MAP.orig), so it has no disc path here.
The maps folder is the build folder's sibling (recipe.maps_out: build/NAME-maps for build/NAME, where the story reads
them; the manifest names its files relative to the build folder, ../NAME-maps/...). The step clears it and copies the
mod's screen files into it (recipe "maps" screens_from) first. build.sh runs this step itself (derive build --recipe
everything --steps maps,retouch --out build/NAME), so it is MOD_BUILD: a plain derive build (build-full.sh's step 0)
leaves it out; derive build --recipe (the player's build) makes it with the rest.
"""
import glob
import json
import os
import shutil

from .. import recipe as R
from .. import runner

NAME = 'maps'
DESCRIPTION = 'New map geometry and backgrounds'
AFTER = ()
FACTS = False
MOD_BUILD = True          # built by the story mod's build.sh into build/NAME-maps, not by build-full.sh's step 0
RECIPE = 'tools/derive/recipes/everything.json'
# recipes that take the screens to make after their arguments (one process each in --jobs): {script: the arguments
# their recipe line leaves to the default, put before the screens}
SPLIT = {'maps/galleries.py': ['galleries'], 'maps/twnb-gate.py': []}


def recipe(ctx):
    with open(os.path.join(ctx.root, RECIPE)) as f:
        return json.load(f)['maps']


def entries(ctx, step):
    """This step's lines of the recipe, in order (the spawn audit stands among the maps')."""
    return [e for e in recipe(ctx)['steps'] if e['step'] == step]


def mpath(ctx, *p):
    """A path in the story mod's maps folder (recipe.maps_out)."""
    return os.path.join(R.maps_out(ctx.out), *p)


def argv(ctx, e):
    return [a.format(screens=mpath(ctx, 'screens'), retouch=mpath(ctx, 'retouch')) for a in e['args']]


def disc_path(ctx, rel):
    """The disc path of a file a recipe writes, or None (the story step changes it before the disc)."""
    d, f = rel.split('/', 1)
    if not f.endswith('.TFS'):
        return None          # rule: the .MAP files go on to the story step (new screens edited in place, DWS_MAPS)
    if d == 'screens':
        return f'MAP/NEW/{f}'
    base = os.path.join(ctx.root, 'extracted', 'MAP')
    for sub in sorted(os.listdir(base)):  # rule: a retouched original replaces the disc's file in its own folder (build.sh RETOUCH)
        if os.path.isfile(os.path.join(base, sub, f[:-4] + '.MAP')):
            return f'MAP/{sub}/{f}'
    return None


def step_outputs(ctx, step):
    return [(os.path.relpath(mpath(ctx, w), ctx.out), disc_path(ctx, w)) for e in entries(ctx, step)
            for w in e.get('writes', [])]


def outputs(ctx):
    return step_outputs(ctx, NAME)


def run_recipe(script, args):
    """One recipe (a unit; in this process or a worker) -> its output; StepError if it failed."""
    return runner.run_script(script, args).out


def step_units(ctx, step):
    """The step's recipes as runner.Unit, in the recipe file's order (a SPLIT recipe: one per screen it writes)."""
    mod = recipe(ctx)['mod']
    out = []
    for e in entries(ctx, step):
        if 'check' in e:
            if e['check'] != 'story-spawns':
                raise runner.StepError(f'unknown map check: {e["check"]}')
            continue
        script = f'{mod}/{e["script"]}'
        inputs = [script, f'{mod}/maps', f'{mod}/art', 'tools/dwmap.py', 'extracted/MAP']
        if e['script'] in SPLIT:
            fill = SPLIT[e['script']][len(e['args']) - 1:]
            for w in e['writes']:
                if w.endswith('.MAP'):
                    f = os.path.basename(w)[:-4]
                    out.append(runner.Unit(f'{e["script"]} {f}', run_recipe, (script, argv(ctx, e) + fill + [f]), inputs,
                                           [x for x in e['writes'] if os.path.basename(x)[:-4] == f]))
        else:
            out.append(runner.Unit(e['script'], run_recipe, (script, argv(ctx, e)), inputs, e.get('writes', [])))
    return out


def units(ctx):
    return step_units(ctx, NAME)


def prepare_step(ctx, step):
    """What comes before the recipes: the step's folder cleared, the mod's screen files copied beside the maps, the mod's screen metadata."""
    d = mpath(ctx, 'screens' if step == NAME else 'retouch')
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(mpath(ctx, 'screens'), exist_ok=True); os.makedirs(mpath(ctx, 'retouch'), exist_ok=True)
    if step == NAME:   # the mod's screen files beside the maps (build.sh's cp; the story and newfiles.py read them there)
        for f in sorted(glob.glob(os.path.join(ctx.root, recipe(ctx)['screens_from']))):
            shutil.copyfile(f, os.path.join(d, os.path.basename(f)))


def finish_step(ctx, step):
    """What comes after the recipes: every file they say they write is there."""
    missing = [w for w, _ in step_outputs(ctx, step) if not os.path.isfile(ctx.path(w))]
    if missing:
        raise runner.StepError(f'{step}: the recipes did not write {", ".join(missing[:5])} (recipes/everything.json "writes")')
    for entry in entries(ctx, step):
        if entry.get('check') == 'story-spawns':
            with open(os.path.join(ctx.root, RECIPE)) as file:
                sources = json.load(file)['story']['sources']
            args = ['check-spawns', *sources, '--screen-content', mpath(ctx, 'screens'),
                    '--maps', mpath(ctx, 'retouch'),
                    '--json', ctx.path('derived', 'spawn-check.json')]
            for source in entry.get('enforce_sources', []):
                args += ['--enforce-source', f'{recipe(ctx)["mod"]}/{source}']
            ctx.run('tools/dws.py', args, env={'DWS_LOWERED': ctx.path('spawn-check-lowered')})



def run(ctx, step):
    """prepare, this step's recipes (runner.run_units: here or side by side), finish."""
    prepare_step(ctx, step)
    ctx.run_units(step_units(ctx, step))
    finish_step(ctx, step)


def prepare(ctx):
    prepare_step(ctx, NAME)


def finish(ctx):
    finish_step(ctx, NAME)


def build(ctx):
    run(ctx, NAME)
