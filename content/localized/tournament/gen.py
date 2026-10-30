"""Generate an image with Gemini (Nano Banana Pro by default) from a prompt file plus numbered reference images.
Usage: gen.py PROMPT.txt OUT.png [--ref img...] [--aspect 5:4] [--size 2K] [--model gemini-3-pro-image-preview] [--n 1]
The references go before the text, in the order given, so "image 1" in the prompt is the first --ref."""
import sys, os, json, base64, argparse, urllib.request, mimetypes, time

ap = argparse.ArgumentParser()
ap.add_argument('prompt'); ap.add_argument('out')
ap.add_argument('--ref', nargs='*', default=[])
ap.add_argument('--aspect', default='5:4'); ap.add_argument('--size', default='2K')
ap.add_argument('--model', default='gemini-3-pro-image-preview'); ap.add_argument('--n', type=int, default=1)
a = ap.parse_args()
key = os.environ.get('GEMINI_API_KEY') or sys.exit('GEMINI_API_KEY not set (source ~/.zshrc)')

parts = []
for r in a.ref:
    mime = mimetypes.guess_type(r)[0] or 'image/png'
    parts.append({'inlineData': {'mimeType': mime, 'data': base64.b64encode(open(r, 'rb').read()).decode()}})
parts.append({'text': open(a.prompt).read()})
body = {'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {'responseModalities': ['IMAGE', 'TEXT'],
                             'imageConfig': {'aspectRatio': a.aspect, 'imageSize': a.size}}}
url = f'https://generativelanguage.googleapis.com/v1beta/models/{a.model}:generateContent'
base, ext = os.path.splitext(a.out)
for i in range(a.n):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    t = time.time()
    for attempt in range(6):                                  # 503 (high demand) and 429 are transient: wait and retry
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=600)); break
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            if e.code in (503, 429) and attempt < 5:
                print(f'HTTP {e.code}, retrying in {20 * (attempt + 1)} s', flush=True); time.sleep(20 * (attempt + 1)); continue
            sys.exit(f'HTTP {e.code}: {err[:2000]}')
    out = a.out if a.n == 1 else f'{base}-{i + 1}{ext}'
    got = False
    for p in resp.get('candidates', [{}])[0].get('content', {}).get('parts', []):
        if 'inlineData' in p and not got:
            open(out, 'wb').write(base64.b64decode(p['inlineData']['data'])); got = True
            print(f'{out}  ({time.time() - t:.0f}s, {p["inlineData"]["mimeType"]})')
        elif 'text' in p:
            print('text:', p['text'][:500])
    if not got:
        print('no image:', json.dumps(resp)[:1500])
