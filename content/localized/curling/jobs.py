"""The curling cups' names as art in each language: one sheet of five names on flat magenta per language (prompt-en.txt makes the English
one; the others redraw its words).  jobs.py LANG -> the prompt for that language, with the English sheet as image 1:

  python3 content/localized/curling/jobs.py es > /tmp/p.txt
  python3 content/localized/tournament/gen.py /tmp/p.txt build/localized-src/curling/es.png --ref build/localized-src/curling/en.png --aspect 5:4

tools/curling_banners.py --make turns the sheets into content/localized/curling/<lang>.png (256 x 200, 128 colours a band, the magenta not drawn).
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
PROMPT = '''Image 1 is a sheet of five title logos for a curling tournament in a 1990s PlayStation game: five names in English, one under the other, in fat, rounded, hand-drawn cartoon letters with a thick dark outline, on a perfectly flat pure magenta (#FF00FF) background that will be removed.

Make the {language} version of this sheet. Keep everything exactly as it is (five names one under the other at the same places and heights, each in the same colour, the same letter style, shine and outline, the same flat pure magenta background) and change only the words:
{lines}

Each name stays on one single line, centred, with a clear margin of magenta on every side and between names: make the letters narrower when the words are longer, never smaller in height. The background stays one flat, uniform pure magenta with no line, shadow, glow or texture. Nothing else: no icon, no frame, no other text. Spell each name exactly as given, accents included. All five names change, the fourth and the fifth too: no English word is left on the sheet.
'''

if __name__ == '__main__':
    language, names = NAMES[sys.argv[1]]
    print(PROMPT.format(language=language, lines='\n'.join(f'{i + 1}. "{e}" becomes "{n}"' for i, (e, n) in enumerate(zip(EN, names)))))
