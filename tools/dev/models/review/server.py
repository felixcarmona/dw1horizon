#!/usr/bin/env python3
"""Review tool for the imported Digimon's animations (web): every species, every animation of it, the studio video of the model
next to its donor, with approve / needs-fix / note per animation, a donor choice per animation (any DW1 donor; its video is
made on demand), and a general note per species.

  server.py [--port 8300] [--workers 6]

Open http://HOST:8300/. One donor per Digimon: arrows (and the keyboard) go through the donors, the
videos of the animations follow. Decisions are saved at once in build/review/decisions.json:
  {"species": {"402": {"approved": true, "chosen": 0, "approved_ver": "...",
                       "donors": {"22": {"note": "general feedback on this donor", "slots": {"2": "feedback on animation 2"}}}}}}
(donor 0 = the default donor).
Videos and models built with other donors are cached in build/review/ (rendered by tools/dev/models/review/lib.py in worker processes).
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, json, os, subprocess, sys, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = _DEV_ROOT
sys.path.insert(0, HERE)
from tools.dev.models.review import lib as lib  # noqa: E402  (re-executes under the venv)

DECISIONS = os.path.join(ROOT, 'build/review/decisions.json')
LOCK = threading.Lock()
JOBS = {}                     # key -> dict(state: queued|running|done|error, msg)
SEM = None
CACHE = {}


def load_decisions():
    try:
        return json.load(open(DECISIONS))
    except (OSError, ValueError):
        return {'species': {}}


def save_decisions(d):
    os.makedirs(os.path.dirname(DECISIONS), exist_ok=True)
    tmp = DECISIONS + '.tmp'
    json.dump(d, open(tmp, 'w'), indent=1, sort_keys=True)
    os.replace(tmp, DECISIONS)


def species_index():
    if 'species' not in CACHE:
        CACHE['species'] = lib.species_list()
    return CACHE['species']


def species_detail(sid):
    key = ('detail', sid)
    if key not in CACHE:
        sp = lib.find(sid)
        model = lib.default_model(sp)
        slots = lib.slots_of(model, sid)
        CACHE[key] = dict(slots=[dict(slot=s, name=lib.slot_name(s)) for s in slots])
    return CACHE[key]


def job_key(sid, slot, donor):
    return f'{sid}:{slot}:{donor}'


def run_job(sid, slot, donor):
    k = job_key(sid, slot, donor)
    with SEM:
        JOBS[k] = dict(state='running')
        try:
            r = subprocess.run([lib.VENV_PY, os.path.join(HERE, 'lib.py'), 'video', str(sid), str(slot), str(donor)],
                               capture_output=True, text=True, timeout=1800)
            JOBS[k] = dict(state='done') if r.returncode == 0 else dict(state='error', msg=(r.stderr or r.stdout)[-400:])
        except Exception as ex:
            JOBS[k] = dict(state='error', msg=str(ex))


def ensure(sid, slot, donor):
    sp = lib.find(sid)
    if os.path.exists(lib.video_path(sp, slot, donor)):
        return 'done'
    k = job_key(sid, slot, donor)
    with LOCK:
        j = JOBS.get(k)
        if j and j['state'] in ('queued', 'running'):
            return j['state']
        JOBS[k] = dict(state='queued')
        threading.Thread(target=run_job, args=(sid, slot, donor), daemon=True).start()
    return 'queued'


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype='application/json', extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); p = u.path
        try:
            if p == '/':
                return self.send(200, open(os.path.join(HERE, 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
            if p == '/api/species':
                d = load_decisions()['species']
                out = []
                for s in species_index():
                    dd = d.get(str(s['id']), {})
                    fb = sum(1 + len(v.get('slots', {})) for v in dd.get('donors', {}).values() if v.get('note') or v.get('slots'))
                    ch = dd.get('chosen')
                    out.append(dict(s, approved=bool(dd.get('approved')), chosen=ch, feedback=fb, made=lib.made_at(lib.find(s['id']), int(ch or 0))))
                return self.send(200, out)
            if p == '/api/donors':
                if 'donors' not in CACHE:
                    CACHE['donors'] = lib.donor_choices()
                return self.send(200, CACHE['donors'])
            if p.startswith('/api/species/'):
                sid = int(p.rsplit('/', 1)[1])
                sp = next(s for s in species_index() if s['id'] == sid)
                det = species_detail(sid)
                dd = load_decisions()['species'].get(str(sid), {})
                return self.send(200, dict(sp, slots=det['slots'], decisions=dd, ver=lib.version(lib.find(sid), 0), made={str(d['donor']): lib.made_at(lib.find(sid), d['donor']) for d in lib.donor_ranking(lib.find(sid))}, donors=lib.donor_ranking(lib.find(sid))))
            if p == '/api/render':
                sid, slot, donor = int(q['id'][0]), int(q['slot'][0]), int(q['donor'][0])
                return self.send(200, dict(state=ensure(sid, slot, donor)))
            if p == '/api/status':
                sid, slot, donor = int(q['id'][0]), int(q['slot'][0]), int(q['donor'][0])
                sp = lib.find(sid)
                if os.path.exists(lib.video_path(sp, slot, donor)):
                    return self.send(200, dict(state='done'))
                return self.send(200, JOBS.get(job_key(sid, slot, donor), dict(state='none')))
            if p == '/dvideo':
                f = lib.donor_video_path(int(q['donor'][0]), int(q['slot'][0]))
                if not os.path.exists(f):
                    return self.send(404, 'not rendered')
                return self.send(200, open(f, 'rb').read(), 'video/mp4', {'Accept-Ranges': 'bytes'})
            if p == '/video':
                sid, slot, donor = int(q['id'][0]), int(q['slot'][0]), int(q['donor'][0])
                f = lib.video_path(lib.find(sid), slot, donor)
                if not os.path.exists(f):
                    return self.send(404, 'not rendered')
                size = os.path.getsize(f); rng = self.headers.get('Range')
                with open(f, 'rb') as fh:
                    if rng and rng.startswith('bytes='):
                        a, _, b = rng[6:].partition('-')
                        a = int(a or 0); b = int(b) if b else size - 1
                        fh.seek(a); data = fh.read(b - a + 1)
                        return self.send(206, data, 'video/mp4', {'Content-Range': f'bytes {a}-{b}/{size}', 'Accept-Ranges': 'bytes'})
                    return self.send(200, fh.read(), 'video/mp4', {'Accept-Ranges': 'bytes'})
            if p == '/api/decisions':
                return self.send(200, load_decisions())
            self.send(404, 'not found', 'text/plain')
        except StopIteration:
            self.send(404, 'unknown species', 'text/plain')
        except Exception as ex:
            self.send(500, dict(error=f'{type(ex).__name__}: {ex}'))

    def do_HEAD(self):
        # the same headers as GET, no body (some players ask first): done by running GET into a throwaway buffer
        import io
        real, self.wfile = self.wfile, io.BytesIO()
        try:
            self.do_GET()
            raw = self.wfile.getvalue()
        finally:
            self.wfile = real
        head = raw.split(b'\r\n\r\n', 1)[0] + b'\r\n\r\n'
        self.wfile.write(head)

    def do_POST(self):
        if urlparse(self.path).path != '/api/decision':
            return self.send(404, 'not found', 'text/plain')
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        with LOCK:
            d = load_decisions()
            sp = d['species'].setdefault(str(body['id']), {})
            if body.get('clear'):                       # every note of this Digimon, for every donor (the approval stays); a copy of the file first
                bk = os.path.join(ROOT, 'build/review/backups'); os.makedirs(bk, exist_ok=True)
                json.dump(d, open(os.path.join(bk, time.strftime('decisions-%Y%m%d-%H%M%S.json')), 'w'), indent=1)
                sp.pop('donors', None)
            elif 'approve' in body:                       # approve every animation with this donor (or take the approval back)
                if body['approve']:
                    sp.update(approved=True, chosen=body['donor'], approved_ver=lib.version(lib.find(body['id']), 0),
                              approved_at=time.strftime('%Y-%m-%d %H:%M'))
                else:
                    for k in ('approved', 'chosen', 'approved_ver', 'approved_at'):
                        sp.pop(k, None)
            else:                                       # feedback about one donor: general (slot absent) or about one animation
                fb = sp.setdefault('donors', {}).setdefault(str(body['donor']), {'note': '', 'slots': {}})
                if body.get('slot') is None:
                    fb['note'] = body.get('note', '')
                else:
                    if body.get('note'):
                        fb['slots'][str(body['slot'])] = body['note']
                    else:
                        fb['slots'].pop(str(body['slot']), None)
                if not fb['note'] and not fb['slots']:
                    sp['donors'].pop(str(body['donor']), None)
            save_decisions(d)
        self.send(200, dict(ok=True))


def main():
    global SEM
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8300); ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    SEM = threading.Semaphore(a.workers)
    srv = ThreadingHTTPServer(('0.0.0.0', a.port), H)
    print(f'review tool on http://0.0.0.0:{a.port}/', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
