#!/usr/bin/env python3
"""The mural of the Second Chamber (screen 304), painted onto the blank panel of the back wall, run by hand (needs numpy,
cv2, torch and Segment Anything). The room (art/full/second-chamber-2304x1856.png) and the mural
(art/full/second-chamber-mural-3168x1344.png, a flat frontal painting) are both ours, as the generator made them; this
composes them the way the sheet prescribes for murals and signs (generated apart, bigger, then laid on the wall):
the mural is squashed into the panel's quad (a frontal wall seen 60 degrees from above), multiplied over the panel's
stone so the wall keeps its own grain and lighting and only the pigments are added, faded at the panel's border, and
the standing tablet in front of the panel (SAM) stays on top. Writes art/second-chamber.png (640x512, the screen's
background) and OUT_DIR/second-chamber-mural-check.png.

    python3 author/second-chamber-compose.py OUT_DIR
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import os, sys
import numpy as np, cv2, torch
from tools.image import Image
from tools.maps.sam import sam_model_registry, SamPredictor
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mapbase import MOD

ROOM = os.path.join(MOD, 'art', 'full', 'second-chamber-2304x1856.png')
MURAL = os.path.join(MOD, 'art', 'full', 'second-chamber-mural-3168x1344.png')
OUT_ART = os.path.join(MOD, 'art', 'second-chamber.png')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
W, H = 640, 512
PANEL = (118, 34, 527, 124)                             # the smooth panel inside the carved border, in 640x512 pixels
FEATHER = 5                                             # px (640 scale) over which the pigments fade at the border
TABLET = (288, 90, 352, 205)                            # box for SAM: the tablet on its pedestal, drawn over the mural


def main(out):
    os.makedirs(out, exist_ok=True)
    room = np.array(Image.open(ROOM).convert('RGB')).astype(np.float32); h0, w0 = room.shape[:2]; sx, sy = w0 / W, h0 / H
    x0, y0, x1, y1 = (int(round(PANEL[0] * sx)), int(round(PANEL[1] * sy)), int(round(PANEL[2] * sx)), int(round(PANEL[3] * sy)))
    pw, ph = x1 - x0, y1 - y0
    mural = np.array(Image.open(MURAL).convert('RGB')).astype(np.float32)
    # the pigments alone: the mural divided by its own stone (the median colour), so multiplying paints them on our wall
    bgc = np.median(mural.reshape(-1, 3), axis=0)
    pig = np.clip(mural / bgc, 0, 1.08)
    pig = cv2.resize(pig, (pw, ph), interpolation=cv2.INTER_AREA)       # squashed into the panel: a frontal wall seen from above
    # fade at the border
    f = int(round(FEATHER * sy)); a = np.ones((ph, pw), np.float32)
    ramp = np.linspace(0, 1, f, endpoint=False)
    a[:f, :] *= ramp[:, None]; a[-f:, :] *= ramp[::-1][:, None]; a[:, :f] *= ramp[None, :]; a[:, -f:] *= ramp[::-1][None, :]
    panel = room[y0:y1, x0:x1]
    painted = panel * (1 - a[..., None]) + panel * pig * a[..., None]
    # the tablet stays in front
    torch.set_num_threads(16)
    pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(room.astype(np.uint8))
    bx = np.array([TABLET[0] * sx, TABLET[1] * sy, TABLET[2] * sx, TABLET[3] * sy])
    masks, scores, _ = pred.predict(box=bx, multimask_output=True)
    tab = masks[int(np.argmax(scores))].astype(np.uint8)
    tab = cv2.dilate(tab, np.ones((3, 3), np.uint8))[y0:y1, x0:x1]
    painted[tab > 0] = panel[tab > 0]
    comp = room.copy(); comp[y0:y1, x0:x1] = painted
    im = Image.fromarray(np.clip(comp, 0, 255).astype(np.uint8))
    im.resize((W, H), Image.LANCZOS).save(OUT_ART)
    im.crop((x0 - 60, y0 - 60, x1 + 60, int(TABLET[3] * sy) + 20)).save(os.path.join(out, 'second-chamber-mural-check.png'))
    print(f'mural on the panel {PANEL} ({pw}x{ph} at full size), tablet score {scores.max():.3f}; wrote {OUT_ART}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
