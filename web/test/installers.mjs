// web/test (not deployed): js/installers.js in Node against the desktop patcher's makers (tools/patcher/apk.py,
// setup_exe.py, mac_app.py, linux_run.py), on synthetic templates and a synthetic disc made here (no game data).
//
//   node web/test/installers.mjs
//
// The Windows setup and the APK (same entry date) must come out byte for byte; the Linux .run with the same header
// and the same tar members (names, modes, links, contents); the Mac zip with the same files, modes, symlinks and
// Info.plist values. Needs python3 (the reference) and Node 22 or later.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { makeApk, makeSetup, makeMac, writeLinuxRun, untar, crcOf, NAME } from '../js/installers.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
process.umask(0o022);   // (mac_app.py zips the new files with the modes they get: 0644, as the page writes them)
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'installers-'));
const at = (...p) => path.join(work, ...p);
const py = (code, ...args) => execFileSync('python3', ['-I', '-c', code, ROOT, work, ...args], { encoding: 'utf8' });
let bad = 0;
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) bad++; };

// ---------------------------------------------------------------- the synthetic inputs and the Python outputs
// A disc of 700 sectors (1.6 MB: more than one 1 MiB slice), an APK template with a deflated manifest, a stored dex, a
// stored .so and an old signature, a Windows "exe", a Mac .app (a plist, an executable, a symlink) zipped as ditto
// does, and a Linux bundle (an executable, a symlink, a name longer than 100 bytes) as a tar.gz.
py(String.raw`
import os, sys, zipfile, tarfile, stat, random
root, work = sys.argv[1], sys.argv[2]
r = random.Random(7)
blob = lambda n: bytes(r.getrandbits(8) for _ in range(n))
with open(os.path.join(work, 'disc.bin'), 'wb') as f:
    f.write(bytes((i * 7 + i // 2352) & 255 for i in range(2352 * 700)))
with open(os.path.join(work, 'disc.cue'), 'w', newline='') as f:
    f.write('FILE "disc.bin" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n')
with zipfile.ZipFile(os.path.join(work, 'template.apk'), 'w') as z:
    z.writestr('AndroidManifest.xml', b'<manifest>' * 300, zipfile.ZIP_DEFLATED)
    z.writestr('classes.dex', blob(3001), zipfile.ZIP_STORED)
    z.writestr('lib/arm64-v8a/libhorizon.so', blob(20000), zipfile.ZIP_STORED)
    z.writestr('res/raw/a.bin', blob(10), zipfile.ZIP_STORED)
    z.writestr('META-INF/CERT.RSA', b'old signature', zipfile.ZIP_DEFLATED)
with open(os.path.join(work, 'template.exe'), 'wb') as f:
    f.write(b'MZ' + blob(5000))
app = os.path.join(work, 'mac', 'Horizon Play.app')
for d in ('Contents/MacOS', 'Contents/Resources', 'Contents/Frameworks/X.framework/Versions/A'):
    os.makedirs(os.path.join(app, d), exist_ok=True)
with open(os.path.join(app, 'Contents/Info.plist'), 'w') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0">\n<dict>\n'
            '\t<key>CFBundleIdentifier</key>\n\t<string>com.example.horizonplay</string>\n'
            '\t<key>CFBundleName</key>\n\t<string>Horizon Play</string>\n</dict>\n</plist>\n')
with open(os.path.join(app, 'Contents/MacOS/horizon-play'), 'wb') as f:
    f.write(blob(4000))
os.chmod(os.path.join(app, 'Contents/MacOS/horizon-play'), 0o755)
with open(os.path.join(app, 'Contents/Frameworks/X.framework/Versions/A/X'), 'wb') as f:
    f.write(blob(100))
os.symlink('Versions/A/X', os.path.join(app, 'Contents/Frameworks/X.framework/X'))
sys.path.insert(0, os.path.join(root, 'tools/patcher'))
import mac_app
mac_app.zip_app(app, os.path.join(work, 'template-mac.zip'))
bundle = os.path.join(work, 'linux', 'Horizon Play')
os.makedirs(os.path.join(bundle, 'lib', 'x' * 60, 'y' * 60), exist_ok=True)
with open(os.path.join(bundle, 'horizon-play'), 'wb') as f:
    f.write(blob(3000))
os.chmod(os.path.join(bundle, 'horizon-play'), 0o755)
with open(os.path.join(bundle, 'lib', 'core.so.1'), 'wb') as f:
    f.write(blob(700))
os.symlink('core.so.1', os.path.join(bundle, 'lib', 'core.so'))
with open(os.path.join(bundle, 'lib', 'x' * 60, 'y' * 60, 'long.txt'), 'wb') as f:
    f.write(b'a long name')
with tarfile.open(os.path.join(work, 'template-linux.tar.gz'), 'w:gz') as t:
    t.add(bundle, 'Horizon Play')
`);
py(String.raw`
import os, sys
root, work = sys.argv[1], sys.argv[2]
sys.path[:0] = [os.path.join(root, 'tools/patcher'), os.path.join(root, 'tools/patcher/app')]
import apk, setup_exe, mac_app, linux_run, make_icons
w = lambda *p: os.path.join(work, *p)
apk.build(w('template.apk'), w('disc.bin'), w('py.apk'), date_time=(2026, 1, 2, 3, 4, 6))
setup_exe.build(w('template.exe'), w('disc.cue'), w('py-Setup.exe'))
mac_app.build(w('mac', 'Horizon Play.app'), w('disc.cue'), w('py-Mac.zip'))
linux_run.build(w('template-linux.tar.gz'), w('disc.cue'), w('py-Linux.run'))
open(w('header.sh'), 'w', newline='').write(linux_run.header())
open(w('icon.png'), 'wb').write(make_icons.png(256))
`);

// ---------------------------------------------------------------- the same in JavaScript
const blob = (name) => fs.openAsBlob(at(name));
const image = await blob('disc.bin');
const key = JSON.parse(fs.readFileSync(path.join(ROOT, 'tools/patcher/android-key.json'), 'utf8'));
const save = async (name, b) => fs.writeFileSync(at(name), new Uint8Array(await b.arrayBuffer()));
const same = (a, b) => fs.readFileSync(at(a)).equals(fs.readFileSync(at(b)));

const crc = await crcOf(image);
let ticks = 0;
await save('js.apk', await makeApk(await blob('template.apk'), image, key, { date: new Date(2026, 0, 2, 3, 4, 6), tick: (n) => { ticks += n; } }));
check(same('js.apk', 'py.apk'), 'APK byte for byte with apk.py');
check(ticks >= 2 * image.size && ticks < 2 * image.size + 65536, `APK progress counts the disc twice (${ticks})`);
await save('js2.apk', await makeApk(await blob('template.apk'), image, key, { crc, date: new Date(2026, 0, 2, 3, 4, 6) }));
check(same('js2.apk', 'py.apk'), 'APK with the CRC given');

await save('js-Setup.exe', makeSetup(await blob('template.exe'), image));
check(same('js-Setup.exe', 'py-Setup.exe'), 'Windows setup byte for byte with setup_exe.py');

await save('js-Mac.zip', await makeMac(await blob('template-mac.zip'), image, { crc }));
const mac = py(String.raw`
import sys, zipfile, plistlib, stat, os, json
work = sys.argv[2]
def files(p):
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None, p
        out = {}
        for i in z.infolist():
            if i.is_dir():
                continue
            data = z.read(i)
            if i.filename.endswith('/Contents/Info.plist'):
                data = json.dumps(plistlib.loads(data), sort_keys=True).encode()
            out[i.filename] = (stat.S_IFMT(i.external_attr >> 16), (i.external_attr >> 16) & 0o777, data)
    return out
a, b = files(os.path.join(work, 'js-Mac.zip')), files(os.path.join(work, 'py-Mac.zip'))
print('same' if a == b else 'differ: ' + repr(sorted(set(a) ^ set(b)) or [(n, a[n][:2], b[n][:2], a[n][2] == b[n][2]) for n in a if a[n] != b[n]]))
`);
check(mac.trim() === 'same', `Mac zip: the same files, modes, links and plist as mac_app.py (${mac.trim()})`);

const header = fs.readFileSync(at('header.sh'), 'utf8');
const chunks = [];
await writeLinuxRun(await blob('template-linux.tar.gz'), image, header, fs.readFileSync(at('icon.png')),
                    new WritableStream({ write: (c) => { chunks.push(Buffer.from(c)); } }));
const jsRun = Buffer.concat(chunks), pyRun = fs.readFileSync(at('py-Linux.run'));
const skip = Buffer.byteLength(header);
check(jsRun.subarray(0, skip).equals(pyRun.subarray(0, skip)), 'Linux .run: the header of linux_run.py');
const members = async (b) => untar(new Uint8Array(await new Response(new Blob([b.subarray(skip)]).stream()
  .pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()))
  .map((m) => JSON.stringify([m.name, m.type, m.mode, m.linkname, m.size, Buffer.from(m.data).toString('base64')]));
const [jm, pm] = [await members(jsRun), await members(pyRun)];
check(jm.length === pm.length && jm.every((m, i) => m === pm[i]), `Linux .run: the same ${pm.length} tar members, in order`);
check(jm.some((m) => m.includes('"lib/' + 'x'.repeat(60))), 'Linux .run: the long name survives');
check(jm.some((m) => m.startsWith(`["${NAME}.bin"`)), 'Linux .run: the disc is inside');

// the run itself: unpacked by the system's tar from the offset the header names
fs.mkdirSync(at('unpacked'));
execFileSync('sh', ['-c', `tail -c +$((${skip} + 1)) "$0" | tar xzf - -C "$1"`, at('py-Linux.run'), at('unpacked')]);
fs.writeFileSync(at('js-Linux.run'), jsRun);
fs.mkdirSync(at('unpacked-js'));
execFileSync('sh', ['-c', `tail -c +$((${skip} + 1)) "$0" | tar xzf - -C "$1"`, at('js-Linux.run'), at('unpacked-js')]);
check(fs.readFileSync(at('unpacked-js', `${NAME}.bin`)).equals(fs.readFileSync(at('disc.bin'))), 'Linux .run: tar unpacks the disc byte for byte');

// cancelling stops the work
let stopped = false;
try {
  await makeApk(await blob('template.apk'), image, key, { cancel: () => true });
} catch (e) { stopped = /cancelled/.test(e.message); }
check(stopped, 'APK: cancel stops it');

fs.rmSync(work, { recursive: true, force: true });
console.log(bad ? `${bad} FAILED` : 'all ok');
process.exit(bad ? 1 : 0);
