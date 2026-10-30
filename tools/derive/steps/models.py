"""The partner/NPC models of the disc's own species (build-full.sh), into build/NAME/models as the bash.

Eight replace a CHDAT model (model.file of content/species), three are new partner-only files in the root
(model.partner_file): the disc paths come from content/species. REUSE_MODELS=1 keeps a model already there (the bash's
model()); the imports' models are the bash's (a disc with the species provider imports needs none).

Units: each model is one (units(ctx)); no script reads another's model. derive build --jobs N runs them side by side
(runner.run_units; one process, in order, is the reference), the browser's workers too.
"""
import os

from .. import runner
from .species import species_tools

NAME = 'models'
DESCRIPTION = 'Partner and NPC model generation'
AFTER = ()
X = 'content/models'
MODELS = [   # (file, script): the order of build-full.sh
    ('TIRS-partner.MMD', f'{X}/master-tyrannomon/make-model.py'),        # MasterTyrannomon 124
    ('JURE-partner.MMD', f'{X}/cherrymon/make-model.py'),                # Cherrymon 121
    ('SCUD-partner.MMD', f'{X}/partners/kingsukamon-model.py'),    # KingSukamon 120
    ('ICEM-partner.MMD', f'{X}/partners/icemon-model.py'),         # Icemon 94
    ('INSE-partner.MMD', f'{X}/partners/meteormon-model.py'),      # Meteormon 113
    ('WARU-partner.MMD', f'{X}/partners/warumonzaemon/make-model.py'),  # 70
    ('VAND-partner.MMD', f'{X}/partners/myotismon/make-model.py'),      # 66
    ('TONO-partner.MMD', f'{X}/partners/shogungekomon/make-model.py'),  # 119
    ('MUGP.MMD', f'{X}/partners/machinedramon.py'),   # Machinedramon 115 (partner-only file)
    ('JIJP.MMD', f'{X}/partners/jijimon.py'),         # Jijimon 117 (partner-only file)
    ('ANLP.MMD', f'{X}/partners/analogman.py'),       # Analogman 116 (partner-only file)
]


def disc_paths():
    """{model file name: disc path} of the models made here: species.py's disc_files (the --file/--add list of the disc's
    species) for the files content/species names under build/models (the bash's $M)."""
    with species_tools() as S:
        return {os.path.basename(f): disc for _, disc, f in S.disc_files() if f.startswith('build/models/')}


def outputs(ctx):
    disc = disc_paths()
    return [(f'models/{f}', disc.get(f)) for f, _ in MODELS]


def make_model(script, out, reuse):
    """One model (a unit; in this process, a forked one or a worker) -> its log."""
    if reuse and os.path.isfile(out) and os.path.getsize(out):
        return f'reuse {os.path.basename(out)}'
    r = runner.run_script(script, [out])
    return f'$ {script} {out}  ({r.seconds:.2f} s)\n' + r.out


def units(ctx):
    reuse = ctx.env.get('REUSE_MODELS') == '1'
    return [runner.Unit(f, make_model, (script, ctx.path('models', f), reuse),
                        [os.path.dirname(script), 'tools', 'extracted'], [f'models/{f}']) for f, script in MODELS]


def prepare(ctx):
    os.makedirs(ctx.path('models'), exist_ok=True)


def build(ctx):
    prepare(ctx)
    ctx.run_units(units(ctx))
