import os, sys, subprocess
sys.path.insert(0, '.')
from jobs import CUPS
def gen(out, prompt, refs, aspect):
    open(out + '.txt', 'w').write(prompt)
    r = subprocess.run([sys.executable, 'gen.py', out + '.txt', out, '--ref', *refs, '--aspect', aspect, '--size', '1K'], capture_output=True, text=True)
    print(out, r.stdout.strip()[:60], r.stderr.strip()[-200:], flush=True)
ERASE_EN = '''Image 1 is a title banner from a 1990s PlayStation game on a flat dark navy background. Erase only the big Japanese katakana logo, leaving flat dark navy where it was (and where other elements were hidden behind it, complete them naturally). Keep every English word and every other element exactly as they are, same places. No Japanese may remain. Same framing and aspect ratio as image 1.'''
ERASE_ALL = '''Image 1 is a title banner from a 1990s PlayStation game on a flat dark navy background. Erase every word and letter: the big Japanese katakana logo, the word "CUP" and all the small English text, leaving flat dark navy where they were. Keep any non-letter decoration (leaves, lightning, glow behind nothing) only if it is not part of a letter; otherwise the result may be just the dark navy background. Same framing and aspect ratio as image 1.'''
WRITE = '''Image 1 is a title banner background from a 1990s PlayStation game (flat dark navy). Image 2 is the original banner: study its logo's 3D style, material, colours, outline, glow and lighting, and its layout.
Draw on image 1, in exactly image 2's style and layout: {what}. Spell every word exactly as given, letter by letter, with accents. No Japanese characters at all. Keep image 1's other elements as they are. Same framing and aspect ratio as image 1.'''
J = sys.argv[1:]
def cup(k, lang, what, erase_all=False):
    blank = f'blank{"all" if erase_all else ""}_{k}.png'
    if not os.path.exists(blank):
        gen(blank, ERASE_ALL if erase_all else ERASE_EN, [f'ref_{k}.png'], '16:9')
    gen(f'gen_{lang}_{k}.png', WRITE.format(what=what), [blank, f'ref_{k}.png'], '16:9')
if 'cups' in J:
    for f in ['gen_en_BT.png','gen_es_BT.png','gen_es_CO.png','gen_es_FR.png','gen_es_GP.png','gen_en_MT.png','gen_en_TW.png','gen_es_TW.png']:
        os.path.exists(f) and os.rename(f, f.replace('gen_', 'old_'))
    cup('BT', 'en', 'the big logo word "BEETLE" where the katakana logo was, in the brown wooden beetle-horn style')
    cup('BT', 'es', 'the big logo word "ESCARABAJO" where the katakana logo was (narrower letters to fit), in the brown wooden beetle-horn style; below it the word "COPA" in the same style and colour as image 2\'s "CUP"; and the two small lines "VENID TODOS" and "¡¡COPA ESCARABAJO!!" in image 2\'s small white-outlined lettering', True)
    cup('CO', 'es', 'the big logo word "GUAY" (G-U-A-Y) in the chrome-and-sky style; "COPA" at the top right in image 2\'s "CUP" style; and the three small lines "¿QUIÉN ES EL MÁS GUAY?", "VENID, VENID TODOS" and "la COPA «GUAY»" in image 2\'s small white lettering', True)
    cup('FR', 'es', 'the big logo word "FUEGO" in the fiery white-yellow glowing brush style; "COPA" in image 2\'s red "CUP" style; and the small yellow lines "¡VENID," / "TODOS," / "DIGIMON" / "DE FUEGO!" at the right in image 2\'s small yellow serif lettering', True)
    cup('GP', 'es', 'at the top the small line "¿QUIÉN ES EL MEJOR LUCHADOR?" in image 2\'s small white lettering; the big logo word "LUCHA" in the chrome style; and below it the word "COPA" in image 2\'s red-outlined chrome "CUP" style (one single COPA, no other word)', True)
    cup('MT', 'en', 'the big logo word "METALLIC" where the katakana logo was, in the gold-chrome metallic style')
    cup('TW', 'en', 'the big logo, two words stacked, "THUNDER" above "WIND", in the electric-blue lightning style, where the katakana logo was')
    cup('TW', 'es', 'the big logo, two words stacked, "TRUENO" above "Y VIENTO", in the electric-blue lightning style; "COPA" at the top right in image 2\'s "CUP" style; and at the bottom the small line "COPA TRUENO Y VIENTO" in image 2\'s small lettering', True)
if 'bt' in J:
    gen('gen_es_BT.png', WRITE.format(what='the big logo word "ESCARABAJO" where the katakana logo was (narrower letters to fit), in the brown wooden beetle-horn style; replace the word "CUP" with "COPA" in the same style and colour; and replace the two small white lines with "VENID TODOS" and "¡¡COPA ESCARABAJO!!" in the same lettering. No English may remain') , ['blank_BT.png', 'ref_BT.png'], '16:9')
G_EN = '''Image 1 is the top of a tournament banner from a 1990s PlayStation game: a big shiny 3D tube-letter logo over a green circuit-board background, made of Japanese katakana followed by the Latin letter {g}.
Replace only the Japanese katakana with the five letters G-R-A-D-E, then a clear space, then keep the existing letter {g}: the logo must read exactly "GRADE {g}" (six letters in all, GRADE and {g}). Same shiny tube style, colour, outline and lighting; the circuit board, wires and the coloured bar at the bottom right exactly as they are. No Japanese may remain. Same framing and aspect ratio as image 1.'''
G_ES = '''Image 1 is the top of a tournament banner from a 1990s PlayStation game: a big shiny 3D tube-letter logo over a green circuit-board background, made of Japanese katakana followed by the Latin letter {g}.
Replace only the Japanese katakana with the nine letters C-A-T-E-G-O-R-Í-A (an accent on the I), narrow enough to fit, then a clear space, then keep the existing letter {g}: the logo must read exactly "CATEGORÍA {g}". Same shiny tube style, colour, outline and lighting; the circuit board, wires and the coloured bar at the bottom right exactly as they are. No Japanese may remain. Same framing and aspect ratio as image 1.'''
if 'grades' in J:
    for lang, g in [('en','A'), ('es','C'), ('en','S'), ('es','S')]:
        f = f'gen_{lang}_GRADE{g}.png'; os.path.exists(f) and os.rename(f, f.replace('gen_', 'old_'))
        gen(f, (G_EN if lang == 'en' else G_ES).format(g=g), [f'ref_GRADE{g}_top.png'], '21:9')
FROM_EN = '''Image 1 is a title banner from a 1990s PlayStation game, on a flat dark navy background. Translate its words into Spanish, keeping exactly the same design, styles, colours, sizes and places: {what}. Spell every Spanish word exactly as given, letter by letter, with its accents. No English may remain. Everything else exactly as in image 1. Same framing and aspect ratio as image 1.'''
if 'fromen' in J:
    for k, what in [('BT', 'the big brown wooden logo "BEETLE" becomes "ESCARABAJO" (narrower letters to fit the same width, on one line); "CUP" becomes "COPA"; the small line "COME TOGETHER" becomes "VENID TODOS" and "BEETLE\'s CUP !!" becomes "¡¡COPA ESCARABAJO!!"'),
                    ('CO', 'the big chrome logo "COOL" becomes "GUAY" (four letters G-U-A-Y on one line, same size as COOL); "CUP" becomes "COPA"; "WHO\'s a MOST COOLER ?" becomes "¿QUIÉN ES EL MÁS GUAY?"; "COME COME TOGETHER" becomes "VENID, VENID TODOS"; "the \\"COOL\\" CUP" becomes "la COPA «GUAY»"'),
                    ('TW', 'the big blue lightning logo "THUNDER" / "WIND" becomes "TRUENO" / "Y VIENTO" (two lines, same place and style); "CUP" becomes "COPA"; the small lines become "ELÉCTRICOS", "ALADOS", "MULTICOLAS"; "WIND&THUNDER" / "CUP" at the bottom becomes "VIENTO Y TRUENO" / "COPA"')]:
        f = f'gen_es_{k}.png'; os.path.exists(f) and os.rename(f, f.replace('gen_', 'old2_'))
        gen(f, FROM_EN.format(what=what), [f'gen_en_{k}.png'], '16:9')
    f = 'gen_en_GRADES.png'; os.rename(f, 'old2_en_GRADES.png')
    gen(f, G_EN.format(g='S').replace('read exactly "GRADE S"', 'read exactly "GRADE S", with a gap as wide as a letter between the E and the S'), ['ref_GRADES_top.png'], '21:9')
