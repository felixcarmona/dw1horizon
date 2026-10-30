// Real Pyodide browser-writer proof with hash-checked cached derived files.
// node changed_build_wasm.mjs /absolute/pyodide-runtime /absolute/config.json
// Config: {release, bases, references, glue, output, source_discs: ["game=/path"]}.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

try {
  const runtime = path.resolve(process.argv[2]);
  const config = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  for (const key of ['release', 'bases', 'references', 'glue', 'output']) {
    if (!path.isAbsolute(config[key])) throw new Error(`${key} must be an absolute path`);
  }
  const {loadPyodide} = await import(pathToFileURL(path.join(runtime, 'pyodide.mjs')));
  const py = await loadPyodide({indexURL: runtime + path.sep});
  py.FS.mkdirTree('/host');
  py.FS.mount(py.FS.filesystems.NODEFS, {root: '/'}, '/host');
  py.globals.set('proof_config', JSON.stringify(config));
  await py.runPythonAsync(`
import hashlib,json,pathlib,sys,time
assert sys.platform == 'emscripten'
config=json.loads(proof_config)
def host(path): return '/host'+path
def forbid(event,args):
    if event=='import' and args[0].split('.')[0] in ('numpy','PIL'):
        raise RuntimeError('non-standard runtime dependency imported')
sys.addaudithook(forbid)
release=pathlib.Path(host(config['release']))
sys.path.insert(0,str(release))
sys.path.insert(0,host(config['glue']))
import dwpatch as P,isowriter as iw,glue
manifest=json.loads((release/'manifest.json').read_text())
variant=manifest['variants'][manifest['default']]
bases=json.load(open(host(config['bases'])))
references=json.load(open(host(config['references'])))
if set(bases)!=set(manifest['bases']) or set(references)!=set(bases):
    raise ValueError('every advertised base requires an input and changed reference')
gate=json.loads((release/'literal-gate.json').read_text())
if gate['passed'] == bool(config.get('expect_blocked',False)):
    raise ValueError('changed package gate differs from expected publication result')
inputs=gate.get('inputs',{})
manifest_sha=hashlib.sha1(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
if inputs.get('manifest_sha1')!=manifest_sha: raise ValueError('gate belongs to another manifest')
for paths in (inputs.get('json_files',{}),inputs.get('runtime',{})):
    for name,want in paths.items():
        if hashlib.sha1((release/name).read_bytes()).hexdigest()!=want:
            raise ValueError('gate input changed: '+name)
class Sink:
    def __init__(self): self.size=0
    def write(self,data): self.size+=len(data);return len(data)
source_discs=[spec.split('=',1)[0]+'='+host(spec.split('=',1)[1]) for spec in config.get('source_discs',[])]
results={}
output=pathlib.Path(host(config['output']))
output.mkdir(parents=True,exist_ok=False)
for key in bases:
    start=time.monotonic()
    print('PYODIDE BASE',key,flush=True)
    image=iw.Image(host(references[key]))
    try:
        holes={}
        for hole in variant['holes']:
            data=image.read(hole['file'])
            if hashlib.sha1(data).hexdigest()!=hole.get('sha1_by_base',{}).get(key,hole['sha1']):
                raise ValueError(key+': cached hole hash mismatch')
            holes[hole['file']]=data
        sink=Sink()
        work=output/key
        work.mkdir()
        mapping_path=manifest['bases'][key].get('mapping')
        mapping=json.loads((release/mapping_path).read_text()) if mapping_path else None
        base=P.BaseDisc(key,host(bases[key]),mapping,tool_root=str(release/'bundle'),
                        work=str(work),source_discs=source_discs)
        payload=P.read_payload3(P.read_patch_file(str(release),variant))
        saved=P.subprocess.run
        P.subprocess.run=glue.run_tool
        try:
            sha,plan=P.build_disc3(payload,base,{h['id']:holes[h['file']] for h in variant['holes']},sink,progress=False)
        finally:
            P.subprocess.run=saved
            base.img.f.close()
            for extra_image in getattr(base,'_copy_images',{}).values(): extra_image.f.close()
        want=variant['outputs'][key]['sha1']
        size=plan.total*2352
        if sha!=want or size!=sink.size or size!=variant['outputs'][key]['size']:
            raise ValueError(key+': reconstructed changed disc mismatch')
        results[key]=dict(sha1=sha,size=size,seconds=round(time.monotonic()-start,2))
        (output/'results.json').write_text(json.dumps(results,indent=2)+'\\n')
        print('PYODIDE PASS',key,sha,flush=True)
    finally:
        image.f.close()
    del holes
`);
} catch (error) {
  console.error(error.message);
  if (error.stack) console.error(error.stack.split('\n').filter(line => line.length < 500).join('\n'));
  process.exitCode = 1;
}
