// Actual Pyodide model replay (standard library only); no imported oracle reads or external Python packages.
// node web/test/imports.mjs EXTRACTED_GAMES [SPECIES_ID ...] (default: all 175)
import { loadPyodide } from '../../build/pyodide-314.0.7/pyodide.mjs';
import { lstatSync, readdirSync, readlinkSync, realpathSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const [games, ...ids] = process.argv.slice(2);
if (!games) throw new Error('usage: node web/test/imports.mjs EXTRACTED_GAMES [SPECIES_ID ...]');
const repo = realpathSync(fileURLToPath(new URL('../../', import.meta.url)));
const py = await loadPyodide({ indexURL: `${repo}/build/pyodide-314.0.7/` });
for (const [path, root] of [['/repo', repo], ['/games', realpathSync(games)]]) {
  py.FS.mkdir(path);
  py.FS.mount(py.FS.filesystems.NODEFS, { root }, path);
}
// a worktree's top-level symlinks (extracted -> the main checkout's): their targets mounted at their own paths, so the
// links resolve inside Pyodide's file system too
for (const name of readdirSync(repo)) {
  const p = `${repo}/${name}`;
  if (!lstatSync(p).isSymbolicLink() || !statSync(p).isDirectory()) continue;
  const target = readlinkSync(p);
  if (!target.startsWith('/')) continue;
  py.FS.mkdirTree(target);
  py.FS.mount(py.FS.filesystems.NODEFS, { root: realpathSync(p) }, target);
}
py.globals.set('SELECTED', JSON.stringify(ids.map(Number)));
await py.runPythonAsync(`
import hashlib, json, sys, shutil
sys.path[:0] = ['/repo', '/repo/tools']
from tools.derive import runner, crmath
from tools.derive.steps.species import species_tools
from tools.derive.importers import Provider
def forbid_oracle(event, args):
    if event == 'open' and isinstance(args[0], str) and '/v61-models/files/' in args[0]:
        raise RuntimeError('oracle read forbidden: ' + args[0])
    if event == 'import' and args[0].split('.')[0] in ('numpy', 'PIL', 'unicorn'):
        raise RuntimeError('unexpected import: ' + args[0])
sys.addaudithook(forbid_oracle)
runner.set_strict(True)
crmath.install()
records = json.load(open('/repo/content/modeldelta/models.json'))['models']
ids = json.loads(SELECTED) or [r['id'] for r in records]
for t in ids:
    work = f'/tmp/imported_models-import-test/{t}'
    with species_tools():
        m, x = Provider('/games', work).model(t)
    print(json.dumps(dict(id=t, mmd=hashlib.sha256(m).hexdigest(), tim=hashlib.sha256(x).hexdigest())), flush=True)
    shutil.rmtree(work)
print(f'{len(ids)} species verified in Pyodide', flush=True)
`);
