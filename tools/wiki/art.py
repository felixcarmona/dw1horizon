"""Small locally generated SVG portraits; no disc pixels or remote hosts."""
from html import escape
import re

# Original vector portraits for native partners which predate the drawn-icon set.
# Shape families share strokes; species keep their own palette and silhouette cues.
NATIVE = {
 1:('blob','#34334b','ears'),2:('blob','#ef99b4','ears'),3:('dino','#f5a739','claws'),
 4:('blob','#64b895','fin'),5:('dino','#eb9037','helmet'),6:('humanoid','#4e455c','bat'),
 7:('serpent','#4ca8dc','wings'),8:('dino','#d95d5e','spikes'),9:('flame','#f28132','fire'),
 10:('serpent','#61b3c7','horn'),11:('blob','#7fa74c','snail'),12:('dino','#586aa3','metal'),
 13:('orb','#e5ac47','fists'),14:('bear','#e5bc49','bear'),15:('blob','#df6a76','spikes'),
 16:('blob','#f7d694','horn'),17:('wolf','#8393c9','horn'),18:('beast','#c44f5c','stripes'),
 19:('beetle','#6b83b6','horn'),20:('humanoid','#f1e0be','wings'),21:('bird','#ef792f','fire'),
 22:('wolf','#a8d0ec','stripes'),23:('bear','#e6f1f5','bear'),24:('whale','#92b7cb','fin'),
 25:('plant','#c09c6a','leaves'),26:('dino','#e2cfa5','bones'),27:('orb','#94a4ba','metal'),
 28:('alien','#d1baac','tentacles'),29:('blob','#97d5e4','plain'),30:('blob','#f6e1c7','ears'),
 31:('blob','#dfab68','wings'),32:('worm','#e9d751','stripes'),33:('horse','#e4e4de','horn'),
 34:('humanoid','#73ab60','club'),35:('snail','#72b5ad','shell'),36:('horse','#b88562','metal'),
 37:('ghost','#e9edf5','ghost'),38:('beast','#b8a4ce','drill'),39:('blob','#d6b044','swirl'),
 40:('humanoid','#b8bdc5','metal'),41:('orb','#bebecb','metal'),42:('beast','#bf9866','glasses'),
 43:('blob','#e5e2d0','hair'),44:('plant','#e7c4d0','leaves'),45:('bird','#eea5c2','feathers'),
 46:('plant','#8cbe8c','flower'),47:('dino','#a6b4b7','horn'),48:('humanoid','#ddaa54','mane'),
 49:('fish','#7ab8bd','fin'),50:('bird','#efefdf','crest'),51:('beetle','#d67a62','pincers'),
 52:('beast','#eee1bc','hair'),53:('orb','#d38d65','glasses'),54:('serpent','#bd7d55','metal'),
 55:('orb','#eca9c4','wings'),56:('egg','#f0e4ca','egg'),57:('bird','#b3a5ce','penguin'),
 58:('humanoid','#a1aa8d','ninja'),59:('bird','#e9b246','fire'),60:('beetle','#dab954','pincers'),
 61:('serpent','#e5b447','crest'),
}


def drawn(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    palette = {}
    index = 1
    while lines[index] != 'idle':
        symbol, color = lines[index].split()
        if not re.fullmatch('[0-9a-fA-F]{6}', color):
            raise ValueError('Invalid drawn-icon color')
        palette[symbol] = '#' + color
        index += 1
    grid = lines[index + 1:index + 17]
    if len(grid) != 16 or any(len(row) != 16 for row in grid):
        raise ValueError('Invalid drawn-icon grid')
    cells = ''.join(f'<path fill="{color}" d="' + ''.join(f'M{x} {y}h1v1h-1z' for y, row in enumerate(grid) for x, c in enumerate(row) if c == symbol) + '"/>' for symbol, color in palette.items())
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" shape-rendering="crispEdges">' + cells + '</svg>'


def native(ident):
    family, color, cue = NATIVE[ident]
    shapes = {
      'blob':'M18 48Q16 25 32 24Q48 25 47 48Q32 58 18 48Z',
      'orb':'M16 37A16 16 0 1 0 48 37A16 16 0 1 0 16 37Z',
      'dino':'M17 53L23 40L21 29L28 18L44 20L50 30L42 34L36 31L37 43L48 52L37 54L30 48L26 54Z',
      'humanoid':'M17 51L22 35L25 29L23 22L29 15L38 18L40 26L36 31L43 35L49 48L42 49L36 41L39 55L32 53L29 43L26 55Z',
      'serpent':'M11 47Q7 35 20 33L39 39Q44 40 41 31L35 27L36 16L46 15L52 25L46 33Q56 47 43 53L21 46Q14 42 15 50Z',
      'bear':'M18 52L18 32Q13 24 18 20Q22 17 26 23L38 23Q43 17 48 21Q52 27 46 32L47 52L37 54L31 47L28 54Z',
      'wolf':'M11 52L18 36L25 30L25 16L34 24L43 18L44 30L51 35L45 41L34 38L37 51L30 54L23 45L19 54Z',
      'beast':'M11 51L17 34L25 26L23 18L31 21L40 19L44 29L48 34L43 43L48 53L37 54L31 47L24 54Z',
      'beetle':'M18 51L12 40L19 34L19 24L27 19L38 19L45 27L44 37L53 43L47 51L39 44L38 55L26 55L24 44Z',
      'bird':'M13 51L20 34L26 30L25 20L33 15L42 22L49 25L42 29L39 36L46 50L36 53L30 48L24 54Z',
      'whale':'M7 42L13 29Q33 19 49 29L57 38L46 48L29 51L17 46L7 51Z',
      'plant':'M19 54L22 39L19 30L26 25L38 25L45 34L40 43L45 53L35 54L30 47L26 54Z',
      'alien':'M20 51L25 33Q11 22 22 14Q33 8 44 17Q49 27 38 33L44 49L38 54L32 43L27 54Z',
      'horse':'M10 52L18 35L27 29L29 18L38 15L46 23L52 27L44 34L35 32L37 49L32 55L27 45L22 54Z',
      'snail':'M9 51L16 41L23 38A17 17 0 1 1 47 48L54 53Z',
      'ghost':'M14 53L19 28Q31 11 44 27L50 53L41 49L34 55L25 49L18 55Z',
      'worm':'M14 51Q9 39 19 38Q12 28 23 27Q20 16 32 17L41 27L36 35L44 43L38 54Z',
      'fish':'M8 29L23 35Q37 17 48 29L54 41L43 50L26 43L11 49L18 39Z',
      'flame':'M13 53L17 33L23 39L27 10L36 29L43 18L46 38L53 49L41 55Z',
      'egg':'M15 46Q14 34 29 14Q35 10 42 23Q53 41 48 50Q33 60 15 46Z',
    }
    extra = {
      'ears':'<path d="M23 27L18 9L29 24M36 25L46 9L42 29"/>',
      'horn':'<path fill="#f3e9cb" d="M29 24L32 5L38 24Z"/>',
      'wings':'<path fill="#f4ede4" d="M22 35L3 20L7 44L21 46M40 35L61 19L57 44L43 47Z"/>',
      'bat':'<path fill="#706480" d="M22 33L4 16L6 43L13 36L21 44M40 33L59 16L58 43L50 36L43 44Z"/>',
      'helmet':'<path fill="#8f6b4d" d="M21 28L25 14L32 21L45 13L49 31L41 33L37 28Z"/>',
      'metal':'<path fill="#bac6d3" d="M21 36L30 31L43 37L39 47L27 48Z"/><path d="M34 35L34 45M39 23L45 22"/>',
      'spikes':'<path fill="#f5d894" d="M20 36L9 28L18 44M27 24L24 13L34 24M38 27L48 13L45 32"/>',
      'fin':'<path fill="#eeb7a1" d="M24 26L29 12L41 30M20 42L8 35L10 47"/>',
      'fists':'<path fill="#e7d5a8" d="M14 36L5 32L4 42L18 45M47 36L59 31L60 43L46 46Z"/>',
      'bear':'<ellipse fill="#fff1d7" cx="33" cy="39" rx="10" ry="9"/>',
      'stripes':'<path d="M20 34L29 38M33 25L36 29M27 45L34 47"/>',
      'leaves':'<path fill="#61a16e" d="M30 26Q7 6 10 25L28 31M33 25Q47 2 55 14L38 30Z"/>',
      'flower':'<path fill="#dc78ab" d="M21 24L17 15L27 13L33 6L40 14L49 13L47 24L38 27Z"/><circle fill="#edc465" cx="33" cy="20" r="5"/>',
      'bones':'<path fill="none" stroke="#685a50" d="M25 36L40 40M25 42L40 46M32 32L30 50"/>',
      'tentacles':'<path fill="none" d="M25 43Q9 44 13 56M32 42Q27 48 30 58M37 41Q49 45 50 56"/>',
      'club':'<path stroke="#ba9a6a" stroke-width="7" d="M46 44L54 15"/>',
      'shell':'<circle fill="#db99a6" cx="35" cy="35" r="17"/><path fill="none" d="M35 26Q47 28 42 40Q29 47 27 33Q29 28 35 31"/>',
      'ghost':'<path fill="#333044" d="M25 33L28 28L31 33L28 38ZM37 33L40 28L43 33L40 38Z"/><path d="M28 44L38 44"/>',
      'drill':'<path fill="#ddd6c3" d="M36 27L55 17L46 33Z"/><path d="M47 23L48 28"/>',
      'swirl':'<path fill="none" d="M21 46Q7 34 25 28Q18 16 30 15Q43 18 37 28Q53 37 40 46Z"/>',
      'glasses':'<path fill="#353449" d="M20 29L31 29L31 36L20 36ZM34 29L45 29L45 36L34 36Z"/>',
      'hair':'<path stroke-width="2" d="M22 25L18 13M27 24L27 10M33 24L36 9M38 26L47 15"/>',
      'mane':'<path fill="#b97037" d="M19 31L17 19L25 20L31 9L38 17L47 17L47 31L40 35L34 26L28 34Z"/>',
      'crest':'<path fill="#cf7275" d="M26 22L22 10L30 13L35 6L40 18L46 18L42 25Z"/>',
      'pincers':'<path fill="none" stroke-width="5" d="M24 26L16 13L24 5M39 26L47 13L39 5"/>',
      'ninja':'<path fill="#536752" d="M20 22L43 22L43 32L20 32Z"/><path fill="#e6dfbc" d="M23 26H39V29H23Z"/>',
      'egg':'<path fill="#60614d" d="M25 33L35 27L43 33L42 43L30 48L22 41Z"/>',
      'penguin':'<ellipse fill="#f6ece2" cx="31" cy="42" rx="10" ry="13"/>',
      'fire':'<path fill="#ffd070" d="M23 47L26 31L31 36L35 20L40 40L45 35L43 49Z"/>',
      'feathers':'<path fill="#b9c7e8" d="M24 20L21 10L31 15M36 20L41 9L43 23"/>',
      'claws':'<path fill="#fff5dc" d="M18 52L23 47L24 54ZM38 51L43 47L47 54Z"/>',
      'plain':'', 'snail':'<path d="M24 31L19 16M37 30L43 17"/>',
    }
    eyes = '' if cue in ('glasses', 'ghost', 'ninja') else '<path stroke="#292838" stroke-width="3" d="M29 29v3M40 29v3"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><g stroke="#383344" stroke-width="2.3" stroke-linejoin="round" stroke-linecap="round" fill="{color}"><path d="{shapes[family]}"/>{extra[cue]}{eyes}</g></svg>'


def portrait(ident, files):
    source = files.get(f'content/icons/{ident}.txt')
    if source:
        return drawn(source.decode())
    if ident in NATIVE:
        return native(ident)
    raise ValueError(f'Species {ident} needs a reviewed local wiki portrait')
