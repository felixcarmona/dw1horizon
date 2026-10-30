"""A PS1 VRAM (1024x512 16-bit words) to sample textures the way the GPU does:
the model's TIMs are uploaded where their headers say, and a primitive reads
its texels through its texture page (TSB) and CLUT position (CBA)."""
from tools.derive import arraymath as np

from .tim import rgba


def page_origin(tsb):
    """(x, y, bpp) of a texture page."""
    return (tsb & 15) * 64, ((tsb >> 4) & 1) * 256, (4, 8, 16, 16)[(tsb >> 7) & 3]


class Vram:
    def __init__(self):
        self.words = np.zeros((512, 1024), np.uint16)
        self.clut_rows = set()          # (x, y) of every uploaded CLUT row

    def resolve_clut(self, clut):
        """The CLUT itself if a TIM of the model uploaded it, else the nearest
        uploaded row. A few models point some faces at rows their TIM does not
        carry (Gekomon uses 10 rows and brings 2); in the game those faces show
        whatever is left in VRAM."""
        if clut in self.clut_rows or not self.clut_rows:
            return clut
        return min(self.clut_rows, key=lambda r: (r[0] != clut[0], abs(r[1] - clut[1])))

    def upload(self, tim):
        if tim.clut.size:
            x, y = tim.clut_xy
            h, w = tim.clut.shape
            self.words[y:y + h, x:x + w] = tim.clut
            self.clut_rows |= {(x, y + i) for i in range(h)}
        x, y = tim.image_xy
        packed = tim.packed
        h, w = packed.shape
        self.words[y:y + h, x:x + w] = packed[:512 - y, :1024 - x]

    def page(self, tsb, clut):
        """The 256x256 texture page as seen through a CLUT, RGBA."""
        x, y, bpp = page_origin(tsb)
        cx, cy = clut
        if bpp == 4:
            w = self.words[y:y + 256, x:x + 64]
            idx = np.stack([(w >> s) & 15 for s in (0, 4, 8, 12)], -1).reshape(w.shape[0], 256)
            colours = self.words[cy, cx:cx + 16][idx]
        elif bpp == 8:
            w = self.words[y:y + 256, x:x + 128]
            idx = np.stack([w & 255, w >> 8], -1).reshape(w.shape[0], 256)
            colours = self.words[cy, cx:cx + 256][idx]
        else:
            colours = self.words[y:y + 256, x:x + 256]
        out = np.zeros((256, 256, 4), np.uint8)
        img = rgba(colours)
        out[:img.shape[0], :img.shape[1]] = img
        return out
