"""The curling cups' banners in each language: one sheet of five bands per language (prompt-en.txt makes the English
one; the others redraw its words).  jobs.py LANG -> the prompt for that language, with the English sheet as image 1:

  python3 content/localized/curling/jobs.py es > /tmp/p.txt
  python3 content/localized/tournament/gen.py /tmp/p.txt build/localized-src/curling/es.png --ref build/localized-src/curling/en.png --aspect 5:4

tools/curling_banners.py --make turns the sheets into content/localized/curling/<lang>.png (256 x 200, 128 colours a band).
"""
import sys

EN = ('ROOKIE CUP', 'AMATEUR CUP', 'EXPERT CUP', 'ELITE CUP', 'LEGEND CUP')
NAMES = {
    'es': ('Spanish', ('COPA NOVATO', 'COPA AFICIONADO', 'COPA EXPERTO', 'COPA ÉLITE', 'COPA LEYENDA')),
    'pt-br': ('Brazilian Portuguese', ('COPA NOVATO', 'COPA AMADOR', 'COPA EXPERIENTE', 'COPA ELITE', 'COPA LENDA')),
    'fr': ('French', ('COUPE DÉBUTANT', 'COUPE AMATEUR', 'COUPE EXPERT', 'COUPE ÉLITE', 'COUPE LÉGENDE')),
    'de': ('German', ('NEULINGS-CUP', 'AMATEUR-CUP', 'EXPERTEN-CUP', 'ELITE-CUP', 'LEGENDEN-CUP')),
    'it': ('Italian', ('COPPA NOVIZIO', 'COPPA DILETTANTE', 'COPPA ESPERTO', 'COPPA ÉLITE', 'COPPA LEGGENDA')),
    'ja': ('Japanese', ('ルーキーカップ', 'アマチュアカップ', 'エキスパートカップ', 'エリートカップ', 'レジェンドカップ')),
    'ca': ('Catalan', ('COPA NOVELL', 'COPA AFICIONAT', 'COPA EXPERT', 'COPA ELIT', 'COPA LLEGENDA')),
    'zh-hans': ('Simplified Chinese', ('新手杯', '业余杯', '专家杯', '精英杯', '传奇杯')),
}
PROMPT = '''Image 1 is a sheet of five title banners for a curling tournament in a 1990s PlayStation game: five horizontal bands of the same height, each with a big 3D logo in English and, at the right, a curling stone and a trophy.

Make the {language} version of this sheet. Keep everything exactly as it is (the five bands at the same places and heights, their backgrounds, the stones, the trophies, the colours, the lighting) and replace only the words of each logo, in exactly the same 3D lettering style, material, outline and colours as the logo it replaces:
{lines}

Each new logo stays on one line, starts at the same left margin, and must not touch or cover the curling stone or the trophy: make the letters narrower when the words are longer, never smaller in height than needed. Spell every word exactly as given, with its accents and hyphens. No other text anywhere, and no English left.'''

if __name__ == '__main__':
    language, names = NAMES[sys.argv[1]]
    print(PROMPT.format(language=language, lines='\n'.join(f'{i + 1}. "{e}" becomes "{n}"' for i, (e, n) in enumerate(zip(EN, names)))))
