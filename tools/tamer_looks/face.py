"""The second face of the tamer's looks: a blush instead of the freckle marks, a finer mouth with lips, a dark upper
eyelid and two lashes. make(texture) returns a copy of the bald head's texture with that face drawn on it.

The head's texture is a mirrored half face at u 0..28 in palette row 6. The animations copy frames over it: nine eye
frames (16x24 at u 56+16k, v 0) onto u 8, v 0 and six mouth frames (16x16 at u 56+16k, v 24) onto u 0, v 24, so
every frame is redrawn as well. Two palette entries are taken for the new colours: 14, which nothing used, and 0,
whose grey the frames share from now on with the almost equal 10.
"""
import copy

W = 256
ROW = 6                                    # the head's palette row
LINE, LIP, BLUSH, BLACK = 12, 0, 14, 15
LIP_RGB, BLUSH_RGB = (215, 95, 100), (246, 178, 160)
FRECKLE = 7                                # a freckle mark: this tone over the next one
EYE_FRAMES, MOUTH_FRAMES = 9, 6
EYE = (8, 0, 16, 24)                       # where the eye frames land: u, v, width, height
MOUTH = (0, 24, 16, 16)
FRAME_U = 56
LID = ((12, 5), (13, 5), (14, 5), (11, 6), (12, 6), (10, 7), (11, 7), (9, 8), (19, 5), (20, 5), (20, 6), (21, 6),
       (22, 6), (22, 7), (23, 7), (14, 4), (15, 4), (16, 4), (17, 4), (18, 4), (19, 4))
LASHES = ((23, 6), (24, 5), (25, 5), (26, 4), (24, 7), (25, 7), (26, 6))
DARK = (15,)                               # the tone of an eye's outline


def c15(r, g, b):
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def blush(put):
    """The blush on the cheek, a dithered ellipse, in face coordinates."""
    cx, cy = 15.5, 20.5
    for v in range(17, 24):
        for u in range(8, 24):
            d = ((u - cx) / 5.6) ** 2 + ((v - cy) / 2.6) ** 2
            if d <= 1.0 and ((u + v) % 2 == 0 or d <= 0.5):
                put(u, v, BLUSH)


def make(texture):
    x = copy.deepcopy(texture)
    x.idx = bytearray(x.idx)
    pal = list(x.pal[ROW])
    pal[LIP], pal[BLUSH] = c15(*LIP_RGB), c15(*BLUSH_RGB)
    x.pal[ROW] = pal
    old = bytes(x.idx)

    def get(u, v):
        return x.idx[v * W + u]

    def put(u, v, i):
        x.idx[v * W + u] = i

    for v in range(0, MOUTH[1] + MOUTH[3]):          # the frames' grey of entry 0 becomes entry 10
        for u in range(FRAME_U, FRAME_U + 16 * EYE_FRAMES):
            if get(u, v) == 0:
                put(u, v, 10)

    def cheek(u0):
        """Freckle marks out and the blush in, for the face (u0 = 0) or an eye frame (u0 = its u - 8)."""
        for v in range(14, 23):
            for u in range(9, 23):
                o = u0 + u
                if old[v * W + o] == FRECKLE and old[(v + 1) * W + o] == FRECKLE + 1 and old[v * W + o - 1] in (1, 2):
                    put(o, v, old[v * W + o - 1])
                    put(o, v + 1, old[(v + 1) * W + o - 1])
        blush(lambda u, v, i: put(u0 + u, v, i))

    def mouth(u0):
        """The closed mouth: a short dark line, a lip under its middle."""
        for v in (27, 28, 29):                # the old mouth's ends and corners go
            for u in range(7, 16):
                put(u0 + u, v, old[26 * W + u0 + u])
        for u in range(0, 7):
            put(u0 + u, 28, LINE)
        put(u0 + 6, 28, 13)
        for u in range(0, 7):
            put(u0 + u, 29, 3)
        for u in range(0, 4):
            put(u0 + u, 29, LIP)

    # the face itself
    cheek(0)
    mouth(0)
    for u, v in LID + LASHES:
        put(u, v, BLACK)
    # the eye frames: the ones that are the face's own eye take the same lid; the others (half shut, shut, looking
    # aside) get a dark line over the eye's upper outline
    face_eye = [old[v * W + EYE[0]:v * W + EYE[0] + 16] for v in range(EYE[3])]
    for k in range(EYE_FRAMES):
        fu = FRAME_U + 16 * k
        frame = [old[v * W + fu:v * W + fu + 16] for v in range(EYE[3])]
        cheek(fu - EYE[0])
        if sum(a != b for r, s in zip(frame, face_eye) for a, b in zip(r, s)) <= 30:
            for u, v in LID + LASHES:
                if EYE[0] <= u < EYE[0] + 16:
                    put(fu + u - EYE[0], v, BLACK)
            continue
        for lu in range(1, 16):
            top = next((v for v in range(1, 16) if frame[v][lu] in DARK), None)
            if top is not None:
                put(fu + lu, top, BLACK)
                if 3 <= lu <= 12:
                    put(fu + lu, top - 1, BLACK)
    # the mouth frames: the shut ones take the new mouth, the open ones keep theirs
    face_mouth = [old[v * W:v * W + 16] for v in range(MOUTH[1], MOUTH[1] + MOUTH[3])]
    for k in range(MOUTH_FRAMES):
        fu = FRAME_U + 16 * k
        frame = [old[v * W + fu:v * W + fu + 16] for v in range(MOUTH[1], MOUTH[1] + MOUTH[3])]
        if sum(a != b for r, s in zip(frame, face_mouth) for a, b in zip(r, s)) <= 60:
            mouth(fu)
    return x
