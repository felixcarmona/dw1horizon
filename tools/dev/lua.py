"""Generated emulator scripts belong in build, with one file per port."""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def write_script(family, name, code):
    directory = ROOT / 'build/dev' / family
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{name}-{os.environ.get("EMU_PORT", "38090")}.lua'
    path.write_text(code)
    return str(path)
