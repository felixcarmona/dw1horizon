"""Keep-going release plan and private recovery state; used by tools/release.py."""
import argparse
import ast
import inspect
import contextlib
import datetime
import hashlib
import fcntl
import threading
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from tools import release_steps as steps
import release


def options(context):
    return argparse.Namespace(**{k:(Path(v) if k in ('out','ending_card','derive_cache','record_save') and v else v)
                                for k,v in context['options'].items()})


def environment(context):
    from tools.derive.recipe import NOT_THE_RECIPES
    env=dict(os.environ)
    for key in (*NOT_THE_RECIPES,'HEAP_OK','MOD_VERSION','DEV','EXTRA_SPECIES','DERIVE_ARGS','DW_BUILD_CACHE','DW_RECORD_CACHE','DW_CLEAN_NATIVE'):
        env.pop(key,None)
    recipe=json.loads((ROOT/'tools/derive/recipes/everything.json').read_text())
    for key,value in recipe['environment'].items():
        if value is None:env.pop(key,None)
        else:env[key]=str(value)
    env.update(W=context['w'],NAME=context['name'],DERIVE_JOBS=str(context['options']['jobs']),REUSE_MODELS='0',
               DW_PORTRAITS_CACHE=str(Path(context['build'])/'derived/portraits-cache'),PYTHONDONTWRITEBYTECODE='1')
    return env


class Commands(release.Run):
    def __init__(self,out,event):
        super().__init__(False,out);self.event=event;self.events=[]

    def cmd(self,argv,env=None,cwd=ROOT):
        row=dict(command=list(map(str,argv)),cwd=str(cwd),exit=None)
        self.events.append(row);steps.atomic(self.event,steps.encoded(self.events))
        try:
            super().cmd(argv,env,cwd)
        except BaseException as error:
            # The command runner includes the actual subprocess exit in its error.
            import re
            match=re.search(r'command exited (-?\d+)',str(error));row['exit']=int(match[1]) if match else 1
            raise
        else:row['exit']=0
        finally:steps.atomic(self.event,steps.encoded(self.events))


def native_runtime():
    """The native builder uses its own interpreter and installed generator libraries."""
    interpreter=ROOT/'.venv/bin/python'
    if not interpreter.exists():interpreter=Path(sys.executable)
    code="import json,sys;from tools.derive.cache import runtime_sources;print(json.dumps([sys.version,runtime_sources()]))"
    value=subprocess.check_output([str(interpreter),'-B','-c',code],cwd=ROOT,text=True)
    toolchain=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}','dw-build'],cwd=ROOT,text=True).strip()
    if not toolchain:raise RuntimeError('native toolchain image has no identity')
    return dict(python=json.loads(value),toolchain=toolchain)


def prepare_decomp(context, runner, destination, revision=None, source=None):
    """Keep the prepared sources immutable; native compilation owns another tree."""
    destination=Path(destination);source=Path(source or context['seed'])
    if destination.exists():
        runner.cmd(['git','-C',context['seed'],'worktree','remove','--force',destination])
    runner.cmd(['git','-C',context['seed'],'worktree','add','--force','--detach',destination,revision or context['pin']])
    if revision is None:
        from tools import patch_series
        patches=patch_series.paths(ROOT)
        if patches:
            runner.cmd(['git','-C',destination,'-c','user.name='+release.git('config','user.name'),
                        '-c','user.email='+release.git('config','user.email'),'am',*patches])
    for relative in ('asm','build/us/psx/generated','external/psyq_headers'):
        shutil.copytree(source/relative,destination/relative,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git'))


def run_step(name,context):
    a=options(context);out=Path(context['out']);build=Path(context['build']);w=Path(context['w'])
    package=out/'package';engine=out/'engine';env=environment(context)
    bases={k:Path(v) for k,v in context['bases'].items()};sources={k:Path(v) for k,v in context['sources'].items()}
    event=out/'commands'/(name.replace('/','-')+'.json');r=Commands(out,event);py=sys.executable
    recipe=json.loads((ROOT/'tools/derive/recipes/everything.json').read_text())
    if name=='identity':
        info=release.identity(a.tag)
        if info!=context['identity']:raise RuntimeError('checkout changed after this recovery round started')
        steps.atomic(out/'identity.json',steps.encoded(info))
    elif name=='published-file':r.cmd([py,'tools/dev/saves/releases.py','check'])
    elif name.startswith('fast/'):
        r.cmd([py,'-W','ignore::ResourceWarning','tools/'+name.split('/',1)[1]+'.py'])
    elif name=='prerequisites':
        seed=Path(context['seed'])
        for path in (*bases.values(),*sources.values(),Path(context['variant']),ROOT/'extracted/SLUS_010.32',
                     ROOT/'.tools/mkpsxiso/build/mkpsxiso',ROOT/'build/digimonworld.xml',seed/'asm',
                     ROOT/'decomp/config/us/symbols.txt',seed/'build/us/psx/generated',seed/'external/psyq_headers'):
            if not path.exists():raise RuntimeError(f'missing prerequisite: {path}')
        from tools.discs import DISCS,DW1_RELEASES,SOURCE_DISCS,SOURCE_VARIANTS
        expected={'us':DISCS[0]['sha1'],**{d['id'][4:]:d['sha1'] for d in DW1_RELEASES if d['supported']},
                  **{d['id']:d['sha1'] for d in SOURCE_DISCS},'dw3-us':next(d['sha1'] for d in SOURCE_VARIANTS if d['id']=='dw3-us')}
        actual={}
        for key,path in dict(bases,**sources,**{'dw3-us':Path(context['variant'])}).items():
            actual[key]=release.sha1(path)
            if actual[key]!=expected[key]:raise RuntimeError(f'{key}: registered input SHA-1 differs')
        for relative,sha in DISCS[0]['files'].items():
            if release.sha1(ROOT/'extracted'/relative)!=sha:raise RuntimeError(f'extracted source differs: {relative}')
        steps.atomic(out/'input-pins.json',steps.encoded(actual))
    elif name=='player-python':
        shutil.rmtree(out/'player-python',ignore_errors=True)
        r.cmd([py,'-m','venv','--without-pip',out/'player-python'])
    elif name=='decomp':
        prepared=out/'prepared-decomp'
        prepare_decomp(context,r,prepared)
        steps.atomic(out/'decomp-ready.json',steps.encoded({'commit':release.git('rev-parse','HEAD',cwd=prepared)}))
    elif name=='sources':
        shutil.rmtree(build/'source-games',ignore_errors=True)
        command=[py,'-m','tools.derive','sources','--out',build/'source-games']
        for key,path in sources.items():command+=['--source-disc',f'{key}={path}']
        r.cmd(command,env)
    elif name=='native':
        import version
        env['MOD_VERSION']=version.game_text(context['frozen_identity'])
        prepared=out/'prepared-decomp'
        ready=json.loads((out/'decomp-ready.json').read_text())
        prepare_decomp(context,r,w,revision=ready['commit'],source=prepared)
        for suffix in ('.bin','.cue'):
            Path(str(build)+suffix).unlink(missing_ok=True)
        r.cmd(['story/mods/what-the-island-forgot/build.sh'],env)
    elif name=='heap':r.cmd([py,'tools/heapcheck.py',w/'build/us/psx/gcc/SLUS_010.32.elf.map'],env)
    elif name=='story-heap':
        from tools.derive import recipe as recipes
        checkenv=dict(env,**recipes.env(recipe,str(build)),DW_HEAP_MAP=str(w/'build/us/psx/gcc/SLUS_010.32.elf.map'),
                      DW_MODEL_ARCHIVE=str(build/'DIGI.DAT'),DW_EXE_FACTS=str(build/'derived/exe-facts.json'),DWS_RELAYOUT='1',SCNASM_PACK_ASCII='1')
        facts=json.loads((build/'derived/exe-facts.json').read_text())
        target=['--ground-pickup-max',str(facts.get('ground_pickup_max') or 0),'--maphead-max',str(facts.get('maphead_script_max') or 0x6800),
                '--font-glyphs',str(facts.get('font_glyphs') or 0),'--exe-font',facts.get('makefile_font') or 'original']
        r.cmd([py,'tools/dws.py','story-build',*recipe['story']['sources'],'--mods','all','--read-only-locks','--exe','mods',
               '--imported-npcs','--exe-dir',w/'build/us/psx/gcc',*target,'-o',out/'story-check/DG.SCN'],checkenv)
    elif name=='fixtures':
        files=release.selftest_fixtures(build)
        steps.atomic(out/'fixtures.json',steps.encoded({'prepared':True,'files':files}))
    elif name=='selftest':
        testenv=release.offline_environment(recipe);testenv.update(DW_SELFTEST_DERIVE=str(build),DW_SELFTEST_DECOMP=str(w),
                       DW_SELFTEST_OUT=str(out/'selftest'),DW_SELFTEST_REPORT=str(out/'selftest-steps.jsonl'))
        r.cmd(['tools/selftest.sh'],testenv)
    elif name=='package':
        for suffix in ('.json','.txt'):(out/'package-state'/('failures'+suffix)).unlink(missing_ok=True)
        command=[py,'tools/patcher/dwpatch.py','make-release','--original',bases['us'],
                 '--variant',f'everything={build}.bin','--title','Digimon World Horizon','-o',package,
                 '--keep-going','--resume-state',out/'package-state','--keep-outputs',out/'reconstructed',
                 '--version',context['frozen_identity']['version']]
        for key,path in bases.items():
            if key!='us':command+=['--base',f'{key}={path}']
        for key,path in sources.items():command+=['--source-disc',f'{key}={path}']
        command+=['--source-variant','dw2003='+context['variant'],'--variant-jobs',str(a.base_jobs),'--base-jobs',str(a.base_jobs),
                  '--worker-memory-mib',str(a.worker_memory_mib),'--metrics',out/'package-timing.json']
        if a.derive_cache:command+=['--derive-cache',a.derive_cache]
        r.cmd(command,env)
    elif name in ('published-save','journey','ending'):
        shutil.rmtree(out/name,ignore_errors=True)
        cue=Path(str(build)+'.cue');exe=build/'exe/SLUS_010.32';env.update(DW_OBJECT_DIR=str(w))
        if name=='published-save':r.cmd([py,'tools/dev/saves/releases.py','emu',cue,'--exe',exe,'--port',str(a.emu_port_base),'--work',out/name],env)
        elif name=='journey':r.cmd([py,'tools/dev/playtest/journey.py',cue,out/name],dict(env,EMU_PORT=str(a.emu_port_base+1),DW_SYMS=str(exe)))
        else:r.cmd([py,'tools/dev/playtest/ending.py',cue,out/name,'--card',a.ending_card],dict(env,EMU_PORT=str(a.emu_port_base+2),DW_SYMS=str(exe)))
    elif name.startswith('standalone/'):
        key=name.split('/',1)[1];base=key.split('+')[0];dest=out/('standalone-'+key)
        shutil.rmtree(dest,ignore_errors=True)
        player=out/'player-python/bin/python';player_env=dict(env)
        for option in ('PYTHONPATH','PYTHONHOME'):player_env.pop(option,None)
        player_env.update(PYTHONNOUSERSITE='1',VIRTUAL_ENV=str(out/'player-python'),
                          PATH=str(player.parent)+os.pathsep+player_env.get('PATH',''))
        command=[player,'-B','-E','-S','-X',f'cpu_count={max(1,(os.cpu_count() or 1)//5)}',package/'dwpatch.py','apply',bases[base],'-o',dest]
        used=dict(sources)
        if '+' in key:used['dw2003']=Path(context['variant'])
        for game,path in used.items():command+=['--source-disc',f'{game}={path}']
        r.cmd(command,player_env,cwd=out)
        manifest=json.loads((package/'manifest.json').read_text());images=list(dest.glob('*.bin'))
        expected=manifest['variants'][manifest['default']]['outputs'][key]['sha1']
        if len(images)!=1 or release.sha1(images[0])!=expected:raise RuntimeError('standalone output pin differs: '+key)
        steps.atomic(dest/'verified.json',steps.encoded({'sha1':expected}))
    elif name=='engine':
        alias=out/'base-discs';alias.mkdir(exist_ok=True)
        names={'us':'Digimon World (USA)','jp1':'DigimonWorld (Japan) (Rev 1)'}
        for key,title in names.items():
            p=alias/(title+'.bin')
            if p.is_symlink():p.unlink()
            p.symlink_to(bases[key])
        key=release.record_key(package,env,sources.items())
        env.update(RECORDS=str(ROOT/'build/release-records'/key),ISOS=str(alias),ENGINE_WORK=str(out/'engine-work'),
                   PYODIDE_CACHE=str(ROOT/'build/pyodide-314.0.7'),ENGINE_JOBS=str(min(a.base_jobs,2)),
                   ENGINE_RECORD_JOBS=str(max(1,(os.cpu_count() or 1)//5)*2),WORKER_MEMORY_MIB=str(a.worker_memory_mib),
                   DCB_IMAGE=str(sources['dcb']),DW2_IMAGE=str(sources['dw2']),DW3_IMAGE=str(sources['dw2003']))
        r.cmd([ROOT/'web/build-engine.sh',package,engine],env)
    elif name=='browser':
        for folder in ('site','browser-profile'):shutil.rmtree(out/folder,ignore_errors=True)
        release.browser(r,out,engine,bases,sources,env,a.browser_timeout)
        steps.atomic(out/'browser-verified.json',steps.encoded(r.sums))
    elif name=='archive':
        archive=out/('horizon-'+context['frozen_identity']['version']+'.tar.gz');release.pack_release(package,archive)
        steps.atomic(out/'inventory.json',steps.encoded({str(p.relative_to(out)):release.sha1(p) for p in [archive,*sorted(package.rglob('*')),*sorted(engine.rglob('*'))] if p.is_file() and not release.python_cache(p)}))
    elif name=='record-save':
        corpus=out/'save-corpus';shutil.rmtree(corpus,ignore_errors=True)
        shutil.copytree(ROOT/'tools/dev/saves/corpus',corpus)
        r.cmd([py,'tools/dev/saves/releases.py','add',Path(str(build)+'.cue'),'--exe',build/'exe/SLUS_010.32','--corpus',corpus,
               '--name',context['frozen_identity']['version']+'-'+context['identity']['commit'][:8],
               '--version',context['frozen_identity']['version'],'--commit',context['identity']['commit'],
               '--date',context['identity']['date'],'--from',a.record_save,'--work',out/'save-recording'],env)
    elif name=='deploy':
        r.cmd(['web/deploy.sh'],dict(env,RELEASE=str(package),ENGINE=str(engine)))
        steps.atomic(out/'deployed.json',steps.encoded({'commit':context['identity']['commit']}))
    elif name=='push-tag':
        r.cmd(['git','push',a.remote,'refs/tags/'+a.tag])
        steps.atomic(out/'pushed.json',steps.encoded({'commit':context['identity']['commit'],'tag':a.tag}))
    elif name=='publish':
        archive=out/('horizon-'+context['frozen_identity']['version']+'.tar.gz')
        r.cmd(['gh','release','create',a.tag,archive,'--verify-tag','--title','Digimon World Horizon '+context['frozen_identity']['version'],'--notes-file',a.notes_file])
        steps.atomic(out/'published.json',steps.encoded({'commit':context['identity']['commit'],'tag':a.tag}))
    elif name=='complete':
        rows=json.loads((out/'recovery/state/round.json').read_text())
        if any(row['status'] not in ('ok','reused') for row in rows if row['name']!='complete'):
            raise RuntimeError('release has failed, blocked or incomplete gates')
        verified=steps.Store(out/'recovery/state');changed=[]
        for row in rows:
            if row['name']=='complete':continue
            marker=json.loads(verified.path(row['name']).read_text())
            if verified.hashes.tree(marker['output_roots'])!=marker['outputs']:changed.append(row['name'])
        if changed:raise RuntimeError('completed outputs changed after their steps: '+', '.join(changed))
        steps.atomic(out/'complete.json',steps.encoded(dict(passed=True,commit=context['identity']['commit'],
                     version=context['frozen_identity']['version'],steps=[row['name'] for row in rows if row['name']!='complete'])))
    elif name=='checkout':
        if release.identity(a.tag)!=context['identity']:raise RuntimeError('checkout or version changed during recovery round')
        steps.atomic(out/'checkout-verified.json',steps.encoded(context['identity']))
    else:raise ValueError('unknown release step: '+name)


def declared_outputs(name,context):
    out=Path(context['out']);build=Path(context['build']);w=Path(context['w'])
    if name=='identity':return [out/'identity.json']
    if name=='prerequisites':return [out/'input-pins.json']
    if name=='player-python':return [out/'player-python']
    if name=='decomp':return [out/'prepared-decomp',out/'decomp-ready.json']
    if name=='sources':return [build/'source-games']
    if name=='native':
        manifest=json.loads((build/'derived/manifest.json').read_text())
        files=[build/'derived/manifest.json',build/'derived/exe-facts.json',build/'exe',Path(str(build)+'.bin'),Path(str(build)+'.cue')]
        files += [build/item['file'] for item in manifest['files'].values()]
        files += [build/p for p in ('models','record-originals') if (build/p).exists()]
        return sorted(set(files+[w]))
    if name=='story-heap':return [out/'story-check/DG.SCN',out/'logs/story-heap.log']
    if name=='selftest':return [out/'selftest',out/'selftest-steps.jsonl',out/'logs/selftest.log']
    if name=='fixtures':return [out/'fixtures.json',*[ROOT/path for path in json.loads((out/'fixtures.json').read_text())['files']]]
    if name=='package':return [out/'package',out/'reconstructed']
    if name in ('published-save','journey','ending'):return [out/name]
    if name.startswith('standalone/'):return [out/('standalone-'+name.split('/',1)[1])]
    if name=='engine':return [out/'engine']
    if name=='browser':return [out/'browser-verified.json',out/'browser.log']
    if name=='archive':return [out/('horizon-'+context['frozen_identity']['version']+'.tar.gz'),out/'inventory.json']
    if name=='checkout':return [out/'checkout-verified.json']
    if name=='complete':return [out/'complete.json']
    if name=='record-save':return [out/'save-corpus',out/'save-recording']
    if name=='deploy':return [out/'deployed.json']
    if name=='push-tag':return [out/'pushed.json']
    if name=='publish':return [out/'published.json']
    return [out/'logs'/(name.replace('/','-')+'.log')]


def phase_code(function,name):
    """Fingerprint this phase's implementation, not unrelated sibling branches."""
    tree=ast.parse(inspect.getsource(function)).body[0]
    common=[];branch=None
    for node in tree.body:
        if isinstance(node,ast.If):branch=node;break
        common.append(node)
    while branch is not None:
        test=ast.Expression(body=branch.test)
        if eval(compile(ast.fix_missing_locations(test),'<release phase>','eval'),{'name':name}):
            return [ast.dump(node,include_attributes=False) for node in common+branch.body]
        branch=branch.orelse[0] if len(branch.orelse)==1 and isinstance(branch.orelse[0],ast.If) else None
    return [ast.dump(node,include_attributes=False) for node in tree.body]


def current_identity(tag):
    try:return release.identity(tag)
    except RuntimeError:
        # Identity is a reported DAG gate, including when the checkout is dirty.
        import version
        return version.describe(str(ROOT))


def child_failure_rows(path, prefix, result, lines=False):
    """A damaged child report is another failure, never a reason to lose the list."""
    def error(message, suffix='report'):
        result['ok']=False
        result['failures'].append(dict(name=prefix+'/'+suffix,status='failed',exit=1,seconds=0,
                                       command=[],log=str(path),error=str(message)))
    try:text=path.read_text()
    except OSError as exc:error(exc);return []
    chunks=text.splitlines() if lines else [text]
    rows=[]
    for index,chunk in enumerate(chunks,1):
        if lines and not chunk.strip():continue
        try:
            data=json.loads(chunk)
            batch=[data] if lines else data['failures']
            if not isinstance(batch,list):raise ValueError('invalid failure list')
            for row in batch:
                if not isinstance(row,dict) or not isinstance(row.get('name'),str):raise ValueError('invalid failure row')
                rows.append(row)
        except (ValueError,KeyError,TypeError) as exc:error(exc,'report-line-'+str(index) if lines else 'report')
    return rows


def driver(a):
    # A sibling lock also protects first creation without making --out nonempty.
    out=a.out.expanduser().resolve();out.parent.mkdir(parents=True,exist_ok=True)
    with (out.parent/(out.name+'.lock')).open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('another release round is using this output directory')
        return locked_driver(a)


def locked_driver(a):
    round_started=time.monotonic()
    if a.dry_run or a.prepare_reuse or a.reuse_from:
        raise ValueError('recovery mode cannot combine a dry-run or sealed reuse')
    out=a.out.expanduser().resolve();state=out/'recovery';context_file=state/'context.json'
    if a.resume:
        context=json.loads(context_file.read_text())
        if context['root']!=str(ROOT):raise ValueError('resume must use the original worktree')
        previous=context['options'];provided=set(getattr(a,'_provided',()))
        path_options={'out','ending_card','derive_cache','record_save','notes_file',*[f'reuse_{n}' for n in ('package','outputs','build','engine','bases','sources')]}
        for key,value in previous.items():
            if key in ('out','resume','keep_going','_provided'):continue
            if '--'+key.replace('_','-') not in provided and not (key=='tag' and a.tag is not None):
                setattr(a,key,Path(value) if value and key in path_options else value)
        if (not previous.get('skip_browser') and a.skip_browser) or (not previous.get('preflight_only') and a.preflight_only):
            raise ValueError('resume cannot remove a previously required gate')
        if a.tag!=previous.get('tag'):raise ValueError('resume cannot change the release tag')
        if a.no_derive_cache:a.derive_cache=None

    else:
        if out.exists():raise ValueError('--out must be new; use --resume for an existing cut')
        info=current_identity(a.tag)
        names={'us':'Digimon World (USA)','eu':'Digimon World (Europe)','fr':'Digimon World (France)','de':'Digimon World (Germany)',
               'es':'Digimon World (Spain)','it':'Digimon World (Italy)','jp1':'DigimonWorld (Japan) (Rev 1)'}
        isos=Path(os.environ.get('ISOS','build/isos/digimon-world')).expanduser();source=Path(os.environ.get('SOURCE_ISOS','build/isos')).expanduser()
        common=Path(release.git('rev-parse','--path-format=absolute','--git-common-dir')).parent
        context=dict(root=str(ROOT),out=str(out),name='release-'+out.name,build=str(ROOT/'build'/('release-'+out.name)),
                     w=str(out/'decomp'),seed=str(Path(os.environ.get('DECOMP_REPO',common/'decomp')).resolve()),
                     pin=release.git('ls-tree','HEAD','decomp').split()[2],frozen_identity=info,
                     bases={k:str(Path(os.environ.get('DW1_'+k.upper()+'_IMAGE',isos/(title+'.bin'))).expanduser().resolve()) for k,title in names.items()},
                     sources={k:str(Path(os.environ.get(variable,source/default)).expanduser().resolve()) for k,variable,default in
                              [('dcb','DCB_IMAGE','digital-card-battle/Digimon Digital Card Battle (USA).bin'),('dw2','DW2_IMAGE','digimon-world-2/Digimon World 2 (USA).bin'),
                               ('dw2003','DW3_IMAGE','digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin')]},
                     variant=str(Path(os.environ.get('DW3_US_IMAGE',source/'digimon-world-2003/Digimon World 3 (USA).bin')).expanduser().resolve()))
        state.mkdir(parents=True)
    if a.publish and (not a.tag or not a.notes_file or not a.notes_file.is_file()):
        raise ValueError('--publish requires a tag and existing notes file')
    context['identity']=current_identity(a.tag)
    context['options']={k:(str(v) if isinstance(v,Path) else v) for k,v in vars(a).items()}
    context['options']['out']=str(out)
    steps.atomic(context_file,steps.encoded(context))
    store=steps.Store(state/'state',resume=True)
    tracked=release.git('ls-files','-z').split('\0')
    native_files=[ROOT/p for p in tracked if p and p.startswith(('tools/','content/','story/','mods/','text/','docs/data/'))
                  and not p.endswith('.md') and '/test' not in p and not Path(p).name.startswith(('test_','release'))]
    native_files += [ROOT/'extracted',ROOT/'build/digimonworld.xml']
    from tools.derive.cache import runtime_sources
    runtime_identity=dict(python=sys.version,executable=store.hashes.file(sys.executable),libraries=runtime_sources())
    env=environment(context)
    from tools.derive.release_cache import environment as normalized
    env_key=hashlib.sha256(steps.encoded(normalized(env))).hexdigest()
    build=Path(context['build']);w=Path(context['w']);package=out/'package';engine=out/'engine'
    base_inputs=list(map(Path,context['bases'].values()));source_inputs=list(map(Path,context['sources'].values()))+[Path(context['variant'])]
    frontend_inputs=[ROOT/name for name in ('LICENSE','THIRD-PARTY.md','docs/release/README-players.md','docs/data/source-releases.md',
                     'tools/font/japanese-license','tools/font/chinese-license','tools/image-license.txt')]
    web_inputs=[ROOT/name for name in tracked if name.startswith('web/') and not name.startswith(('web/enginebuild/','web/media/'))]
    for candidate in (shutil.which('node'),os.environ.get('CHROMIUM','/snap/bin/chromium'),
                      '/snap/chromium/current/usr/lib/chromium-browser/chrome',os.environ.get('FIREFOX')):
        if candidate and Path(candidate).is_file():web_inputs.append(Path(candidate))
    module=os.environ.get('PUPPETEER_MODULE','')
    if module.startswith('file://'):
        from urllib.parse import unquote,urlparse
        module=Path(unquote(urlparse(module).path))
        if module.exists():
            installation=next((parent for parent in module.parents if parent.name=='node_modules'),module.parent)
            web_inputs.append(installation)

    from tools import patch_series
    plan=[]
    children=set();children_lock=threading.Lock()
    def add(name,deps=(),inputs=(),values=None,reuse=True,after=()):
        command=(sys.executable,'-B',str(Path(__file__)),'_step',name,str(context_file))
        log=out/'logs'/(name.replace('/','-')+'.log')
        def fingerprint():
            if name=='complete':
                changed=[]
                for prior in plan:
                    if prior.name in ('complete','deploy','push-tag','publish'):continue
                    current=hashlib.sha256(steps.encoded(prior.inputs())).hexdigest()
                    if current!=store.rows[prior.name].get('fingerprint'):changed.append(prior.name)
                if changed:raise RuntimeError('inputs changed after validation: '+', '.join(changed))
            paths=inputs() if callable(inputs) else inputs
            return dict(format=1,files=store.hashes.tree(paths),values=values() if callable(values) else values,environment=env_key,
                        runtime=runtime_identity,phase=phase_code(run_step,name),outputs=phase_code(declared_outputs,name),
                        commands=[inspect.getsource(Commands),inspect.getsource(release.Run.cmd),inspect.getsource(release.stop_group)],
                        shared=[inspect.getsource(options),inspect.getsource(environment)],
                        release_helpers=store.hashes.file(ROOT/'tools/release.py'),
                        preparation=inspect.getsource(prepare_decomp) if name in ('decomp','native') else None,
                        native_runtime_code=inspect.getsource(native_runtime) if name=='native' else None,
                        validated_steps={key:row.get('fingerprint') for key,row in store.rows.items() if key!='complete'} if name=='complete' else None,
                        helper=inspect.getsource(release.browser) if name=='browser' else inspect.getsource(release.selftest_fixtures) if name=='fixtures' else None)
        def invoke():
            log.parent.mkdir(parents=True,exist_ok=True)
            with log.open('w') as f:
                p=subprocess.Popen(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
                with children_lock:children.add(p)
                try:code=p.wait()
                finally:
                    release.stop_group(p)
                    with children_lock:children.discard(p)
            if code:
                error=steps.StepFailure(name,code,'release step failed')
                events=out/'commands'/(name.replace('/','-')+'.json')
                if events.exists():
                    failures=[row for row in json.loads(events.read_text()) if row['exit'] not in (None,0)]
                    if failures:error.code=failures[-1]['exit'];error.command=failures[-1]['command']
                raise error
        plan.append(steps.Step(name,invoke,fingerprint,lambda value:declared_outputs(name,context),tuple(deps),command,log,reuse,tuple(after)))
    add('identity',values=context['identity'],reuse=False)
    add('published-file',['identity'],[ROOT/'tools/dev/saves/releases.py',ROOT/'tools/dev/saves/corpus'])
    for test in release.FAST:add('fast/'+test,['identity'],[ROOT/'tools'/(test+'.py'),*native_files])
    if not a.preflight_only:
        add('prerequisites',['identity'],[*base_inputs,*source_inputs,ROOT/'extracted',ROOT/'tools/discs.py'],values=context['pin'])
        add('player-python',['identity'],[Path(sys.executable)],values=sys.version)
        add('decomp',['prerequisites'],[ROOT/'mods/patches/series',ROOT/'tools/patch_series.py',*patch_series.paths(ROOT),Path(context['seed'])/'asm',Path(context['seed'])/'external/psyq_headers',Path(context['seed'])/'build/us/psx/generated'],values=context['pin'])
        add('sources',['prerequisites'],[*source_inputs,*[p for p in native_files if '/tools/' in str(p)]])
        add('native',['decomp','sources'],lambda:[*native_files,ROOT/'tools',out/'prepared-decomp',out/'decomp-ready.json',build/'source-games'],values=lambda:dict(version=context['frozen_identity']['version'],runtime=native_runtime(),
                                               iso_writer=store.hashes.file(ROOT/'.tools/mkpsxiso/build/mkpsxiso')))
        add('heap',['native'],[ROOT/'tools/heapcheck.py',w/'build/us/psx/gcc/SLUS_010.32.elf.map'])
        add('story-heap',['native'],lambda:[*native_files,build/'DIGI.DAT',build/'derived/exe-facts.json',w/'build/us/psx/gcc/SLUS_010.32.elf.map'])
        safe=['native','heap','story-heap']
        add('fixtures',safe,lambda:[*native_files,ROOT/'tools',build/'derived/manifest.json',build/'models',build/'record-originals',build/'source-games'])
        add('selftest',['fixtures'],lambda:[*native_files,ROOT/'tools',w/'src',build/'derived/manifest.json'])
        add('package',safe+['published-file'],lambda:[*native_files,ROOT/'tools',*frontend_inputs,*base_inputs,*source_inputs,Path(str(build)+'.bin'),build/'derived/manifest.json'],values=context['identity']['commit'])
        if a.save_check_emu:
            for name in ('published-save','journey'):add(name,safe,[ROOT/'tools/dev',Path(str(build)+'.bin'),build/'exe/SLUS_010.32'])
        if a.ending_card:add('ending',safe,[ROOT/'tools/dev',a.ending_card,Path(str(build)+'.bin'),build/'exe/SLUS_010.32'])
        for key in ('us','jp1','eu+dw3-us'):add('standalone/'+key,['package','player-python'],lambda key=key:[package,*source_inputs,Path(context['bases'][key.split('+')[0]])])
        add('engine',['package'],lambda:[package,ROOT/'web/enginebuild',ROOT/'web/build-engine.sh',*base_inputs,*source_inputs,
                                                        *([ROOT/'build/pyodide-314.0.7'] if (ROOT/'build/pyodide-314.0.7').exists() else [])])
        if a.record_save:add('record-save',safe,[a.record_save,ROOT/'tools/dev/saves',Path(str(build)+'.bin')])
        if not a.skip_browser:add('browser',['engine','package'],lambda:[engine,package,*web_inputs],values=a.browser_timeout)
        add('archive',['package','engine'],lambda:[package,engine])
        prior=[step.name for step in plan]
        add('checkout',['identity'],values=context['identity'],reuse=False,after=prior)
        add('complete',[step.name for step in plan],values=context['identity'])
        if a.deploy:add('deploy',['complete'],lambda:[package,engine,ROOT/'web/deploy.sh'])
        if a.publish:
            add('push-tag',['complete'],values={'tag':a.tag,'commit':context['identity']['commit'],'remote':a.remote})
            add('publish',['push-tag']+(['deploy'] if a.deploy else []),lambda:[a.notes_file,out/('horizon-'+context['frozen_identity']['version']+'.tar.gz')])
    steps.atomic(state/'plan.json',steps.encoded([dict(name=s.name,dependencies=s.deps,after=s.after,command=s.command) for s in plan]))
    def interrupt(*_):
        with children_lock:running=list(children)
        for process in running:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        raise KeyboardInterrupt()
    handlers={sig:signal.signal(sig,interrupt) for sig in (signal.SIGINT,signal.SIGTERM)} if threading.current_thread() is threading.main_thread() else {}
    try:result=steps.run(plan,store,a.step_workers)
    finally:
        for sig,handler in handlers.items():signal.signal(sig,handler)
    package_row=next((row for row in result['steps'] if row['name']=='package'),{})
    package_failures=out/'package-state/failures.json'
    if package_row.get('status')=='failed' and package_failures.exists():
        for inner in child_failure_rows(package_failures,'package',result):
            row=dict(inner,name='package/'+inner['name'])
            row['blocked_by']=['package/'+name for name in row.get('blocked_by',[])]
            row['dependencies']=['package/'+name for name in row.get('dependencies',[])]
            result['failures'].append(row)
    selftest_row=next((row for row in result['steps'] if row['name']=='selftest'),{})
    selftest_report=out/'selftest-steps.jsonl'
    if selftest_row.get('status')=='failed' and selftest_report.exists():
        for row in child_failure_rows(selftest_report,'selftest',result,lines=True):
            if row['status'] in ('failed','blocked'):
                result['failures'].append(dict(row,name='selftest/'+row['name']))
    lines=[]
    for row in result['failures']:
        if row['status']=='blocked':lines.append(row['name']+': blocked by '+', '.join(row['blocked_by']))
        else:lines.append(f"{row['name']}: exit {row['exit']}; log {row['log']}; command {row['command']}; {row.get('error','')}")
    steps.atomic(out/'failures.json',steps.encoded(result))
    steps.atomic(out/'failures.txt',(('\n'.join(lines) if lines else 'All steps passed.')+'\n').encode())
    print('\n'.join(lines) if lines else 'All required release steps passed.',flush=True)
    round_number=len(list((out/'rounds').glob('*.json')))+1
    result.update(seconds=round(time.monotonic()-round_started,3),round=round_number,commit=context['identity']['commit'],frozen_version=context['frozen_identity']['version'])
    # Preserve evidence before a resume replaces a worker's current log.
    history=out/'rounds'/f'round-{round_number:03}-logs';history.mkdir(parents=True,exist_ok=True)
    for relative,label in (('recovery/context.json','context.json'),('recovery/plan.json','driver-plan.json'),
                           ('package-state/plan.json','package-plan.json'),('package-state/round.json','package-round.json'),
                           ('package-timing.json','package-timing.json'),('browser.log','browser-runner.log')):
        if (out/relative).is_file():shutil.copy2(out/relative,history/label)
    for row in result['steps']:
        if row.get('log') and Path(row['log']).is_file():
            saved=history/(row['name'].replace('/','-')+'.log')
            shutil.copy2(row['log'],saved);row['archived_log']=str(saved)
    for row in result['failures']:
        if row.get('log') and Path(row['log']).is_file() and row['name'].startswith(('selftest/','package/')):
            shutil.copy2(row['log'],history/(row['name'].replace('/','-')+'.log'))
            if row.get('worker_log') and Path(row['worker_log']).is_file():
                shutil.copy2(row['worker_log'],history/(row['name'].replace('/','-')+'-worker.log'))
    if selftest_report.exists():shutil.copy2(selftest_report,history/'selftest-steps.jsonl')
    if (out/'package-state/failures.json').exists():
        shutil.copy2(out/'package-state/failures.json',history/'package-failures.json')
    steps.atomic(out/'rounds'/f'round-{round_number:03}.json',steps.encoded(result))
    steps.atomic(out/'summary.json',steps.encoded(dict(seconds=result['seconds'],result='ok' if result['ok'] else 'FAILED',round=round_number,
        steps=[(row['name'],row['seconds'],row['status']) for row in result['steps']])))
    return 0 if result['ok'] else 1


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='_step':
        signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
        run_step(sys.argv[2],json.loads(Path(sys.argv[3]).read_text()))
    else:raise SystemExit('internal release step runner')
