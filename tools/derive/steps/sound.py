"""Route DWS-owned bank commands through the shared sound codec.

DWS owns music sources, font bindings and instrument programs. Derive supplies
output/scratch directories and the staging limit measured from the executable.
Committed source audio keeps host math differences out of the bank bytes.
"""
import filecmp
import os
import tempfile

from .. import facts as F

NAME = 'sound'
DESCRIPTION = 'Sound banks and music'
AFTER = ()
FACTS = True


def outputs(ctx):
    from tools.dws import audio
    return [(f'sound/{k}.VHB', f'SOUND/VHB/{k}.VHB') for k in audio.bank_names()]


def build(ctx):
    env = {'SOUND_STAGING_MAX': hex(F.sound_staging_max(ctx.facts))}
    s = ctx.path('sound')
    os.makedirs(s, exist_ok=True)
    from tools.dws import audio
    with tempfile.TemporaryDirectory(dir=ctx.path('derived')) as scratch:
        for args in audio.bank_commands(s, scratch):
            ctx.run('tools/sound.py', args, env=env)


def check(ctx):
    """The committed song and instruments are still what their generator makes (else: a warning, the bank keeps the
    committed ones); every bank's chunks within the staging buffer (sound.py check)."""
    env = {'SOUND_STAGING_MAX': hex(F.sound_staging_max(ctx.facts))}
    from tools.dws import audio
    sources = audio.load(audio.DEFAULT_MANIFEST)['banks']['sources']
    with tempfile.TemporaryDirectory(dir=ctx.path('derived')) as t:
        ctx.run('tools/dws/audio_sources.py', [t])
        for relative in sources.values():
            f = os.path.basename(relative)
            if not filecmp.cmp(os.path.join(t, f), os.path.join(ctx.root, relative), shallow=False):
                ctx.log(f'warning: tools/dws/audio_sources.py no longer makes {relative} (this machine\'s libm, '
                        'or the generator changed: commit its output if the change is meant)')
    for k in audio.bank_names():
        r = ctx.run('tools/sound.py', ['check', ctx.path('sound', f'{k}.VHB')], env=env, check=False)
        if 'staging buffer' in r.out:
            raise SystemExit(f'{k}.VHB: ' + [l for l in r.out.splitlines() if 'staging buffer' in l][0])
