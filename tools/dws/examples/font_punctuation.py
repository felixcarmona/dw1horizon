# The punctuation glyphs of the mod executables' font (docs/mods/font.md): ( ) & % / … [ ] # * ~ @ – — ♪ in Jijimon's lines.
#   python3 tools/dws.py disc tools/dws/examples/font_punctuation.py --name fontp --exe mods      (or --exe story-state)
# The original executable has no glyph for them: `check` without --exe refuses ( ) & % / [ ] # * ~ @ at their line.
from dw import *
from dw.base.jijimons_house import jijimon

@jijimon.on_talk
def punctuation():
    say("Jijimon (the elder) & friends: 50% off, 2/3 of the price… Wait!")
    say("[Note] #1 *star* ~wave~ @home: 1–2 days—maybe ♪")
