"""The 17 retouch recipes (story/mods/what-the-island-forgot/build.sh): the player's own maps
and backgrounds of the screens the story changes, with our art pasted over them (dwmap.py bg, called in this process),
into build/NAME-maps/retouch as the bash (gcan07-crack.py also writes screen 368's files into screens/).

The story step reads the retouched .MAP files (DWS_MAPS) and the balance and sign steps change them again, so only the
backgrounds have a disc path here. The recipes, the units (one per recipe, twnb-gate.py one per screen) and MOD_BUILD are as in maps.py.
"""
from . import maps

NAME = 'retouch'
DESCRIPTION = 'Existing map edits'
AFTER = ()
FACTS = False
MOD_BUILD = True


def outputs(ctx):
    return maps.step_outputs(ctx, NAME)


def units(ctx):
    return maps.step_units(ctx, NAME)


def prepare(ctx):
    maps.prepare_step(ctx, NAME)


def finish(ctx):
    maps.finish_step(ctx, NAME)


def build(ctx):
    maps.run(ctx, NAME)
