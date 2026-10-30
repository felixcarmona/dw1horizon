/* Software rasterizer for tools/animstudio.py: textured or flat triangles with a z-buffer (the same maths as the Python one,
   a few hundred times faster). Built on first use: gcc -O2 -shared -fPIC animraster.c -o build/review/animraster.so */
#include <math.h>
#include <string.h>

void raster(int T, const float *P, const int *UV, const int *row, const float *shade, const unsigned char *flat, const unsigned char *textured,
            const unsigned char *pal, int nrows, const unsigned char *idx, int tw, int th, int W, int H, float *zb, unsigned char *out,
            unsigned char *hit)
{
    for (int t = 0; t < T; t++) {
        const float *p = P + 9 * t;
        float x0 = p[0], y0 = p[1], z0 = p[2], x1 = p[3], y1 = p[4], z1 = p[5], x2 = p[6], y2 = p[7], z2 = p[8];
        float area = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0);
        if (fabsf(area) < 1e-9f) continue;
        int bx0 = (int)fminf(fminf(x0, x1), x2), bx1 = (int)fmaxf(fmaxf(x0, x1), x2) + 1;
        int by0 = (int)fminf(fminf(y0, y1), y2), by1 = (int)fmaxf(fmaxf(y0, y1), y2) + 1;
        if (bx0 < 0) bx0 = 0; if (by0 < 0) by0 = 0; if (bx1 > W - 1) bx1 = W - 1; if (by1 > H - 1) by1 = H - 1;
        const int *uv = UV + 6 * t;
        int r = row[t]; if (r < 0) r = 0; if (r >= nrows) r = nrows - 1;
        float sh = shade[t];
        for (int y = by0; y <= by1; y++) {
            float py = y + 0.5f;
            for (int x = bx0; x <= bx1; x++) {
                float px = x + 0.5f;
                float w0 = ((x1 - px) * (y2 - py) - (y1 - py) * (x2 - px)) / area;
                float w1 = ((x2 - px) * (y0 - py) - (y2 - py) * (x0 - px)) / area;
                float w2 = 1.0f - w0 - w1;
                if (w0 < 0 || w1 < 0 || w2 < 0) continue;
                float z = w0 * z0 + w1 * z1 + w2 * z2;
                int k = y * W + x;
                if (z >= zb[k]) continue;
                unsigned char cr, cg, cb;
                if (textured[t]) {
                    int u = (int)(w0 * uv[0] + w1 * uv[2] + w2 * uv[4]);
                    int v = (int)(w0 * uv[1] + w1 * uv[3] + w2 * uv[5]);
                    if (u < 0) u = 0; if (u >= tw) u = tw - 1; if (v < 0) v = 0; if (v >= th) v = th - 1;
                    const unsigned char *c = pal + (r * 16 + idx[v * tw + u]) * 4;
                    if (c[3] == 0) continue;
                    cr = c[0]; cg = c[1]; cb = c[2];
                } else {
                    cr = flat[3 * t]; cg = flat[3 * t + 1]; cb = flat[3 * t + 2];
                }
                zb[k] = z;
                out[3 * k] = (unsigned char)(cr * sh); out[3 * k + 1] = (unsigned char)(cg * sh); out[3 * k + 2] = (unsigned char)(cb * sh);
                hit[k] = 1;
            }
        }
    }
}
