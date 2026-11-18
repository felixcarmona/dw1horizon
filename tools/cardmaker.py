#!/usr/bin/env python3
"""Card maker: new collectible cards from kept art, so a change of frame, colours or font is one re-run.

The card of a species is two things kept apart:
  - its ART, generated once and kept as it came: content/cards/art/<id>-<name>.png (+ .json with the prompt),
  - its FRAME, drawn here: the border and corner ornaments in the colour of the species' element, the number and the
    name in our card font (tools/localize/textures/cards-cups/cardfont.py), on the 150x180 card of the game.
Changing the frame, the colours or the font means running `render` again: the art is never touched.

Usage (from the repository root, with the repository's venv for the reference render):
  cardmaker.py ref SPECIES OUT.png          reference sheet of the species' 3D model (what the generator sees)
  cardmaker.py art KEY [--new-bg] [--new-model]  art = our render of the species' 3D model over a creature-free background
                                            generated with Gemini (GEMINI_API_KEY); parts kept as art/<key>-model.png, -bg.png
  cardmaker.py gen KEY                      the older way: Gemini re-imagines the creature from the reference sheet
  cardmaker.py render [KEY ...]             compose the cards of content/cards/new.json into build/cards/
                                            (PNG preview, 8 bpp indices .idx and 15-bit CLUT .clut per card)
  cardmaker.py prompt KEY                   print the prompt, change nothing

content/cards/new.json lists the cards: {"key", "number", "species", "with": [species...], "rarity", "merit",
"scene"?, "pose"?, "frame"?, "style"?}. A species may have any number of cards (one per key), and a card may show several Digimon:
`species` names it, `with` adds the others to the art. Art is content/cards/art/<key>.png.
SPECIES is an id or a name of content/species. Standard library plus tools/image.py (cv2 only to decode non-PNG).
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))

import argparse
import base64
import glob
import json
import os
import struct
import subprocess
import sys
import urllib.request

from tools.image import Image

ROOT = _ImagePath(__file__).resolve().parents[1]
ART = ROOT / 'content' / 'cards' / 'art'
CARDS = ROOT / 'content' / 'cards' / 'new.json'
OUT = ROOT / 'build' / 'cards'
W, H = 150, 180
WIN = (5, 5, 144, 157)            # the art window, inclusive: 140 x 153
GEMINI = 'gemini-3-pro-image-preview'

# Frame colours, one per element, as the original cards do (sampled by eye from them, redrawn here):
# line = the coloured rule round the art and the name bar, dark = the thin shadow rule inside it,
# tint = the card's margin, bar = the fill of the name bar.
FRAMES = {
    'red':    dict(line=(232, 56, 48),  dark=(112, 24, 24), tint=(248, 232, 216), bar=(232, 56, 48)),
    'blue':   dict(line=(40, 96, 160),  dark=(16, 48, 80),  tint=(208, 220, 240), bar=(40, 96, 160)),
    'green':  dict(line=(72, 120, 32),  dark=(32, 56, 16),  tint=(224, 240, 208), bar=(72, 120, 32)),
    'purple': dict(line=(152, 96, 200), dark=(72, 48, 96),  tint=(236, 224, 244), bar=(152, 96, 200)),
    'orange': dict(line=(248, 152, 48), dark=(120, 72, 24), tint=(248, 236, 216), bar=(224, 136, 40)),
    'yellow': dict(line=(200, 152, 48), dark=(96, 72, 24),  tint=(244, 232, 184), bar=(200, 152, 48)),
}
# species specialty (first slot) -> frame colour and the scene the art is set in
ELEMENTS = {
    'fire':    ('red',    'a blazing volcanic landscape, embers and warm orange-red light'),
    'water':   ('blue',   'a bright underwater scene with soft light from above, bubbles and coral'),
    'ice':     ('blue',   'a glittering snowy glacier under a pale blue sky'),
    'plant':   ('green',  'a lush forest clearing with large leaves and soft green light'),
    'wind':    ('green',  'an open sky with drifting clouds and a distant green landscape'),
    'earth':   ('orange', 'a rocky canyon with sandstone cliffs under a warm sky'),
    'metal':   ('orange', 'a gleaming machine workshop with brass gears and steel plates'),
    'dark':    ('purple', 'a dusk gothic scene, purple sky and ruined towers'),
    'thunder': ('yellow', 'a stormy sky with golden lightning bolts in the distance'),
    'light':   ('yellow', 'a radiant heavenly sky with soft golden clouds'),
    'battle':  ('red',    'a dramatic arena with dust and warm light'),
}
DEFAULT_ELEMENT = 'battle'
# how the creature is rendered: 'faithful' (keeps the model's own look) is the default
STYLES = {
    'exact': (
        "The attached image is a render of the real in-game 3D model of the character. USE THIS EXACT CHARACTER as the "
        "subject: copy its DESIGN faithfully, with its identical faceted low-polygon shapes, proportions, pixel-art texture "
        "details, colours, markings, eyes and claws. The reference shows the model in a neutral rest pose: do NOT copy "
        "that pose, re-pose the character freely. Do not redesign, smooth, round off or re-draw it in another "
        "style: it must look like the same model, only now standing inside the scene, lit consistently with it and "
        "casting a soft shadow on the ground. Only the scene around it is yours to paint, and the scene MUST be in the SAME "
        "visual style as the character: a late-1990s PlayStation 3D game environment made of flat-shaded low-polygon "
        "facets with small pixelated texture maps, blocky angular rocks, trees and terrain, plain colour areas, crisp "
        "edges. NOT a painting: no brush strokes, no soft airbrushed gradients, no glow, no sparks or embers, no "
        "smoke, no fog, no bokeh, no glossy or wet surfaces. The character must look native to the scene, "
        "as if both were rendered by the same game engine. The character fills about 60% of the image height, "
        "with the scene visible around it."),
    'faithful': (
        "Re-imagine each as a polished, richly detailed, softly shaded 3D-rendered illustration, friendly and "
        "heroic. Keep the chibi proportions of the models (big head, small body)."),
    'lowpoly': (
        "KEEP the low-poly look: the visible flat polygon facets and angular, chunky shapes of the model, as in a "
        "late-1990s PlayStation 3D game, lit with simple flat shading and a few clean highlights. Make it look like a "
        "crisp render from the game's own engine, NOT a glossy modern illustration. Keep the background in the same "
        "era: simple, slightly stylised, hand-painted texture-map look, with blocky rocks and plain colour areas, no "
        "bokeh, no lens effects, no floating glowing particles, no shiny wet surfaces, no cinematic depth of field."),
    'smooth': (
        "Do NOT reproduce the polygon facets or flat shading: render smooth, rounded, organic forms with soft skin, "
        "gentle shading and fine detail, as a polished high-quality 3D illustration."),
}


def species_of(key):
    for f in sorted(glob.glob(str(ROOT / 'content' / 'species' / '*.json'))):
        d = json.load(open(f))
        if str(d['id']) == str(key) or d['name'].lower() == str(key).lower():
            return d
    raise SystemExit(f'no species {key!r} in content/species')


def element_of(sp):
    for s in sp.get('specialties') or []:
        if s in ELEMENTS:
            return s
    return DEFAULT_ELEMENT


def card_of(key):
    for c in json.load(open(CARDS))['cards']:
        if c['key'] == key:
            return c
    raise SystemExit(f'no card {key!r} in content/cards/new.json')


def art_path(card):
    return ART / f"{card['key']}.png"


# ---------------------------------------------------------------- prompt and generation
def prompt_for(card):
    sp = species_of(card['species'])
    others = [species_of(k) for k in card.get('with', [])]
    scene = card.get('scene') or ELEMENTS[element_of(sp)][1]
    names = ' and '.join([sp['name']] + [o['name'] for o in others])
    many = bool(others)
    return (
        f"Illustration for a collectible Digimon trading card showing {names}.\n"
        f"The attached image{'s are reference sheets' if many else ' is a reference sheet'} of the 3D game "
        f"model{'s' if many else ''} in three-quarter view{', in the order named' if many else ''}. "
        "They are low-polygon PlayStation models: keep each design EXACTLY (proportions, head shape, eyes, claws, "
        "colours and markings). " + STYLES[card.get('style', 'exact')] + "\n"
        f"Pose: {card.get('pose') or 'a dynamic, characteristic pose of your own choice that suits this creature (leaping, attacking, roaring, flying, running, playing...), different from the neutral rest pose of the reference, with a fresh camera angle'}, full body visible from head to feet. "
        f"Setting: {scene}, painterly and colourful, with depth behind the creature and a clear single subject.\n"
        "Composition: the creature centred, filling about 70% of the height, with comfortable margins on every side "
        "(the card crops the edges). Soft, even light. No light beams, no god rays, no haze, no glare.\n"
        "Strictly: no text, no letters, no numbers, no logos, no watermark, no border, no card frame, no UI. "
        "Square image."
    )


def b64(path):
    return base64.b64encode(open(path, 'rb').read()).decode()


def generate(card, refs):
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        raise SystemExit('GEMINI_API_KEY is not set (source ~/.zshrc)')
    prompt = prompt_for(card)
    parts = [{"text": prompt}] + [{"inline_data": {"mime_type": "image/png", "data": b64(r)}} for r in refs]
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1", "imageSize": "2K"}}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI}:generateContent",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    out = art_path(card)
    cand = r['candidates'][0]
    if 'parts' not in cand.get('content', {}):
        raise SystemExit('the generator refused: %s' % cand.get('finishReason'))
    for p in cand['content']['parts']:
        d = p.get('inline_data') or p.get('inlineData')
        if d:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(base64.b64decode(d['data']))
            out.with_suffix('.json').write_text(json.dumps(
                {"key": card['key'], "species": card['species'], "with": card.get('with', []), "model": GEMINI,
                 "prompt": prompt, "reference": "3D model reference sheet of each species (cardmaker.py ref)"},
                indent=1) + '\n')
            return out
        if 'text' in p:
            print(p['text'])
    raise SystemExit('the generator returned no image')


def model_file(sp):
    name = sp['model']['name']
    hits = glob.glob(str(ROOT / 'extracted' / 'CHDAT' / 'MMD*' / f'{name}.MMD')) + \
        glob.glob(str(ROOT / 'content' / 'models' / '**' / f'{name}.MMD'), recursive=True)
    if not hits:
        raise SystemExit(f"no model file {name}.MMD for {sp['name']}")
    return hits[0]


def reference(sp, out):
    cmd = [sys.executable, str(ROOT / 'tools' / 'animstudio.py'), 'sheet', str(out),
           f"{model_file(sp)}:{sp['id']}", '--slot', '0', '--panels', 'mesh:three,mesh:front,mesh:side',
           '--size', '420', '--ticks', '0']
    subprocess.run(cmd, check=True, cwd=ROOT)


# ---------------------------------------------------------------- the model itself
def render_model(sp, size=1800, view='three'):
    """RGBA render of the species' textured 3D model at rest, drawn twice (on black and on white) so the
    silhouette is exact; the result is cropped to the creature."""
    import numpy as np
    sys.path.insert(0, str(ROOT / 'tools'))
    import animstudio as A
    mod = A.Model(f"{model_file(sp)}:{sp['id']}", 0)
    panel = A.Panel(mod, 'mesh', view, size)
    pose, _ = mod.pose(0)
    shots = []
    for bg in ((0, 0, 0), (255, 255, 255)):
        img = A.Image.new('RGB', (size, size), bg)
        panel.mesh(img, pose, 1.0)
        shots.append(np.asarray(img, np.int32))
    alpha = 255 - np.abs(shots[1] - shots[0]).max(axis=2)
    a = np.clip(alpha, 0, 255).astype(np.uint8)
    rgb = np.where(a[..., None] > 0, shots[0] * 255 // np.maximum(a[..., None], 1), 0).clip(0, 255).astype(np.uint8)
    out = np.dstack([rgb, a])
    ys, xs = np.nonzero(a > 8)
    return A.Image.fromarray(out[ys.min():ys.max() + 1, xs.min():xs.max() + 1], 'RGBA')


def model_path(card, k=None):
    return ART / f"{card['key']}-model{'' if k is None else '-%d' % k}.png"


def bg_path(card):
    return ART / f"{card['key']}-bg.png"


def bg_prompt(card):
    sp = species_of(card['species'])
    scene = card.get('scene') or ELEMENTS[element_of(sp)][1]
    return (
        f"Background scene for a collectible trading card: {scene}. Painterly, colourful, late-1990s 3D-game look with "
        "simple blocky shapes and hand-painted textures. NO creature, NO character, NO animal, NO person in the image. "
        "The middle and lower centre of the image is an empty, open ground area where a character will be placed later; "
        "the horizon sits at about 55% of the height. Soft, even light, no light beams, no haze, no glare. "
        "Strictly: no text, no letters, no numbers, no logos, no border, no frame. Square image.")


def generate_bg(card):
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        raise SystemExit('GEMINI_API_KEY is not set (source ~/.zshrc)')
    prompt = bg_prompt(card)
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1", "imageSize": "2K"}}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI}:generateContent",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    for p in r['candidates'][0]['content']['parts']:
        d = p.get('inline_data') or p.get('inlineData')
        if d:
            bg_path(card).parent.mkdir(parents=True, exist_ok=True)
            bg_path(card).write_bytes(base64.b64decode(d['data']))
            bg_path(card).with_suffix('.json').write_text(json.dumps({"key": card['key'], "model": GEMINI, "prompt": prompt}, indent=1) + '\n')
            return
    raise SystemExit('the generator returned no image')


def build_art(card, regen_bg=False, regen_model=False):
    """art/<key>.png = background + soft shadow + the species' model render(s) (one per Digimon of the card)."""
    ART.mkdir(parents=True, exist_ok=True)
    species = [card['species']] + card.get('with', [])
    for k, sp_key in enumerate(species):
        mp = model_path(card, k or None)
        if regen_model or not mp.exists():
            render_model(species_of(sp_key)).save(str(mp))
    if regen_bg or not bg_path(card).exists():
        generate_bg(card)
    bg = Image.open(bg_path(card)).convert('RGB')
    S = bg.size[0]
    canvas = bg.convert('RGBA')
    n = len(species)
    for k in range(n):
        m = Image.open(model_path(card, k or None)).convert('RGBA')
        hmax = S * (0.70 if n == 1 else 0.58)
        wmax = S * (0.78 if n == 1 else 0.46)
        sc = min(hmax / m.size[1], wmax / m.size[0])
        m = m.resize((round(m.size[0] * sc), round(m.size[1] * sc)), Image.Resampling.LANCZOS)
        cx = S * (0.5 if n == 1 else (0.3 + 0.4 * k / (n - 1)))
        foot = S * 0.90
        x, y = round(cx - m.size[0] / 2), round(foot - m.size[1])
        # soft contact shadow: the silhouette squashed flat under the feet, blurred by successive halvings
        sh = Image.new('RGBA', (m.size[0], max(8, m.size[1] // 7)), (0, 0, 0, 0))
        al = m.getchannel('A').resize(sh.size, Image.Resampling.LANCZOS)
        sh.putalpha(Image.frombytes('L', al.size, bytes(v * 110 // 255 for v in al.tobytes())))
        sh = sh.resize((sh.size[0] // 4, sh.size[1] // 4), Image.Resampling.LANCZOS).resize(sh.size, Image.Resampling.BICUBIC)
        canvas.alpha_composite(sh, (x, round(foot - sh.size[1] * 0.6)))
        canvas.alpha_composite(m, (x, y))
    canvas.convert('RGB').save(str(art_path(card)))
    return art_path(card)


# ---------------------------------------------------------------- frame
DIGITS = {
    '0': '+###+/##.##/##.##/##.##/##.##/##.##/+###+', '1': '.##/###/.##/.##/.##/.##/####',
    '2': '+###+/##.##/...##/..##+/.##../##.../#####', '3': '####+/...##/...##/.###+/...##/##.##/+###+',
    '4': '...##/..###/.####/##.##/#####/...##/...##', '5': '#####/##.../####+/...##/...##/##.##/+###+',
    '6': '+###+/##.../####+/##.##/##.##/##.##/+###+', '7': '#####/...##/..##./.##../.##../.##../.##..',
    '8': '+###+/##.##/##.##/+###+/##.##/##.##/+###+', '9': '+###+/##.##/##.##/+####/...##/...##/+###+',
}


def text_mask(text):
    """Bold card font as {(x, y): 1.0 | 0.5} and its width; names by cardfont, digits by DIGITS."""
    sys.path.insert(0, str(ROOT / 'tools' / 'localize' / 'textures' / 'cards-cups'))
    import cardfont
    m, x = {}, 0
    for i, ch in enumerate(text):
        rows = DIGITS[ch].split('/') if ch in DIGITS else cardfont.G[ch]
        w = max(len(r) for r in rows)
        top = 1 if ch in DIGITS else 0
        for y, r in enumerate(rows):
            for dx, c in enumerate(r):
                if c in '#+':
                    m[(x + dx, y + top)] = 1.0 if c == '#' else 0.5
        x += w + (1 if i < len(text) - 1 else 0)
    return m, x


def draw_frame(card, spec, number, name):
    f = FRAMES[spec]
    im = card
    def rect(x0, y0, x1, y1, col):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                im.putpixel((x, y), col)
    rect(0, 0, W - 1, H - 1, f['tint'])
    # coloured rule + dark rule round the art window
    x0, y0, x1, y1 = WIN
    rect(x0 - 2, y0 - 2, x1 + 2, y1 + 3, f['line'])
    rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1, f['dark'])
    # name bar
    rect(3, 162, 146, 176, f['bar'])
    rect(3, 162, 146, 162, f['line'])
    rect(3, 176, 146, 176, f['dark'])
    rect(3, 163, 146, 163, tuple(min(255, c + 60) for c in f['bar']))
    # corner ornaments: filled square top left, small stair of squares bottom right
    rect(0, 0, 9, 9, f['line']); rect(0, 9, 9, 9, f['dark']); rect(9, 0, 9, 9, f['dark'])
    return im


def draw_stair(im, spec):
    """The three small squares in the art's bottom right corner: drawn over the art, after it is pasted."""
    f = FRAMES[spec]
    for (sx, sy) in ((133, 152), (140, 145), (140, 152)):
        for y in range(sy, sy + 6):
            for x in range(sx, sx + 6):
                edge = x in (sx, sx + 5) or y in (sy, sy + 5)
                im.putpixel((x, y), f['tint'] if edge else f['line'])


def put_text(im, x, y, text, ink=(255, 255, 255), shadow=(40, 24, 24)):
    m, w = text_mask(text)
    for (gx, gy), a in m.items():
        sx, sy = x + gx + 1, y + gy + 1
        if 0 <= sx < W and 0 <= sy < H:
            im.putpixel((sx, sy), shadow)
    for (gx, gy), a in m.items():
        px, py = x + gx, y + gy
        if 0 <= px < W and 0 <= py < H:
            bg = im.getpixel((px, py))
            im.putpixel((px, py), tuple(round(bg[i] * (1 - a) + ink[i] * a) for i in range(3)))
    return w


def compose(card_def, number):
    sp = species_of(card_def['species'])
    art = Image.open(art_path(card_def)).convert('RGB')
    x0, y0, x1, y1 = WIN
    ww, hh = x1 - x0 + 1, y1 - y0 + 1
    aw, ah = art.size
    # cover-crop the art to the window's proportions, centred a little above the middle
    ch = round(aw * hh / ww)
    if ch <= ah:
        top = round((ah - ch) * 0.4)
        art = art.crop((0, top, aw, top + ch))
    else:
        cw = round(ah * ww / hh)
        left = (aw - cw) // 2
        art = art.crop((left, 0, left + cw, ah))
    art = art.resize((ww, hh), Image.Resampling.LANCZOS)
    card = Image.new('RGB', (W, H), (0, 0, 0))
    spec = card_def.get('frame') or ELEMENTS[element_of(sp)][0]
    draw_frame(card, spec, number, sp['name'])
    card.paste(art, (x0, y0))
    draw_stair(card, spec)
    # number left, name centred in the rest of the bar
    put_text(card, 9, 165, '%02d' % number)
    m, tw = text_mask(sp['name'])
    put_text(card, max(34, round(90 - tw / 2)), 165, sp['name'])
    return card


def to_indexed(card):
    """Quantize to the card's 256 colours of 15 bits: (indices, clut as 16-bit words). Index 0 stays black."""
    px = [tuple((c >> 3) << 3 | (c >> 5) for c in p) for p in card.getdata()]
    q = Image.frombytes('RGB', card.size, bytes(c for p in px for c in p)).quantize(255)
    pal = q.getpalette()
    idx = [i + 1 for i in q.getdata()]
    clut = [0]
    for i in range(255):
        r, g, b = pal[3 * i:3 * i + 3]
        clut.append((r >> 3) | (g >> 3) << 5 | (b >> 3) << 10 | 0x8000 if (r or g or b) else 0x8000)
    return bytes(idx), clut


def render(keys):
    OUT.mkdir(parents=True, exist_ok=True)
    cards = json.load(open(CARDS))['cards']
    for c in cards:
        if keys and c['key'] not in keys:
            continue
        card = compose(c, c['number'])
        base = OUT / f"card-{c['number']:03d}-{c['key']}"
        card.save(str(base) + '.png')
        idx, clut = to_indexed(card)
        open(str(base) + '.idx', 'wb').write(idx)
        open(str(base) + '.clut', 'wb').write(struct.pack('<%dH' % len(clut), *clut))
        print(base.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['ref', 'art', 'gen', 'render', 'prompt'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--ref')
    ap.add_argument('--new-bg', action='store_true')
    ap.add_argument('--new-model', action='store_true')
    a = ap.parse_args()
    if a.cmd == 'render':
        return render({x.lower() for x in a.args})
    if a.cmd == 'ref':
        return reference(species_of(a.args[0]), a.args[1])
    card = card_of(a.args[0])
    if a.cmd == 'art':
        print(build_art(card, a.new_bg, a.new_model))
        return
    if a.cmd == 'prompt':
        print(prompt_for(card))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    refs = []
    for k in [card['species']] + card.get('with', []):
        r = OUT / f"ref-{k}.png"
        m = render_model(species_of(k), 1400)
        bgim = Image.new('RGBA', (m.size[0] + 160, m.size[1] + 160), (128, 128, 128, 255))
        bgim.alpha_composite(m, (80, 80))
        bgim.convert('RGB').save(str(r))
        refs.append(str(r))
    print(generate(card, refs))


if __name__ == '__main__':
    main()
