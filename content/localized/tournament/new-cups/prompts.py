"""The fifteen new cups' banners: Gemini prompts. KEY: (material of the logo, glow)"""
LANGS = ['en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans']
STYLE = {
 'ROOKIE_CUP': 'chunky glossy lime-green jelly letters with a bright yellow outline glow, playful and rounded',
 'CHAMPION_CUP': 'polished blue steel letters with bevelled edges and a white-blue glow',
 'ULTIMATE_CUP': 'faceted purple amethyst crystal letters with a violet glow',
 'MEGA_CUP': 'heavy molten gold letters with glowing red-hot cracks and a crimson glow',
 'VACCINE_CUP': 'clean white and teal glass letters like a medicine capsule, with a soft cyan glow',
 'DATA_CUP': 'letters cut from a green-blue printed circuit board with thin bright traces, with a blue glow',
 'VIRUS_CUP': 'dark magenta corroded letters with spikes and dripping slime, with a sickly pink-purple glow',
 'NATURE_SPIRITS_CUP': 'letters carved from rough tree bark, wrapped in vines and green leaves, with a soft green glow',
 'DEEP_SAVERS_CUP': 'deep-sea blue water letters with ripples and small bubbles, with an aqua glow',
 'NIGHTMARE_SOLDIERS_CUP': 'pale bone letters wrapped in dark purple ghostly mist, with a violet glow',
 'WIND_GUARDIANS_CUP': 'sky-blue and white letters made of clouds and feathers with swirls of wind, with a pale glow',
 'METAL_EMPIRE_CUP': 'grey riveted steel plate letters with bolts and orange rust at the edges, with a cold steel glow',
 'VIRUS_BUSTERS_CUP': 'shining holy gold letters with white light rays and small white feathers, with a warm white glow',
 'DRAGONS_ROAR_CUP': 'dark crimson dragon-scale letters with sharp horn-like spikes and cracks of fire, with a fiery orange glow',
 'JUNGLE_TROOPERS_CUP': 'mossy carved jungle-temple stone letters with tropical leaves and small orange flowers, with a warm amber glow',
}
FAMILY = {k: 'level' for k in list(STYLE)[:4]} | {k: 'attribute' for k in list(STYLE)[4:7]} | {k: 'field' for k in list(STYLE)[7:]}
CUP = dict(zip(LANGS, ['CUP', 'COPA', 'COPA', 'COUPE', 'POKAL', 'COPPA', 'カップ', 'COPA', '杯']))
WORD = {   # the logo word: the cup's name (text/<language>/names.json) without the word for cup
 'en': ['ROOKIE', 'CHAMPION', 'ULTIMATE', 'MEGA', 'VACCINE', 'DATA', 'VIRUS'],
 'es': ['NOVATO', 'CAMPEÓN', 'PERFECTO', 'MEGA', 'VACUNA', 'DATOS', 'VIRUS'],
 'pt-br': ['NOVATO', 'CAMPEÃO', 'PERFEITO', 'MEGA', 'VACINA', 'DADOS', 'VÍRUS'],
 'fr': ['DISCIPLE', 'CHAMPION', 'ULTIME', 'MÉGA', 'VACCIN', 'DONNÉE', 'VIRUS'],
 'de': ['ROOKIE', 'CHAMPION', 'ULTRA', 'MEGA', 'SERUM', 'DATEI', 'VIRUS'],
 'it': ['INTERMEDIO', 'CAMPIONE', 'EVOLUTO', 'MEGA', 'VACCINO', 'DATI', 'VIRUS'],
 'ja': ['成長期', '成熟期', '完全体', '究極体', 'ワクチン', 'データ', 'ウイルス'],
 'ca': ['NOVELL', 'CAMPIÓ', 'PERFECTE', 'MEGA', 'VACUNA', 'DADES', 'VIRUS'],
 'zh-hans': ['成长期', '成熟期', '完全体', '究极体', '疫苗', '数据', '病毒'],
}
FIELDS = ['NATURE SPIRITS', 'DEEP SAVERS', 'NIGHTMARE SOLDIERS', 'WIND GUARDIANS', 'METAL EMPIRE', 'VIRUS BUSTERS', "DRAGON'S ROAR", 'JUNGLE TROOPERS']
FIELDS_JA = ['ネイチャースピリッツ', 'ディープセイバーズ', 'ナイトメアソルジャーズ', 'ウィンドガーディアンズ', 'メタルエンパイア', 'ウイルスバスターズ', 'ドラゴンズロアー', 'ジャングルトルーパーズ']
CAPTION = {
 'level': dict(zip(LANGS, ['COME TOGETHER !! {w} LEVEL ONLY', '¡¡VENID TODOS!! SOLO NIVEL {w}', 'VENHAM TODOS!! SÓ NÍVEL {w}',
     'VENEZ TOUS !! NIVEAU {w} SEULEMENT', 'KOMMT ALLE!! NUR {w}-LEVEL', 'VENITE TUTTI!! SOLO LIVELLO {w}',
     'みんな あつまれ！！ {w}だけ', 'VENIU TOTS!! NOMÉS NIVELL {w}', '大家集合！！仅限{w}'])),
 'attribute': dict(zip(LANGS, ["WHO's FIRST {w} DIGIMON ?", '¿QUIÉN ES EL MEJOR DIGIMON {w}?', 'QUEM É O MELHOR DIGIMON {w}?',
     'QUI EST LE MEILLEUR DIGIMON {w} ?', 'WER IST DAS BESTE {w}-DIGIMON?', 'CHI È IL MIGLIOR DIGIMON {w}?',
     '{w}の いちばんは だれだ？', 'QUI ÉS EL MILLOR DIGIMON {w}?', '谁是最强的{w}数码宝贝？'])),
 'field': dict(zip(LANGS, ['COME TOGETHER !! FIELD CUP', '¡¡VENID TODOS!! COPA DE FIELD', 'VENHAM TODOS!! COPA DE FIELD',
     'VENEZ TOUS !! COUPE DE FIELD', 'KOMMT ALLE!! FIELD-POKAL', 'VENITE TUTTI!! COPPA DI FIELD',
     'みんな あつまれ！！ フィールドカップ', 'VENIU TOTS!! COPA DE FIELD', '大家集合！！领域杯'])),
}
NAME = dict(zip(LANGS, ['English', 'Spanish', 'Brazilian Portuguese', 'French', 'German', 'Italian', 'Japanese', 'Catalan', 'Simplified Chinese']))

def words(key, lang):
    """(logo word, word for cup, caption)"""
    i = list(STYLE).index(key)
    w = WORD[lang][i] if i < 7 else (FIELDS_JA if lang == 'ja' else FIELDS)[i - 7]
    return w, CUP[lang], CAPTION[FAMILY[key]][lang].format(w=w)

MASTER = '''Images 1, 2 and 3 are tournament title banners from a 1990s PlayStation game. Make a new banner of the same family for another cup, in exactly their style: late-1990s pre-rendered 3D logo art, low-resolution and slightly soft, a big textured logo word, a smaller word "CUP" in a matching simpler style overlapping or beside it, and one small caption in plain bold capitals, all on a flat dark navy background (RGB 0,0,40: it is transparent in the game, so keep it perfectly flat, no gradient, no texture, no vignette, no frame).

Large main logo: "{w}" as {style}. {two}Secondary cup logo: "{c}". Small caption text, in small plain bold capitals of one matching colour, on one or two lines: "{cap}".

Spell every word exactly as given. No other text, no pictures of characters or creatures, no trophy, no border, no watermark. The lettering fills most of the frame like in the references, slightly off-centre and informal, and stays clear of the edges. The picture will be shown at 256x128 pixels: keep the letters thick and readable, the caption not too small.'''
LOCAL = '''Use case: text-localization. Image 1 is the edit target: our English tournament banner for a 1990s PlayStation game. Make its {name} version, using ONLY the exact wording below. Keep the framing, the composition, the materials, colours, outlines, texture, glow and the soft low-resolution pre-rendered look, and the flat dark navy background (RGB 0,0,40, perfectly flat). Replace every English word, including the small caption. Spell accents and characters exactly as given. No invented words, no watermark, no border.

Large main logo, in exactly the same material and style as image 1's (narrower letters if it is longer), reads exactly "{w}" and nothing else{lines}; if image 1's logo has two lines, both are replaced. Secondary cup logo: "{c}". Small caption text: "{cap}".

Keep the lettering hierarchy, thick and readable at 256x128 pixels, clear of the edges.'''

SPLIT_JA = {'ネイチャースピリッツ': 'ネイチャー / スピリッツ', 'ディープセイバーズ': 'ディープ / セイバーズ', 'ナイトメアソルジャーズ': 'ナイトメア / ソルジャーズ',
            'ウィンドガーディアンズ': 'ウィンド / ガーディアンズ', 'メタルエンパイア': 'メタル / エンパイア', 'ウイルスバスターズ': 'ウイルス / バスターズ',
            'ドラゴンズロアー': 'ドラゴンズ / ロアー', 'ジャングルトルーパーズ': 'ジャングル / トルーパーズ'}
def lines(w):
    if w in SPLIT_JA: return f', on two lines: {SPLIT_JA[w]} (no Latin letter may remain anywhere in the picture)'
    return ', on two lines as in image 1' if ' ' in w else ', on one line'

REDO = '''Image 1 is the English banner of a tournament cup from a 1990s PlayStation game. Draw the {name} banner of the same cup, from scratch: the same materials, colours, outlines, glow, layout, soft low-resolution pre-rendered look and flat dark navy background (RGB 0,0,40, perfectly flat) as image 1, but with entirely new lettering. Do not keep, trace or mix in any letter of image 1: every English word of image 1 is gone.

Large main logo, in the material of image 1's logo, reads exactly "{w}"{lines}: {spell}. Secondary cup logo, in the style of image 1's word CUP, reads exactly "{c}": {cspell}. The word "CUP" must not appear. Small caption text in plain bold: "{cap}".

Nothing else is written. Thick lettering, readable at 256x128 pixels, clear of the edges. No watermark, no border.'''
def spell(w):
    s = w.replace(' ', '')
    return f'{len(s)} characters, {" ".join(s)}'

FRESH = '''Images 1, 2 and 3 are tournament title banners from a 1990s PlayStation game. Make a new banner of the same family for another cup, in {name}, in exactly their style: late-1990s pre-rendered 3D logo art, low-resolution and slightly soft, a big textured logo word, a smaller secondary word in a matching simpler style overlapping or beside it, and one small caption in plain bold letters, all on a flat dark navy background (RGB 0,0,40: perfectly flat, no gradient, no texture, no vignette, no frame).

Large main logo reads exactly "{w}" ({spell}), as {style}. Secondary logo reads exactly "{c}" ({cspell}). Small caption text, in small plain bold letters of one matching colour, on one or two lines: "{cap}".

Spell every word exactly as given, letter by letter; the English words "DATA", "VACCINE", "ULTIMATE" and "CUP" must not appear unless given above. No other text, no pictures of characters or creatures, no trophy, no border, no watermark. The lettering fills most of the frame, slightly off-centre and informal, and stays clear of the edges. It will be shown at 256x128 pixels: keep the letters thick and readable, the caption not too small.'''
