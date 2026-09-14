"""Configuration, lineage, atomic writes and shared resource accounting."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import os
import shutil
import sqlite3
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT/'configs/experiments/vni_qni.json'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def clean(value):
    import numpy as np
    import pandas as pd
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [clean(v) for v in value]
    if isinstance(value,(pd.Timestamp,Path)):return str(value)
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(np.bool_,)):return bool(value)
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    return value


def load_config(path=DEFAULT):
    path=Path(path).resolve()
    c=json.loads(path.read_text(encoding='utf-8'))
    if c.get('schema_version')!=1:raise ValueError('Unsupported experiment schema')
    ids=[x['id'] for x in c['connectors']]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate connector')
    if not all(1<=x<=336 for x in c['leads']):raise ValueError('Invalid lead')
    run=(ROOT/c['root']/c['campaign']).resolve()
    allowed=(ROOT/'data/forecast_experiments').resolve()
    if not run.is_relative_to(allowed) or run==allowed:raise ValueError('Run root must be a child of data/forecast_experiments')
    c['_path']=path;c['_run']=run
    return c


def code_manifest():
    paths=sorted((ROOT/'nemic/experiments').glob('*.py'))
    paths += [ROOT/'nemic/constraint_features.py',ROOT/'nemic/event_atlas.py']
    return [{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in paths]


class Store:
    def __init__(self,c):
        self.c=c;self.root=c['_run'];self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'ledger.sqlite'
        self.budget_db=self.root.parent/'budget.sqlite'
        with self.connection() as con:
            con.executescript('CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, bytes INTEGER, pid INTEGER, created REAL); CREATE TABLE IF NOT EXISTS trials (id TEXT PRIMARY KEY, fingerprint TEXT, status TEXT, output TEXT, hash TEXT, detail TEXT, updated REAL);')
        with sqlite3.connect(self.budget_db) as con:con.execute('CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, bytes INTEGER, pid INTEGER, created REAL)')

    @contextmanager
    def connection(self,budget=False):
        con=sqlite3.connect(self.budget_db if budget else self.db,timeout=60)
        try:yield con;con.commit()
        finally:con.close()

    def used(self):
        # Budget shared by all campaigns, not just this connector or trial.
        total=0
        for p in self.root.parent.rglob('*'):
            try:
                if p.is_file():total+=p.stat().st_size
            except FileNotFoundError:pass
        return total

    @contextmanager
    def reserve(self,n):
        import psutil
        ident=uuid.uuid4().hex
        with self.connection(budget=True) as con:
            con.execute('BEGIN IMMEDIATE')
            for rid,pid in con.execute('SELECT id,pid FROM reservations').fetchall():
                if not psutil.pid_exists(pid):con.execute('DELETE FROM reservations WHERE id=?',(rid,))
            outstanding=con.execute('SELECT COALESCE(SUM(bytes),0) FROM reservations').fetchone()[0]
            if self.used()+outstanding+n>self.c['limits']['additional_bytes']:raise RuntimeError('Shared 10 GB additional-storage budget exhausted')
            if shutil.disk_usage(self.root).free-outstanding-n<self.c['limits']['min_free_bytes']:raise RuntimeError('Free-disk reserve would be breached')
            con.execute('INSERT INTO reservations VALUES (?,?,?,?)',(ident,n,os.getpid(),time.time()))
        try:yield
        finally:
            with self.connection(budget=True) as con:con.execute('DELETE FROM reservations WHERE id=?',(ident,))

    def owned(self,path):
        p=Path(path).resolve()
        if not p.is_relative_to(self.root) or p==self.root:raise ValueError('Artifact outside campaign root')
        return p

    def json(self,path,value):
        p=self.owned(path);data=json.dumps(clean(value),indent=2,allow_nan=False).encode()
        with self.reserve(len(data)):
            p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
            tmp.write_bytes(data);os.replace(tmp,p)
        return p

    def parquet(self,path,frame):
        p=self.owned(path)
        estimate=max(int(frame.memory_usage(deep=True).sum()*1.3),65536)
        with self.reserve(estimate):
            p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp')
            frame.to_parquet(tmp,index=False,compression='zstd');os.replace(tmp,p)
        return p

    def complete(self,ident,fp,path,detail=None):
        p=self.owned(path)
        with self.connection() as con:
            con.execute('INSERT OR REPLACE INTO trials VALUES (?,?,?,?,?,?,?)',(ident,fp,'complete',str(p.relative_to(self.root)),digest(p),json.dumps(clean(detail or {})),time.time()))

    def valid(self,ident,fp):
        with self.connection() as con:r=con.execute('SELECT fingerprint,status,output,hash FROM trials WHERE id=?',(ident,)).fetchone()
        if not r or r[0]!=fp or r[1]!='complete':return False
        p=self.root/r[2]
        if not p.exists() or digest(p)!=r[3]:return False
        if p.suffix=='.json':
            payload=json.loads(p.read_text())
            for item in payload.get('artifacts',[]):
                artifact=self.root/item['path']
                if not artifact.exists() or digest(artifact)!=item['sha256']:return False
            if payload.get('output_sha256'):
                artifact=self.root/payload['output']
                if not artifact.exists() or digest(artifact)!=payload['output_sha256']:return False
        return True

    def scratch_delete(self,path):
        p=self.owned(path);base=(self.root/'scratch').resolve()
        if not p.is_relative_to(base) or p==base:raise ValueError('Deletion requires an explicit scratch child')
        if p.is_dir():raise ValueError('Delete explicit scratch files, not directories')
        if p.exists():p.unlink()


def source_item(p,role):
    p=Path(p)
    return {'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p),'role':role}
