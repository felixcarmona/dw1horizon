"""Explicit release dependencies, complete failure reports and verified completion markers."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import traceback


def atomic(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + str(threading.get_ident()) + '.tmp')
    temporary.write_bytes(data)
    os.replace(temporary, path)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


class Hashes:
    def __init__(self):
        self.memo = {}
        self.lock = threading.Lock()

    def file(self, path):
        path = Path(path)
        s = path.stat()
        identity = (str(path.resolve()), s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
        with self.lock:
            cached = self.memo.get(identity)
        if cached is not None:
            return cached
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        result = h.hexdigest()
        with self.lock:
            self.memo[identity] = result
        return result

    def tree(self, paths):
        result = {}
        for item in paths:
            root = Path(item).absolute()
            if not root.exists():
                raise FileNotFoundError(root)
            entries = [root] + sorted(root.rglob('*')) if root.is_dir() else [root]
            for path in entries:
                if '__pycache__' in path.parts or path.suffix == '.pyc':
                    continue
                info = {'mode': path.stat().st_mode & 0o7777}
                if path.is_symlink():
                    info['link'] = os.readlink(path)
                if path.is_dir():
                    info['type'] = 'directory'
                elif path.is_file():
                    info.update(type='file', sha256=self.file(path), bytes=path.stat().st_size)
                else:
                    raise ValueError(f'unsupported release artifact: {path}')
                result[str(path)] = info
        return result


class StepFailure(RuntimeError):
    def __init__(self, name, code, message):
        self.name, self.code = name, code
        super().__init__(message)


class Store:
    """Private state. A marker alone is insufficient: every output is rehashed."""
    def __init__(self, root, resume=True):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.resume, self.hashes = resume, Hashes()
        self.rows = {}
        self.dependencies = {}
        self.lock = threading.Lock()

    def path(self, name):
        safe = re.sub(r'[^a-zA-Z0-9._-]+', '-', name)[:80]
        suffix = hashlib.sha256(name.encode()).hexdigest()[:12]
        return self.root / 'steps' / (safe + '-' + suffix + '.json')

    def note(self, row):
        with self.lock:
            row['dependencies']=list(self.dependencies.get(row['name'],()))
            self.rows[row['name']] = row
            atomic(self.root / 'round.json', encoded(list(self.rows.values())))

    def blob(self, data):
        sha = hashlib.sha256(data).hexdigest(); path = self.root / 'blobs' / sha
        if not path.exists() or self.hashes.file(path) != sha:
            atomic(path, data)
        return sha

    def pack(self, value):
        if isinstance(value, bytes):return {'$bytes': self.blob(value)}
        if isinstance(value, Path):return {'$path': str(value)}
        if isinstance(value, tuple):return {'$tuple': [self.pack(v) for v in value]}
        if isinstance(value, list):return {'$list': [self.pack(v) for v in value]}
        if isinstance(value, dict):return {'$dict': [[self.pack(k), self.pack(v)] for k,v in value.items()]}
        if value is None or type(value) in (str,int,float,bool):return value
        raise TypeError(f'unsupported checkpoint value: {type(value).__name__}')

    def unpack(self, value):
        if not isinstance(value, dict):return value
        if '$bytes' in value:
            sha=value['$bytes']
            if not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('invalid blob identity')
            path=self.root/'blobs'/sha
            if self.hashes.file(path)!=sha:raise ValueError('checkpoint blob hash mismatch')
            return path.read_bytes()
        if '$path' in value:return Path(value['$path'])
        if '$tuple' in value:return tuple(self.unpack(v) for v in value['$tuple'])
        if '$list' in value:return [self.unpack(v) for v in value['$list']]
        if '$dict' in value:return {self.unpack(k):self.unpack(v) for k,v in value['$dict']}
        raise ValueError('invalid checkpoint value')

    def call(self, name, function, inputs, outputs=(), command=(), log=None, reuse=True):
        started=time.monotonic(); marker=self.path(name)
        log=Path(log or marker.with_suffix('.log')); log.parent.mkdir(parents=True,exist_ok=True)
        row=dict(name=name,command=list(map(str,command)),log=str(log),status='running',exit=None)
        try:
            values=inputs() if callable(inputs) else inputs
            fingerprint=hashlib.sha256(encoded(values)).hexdigest()
            row['fingerprint']=fingerprint
            if self.resume and reuse:
                try:
                    previous=json.loads(marker.read_text())
                    roots=previous['output_roots']
                    if (previous['status']=='ok' and previous['fingerprint']==fingerprint
                            and self.hashes.tree(roots)==previous['outputs']):
                        value=self.unpack(previous['value'])
                        current=outputs(value) if callable(outputs) else outputs
                        current=current or [log]
                        if list(map(lambda p:str(Path(p).absolute()),current))!=roots:
                            raise ValueError('declared outputs changed')
                        row.update(status='reused',exit=0,seconds=round(time.monotonic()-started,3),reused_from_seconds=previous['seconds'],outputs=previous['outputs'])
                        self.note(row);print(f'REUSED {name}',flush=True)
                        return value
                except (OSError,ValueError,KeyError,TypeError):
                    pass
            atomic(marker,encoded(row));self.note(row);print(f'RUN {name}: {log}',flush=True)
            log.write_text('RUN '+name+'\ncommand '+str(row['command'])+'\n')
            value=function()
            with log.open('a') as stream:stream.write('\nPASS '+name+'\n')
            roots=outputs(value) if callable(outputs) else outputs
            roots=roots or [log]
            roots=list(map(lambda p:str(Path(p).absolute()),roots))
            artifacts=self.hashes.tree(roots)
            packed=self.pack(value)
            row.update(status='ok',exit=0,seconds=round(time.monotonic()-started,3),output_roots=roots,outputs=artifacts,value=packed)
            atomic(marker,encoded(row));self.note(row);print(f'PASS {name} ({row["seconds"]:.1f} s)',flush=True)
            return value
        except (Exception,SystemExit) as error:
            code=getattr(error,'code',1)
            if not isinstance(code,int) or code==0:code=1
            row.update(status='failed',exit=code,error=str(error),seconds=round(time.monotonic()-started,3))
            if getattr(error,'command',None):row['command']=list(map(str,error.command))
            with log.open('a') as f:f.write('\n'+traceback.format_exc())
            atomic(marker,encoded(row));self.note(row);print(f'FAILED {name}: {error}; {log}',flush=True)
            raise StepFailure(name,code,str(error)) from error

    def blocked(self,name,dependencies,command=()):
        row=dict(name=name,status='blocked',blocked_by=dependencies,command=list(map(str,command)),log=None,exit=None,seconds=0)
        marker=self.path(name)
        try:previous=json.loads(marker.read_text())
        except (OSError,ValueError):previous={}
        # A blocked attempt did not execute or invalidate a prior verified result.
        if previous.get('status')!='ok':atomic(marker,encoded(row))
        self.note(row)
        print(f'BLOCKED {name} by {", ".join(dependencies)}',flush=True)

    def report(self, prefix='failures'):
        rows=list(self.rows.values())
        failures=[r for r in rows if r['status'] in ('failed','blocked')]
        data=dict(ok=not failures,failures=failures,steps=rows)
        atomic(self.root/(prefix+'.json'),encoded(data))
        lines=[]
        for row in failures:
            if row['status']=='blocked':lines.append(f'{row["name"]}: blocked by {", ".join(row["blocked_by"])}')
            else:lines.append(f'{row["name"]}: exit {row["exit"]}; {row.get("error","")}; log {row["log"]}; command {row["command"]}')
        atomic(self.root/(prefix+'.txt'),(('\n'.join(lines) if lines else 'All steps passed.')+'\n').encode())
        print('\n'.join(lines) if lines else 'All steps passed.',flush=True)
        return data


@dataclass
class Step:
    name: str
    run: object
    inputs: object
    outputs: object=field(default_factory=tuple)
    deps: tuple=()
    command: tuple=()
    log: object=None
    reuse: bool=True
    after: tuple=()


def run(steps, store, workers=4):
    by_name={step.name:step for step in steps}
    if len(by_name)!=len(steps):raise ValueError('duplicate release step name')
    for step in steps:
        if set(step.deps+step.after)-by_name.keys():raise ValueError(f'unknown dependency for {step.name}')
    checked=set()
    def visit(name,stack):
        if name in stack:raise ValueError('cycle in release dependencies')
        if name in checked:return
        for dependency in by_name[name].deps+by_name[name].after:visit(dependency,stack|{name})
        checked.add(name)
    for name in by_name:visit(name,set())
    store.dependencies={step.name:list(step.deps) for step in steps}
    pending=dict(by_name);active={};finished={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while pending or active:
            for name,step in list(pending.items()):
                if any(dep not in finished for dep in step.deps+step.after):continue
                blocked=[dep for dep in step.deps if not finished[dep]]
                if blocked:
                    store.blocked(name,blocked,step.command);finished[name]=False;del pending[name]
                elif len(active)<workers:
                    active[pool.submit(store.call,step.name,step.run,step.inputs,step.outputs,step.command,step.log,step.reuse)]=name
                    del pending[name]
            if active:
                done,_=wait(active,timeout=1,return_when=FIRST_COMPLETED)
                for future in done:
                    name=active.pop(future)
                    try:future.result();finished[name]=True
                    except StepFailure:finished[name]=False
            elif pending and not any(all(dep in finished for dep in s.deps+s.after) for s in pending.values()):
                raise ValueError('unresolved release dependencies')
    return store.report()
